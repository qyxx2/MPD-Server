from __future__ import annotations

import asyncio
import sqlite3

import pytest
from starlette.requests import Request
from starlette.responses import StreamingResponse

from server.app.repositories.database import run_transaction
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.app.services.idempotency_service import IdempotencyService
from server.tests.invariants.assertions import (
    assert_execution_relationship,
    server_snapshot,
)
from server.tests.support.playback import mutate, run, start


@pytest.mark.parametrize("transition", ["next", "skip", "stop"])
@pytest.mark.parametrize("failure", ["terminal", "outer", "cancellation"])
def test_transaction_restores_persisted_and_session_state_and_retry(
    real_client, monkeypatch, transition, failure
):
    client, library, player, service = real_client
    start(client)
    if transition == "skip":
        song = run(library.get_song("b"))
        run(
            library.upsert_song(
                song.model_copy(update={"availability_status": "UNREADABLE"})
            )
        )
    before = server_snapshot(service)
    path = service.queue_manager.queue_repository.path
    endpoint = "/api/playback/stop" if transition == "stop" else "/api/playback/next"
    records = IdempotencyRepository(path)
    if failure == "terminal":
        run(
            run_transaction(
                path,
                lambda c: c.execute("""
            CREATE TRIGGER reject_terminal BEFORE INSERT ON idempotency_records
            WHEN NEW.idempotency_key = 'rollback'
            BEGIN SELECT RAISE(ABORT, 'terminal failure'); END
        """),
            )
        )
        with pytest.raises(sqlite3.IntegrityError, match="terminal failure"):
            mutate(client, "POST", endpoint, key="rollback")
        run(run_transaction(path, lambda c: c.execute("DROP TRIGGER reject_terminal")))
    else:
        # Real IdempotencyService owns the transaction; cancel/fail after both the
        # business operation and terminal INSERT, before the outer commit.
        original_create = records.create

        async def fail_after_insert(**kwargs):
            await original_create(**kwargs)
            if failure == "cancellation":
                asyncio.current_task().cancel()
                await asyncio.sleep(0)
            raise RuntimeError("outer failure")

        monkeypatch.setattr(records, "create", fail_after_insert)

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": endpoint,
                "headers": [(b"idempotency-key", b"rollback")],
            },
            receive,
        )

        async def call_next(_request):
            state = await (service.stop() if transition == "stop" else service.next())
            return StreamingResponse(iter([state.model_dump_json().encode()]))

        error = asyncio.CancelledError if failure == "cancellation" else RuntimeError
        with pytest.raises(error):
            run(IdempotencyService(records).execute(request, call_next))
        monkeypatch.setattr(records, "create", original_create)
    assert server_snapshot(service) == before
    assert run(records.get_by_key("rollback")) is None
    # Player side effects are external to SQLite; retry must reconcile them.
    retry = mutate(client, "POST", endpoint, key="rollback")
    assert retry.status_code == 200, retry.text
    assert_execution_relationship(service, player)
    assert [
        (e.song_id, e.reason) for e in run(service.history_service.list_history())
    ] == [("a", "STOP" if transition == "stop" else "SWITCH_AWAY")]
    if transition != "stop":
        assert service.history_service.active_event.song_id == (
            "c" if transition == "skip" else "b"
        )
    final = server_snapshot(service)
    assert mutate(client, "POST", endpoint, key="rollback").json() == retry.json()
    assert server_snapshot(service) == final
