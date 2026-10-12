from fastapi.testclient import TestClient

from server.app.main import app
from server.app.player.mock_mpd import MockMPD


def test_health(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "health.db"))
    monkeypatch.setattr(app.state, "player", MockMPD(), raising=False)
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == body["ms"]["status"] == "ok"
        assert body["mpd"]["status"] == "connected"
        assert body["mpd"]["observed_at"]
        assert body["library_sync"]["status"] == "IDLE"
