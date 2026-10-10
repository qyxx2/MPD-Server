"""Regenerate with .venv/bin/python -m server.tests.api.test_web_wire_fixture.

Golden data comes from real domain/public Pydantic serializers, not handwritten
Web DTOs. Control-target DTO exists at this checkout; W4 must rerun P3 Gate.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from server.app.api.realtime_schemas import FullStateSnapshotResponse
from server.app.api.schemas import ErrorBody, ErrorResponse, PlaybackStateResponse
from server.app.api.system_schemas import OutputSnapshotResponse
from server.app.models.history import HistoryEvent
from server.app.models.library import Song
from server.app.models.output import (
    OutputMode,
    OutputRequestState,
    OutputSnapshot,
    OutputState,
)
from server.app.models.playback_control import PlaybackControlTarget
from server.app.models.queue import PlaybackState, QueueItem, QueueSnapshot
from server.app.models.realtime import (
    ActualCurrent,
    FullStateSnapshot,
    HistoryAvailability,
    Invalidation,
    OutputObservation,
    PlaybackObservation,
)

FIXTURE = Path(__file__).resolve().parents[3] / "web/tests/fixtures/wire.json"
NOW = datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc)


def build_fixture():
    output = OutputSnapshot(states=(
        OutputState(mode=OutputMode.NAS_DAC, status="ACTIVE", updated_at=NOW,
                    sample_rate=96000, bit_depth=24, channels=2, format="pcm"),
        OutputState(mode=OutputMode.CLIENT_STREAM, status="UNAVAILABLE", updated_at=NOW),
    ), last_request=OutputRequestState(mode=OutputMode.NAS_DAC, enabled=False,
                                    status="SWITCH_FAILED", error_code="OUTPUT_FAILED",
                                    error_message="fixture failure", updated_at=NOW))
    playback = PlaybackState(song_id="song-a", state="PAUSED", playback_context_id="context-a",
                             position_seconds=37, autoplay_enabled=True, updated_at=NOW)
    state = FullStateSnapshot(
        epoch="fixture-epoch", sequence=12, captured_at=NOW,
        revisions={"library": 3, "playlist": 5}, playback=playback,
        current_song=Song(song_id="song-a", title="长标题 / Song A", file_uri="fixture/a.flac",
                          artists=("Artist",), duration=None, lyrics="[00:01]fixture", lyrics_format="lrc"),
        queue=QueueSnapshot(revision=7, items=(
            QueueItem(queue_item_id="item-a", song_id="song-a", position=0, source="MANUAL", playback_context_id="context-a"),
            QueueItem(queue_item_id="item-b", song_id="song-a", position=1, source="AUTOPLAY"),
        )),
        history=HistoryAvailability(has_entries=True, session_id="session-a", active_event=HistoryEvent(
            song_id="song-a", started_at=NOW, session_id="session-a")),
        output=output,
        playback_observation=PlaybackObservation(
            actual_state="paused", actual_current=ActualCurrent(entry_id=8, uri="fixture/a.flac", position=0),
            actual_freshness="fresh", bound_queue_item_id="item-a",
            control_target=PlaybackControlTarget(queue_item_id="item-a", token="fixture-opaque-token"),
            sync_status="CONFIRMED", matches_current=True, position_seconds=37, duration_seconds=None,
            observed_at=NOW, freshness="fresh"),
        output_observation=OutputObservation(observed_at=NOW, freshness="fresh"),
    )
    snapshot = FullStateSnapshotResponse.model_validate(state.model_dump()).model_dump(mode="json", by_alias=True)
    empty = state.model_copy(update={"playback": None, "current_song": None,
                                    "queue": QueueSnapshot(revision=0, items=()),
                                    "history": HistoryAvailability(has_entries=False),
                                    "playback_observation": PlaybackObservation(),
                                    "output_observation": OutputObservation()})
    return {
        "provenance": {"source": "Pydantic domain/public model_dump(mode=json, by_alias=True)",
                       "control_target": "actual DTO present; P3 full Gate must be freshly verified in W4"},
        "snapshot": snapshot,
        "empty_snapshot": FullStateSnapshotResponse.model_validate(empty.model_dump()).model_dump(mode="json", by_alias=True),
        "snapshot_frame": {"type": "snapshot", "protocol_version": 1,
                           "epoch": state.epoch, "sequence": state.sequence, "state": snapshot},
        "invalidate_frame": Invalidation(epoch=state.epoch, sequence=13, domains=frozenset({"playback"}),
                                         revisions=state.revisions).model_dump(mode="json", by_alias=True),
        "rest_output": OutputSnapshotResponse.model_validate(output.model_dump()).model_dump(mode="json", by_alias=True),
        "playback_receipt": PlaybackStateResponse.model_validate(playback.model_dump()).model_dump(mode="json", by_alias=True),
        "error": ErrorResponse(error=ErrorBody(code="PLAYBACK_TARGET_CONFLICT", message="Changed", details={"target": "old"})).model_dump(mode="json", by_alias=True),
    }


def test_web_fixture_matches_actual_public_dto_serialization():
    assert FIXTURE.exists(), "W1 generated wire fixture is missing"
    actual = json.loads(FIXTURE.read_text())
    assert actual == build_fixture(), "Regenerate fixture after reviewing the DTO contract change"
    # Independent checks guard alias/nullability assumptions, including the
    # deliberately mixed outer snake_case / inner camelCase REST Output DTO.
    assert "last_request" in actual["rest_output"]
    assert "lastRequest" not in actual["rest_output"]
    assert actual["rest_output"]["states"][0]["sampleRate"] == 96000
    assert actual["snapshot"]["output"]["states"][0]["sample_rate"] == 96000
    assert actual["snapshot"]["playback_observation"]["duration_seconds"] is None
    assert actual["empty_snapshot"]["playback_observation"]["control_target"] is None
    assert actual["snapshot_frame"]["state"] == actual["snapshot"]


def test_real_native_lifespan_injected_mock_get_ws_and_rest_aliases(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from server.app.main import app
    from server.app.player.mock_mpd import MockMPD

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "w1-isolated.db"))
    monkeypatch.setattr(app.state, "player", MockMPD([]), raising=False)
    with TestClient(app) as client:
        get = client.get("/api/state")
        assert get.status_code == 200
        FullStateSnapshotResponse.model_validate(get.json())
        with client.websocket_connect("/api/realtime") as socket:
            frame = socket.receive_json()
            assert frame["type"] == "snapshot" and frame["protocol_version"] == 1
            assert frame["epoch"] == frame["state"]["epoch"]
            assert frame["sequence"] == frame["state"]["sequence"]
            assert frame["state"]["queue"] == get.json()["queue"]
            assert frame["state"]["playback_observation"]["control_target"] is None
        rest = client.get("/api/system/output").json()
        assert "last_request" in rest
        assert "updatedAt" in rest["states"][0]
        assert "updated_at" not in rest["states"][0]
    assert (tmp_path / "w1-isolated.db").exists()


if __name__ == "__main__":
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(build_fixture(), ensure_ascii=False, indent=2) + "\n")


def test_existing_container_entry_point_supplies_backend_proxy_target():
    # Parse the actual Compose environment; do not start containers. PyYAML is
    # already supplied by the declared uvicorn[standard] runtime dependency.
    from urllib.parse import urlparse

    import yaml

    compose = yaml.safe_load((FIXTURE.parents[3] / "deploy/docker-compose.dev.yml").read_text())
    web = compose["services"]["web"]
    target = web.get("environment", {}).get("API_PROXY_TARGET")
    assert target, "Native loopback default requires an explicit container backend target"
    url = urlparse(target)
    assert url.scheme == "http" and url.hostname == "server" and url.port == 8000
    assert url.hostname in compose["services"]
    assert "8000:8000" in compose["services"][url.hostname]["ports"]
