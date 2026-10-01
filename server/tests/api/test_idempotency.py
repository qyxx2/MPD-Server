from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from server.app.main import app
from server.app.repositories.idempotency_repository import IdempotencyRepository


def run(awaitable):
    return asyncio.run(awaitable)


def test_playlist_create_commits_business_result_and_replay_record_together(
    tmp_path,
    monkeypatch,
):
    database_path = str(tmp_path / "idempotency.db")
    monkeypatch.setenv("DATABASE_PATH", database_path)
    headers = {"Idempotency-Key": "persisted-create"}

    with TestClient(app) as client:
        first = client.post("/api/playlists", json={"name": "Saved"}, headers=headers)
        replay = client.post(
            "/api/playlists",
            json={"name": "Saved"},
            headers=headers,
        )
        playlists = client.get("/api/playlists")

    record = run(IdempotencyRepository(database_path).get_by_key("persisted-create"))
    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert playlists.json()["count"] == 1
    assert record is not None
    assert record.response_status == 201
    assert record.response_body == first.text


def test_schema_failure_does_not_consume_idempotency_key(tmp_path, monkeypatch):
    database_path = str(tmp_path / "idempotency.db")
    monkeypatch.setenv("DATABASE_PATH", database_path)
    headers = {"Idempotency-Key": "retry-after-validation"}

    with TestClient(app) as client:
        rejected = client.post("/api/playlists", json={"name": ""}, headers=headers)
        accepted = client.post(
            "/api/playlists",
            json={"name": "Valid"},
            headers=headers,
        )

    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"
    assert accepted.status_code == 201
