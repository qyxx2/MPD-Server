import asyncio
from dataclasses import replace

import pytest

from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.mock_mpd import MockMPD
from server.app.player.models import MPDStats, OutputInfo
from server.app.services.mpd_info_service import MPDInfoService


class ObservedInfoMPD(MockMPD):
    def __init__(self):
        super().__init__(
            songs=["a.flac"],
            stats=MPDStats(songs=0, albums=2, artists=None, db_playtime=123,
                           db_update=1700000000, playtime=7, uptime=45),
            outputs=[OutputInfo(id=17, name="DAC", plugin="alsa", enabled=True)],
        )
        self.calls = []

    def _check(self, command):
        self.calls.append(command)
        super()._check(command)


async def player_facts(player):
    return (
        await player.status(), await player.queue_entries(),
        await player.outputs(), await player.database_update_status(),
    )


@pytest.mark.parametrize("failure", [
    None, "stats", "database_update_status", "status", "disconnected", "unverified",
])
def test_info_preserves_runtime_sources_nulls_and_real_zero(failure):
    async def run():
        player = ObservedInfoMPD()
        first = await player.queue_add("a.flac")
        await player.queue_add("a.flac")
        await player.queue_play(first)
        await player.seek(19)
        await player.pause()
        await player.set_repeat(True)
        await player.set_random(True)
        await player.set_volume(23)
        before = await player_facts(player)
        cap = replace(
            MPDCapabilities.from_commands({"stats", "status", "currentsong", "update"}),
            version="0.23.5", stats={"songs": "999", "playtime": "999"},
            verified_operations=frozenset({"stats", "database_update_status"}),
        )
        if failure == "unverified":
            cap = MPDCapabilities.from_commands(set())
        elif failure == "disconnected":
            player.disconnect()
        elif failure:
            player.fail_next(failure, "read rejected")
        service = MPDInfoService(player=VerifiedPlayerPort(player, cap), capabilities=cap)
        player.calls.clear()
        info = await service.get_info()
        assert player.calls == ([] if failure == "unverified" else [
            "stats", "database_update_status", "status",
        ])
        expected_stats = {
            "songs": 0, "albums": 2, "artists": None, "db_playtime": 123,
            "db_update": 1700000000, "playtime": 7, "uptime": 45,
        }
        if failure in {"stats", "disconnected", "unverified"}:
            assert info.stats.model_dump() == dict.fromkeys(expected_stats)
        else:
            assert info.stats.model_dump() == expected_stats
        assert info.database_update_status.model_dump() == (
            {"updating": None, "job_id": None}
            if failure in {"database_update_status", "disconnected", "unverified"}
            else {"updating": False, "job_id": None}
        )
        assert info.connected is (
            False if failure == "disconnected"
            else None if failure in {"status", "unverified"} else True
        )
        assert info.version == (None if failure == "unverified" else "0.23.5")
        assert info.version_source == (None if failure == "unverified" else "verified_capability")
        expected_errors = (
            {source: "PLAYER_UNAVAILABLE" if failure == "disconnected" else "CAPABILITY_UNVERIFIED"
             for source in ["stats", "database_update_status", "status"]}
            if failure in {"disconnected", "unverified"}
            else {failure: "PLAYER_COMMAND_ERROR"} if failure else {}
        )
        assert {source: error.code for source, error in info.errors.items()} == expected_errors
        assert all(error.message for error in info.errors.values())
        player.reconnect()
        assert await player_facts(player) == before
        # Failed reads are retried; neither probe samples nor a cached failure is replayed.
        service.capabilities = replace(cap, commands=frozenset({"stats", "status", "currentsong", "update"}),
                                       verified_operations=frozenset({"stats", "database_update_status"}))
        service.player = VerifiedPlayerPort(player, service.capabilities)
        player.calls.clear()
        fresh = await service.get_info()
        assert fresh.stats.model_dump() == expected_stats
        assert fresh.connected is True
        assert fresh.errors == {}
        assert fresh.observed_at >= info.observed_at
        assert player.calls == ["stats", "database_update_status", "status"]
        assert await player_facts(player) == before
        assert info.errors.keys() == expected_errors.keys()

    asyncio.run(run())
