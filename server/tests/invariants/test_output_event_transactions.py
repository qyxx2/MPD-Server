"""B4 hook proofs: no output commands or System API behavior are implemented here."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone

import pytest
from starlette.requests import Request
from starlette.responses import StreamingResponse

from server.app.models.output import (
    OutputMode,
    OutputRequestState,
    OutputSnapshot,
    OutputState,
)
from server.app.repositories import database
from server.app.repositories.database import on_transaction_commit as commit_hook
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.app.services import events
from server.app.services.idempotency_service import IdempotencyService


def confirmed_event():
    snapshot = OutputSnapshot(
        states=(
            OutputState(
                mode=OutputMode.NAS_DAC,
                status="ACTIVE",
                updated_at=datetime.now(timezone.utc),
            ),
        ),
        last_request=OutputRequestState(
            mode=OutputMode.NAS_DAC,
            enabled=True,
            status="SUCCEEDED",
            updated_at=datetime.now(timezone.utc),
        ),
    )
    event_type = getattr(events, "OutputChangedEvent", None)
    assert event_type is not None, "confirmed output snapshot event is missing"
    return snapshot, event_type(snapshot=snapshot)


def test_output_event_owns_confirmed_snapshot():
    snapshot, event = confirmed_event()
    assert isinstance(event, events.DomainEvent)
    assert event.event_type == "output.changed"
    snapshot.states[0].status = "INACTIVE"
    snapshot.last_request.status = "SWITCH_FAILED"
    assert event.snapshot.states[0].status == "ACTIVE"
    assert event.snapshot.last_request.status == "SUCCEEDED"


async def create_terminal(records):
    return await records.create(
        operation_scope="B4 hook witness",
        idempotency_key="confirmed",
        payload_hash="witness",
        response_status=200,
        response_body='{"confirmed":true}',
    )


def test_output_notification_waits_for_outer_commit(tmp_path):
    path = str(tmp_path / "events.db")
    records = IdempotencyRepository(path)
    snapshot, event = confirmed_event()
    delivered = []

    class Publisher:
        async def publish(self, notification):
            # Different task/connection: both committed data and released lock are required.
            terminal = await asyncio.wait_for(
                asyncio.create_task(records.get_by_key("confirmed")),
                timeout=1,
            )
            with pytest.raises(RuntimeError, match="active transaction"):
                database.on_transaction_rollback(path, lambda: None)
            delivered.append((notification, terminal))

    async def scenario():
        await database.initialize_database(path)

        async def outer(_):
            await database.run_transaction(
                path, lambda _: commit_hook(path, lambda: Publisher().publish(event))
            )
            assert delivered == []
            await create_terminal(records)
            assert delivered == []
            # The source snapshot can be reused before delivery without altering the event.
            snapshot.states[0].status = "INACTIVE"
            return "receipt"

        assert await database.run_transaction(path, outer) == "receipt"

    asyncio.run(scenario())
    assert len(delivered) == 1
    notification, terminal = delivered[0]
    assert notification.snapshot.states[0].status == "ACTIVE"
    assert terminal.response_status == 200
    assert terminal.response_body == '{"confirmed":true}'


@pytest.mark.parametrize("failure", ["outer", "cancel", "commit"])
def test_rollback_and_cancellation_discard_notification(tmp_path, monkeypatch, failure):
    path = str(tmp_path / "events.db")
    records = IdempotencyRepository(path)
    _, event = confirmed_event()
    delivered = []
    restored = []

    class Publisher:
        async def publish(self, notification):
            delivered.append(notification)

    async def scenario():
        await database.initialize_database(path)
        connect = database._connect

        class FailingCommit(sqlite3.Connection):
            def commit(self):
                raise sqlite3.OperationalError("commit rejected")

        if failure == "commit":
            monkeypatch.setattr(
                database,
                "_connect",
                lambda p: sqlite3.connect(p, factory=FailingCommit),
            )

        async def outer(_):
            database.on_transaction_rollback(path, lambda: restored.append("request"))
            await database.run_transaction(
                path, lambda _: commit_hook(path, lambda: Publisher().publish(event))
            )
            await create_terminal(records)
            if failure == "outer":
                raise RuntimeError("outer rejected")
            if failure == "cancel":
                asyncio.current_task().cancel()
                await asyncio.sleep(0)

        error = {
            "outer": RuntimeError,
            "cancel": asyncio.CancelledError,
            "commit": sqlite3.OperationalError,
        }[failure]
        with pytest.raises(error):
            await asyncio.create_task(database.run_transaction(path, outer))
        assert restored == ["request"]
        assert delivered == []
        monkeypatch.setattr(database, "_connect", connect)
        assert await records.get_by_key("confirmed") is None

        async def retry(_):
            commit_hook(path, lambda: Publisher().publish(event))
            await create_terminal(records)

        await database.run_transaction(path, retry)
        assert len(delivered) == 1
        assert await records.get_by_key("confirmed") is not None

    asyncio.run(scenario())


def test_publisher_failure_cannot_undo_commit(tmp_path, caplog):
    path = str(tmp_path / "events.db")
    records = IdempotencyRepository(path)
    _, event = confirmed_event()
    seen = []
    restored = []

    class Publisher:
        async def publish(self, notification):
            seen.append((notification, await records.get_by_key("confirmed")))
            raise RuntimeError("output publisher offline")

    async def scenario():
        await database.initialize_database(path)

        async def operation(_):
            database.on_transaction_rollback(path, lambda: restored.append(True))
            commit_hook(path, lambda: Publisher().publish(event))
            return await create_terminal(records)

        receipt = await database.run_transaction(path, operation)
        assert await records.get_by_key("confirmed") == receipt

    asyncio.run(scenario())
    assert restored == []
    assert len(seen) == 1
    assert seen[0][1].response_body == '{"confirmed":true}'
    assert "output publisher offline" in caplog.text
    assert path in caplog.text


@pytest.mark.parametrize("phase", ["at-commit", "during-publish"])
def test_post_commit_cancellation_keeps_terminal_for_replay(
    tmp_path, monkeypatch, phase
):
    path = str(tmp_path / "events.db")
    records = IdempotencyRepository(path)
    service = IdempotencyService(records)
    _, event = confirmed_event()
    restored = []
    calls = []
    delivered = []

    def request():
        async def receive():
            return {"type": "http.request", "body": b"{}", "more_body": False}

        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/b4-hook-witness",
                "headers": [(b"idempotency-key", b"confirmed")],
            },
            receive,
        )

    async def scenario():
        await database.initialize_database(path)
        entered = asyncio.Event()
        interrupted = asyncio.Event()
        connect = database._connect

        class CancelAfterCommit(sqlite3.Connection):
            def commit(self):
                super().commit()
                asyncio.current_task().cancel()

        class Publisher:
            async def publish(self, notification):
                entered.set()
                await interrupted.wait()
                delivered.append(notification)

        async def call_next(_):
            calls.append("business")
            database.on_transaction_rollback(path, lambda: restored.append(True))
            commit_hook(path, lambda: Publisher().publish(event))
            return StreamingResponse(iter([b'{"confirmed":true}']))

        if phase == "at-commit":
            monkeypatch.setattr(
                database,
                "_connect",
                lambda p: sqlite3.connect(p, factory=CancelAfterCommit),
            )
        task = asyncio.create_task(service.execute(request(), call_next))
        if phase == "during-publish":
            await asyncio.wait_for(entered.wait(), timeout=1)
            task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=1)
        monkeypatch.setattr(database, "_connect", connect)
        terminal = await records.get_by_key("confirmed")
        assert terminal is not None
        assert terminal.response_status == 200
        assert terminal.response_body == '{"confirmed":true}'
        assert restored == []
        assert delivered == []
        response = await service.execute(request(), call_next)
        assert response.status_code == 200
        assert response.body == b'{"confirmed":true}'
        assert calls == ["business"]
        assert delivered == []
        assert await records.get_by_key("confirmed") == terminal

    asyncio.run(scenario())
