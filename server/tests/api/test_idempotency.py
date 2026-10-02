from __future__ import annotations

import asyncio
import sqlite3

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.repositories.database import run_transaction
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.app.repositories.playlist_repository import PlaylistRepository


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


def test_terminal_record_write_failure_rolls_back_business_mutation(
    tmp_path, monkeypatch
):
    database_path = str(tmp_path / "rollback.db")
    monkeypatch.setenv("DATABASE_PATH", database_path)

    def fail_terminal_write(connection):
        connection.execute(
            """
            CREATE TRIGGER fail_terminal_record
            AFTER INSERT ON idempotency_records
            BEGIN
                SELECT CASE
                    WHEN EXISTS(SELECT 1 FROM playlists WHERE name = 'Rollback')
                    THEN RAISE(ABORT, 'terminal write failed after business mutation')
                    ELSE RAISE(ABORT, 'business mutation missing')
                END;
            END
            """
        )

    with TestClient(app) as client:
        run(run_transaction(database_path, fail_terminal_write))
        with pytest.raises(
            sqlite3.IntegrityError,
            match="terminal write failed after business mutation",
        ):
            client.post(
                "/api/playlists",
                json={"name": "Rollback"},
                headers={"Idempotency-Key": "terminal-write-failure"},
            )

    assert run(PlaylistRepository(database_path).list_playlists()) == []
    assert (
        run(
            IdempotencyRepository(database_path).get_by_key(
                "terminal-write-failure"
            )
        )
        is None
    )
