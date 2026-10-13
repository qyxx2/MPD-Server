"""SYS-MPD-CONNECTION-001: persist only, activate at next startup."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.player.mock_mpd import MockMPD


def test_save_is_atomic_and_does_not_change_active_player_or_business(
    tmp_path, monkeypatch
):
    path = tmp_path / "connection.json"
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "music.db"))
    monkeypatch.setenv("MPD_CONNECTION_PATH", str(path))
    monkeypatch.setenv("MPD_HOST", "old.example")
    monkeypatch.setenv("MPD_PORT", "6600")
    monkeypatch.setattr(app.state, "player", MockMPD(), raising=False)
    with TestClient(app) as client:
        before = client.get("/api/state").json()
        player = app.state.playback_service.player
        response = client.put(
            "/api/system/mpd/connection",
            json={"host": "new.example", "port": 6601},
            headers={"Idempotency-Key": "save-address"},
        )
        assert response.status_code == 200
        assert response.json() == {
            "active": {"host": "old.example", "port": 6600},
            "saved": {"host": "new.example", "port": 6601},
            "restart_required": True,
        }
        assert json.loads(path.read_text()) == {"host": "new.example", "port": 6601}
        after = client.get("/api/state").json()
        for field in ("queue", "playback", "history", "revisions", "epoch"):
            assert after[field] == before[field]
        # Fail-closed Output reads assign a new observation timestamp on each GET.
        for snapshot in (before, after):
            for state in snapshot["output"]["states"]:
                state.pop("updated_at")
        assert after["output"] == before["output"]
        assert app.state.playback_service.player is player
        assert (
            client.put(
                "/api/system/mpd/connection",
                json={"host": "new.example", "port": 6601},
                headers={"Idempotency-Key": "save-address"},
            ).json()
            == response.json()
        )
        assert (
            client.put(
                "/api/system/mpd/connection",
                json={"host": "other", "port": 6601},
                headers={"Idempotency-Key": "save-address"},
            ).status_code
            == 409
        )
        assert client.get("/api/system/mpd/connection").json() == response.json()
    with TestClient(app) as client:
        assert client.get("/api/system/mpd/connection").json() == {
            "active": {"host": "new.example", "port": 6601},
            "saved": {"host": "new.example", "port": 6601},
            "restart_required": False,
        }


@pytest.mark.parametrize(
    "payload",
    [
        {"host": "http://mpd", "port": 6600},
        {"host": "", "port": 6600},
        {"host": "a b", "port": 6600},
        {"host": "mpd", "port": True},
        {"host": "mpd", "port": 0},
        {"host": "mpd", "port": 65536},
        {"host": "mpd", "port": "6600"},
    ],
)
def test_invalid_connection_does_not_write(tmp_path, monkeypatch, payload):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "music.db"))
    path = tmp_path / "connection.json"
    monkeypatch.setenv("MPD_CONNECTION_PATH", str(path))
    monkeypatch.setattr(app.state, "player", MockMPD(), raising=False)
    with TestClient(app) as client:
        assert (
            client.put(
                "/api/system/mpd/connection",
                json=payload,
                headers={"Idempotency-Key": "invalid"},
            ).status_code
            == 422
        )
        assert not path.exists()


def test_replace_failure_preserves_saved_file_and_cleans_own_temp(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "music.db"))
    path = tmp_path / "connection.json"
    path.write_text('{"host":"old","port":6600}')
    monkeypatch.setenv("MPD_CONNECTION_PATH", str(path))
    monkeypatch.setattr(app.state, "player", MockMPD(), raising=False)
    with (
        TestClient(app) as client,
        patch("os.replace", side_effect=OSError("disk failed")),
    ):
        response = client.put(
            "/api/system/mpd/connection",
            json={"host": "new", "port": 6601},
            headers={"Idempotency-Key": "failure"},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "MPD_CONNECTION_SAVE_FAILED"
        assert json.loads(path.read_text()) == {"host": "old", "port": 6600}
        assert not list(tmp_path.glob(".mpd-connection-*"))


def test_corrupt_saved_connection_fails_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "music.db"))
    path = tmp_path / "connection.json"
    path.write_text("broken")
    monkeypatch.setenv("MPD_CONNECTION_PATH", str(path))
    with pytest.raises(ValueError, match="MPD connection"), TestClient(app):
        pass


def test_real_mpd_info_serialization_matches_web_fixture(monkeypatch):
    from datetime import datetime, timezone

    from server.app.models.mpd_info import MPDInfo, MPDInfoError
    from server.app.player.models import DatabaseUpdateStatus, MPDStats

    class Reader:
        async def get_info(self):
            return MPDInfo(
                version="0.23.5",
                version_source="verified_capability",
                stats=MPDStats(songs=0, uptime=0, db_playtime=123, playtime=7),
                database_update_status=DatabaseUpdateStatus(updating=True, job_id=0),
                connected=None,
                errors={
                    "status": MPDInfoError(
                        code="PLAYER_COMMAND_ERROR", message="rejected"
                    )
                },
                observed_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
            )

    monkeypatch.setattr(app.state, "mpd_info_service", Reader(), raising=False)
    response = TestClient(app).get("/api/system/mpd")
    assert response.status_code == 200
    assert response.json() == json.loads(
        Path("web/tests/fixtures/settings.json").read_text()
    )


def test_saved_endpoint_overrides_invalid_old_environment_and_adapter_uses_it(
    tmp_path, monkeypatch
):
    from server.app import main

    # Exercise adapter composition even when the suite defaults to mock mode;
    # the adapter below still returns a deterministic MockMPD.
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("MPD_MODE", "real")
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("MUSIC_ROOT", str(tmp_path))
    path = tmp_path / "connection.json"
    path.write_text('{"host":"new.example","port":6601}')
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "music.db"))
    monkeypatch.setenv("MPD_CONNECTION_PATH", str(path))
    monkeypatch.setenv("MPD_HOST", "http://invalid")
    monkeypatch.setenv("MPD_PORT", "invalid")
    monkeypatch.setenv("MPD_PASSWORD", "private-deployment-password")
    monkeypatch.delattr(app.state, "player", raising=False)
    created = []

    def adapter(host, *, port, password, uri_mapper):
        created.append((host, port, password))
        return MockMPD()

    monkeypatch.setattr(main, "MPDAdapter", adapter)
    with TestClient(app) as client:
        assert client.get("/api/system/mpd/connection").json()["active"] == {
            "host": "new.example",
            "port": 6601,
        }
    assert created == [("new.example", 6601, "private-deployment-password")]
    assert "password" not in path.read_text()


def test_saved_file_survives_terminal_failure_and_same_key_retry_is_safe(
    tmp_path, monkeypatch
):
    from server.app.repositories.idempotency_repository import IdempotencyRepository

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "music.db"))
    path = tmp_path / "connection.json"
    monkeypatch.setenv("MPD_CONNECTION_PATH", str(path))
    monkeypatch.setattr(app.state, "player", MockMPD(), raising=False)
    original = IdempotencyRepository.create

    async def fail(*args, **kwargs):
        raise RuntimeError("terminal failed")

    with TestClient(app, raise_server_exceptions=False) as client:
        monkeypatch.setattr(IdempotencyRepository, "create", fail)
        body = {"host": "new.example", "port": 6601}
        headers = {"Idempotency-Key": "terminal"}
        assert (
            client.put(
                "/api/system/mpd/connection", json=body, headers=headers
            ).status_code
            == 500
        )
        assert json.loads(path.read_text()) == body
        monkeypatch.setattr(IdempotencyRepository, "create", original)
        response = client.put("/api/system/mpd/connection", json=body, headers=headers)
        assert response.status_code == 200
        assert response.json()["saved"] == body
        assert response.json()["active"] != body


def test_ipv6_address_and_five_digit_port_persist_without_http_or_brackets(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "music.db"))
    path = tmp_path / "connection.json"
    monkeypatch.setenv("MPD_CONNECTION_PATH", str(path))
    monkeypatch.setattr(app.state, "player", MockMPD(), raising=False)
    body = {"host": "2001:db8:1234:5678:90ab:cdef:1234:5678", "port": 16600}
    with TestClient(app) as client:
        response = client.put(
            "/api/system/mpd/connection", json=body, headers={"Idempotency-Key": "ipv6"}
        )
        assert response.status_code == 200
        assert response.json()["saved"] == body
        assert client.get("/api/system/mpd/connection").json()["saved"] == body
        assert json.loads(path.read_text()) == body
    with TestClient(app) as client:
        assert client.get("/api/system/mpd/connection").json()["active"] == body
