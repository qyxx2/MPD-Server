"""F7: REST preserves real Service/PlayerPort facts and authoritative state."""

import asyncio

import pytest

from server.app.main import app
from server.app.models.output import OutputMode
from server.app.player.models import OutputInfo
from server.tests.invariants.test_output_enable import enable_manager
from server.tests.invariants.test_output_serialization import authority_snapshot
from server.tests.support.playback import start


@pytest.mark.parametrize("request_status", [None, "SUCCEEDED", "SWITCH_FAILED"])
@pytest.mark.parametrize("offline", [False, True])
def test_system_rest_preserves_service_facts_and_sources(
    real_client, monkeypatch, request_status, offline,
):
    client, _, player, service = real_client
    start(client)
    player._outputs = [OutputInfo(id=37, name="DAC", plugin="alsa", enabled=True)]
    manager = enable_manager(service, player, monotonic_clock=lambda: 0.0)
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    manager.event_publisher = Publisher()
    monkeypatch.setattr(app.state, "output_manager", manager, raising=False)

    async def prepare():
        await service.pause()
        await service.seek(17)
        await manager.get_state()
        if request_status == "SUCCEEDED":
            await manager.set_enabled(OutputMode.NAS_DAC, True)
        elif request_status == "SWITCH_FAILED":
            player.fail_next("set_output_enabled", "rejected")
            with pytest.raises(Exception, match="rejected"):
                await manager.set_enabled(OutputMode.NAS_DAC, False)
        return await authority_snapshot(service)

    before = asyncio.run(prepare())
    calls = []
    original_check = player._check

    def check(command):
        calls.append(command)
        return original_check(command)

    monkeypatch.setattr(player, "_check", check)
    if offline:
        player.disconnect()
    response = client.get("/api/system/output")
    assert response.status_code == 200
    body = response.json()
    nas, stream = body["states"]
    assert nas["status"] == "ACTIVE"
    assert nas["stale"] is offline
    assert nas["errorCode"] == ("PLAYER_UNAVAILABLE" if offline else None)
    assert bool(nas["errorMessage"]) is offline
    assert stream["mode"] == "CLIENT_STREAM"
    assert stream["status"] == "UNAVAILABLE"
    for state in body["states"]:
        assert set(state) == {
            "mode", "status", "targetClientId", "streamUrl", "format", "sampleRate",
            "bitDepth", "channels", "errorCode", "errorMessage", "updatedAt", "stale",
        }
        assert all(state[field] is None for field in [
            "targetClientId", "streamUrl", "format", "sampleRate", "bitDepth", "channels",
        ])
    if request_status:
        request = body["last_request"]
        assert request["status"] == request_status
        assert request["enabled"] is (request_status != "SWITCH_FAILED")
        assert request["mode"] == "NAS_DAC"
        assert set(request) == {"mode", "enabled", "status", "errorCode", "errorMessage", "updatedAt"}
    else:
        assert body["last_request"] is None
    assert calls == ["outputs"]
    assert events == []
    player.reconnect()
    assert asyncio.run(authority_snapshot(service)) == before
    # GET retries current reads; neither an old ID nor a previous response is replayed.
    player._outputs = [OutputInfo(id=91, name="DAC", plugin="alsa", enabled=False)]
    calls.clear()
    fresh = client.get("/api/system/output").json()
    assert fresh["states"][0]["status"] == "INACTIVE"
    assert fresh["states"][0]["stale"] is False
    assert fresh["states"][0]["errorCode"] is None
    assert calls == ["outputs"]


