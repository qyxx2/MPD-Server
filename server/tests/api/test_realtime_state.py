from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.models.output import OutputMode
from server.app.services.state_service import StateService
from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_realtime_output import setup_output
from server.tests.support.playback import mutate, real_client, run, start

__all__ = ["real_client"]


@pytest.fixture
def state_client(real_client, monkeypatch):
    client = real_client[0]
    playback, player, library, coordinator, clock, output = setup_output(real_client)
    state = StateService(
        coordinator=coordinator,
        queue_manager=playback.queue_manager,
        history_service=playback.history_service,
        library_service=app.state.library_service,
        playback_service=playback,
        output_snapshot=output.get_cached_state,
        output_observation=output.get_observation,
    )
    monkeypatch.setattr(app.state, "state_service", state)
    monkeypatch.setattr(app.state, "playback_service", playback)
    monkeypatch.setattr(app.state, "output_manager", output)
    return client, state, playback, player, library, coordinator, clock, output


@pytest.mark.parametrize("sampled", [False, True])
def test_state_api_fails_whole_local_snapshot_but_keeps_external_degradation(
    state_client, monkeypatch, sampled,
):
    """RT-SNAPSHOT HTTP consumes real Services; local failure is never empty success."""
    client, _, playback, player, _, coordinator, _, output = state_client
    if sampled:
        run(playback.observe())
        run(output.get_state())
    before = server_snapshot(playback)

    async def failed_read():
        raise RuntimeError("local queue read failed")

    with monkeypatch.context() as patch:
        patch.setattr(playback.queue_manager, "get_snapshot", failed_read)
        failed = client.get("/api/state")
    assert failed.status_code == 503, failed.text
    assert failed.json()["error"]["code"] == "STATE_SNAPSHOT_UNAVAILABLE"
    assert set(failed.json()) == {"error"}
    assert server_snapshot(playback) == before

    player.disconnect()
    run(playback.observe())
    run(output.get_state())
    marker = coordinator.marker()
    degraded = client.get("/api/state")
    assert degraded.status_code == 200, degraded.text
    body = degraded.json()
    assert body["playback_observation"]["freshness"] == ("stale" if sampled else "unknown")
    assert body["playback_observation"]["error_code"] == "PLAYER_UNAVAILABLE"
    assert body["playback_observation"]["position_seconds"] == (0 if sampled else None)
    assert body["output_observation"]["freshness"] == ("stale" if sampled else "unknown")
    assert body["output_observation"]["error_code"] == "PLAYER_UNAVAILABLE"
    assert body["queue"] == before[0].model_dump(mode="json")
    assert body["playback"] == before[1].model_dump(mode="json")
    assert body["history"]["active_event"] == before[3].model_dump(mode="json")
    assert server_snapshot(playback) == before
    assert coordinator.marker() == marker


@pytest.mark.parametrize("domain", ["playback", "queue", "history", "song", "marker", "output"])
def test_each_required_local_read_fails_closed_and_retry_reads_again(
    state_client, monkeypatch, domain,
):
    client, state, playback, _, _, coordinator, _, output = state_client
    before = server_snapshot(playback)
    marker = coordinator.marker()

    async def failed(*args):
        raise RuntimeError("required local read failed")

    def failed_sync():
        raise RuntimeError("required local read failed")

    target, name, failure = {
        "playback": (playback.queue_manager, "get_playback_state", failed),
        "queue": (playback.queue_manager, "get_snapshot", failed),
        "history": (playback.history_service, "get_availability", failed),
        "song": (app.state.library_service, "get_song", failed),
        "marker": (coordinator, "marker", failed_sync),
        "output": (state, "_output_snapshot", failed_sync),
    }[domain]
    with monkeypatch.context() as patch:
        patch.setattr(target, name, failure)
        response = client.get("/api/state", headers={"Idempotency-Key": "read-failure"})
    assert response.status_code == 503, response.text
    assert response.json() == {"error": {
        "code": "STATE_SNAPSHOT_UNAVAILABLE",
        "message": "State snapshot is unavailable",
        "details": None,
    }}
    assert server_snapshot(playback) == before
    assert coordinator.marker() == marker
    assert output.get_cached_state() == run(state.get_full_snapshot()).output
    assert client.get("/api/state").status_code == 200
    assert run(app.state.idempotency_service._repository.get_by_key("read-failure")) is None


