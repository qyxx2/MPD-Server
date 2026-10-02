from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.models.library import Song
from server.app.player.mock_mpd import MockMPD
from server.app.repositories.library_repository import LibraryRepository


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def real_client(tmp_path, monkeypatch):
    path = str(tmp_path / "pre-batch6.db")
    monkeypatch.setenv("DATABASE_PATH", path)
    with TestClient(app) as client:
        library = LibraryRepository(path)
        for song_id in "abc":
            run(
                library.upsert_song(
                    Song(
                        song_id=song_id,
                        title=song_id,
                        file_uri=f"{song_id}.flac",
                    )
                )
            )
        player = MockMPD([f"{song_id}.flac" for song_id in "abcd"])
        app.state.playback_service.player = player
        yield client, library, player, app.state.playback_service


def mutate(client, method, path, body=None, key=None):
    return client.request(
        method,
        path,
        json=body,
        headers={
            "Idempotency-Key": key or f"{method}:{path}:{body}",
        },
    )


def start(client):
    response = mutate(
        client,
        "POST",
        "/api/playback/collections/play",
        {
            "source_type": "SONGS",
            "song_ids": ["a", "b", "c"],
        },
    )
    assert response.status_code == 200, response.text
    return client.get("/api/playback/queue").json()["items"]