@pytest.mark.parametrize("failure", [None, "stats", "database_update_status", "status", "offline", "unverified"])
def test_mpd_rest_keeps_independent_live_sources(real_client, monkeypatch, failure):
    from dataclasses import replace

    from server.app.player.capabilities import MPDCapabilities
    from server.app.player.models import MPDStats
    from server.app.services.mpd_info_service import MPDInfoService

    client, _, player, service = real_client
    start(client)
    before = asyncio.run(authority_snapshot(service))
    player._stats = MPDStats(songs=0, albums=2, db_playtime=123, playtime=7, uptime=0)
    caps = replace(
        MPDCapabilities.from_commands({"stats", "status", "currentsong", "update"}),
        version="0.23.5", stats={"songs": "999"},
        verified_operations=frozenset({"stats", "database_update_status"}),
    )
    if failure == "unverified":
        caps = MPDCapabilities.from_commands(set())
    elif failure == "offline":
        player.disconnect()
    elif failure:
        player.fail_next(failure, "read rejected")
    monkeypatch.setattr(app.state, "mpd_info_service", MPDInfoService(
        player=player, capabilities=caps,
    ), raising=False)
    calls = []
    original = player._check

    def check(command):
        calls.append(command)
        return original(command)

    monkeypatch.setattr(player, "_check", check)
    response = client.get("/api/system/mpd")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"version", "version_source", "stats", "database_update_status",
                         "connected", "errors", "observed_at"}
    stats = {"songs": 0, "albums": 2, "artists": None, "db_playtime": 123,
             "db_update": None, "playtime": 7, "uptime": 0}
    assert body["stats"] == (dict.fromkeys(stats) if failure in {"stats", "offline", "unverified"} else stats)
    assert body["database_update_status"] == (
        {"updating": None, "job_id": None}
        if failure in {"database_update_status", "offline", "unverified"}
        else {"updating": False, "job_id": None}
    )
    assert body["connected"] is (False if failure == "offline" else None if failure in {"status", "unverified"} else True)
    assert body["version"] == (None if failure == "unverified" else "0.23.5")
    assert body["version_source"] == (None if failure == "unverified" else "verified_capability")
    expected_errors = (
        {source: "PLAYER_UNAVAILABLE" if failure == "offline" else "CAPABILITY_UNVERIFIED"
         for source in ["stats", "database_update_status", "status"]}
        if failure in {"offline", "unverified"}
        else {failure: "PLAYER_COMMAND_ERROR"} if failure else {}
    )
    assert {source: error["code"] for source, error in body["errors"].items()} == expected_errors
    assert all(error["message"] for error in body["errors"].values())
    assert calls == ([] if failure == "unverified" else ["stats", "database_update_status", "status"])
    player.reconnect()
    assert asyncio.run(authority_snapshot(service)) == before


@pytest.mark.parametrize("offline", [False, True])
def test_system_composition_uses_injected_capabilities_without_probe(tmp_path, monkeypatch, offline):
    import sqlite3
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from server.app import main
    from server.app.player.capabilities import MPDCapabilities
    from server.app.player.mock_mpd import MockMPD
    from server.app.player.models import MPDStats

    path = str(tmp_path / "system.db")
    player = MockMPD(
        outputs=[OutputInfo(id=37, name="first", plugin="alsa", enabled=True),
                 OutputInfo(id=72, name="second", plugin="alsa", enabled=False)],
        stats=MPDStats(songs=0),
    )
    caps = replace(
        MPDCapabilities.from_commands({"outputs", "stats", "status", "currentsong", "update"}),
        version="0.23.5", stats={"songs": "999"},
        verified_operations=frozenset({"stats", "database_update_status"}),
    )
    def selector(candidates):
        return candidates[1]
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    publisher = Publisher()
    monkeypatch.setattr(app.state, "mpd_capabilities", caps, raising=False)
    monkeypatch.setattr(app.state, "output_selector", selector, raising=False)
    monkeypatch.setattr(app.state, "event_publisher", publisher, raising=False)
    monkeypatch.setattr(main, "MPDAdapter", lambda *args, **kwargs: player)
    monkeypatch.setenv("DATABASE_PATH", path)
    calls = []
    original = player._check

    def check(command):
        calls.append(command)
        return original(command)

    monkeypatch.setattr(player, "_check", check)
    if offline:
        player.disconnect()
    with TestClient(app) as client:
        manager = app.state.output_manager
        info_service = app.state.mpd_info_service
        assert manager.player is info_service.player is app.state.playback_service.player is player
        assert manager.capabilities is info_service.capabilities is caps
        assert manager.selector is selector
        assert manager.event_publisher is publisher
        assert manager.operation_runner == app.state.playback_service.run_output_operation
        assert calls == []  # Startup never queries or probes MPD.
        with sqlite3.connect(path) as connection:
            before = list(connection.iterdump())
        output = client.get("/api/system/output")
        info = client.get("/api/system/mpd")
        assert output.status_code == info.status_code == 200
        assert output.json()["states"][0]["status"] == ("UNAVAILABLE" if offline else "INACTIVE")
        assert info.json()["version"] == "0.23.5"
        assert info.json()["connected"] is (not offline)
        assert info.json()["stats"]["songs"] == (None if offline else 0)
        assert calls == ["outputs", "stats", "database_update_status", "status"]
        with sqlite3.connect(path) as connection:
            assert list(connection.iterdump()) == before
        assert events == []
        paths = client.get("/openapi.json").json()["paths"]
        assert {path: set(operations) for path, operations in paths.items()
                if path.startswith("/api/system/")} == {
            "/api/system/output": {"get", "put"}, "/api/system/mpd": {"get"},
        }