@pytest.mark.parametrize("availability", ["AVAILABLE", "MISSING", "UNREADABLE"])
def test_full_http_dto_preserves_all_occurrences_and_business_authorities(
    state_client, monkeypatch, availability,
):
    client, state, playback, player, library, coordinator, _, output = state_client
    # Advance into the second occurrence of the same URI: Played/current/pending
    # must all survive serialization with their own IDs and context.
    run(playback.next())
    song = run(library.get_song("a"))
    run(library.upsert_song(song.model_copy(update={"availability_status": availability})))
    playlist = run(app.state.playlist_service.create_playlist("preserved"))
    run(app.state.playlist_service.add_song(playlist.playlist_id, "a"))
    run(app.state.playlist_service.set_favorite("a", True))
    seek = mutate(client, "POST", "/api/playback/seek", {"seconds": 0}, key="retained-terminal")
    assert seek.status_code == 200, seek.text
    terminals = app.state.idempotency_service._repository
    terminal = run(terminals.get_by_key("retained-terminal"))
    assert terminal is not None
    run(output.set_enabled(OutputMode.NAS_DAC, False))
    player._elapsed = 12
    run(playback.observe())
    expected = run(state.get_full_snapshot()).model_dump(mode="json")
    # Current Song uses the established public Library representation, which
    # deliberately omits the repository's internal identity_key.
    expected["current_song"] = client.get("/api/library/songs/a").json()
    before = server_snapshot(playback)
    songs = run(library.list_songs())
    playlists = run(app.state.playlist_service.revision_content())
    entries, outputs = run(player.queue_entries()), run(player.outputs())
    history_rest = client.get("/api/history").json()
    played_rest = client.get("/api/history/played").json()
    playback_rest = client.get("/api/playback/state").json()
    marker = coordinator.marker()

    async def forbidden(*args, **kwargs):
        raise AssertionError("snapshot performed external I/O or business recovery/control")

    for name in ("status", "queue_entries", "outputs", "play", "pause", "stop", "next",
                 "previous", "seek", "queue_add", "queue_delete", "queue_move", "queue_clear",
                 "queue_play", "set_output_enabled", "set_volume", "set_repeat", "set_random",
                 "update_database"):
        monkeypatch.setattr(player, name, forbidden)
    monkeypatch.setattr(playback, "reconcile_external_status", forbidden)
    response = client.get("/api/state", headers={"Idempotency-Key": "read-only"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.pop("captured_at")
    expected.pop("captured_at")
    assert body == expected
    items = body["queue"]["items"]
    manual = [i for i in items if i["source"] == "MANUAL"]
    assert [i["position"] for i in manual] == [-1, 0, 1]
    assert [i["song_id"] for i in manual] == ["a", "a", "b"]
    assert len({i["queue_item_id"] for i in items}) == len(before[0].items)
    assert {i["playback_context_id"] for i in manual} == {"repeated"}
    assert any(i["source"] == "AUTOPLAY" and i["position"] > 0 for i in items)
    assert body["playback"]["playback_context_id"] == "repeated"
    assert body["current_song"]["availability_status"] == availability
    assert body["history"]["has_entries"] is True
    assert body["history"]["active_event"]["song_id"] == "a"
    assert body["output"]["last_request"]["status"] == "SUCCEEDED"
    assert body["playback_observation"]["position_seconds"] == 12
    assert body["playback_observation"]["actual_state"] == "playing"
    assert body["playback"]["position_seconds"] == 0
    assert body["revisions"] == {"library": marker.library_revision, "playlist": marker.playlist_revision}
    assert body["epoch"] == marker.epoch and body["sequence"] == marker.sequence
    assert server_snapshot(playback) == before
    assert run(library.list_songs()) == songs
    assert run(app.state.playlist_service.revision_content()) == playlists
    assert client.get("/api/history").json() == history_rest
    assert client.get("/api/history/played").json() == played_rest
    assert client.get("/api/playback/state").json() == playback_rest
    assert run(app.state.idempotency_service._repository.get_by_key("read-only")) is None
    assert run(terminals.get_by_key("retained-terminal")) == terminal
    assert coordinator.marker() == marker
    # Port reads above are now forbidden; its queue/output facts remain intact.
    assert player._queue == [(entry.song_uri, entry.mpd_song_id) for entry in entries]
    assert player._outputs == outputs


def test_http_cache_expiry_registers_waterline_once_and_keeps_control_receipt(state_client):
    client, _, playback, player, _, coordinator, clock, output = state_client
    run(output.set_enabled(OutputMode.NAS_DAC, False))
    player._elapsed = 18
    run(playback.observe())
    first = client.get("/api/state").json()
    before = server_snapshot(playback)
    clock.advance(6)
    at_limit = client.get("/api/state").json()
    assert at_limit["sequence"] == first["sequence"]
    assert at_limit["playback_observation"]["freshness"] == "fresh"
    assert at_limit["output_observation"]["freshness"] == "fresh"
    clock.advance(.01)
    expired = client.get("/api/state").json()
    assert expired["playback_observation"]["freshness"] == "stale"
    assert expired["output_observation"]["freshness"] == "stale"
    assert expired["playback_observation"]["position_seconds"] == 18
    assert expired["output"]["last_request"] == first["output"]["last_request"]
    assert expired["sequence"] > first["sequence"]
    assert expired["sequence"] == coordinator.marker().sequence
    assert expired["revisions"] == first["revisions"]
    assert client.get("/api/state").json()["sequence"] == expired["sequence"]
    assert server_snapshot(playback) == before


def test_root_wires_empty_snapshot_and_keeps_rest_schema_and_ws_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "empty-state.db"))
    with TestClient(app) as client:
        response = client.get("/api/state")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["playback"] is None and body["current_song"] is None
        assert body["queue"] == {"revision": 0, "items": []}
        assert body["history"] == {"has_entries": False, "active_event": None, "session_id": None}
        assert body["revisions"] == {"library": 0, "playlist": 0}
        assert body["playback_observation"]["observed_at"] is None
        assert body["playback_observation"]["matches_current"] is None
        assert body["playback_observation"]["duration_seconds"] is None
        assert body["playback_observation"]["freshness"] == "unknown"
        assert body["output_observation"]["freshness"] == "unknown"
        assert body["output"]["last_request"] is None
        assert all(s["sample_rate"] is None for s in body["output"]["states"])
        assert client.get("/api/history").json() == {"items": [], "count": 0}
    schema = app.openapi()
    assert "/api/realtime" not in schema["paths"]
    assert not any(getattr(route, "path", "") == "/api/realtime" for route in app.routes)
    output_properties = schema["components"]["schemas"]["OutputStateResponse"]["properties"]
    assert "sampleRate" in output_properties and "sample_rate" not in output_properties
    assert schema["paths"]["/api/state"]["get"]["responses"]["503"]["content"]["application/json"]


