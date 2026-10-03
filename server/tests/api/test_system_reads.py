"""SYS-READ-001: GET resources preserve complete facts without mutation keys."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from server.app.main import app
from server.app.models.output import OutputSnapshot, OutputState


def test_output_get_preserves_full_nullable_schema(monkeypatch):
    now = datetime(2026, 10, 2, tzinfo=timezone.utc)

    class OutputReader:
        async def get_state(self):
            return OutputSnapshot(states=(
                OutputState(mode="NAS_DAC", status="ACTIVE", updated_at=now),
                OutputState(mode="CLIENT_STREAM", status="UNAVAILABLE", updated_at=now),
            ))

    monkeypatch.setattr(app.state, "output_manager", OutputReader(), raising=False)
    response = TestClient(app).get("/api/system/output")
    assert response.status_code == 200
    assert response.json() == {
        "states": [{
            "mode": mode, "status": status, "targetClientId": None,
            "streamUrl": None, "format": None, "sampleRate": None,
            "bitDepth": None, "channels": None, "errorCode": None,
            "errorMessage": None, "updatedAt": "2026-10-02T00:00:00Z", "stale": False,
        } for mode, status in [("NAS_DAC", "ACTIVE"), ("CLIENT_STREAM", "UNAVAILABLE")]],
        "last_request": None,
    }


def test_mpd_get_preserves_null_zero_and_source_errors(monkeypatch):
    from server.app.models.mpd_info import MPDInfo, MPDInfoError
    from server.app.player.models import DatabaseUpdateStatus, MPDStats

    class InfoReader:
        async def get_info(self):
            return MPDInfo(
                version="0.23.5", version_source="verified_capability",
                stats=MPDStats(songs=0, db_playtime=123, playtime=7, uptime=0),
                database_update_status=DatabaseUpdateStatus(updating=True, job_id=0),
                connected=None,
                errors={"status": MPDInfoError(code="PLAYER_COMMAND_ERROR", message="rejected")},
                observed_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
            )

    monkeypatch.setattr(app.state, "mpd_info_service", InfoReader(), raising=False)
    response = TestClient(app).get("/api/system/mpd")
    assert response.status_code == 200
    assert response.json() == {
        "version": "0.23.5", "version_source": "verified_capability",
        "stats": {"songs": 0, "albums": None, "artists": None, "db_playtime": 123,
                  "db_update": None, "playtime": 7, "uptime": 0},
        "database_update_status": {"updating": True, "job_id": 0},
        "connected": None,
        "errors": {"status": {"code": "PLAYER_COMMAND_ERROR", "message": "rejected"}},
        "observed_at": "2026-10-02T00:00:00Z",
    }


def test_startup_wires_shared_system_services_fail_closed(tmp_path, monkeypatch):
    from server.app import main
    from server.app.player.mock_mpd import MockMPD

    player = MockMPD()
    calls = []
    original = player._check

    def check(command):
        calls.append(command)
        return original(command)

    monkeypatch.setattr(player, "_check", check)
    monkeypatch.setattr(main, "MPDAdapter", lambda *args, **kwargs: player)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "system.db"))
    monkeypatch.delattr(app.state, "mpd_capabilities", raising=False)
    player.disconnect()
    with TestClient(app) as client:
        assert app.state.output_manager.player is app.state.playback_service.player is player
        assert app.state.mpd_info_service.player is player
        assert app.state.output_manager.operation_runner == app.state.playback_service.run_output_operation
        output = client.get("/api/system/output")
        info = client.get("/api/system/mpd")
        assert output.status_code == info.status_code == 200
        assert output.json()["states"][0]["status"] == "UNAVAILABLE"
        assert output.json()["states"][0]["errorCode"] == "OUTPUT_CAPABILITY_UNVERIFIED"
        assert info.json()["connected"] is None
        assert info.json()["version"] is None
        assert {error["code"] for error in info.json()["errors"].values()} == {"CAPABILITY_UNVERIFIED"}
        assert client.get("/api/health").json() == {"status": "ok"}
    assert calls == []


def test_output_get_preserves_preparing_as_request_fact(monkeypatch):
    from server.app.models.output import OutputRequestState

    now = datetime(2026, 10, 2, tzinfo=timezone.utc)

    class PreparingReader:
        async def get_state(self):
            return OutputSnapshot(
                states=(OutputState(mode="NAS_DAC", status="INACTIVE", updated_at=now),),
                last_request=OutputRequestState(
                    mode="NAS_DAC", enabled=True, status="PREPARING", updated_at=now,
                ),
            )

    monkeypatch.setattr(app.state, "output_manager", PreparingReader(), raising=False)
    response = TestClient(app).get("/api/system/output")
    assert response.status_code == 200
    assert response.json()["states"][0]["status"] == "INACTIVE"
    assert response.json()["last_request"] == {
        "mode": "NAS_DAC", "enabled": True, "status": "PREPARING",
        "errorCode": None, "errorMessage": None, "updatedAt": "2026-10-02T00:00:00Z",
    }


def test_system_internal_failure_uses_existing_envelope(monkeypatch):
    class BrokenReader:
        async def get_state(self):
            raise RuntimeError("private service failure")

    monkeypatch.setattr(app.state, "output_manager", BrokenReader(), raising=False)
    response = TestClient(app, raise_server_exceptions=False).get("/api/system/output")
    assert response.status_code == 500
    assert response.json() == {"error": {
        "code": "INTERNAL_SERVER_ERROR", "message": "internal server error", "details": None,
    }}
