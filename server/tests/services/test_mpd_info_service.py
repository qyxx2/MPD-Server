import asyncio
from dataclasses import replace

import pytest

from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.mock_mpd import MockMPD
from server.app.player.models import DatabaseUpdateStatus, MPDStats
from server.app.services.mpd_info_service import MPDInfoService


def capabilities():
    return replace(
        MPDCapabilities.from_commands({"stats", "status", "currentsong", "update"}),
        version="0.23.5",
        stats={"songs": "999", "playtime": "999", "db_playtime": "999"},
        verified_operations=frozenset({"stats", "database_update_status"}),
    )


def info_service(player, cap):
    return MPDInfoService(player=VerifiedPlayerPort(player, cap), capabilities=cap)


def test_info_reads_all_runtime_stats_preserving_zero_and_unknown():
    async def run():
        player = MockMPD(stats=MPDStats(
            songs=0, albums=2, artists=None, db_playtime=120,
            db_update=1700000000, playtime=7, uptime=45,
        ))
        info = await info_service(player, capabilities()).get_info()
        assert info.stats.model_dump() == {
            "songs": 0, "albums": 2, "artists": None, "db_playtime": 120,
            "db_update": 1700000000, "playtime": 7, "uptime": 45,
        }
        assert info.version == "0.23.5"
        assert info.version_source == "verified_capability"
        assert info.observed_at.tzinfo is not None

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["command", "disconnected", "unverified"])
def test_stats_failure_is_classified_without_fabricated_values(failure):
    async def run():
        player = MockMPD(stats=MPDStats(songs=12))
        cap = capabilities()
        if failure == "command":
            player.fail_next("stats", "stats rejected")
        elif failure == "disconnected":
            player.disconnect()
        else:
            cap = replace(cap, verified_operations=frozenset({"database_update_status"}))
        info = await info_service(player, cap).get_info()
        assert info.stats.model_dump() == dict.fromkeys([
            "songs", "albums", "artists", "db_playtime", "db_update", "playtime", "uptime",
        ])
        assert info.errors["stats"].code == {
            "command": "PLAYER_COMMAND_ERROR", "disconnected": "PLAYER_UNAVAILABLE",
            "unverified": "CAPABILITY_UNVERIFIED",
        }[failure]
        assert info.errors["stats"].message
        assert info.version_source == "verified_capability"

    asyncio.run(run())


@pytest.mark.parametrize("updating,job_id", [(True, 8), (False, 0), (None, None)])
def test_info_reads_update_status_without_starting_update(updating, job_id):
    class UpdatePlayer(MockMPD):
        async def database_update_status(self):
            return DatabaseUpdateStatus(updating=updating, job_id=job_id)

        async def update_database(self):
            pytest.fail("About must not start a database update")

    async def run():
        info = await info_service(UpdatePlayer(), capabilities()).get_info()
        assert info.database_update_status.model_dump() == {
            "updating": updating, "job_id": job_id,
        }

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["command", "unverified"])
def test_update_failure_preserves_successful_stats(failure):
    async def run():
        player = MockMPD(stats=MPDStats(songs=12))
        cap = capabilities()
        if failure == "command":
            player.fail_next("database_update_status", "update status rejected")
        else:
            cap = replace(cap, verified_operations=frozenset({"stats"}))
        info = await info_service(player, cap).get_info()
        assert info.stats.songs == 12
        assert info.database_update_status.model_dump() == {"updating": None, "job_id": None}
        assert info.errors["database_update_status"].code == (
            "PLAYER_COMMAND_ERROR" if failure == "command" else "CAPABILITY_UNVERIFIED"
        )

    asyncio.run(run())


@pytest.mark.parametrize("failure,connected,code", [
    (None, True, None),
    ("command", None, "PLAYER_COMMAND_ERROR"),
    ("disconnected", False, "PLAYER_UNAVAILABLE"),
    ("unverified", None, "CAPABILITY_UNVERIFIED"),
])
def test_connection_uses_final_status_independently_of_stats(failure, connected, code):
    class StatusPlayer(MockMPD):
        async def database_update_status(self):
            result = await super().database_update_status()
            if failure == "disconnected":
                self.disconnect()
            return result

    async def run():
        player = StatusPlayer(stats=MPDStats(songs=12))
        cap = capabilities()
        if failure == "command":
            player.fail_next("status", "status rejected")
        elif failure == "unverified":
            cap = replace(cap, commands=cap.commands - {"currentsong"})
        info = await info_service(player, cap).get_info()
        assert info.connected is connected
        assert info.stats.songs == 12
        assert info.database_update_status.updating is False
        assert info.version == "0.23.5"
        if code:
            assert info.errors["status"].code == code
        else:
            assert info.errors == {}

    asyncio.run(run())


def test_each_read_uses_new_runtime_data_without_modifying_previous_result():
    class ChangingPlayer(MockMPD):
        runtime_stats = MPDStats(songs=1, playtime=3, db_playtime=100)
        runtime_update = DatabaseUpdateStatus(updating=True, job_id=8)

        async def stats(self):
            await super().stats()
            return self.runtime_stats.model_copy(deep=True)

        async def database_update_status(self):
            await super().database_update_status()
            return self.runtime_update.model_copy(deep=True)

    async def run():
        player = ChangingPlayer()
        service = info_service(player, capabilities())
        first = await service.get_info()
        player.runtime_stats = MPDStats(songs=0, playtime=9, db_playtime=None)
        player.runtime_update = DatabaseUpdateStatus(updating=False, job_id=None)
        second = await service.get_info()
        assert (second.stats.songs, second.stats.playtime, second.stats.db_playtime) == (0, 9, None)
        assert second.database_update_status.model_dump() == {"updating": False, "job_id": None}
        assert (first.stats.songs, first.stats.playtime, first.stats.db_playtime) == (1, 3, 100)
        assert first.database_update_status.model_dump() == {"updating": True, "job_id": 8}

    asyncio.run(run())
