from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.models.history import HistoryEvent
from server.app.models.queue import QueueItem


@contextmanager
def app_services(**services):
    previous = {}
    missing = object()
    for name, service in services.items():
        previous[name] = getattr(app.state, name, missing)
        setattr(app.state, name, service)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is missing:
                try:
                    delattr(app.state, name)
                except AttributeError:
                    pass
            else:
                setattr(app.state, name, value)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "history-api.db"))
    with TestClient(app) as client:
        yield client


class FakeHistoryService:
    def __init__(self, *, history=None, played=None) -> None:
        self.history = list(history or [])
        self.played = list(played or [])
        self.calls: list[tuple[str, object]] = []

    async def list_history(self):
        self.calls.append(("list_history", None))
        return self.history

    async def list_played(self):
        self.calls.append(("list_played", None))
        return self.played


def test_history_endpoint_delegates_to_history_service_and_uses_stable_schema(client):
    event = HistoryEvent(
        history_id=7,
        song_id="song-1",
        started_at=datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 9, 30, 10, 4, tzinfo=timezone.utc),
        reason="SKIP",
        session_id="session-1",
    )
    service = FakeHistoryService(history=[event])

    with app_services(history_service=service):
        response = client.get("/api/history")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "history_id": 7,
                "song_id": "song-1",
                "started_at": "2026-09-30T10:00:00Z",
                "ended_at": "2026-09-30T10:04:00Z",
                "reason": "SKIP",
                "session_id": "session-1",
            }
        ],
        "count": 1,
    }
    assert service.calls == [("list_history", None)]


def test_played_endpoint_delegates_to_history_service_and_reuses_queue_item_schema(
    client,
):
    item = QueueItem(
        queue_item_id="queue-1",
        song_id="song-1",
        position=-1,
        source="MANUAL",
        playback_context_id="context-1",
    )
    service = FakeHistoryService(played=[item])

    with app_services(history_service=service):
        response = client.get("/api/history/played")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "queue_item_id": "queue-1",
                "song_id": "song-1",
                "position": -1,
                "source": "MANUAL",
                "playback_context_id": "context-1",
            }
        ],
        "count": 1,
    }
    assert service.calls == [("list_played", None)]


def test_history_empty_results_are_successful(client):
    service = FakeHistoryService()

    with app_services(history_service=service):
        history = client.get("/api/history")
        played = client.get("/api/history/played")

    assert history.status_code == 200
    assert history.json() == {"items": [], "count": 0}
    assert played.status_code == 200
    assert played.json() == {"items": [], "count": 0}
    assert service.calls == [
        ("list_history", None),
        ("list_played", None),
    ]


def test_history_routes_are_registered():
    paths = app.openapi()["paths"]

    assert "/api/history" in paths
    assert "get" in paths["/api/history"]

    assert "/api/history/played" in paths
    assert "get" in paths["/api/history/played"]