def test_snapshot_openapi_describes_its_actual_output_field_names(state_client):
    client = state_client[0]
    body = client.get("/api/state").json()
    components = app.openapi()["components"]["schemas"]

    def referenced(schema):
        return components[schema["$ref"].rsplit("/", 1)[1]]

    snapshot = components["FullStateSnapshotResponse"]
    output = referenced(snapshot["properties"]["output"])
    output_state = referenced(output["properties"]["states"]["items"])
    assert set(output_state["properties"]) == set(body["output"]["states"][0])


def test_root_snapshot_reports_real_producer_versions(real_client, media_fixture_dir):
    client, _, _, playback = real_client
    start(client)
    # Use the composition root's real Services/coordinator/StateService without
    # replacing the aggregator, and observe actual committed producer versions.
    run(app.state.library_scanner.scan_paths([media_fixture_dir / "metadata.flac"]))
    playlist = mutate(client, "POST", "/api/playlists", {"name": "versioned"})
    assert playlist.status_code == 201, playlist.text
    marker = app.state.realtime_coordinator.marker()
    assert marker.library_revision == marker.playlist_revision == 1
    before = server_snapshot(playback)
    response = client.get("/api/state")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revisions"] == {"library": 1, "playlist": 1}
    assert body["epoch"] == marker.epoch and body["sequence"] == marker.sequence
    assert body["queue"] == before[0].model_dump(mode="json")
    assert body["playback"] == before[1].model_dump(mode="json")
    assert server_snapshot(playback) == before
    assert app.state.realtime_coordinator.marker() == marker
