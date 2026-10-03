"""B4.5 lifecycle bridge proofs using the real transaction owner and guard."""

from __future__ import annotations

import asyncio

import pytest

from server.app.repositories.database import run_transaction
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.tests.invariants.test_output_event_transactions import create_terminal
from server.tests.invariants.test_output_serialization import (
    authority_snapshot,
    output_manager,
)
from server.tests.support.playback import start


def test_output_runner_exposes_only_transaction_lifecycle_capability(real_client):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        before = await authority_snapshot(service)
        facts = (await player.outputs(), await player.status(), await player.queue_entries())
        manager = output_manager(service, player, monotonic_clock=lambda: 0.0)
        delivered = []

        async def operation(lifecycle=None):
            assert lifecycle is not None, "output callback lacks lifecycle capability"
            public = {name for name in dir(lifecycle) if not name.startswith("_")}
            assert public == {"on_commit", "on_rollback"}
            lifecycle.on_commit(lambda: delivered.append("commit"))
            lifecycle.on_rollback(lambda: delivered.append("rollback"))
            assert delivered == []
            return 17

        assert await manager._run_preserved_operation(operation) == 17
        assert delivered == ["commit"]
        assert await authority_snapshot(service) == before
        assert (await player.outputs(), await player.status(), await player.queue_entries()) == facts
        assert (await manager.get_state()).last_request is None

    asyncio.run(scenario())


@pytest.mark.parametrize("phase", ["commit", "outer-failure", "callback-failure", "cancel-callback", "cancel-outer"])
def test_output_lifecycle_follows_outer_commit_rollback_and_cancellation(real_client, phase):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        path = service.queue_manager.queue_repository.path
        records = IdempotencyRepository(path)
        before = await authority_snapshot(service)
        facts = (await player.outputs(), await player.status(), await player.queue_entries())
        manager = output_manager(service, player, monotonic_clock=lambda: 0.0)
        delivered = []
        restored = []
        captured = []
        entered = asyncio.Event()
        release = asyncio.Event()

        async def notification():
            # A separate task reads committed data with the owning lock released.
            terminal = await asyncio.wait_for(
                asyncio.create_task(records.get_by_key("confirmed")), 3,
            )
            assert terminal is not None
            delivered.append(terminal.response_body)

        async def operation(lifecycle):
            captured.append(lifecycle)
            lifecycle.on_commit(notification)
            lifecycle.on_rollback(lambda: restored.append("request cleanup"))
            if phase == "callback-failure":
                raise RuntimeError("callback rejected")
            if phase == "cancel-callback":
                entered.set()
                await release.wait()
            return 17

        async def outer(_):
            assert await manager._run_preserved_operation(operation) == 17
            assert delivered == restored == []
            await create_terminal(records)
            if phase == "outer-failure":
                raise RuntimeError("outer rejected")
            if phase == "cancel-outer":
                entered.set()
                await release.wait()
            assert delivered == restored == []

        task = asyncio.create_task(run_transaction(path, outer))
        if phase.startswith("cancel-"):
            await asyncio.wait_for(entered.wait(), 3)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 3)
        elif phase.endswith("failure"):
            with pytest.raises(RuntimeError, match="rejected"):
                await task
        else:
            await asyncio.wait_for(task, 3)

        terminal = await records.get_by_key("confirmed")
        assert delivered == (['{"confirmed":true}'] if phase == "commit" else [])
        assert restored == ([] if phase == "commit" else ["request cleanup"])
        assert (terminal is not None) == (phase == "commit")
        assert await authority_snapshot(service) == before
        assert (await player.outputs(), await player.status(), await player.queue_entries()) == facts
        for hook in ("on_commit", "on_rollback"):
            with pytest.raises(RuntimeError):
                getattr(captured[0], hook)(lambda: None)

        # Retry uses a new invocation and cannot replay hooks from a failed one.
        async def retry(lifecycle):
            assert lifecycle is not captured[0]
            lifecycle.on_commit(lambda: delivered.append("retry committed"))
            return await manager.get_state()

        assert (await manager._run_preserved_operation(retry)).last_request is None
        assert delivered[-1] == "retry committed"
        assert restored == ([] if phase == "commit" else ["request cleanup"])
        assert await authority_snapshot(service) == before

    asyncio.run(scenario())


def test_nested_output_invocations_register_on_the_same_outer_transaction(real_client):
    _, _, player, service = real_client

    async def scenario():
        manager = output_manager(service, player, monotonic_clock=lambda: 0.0)
        captured = []
        delivered = []

        async def inner(lifecycle):
            assert lifecycle is not captured[0]
            lifecycle.on_commit(lambda: delivered.append("inner"))
            captured.append(lifecycle)
            return "nested receipt"

        async def outer(lifecycle):
            captured.append(lifecycle)
            lifecycle.on_commit(lambda: delivered.append("outer"))
            assert await manager._run_preserved_operation(inner) == "nested receipt"
            assert delivered == []
            with pytest.raises(RuntimeError):
                captured[1].on_commit(lambda: delivered.append("expired inner"))
            lifecycle.on_commit(lambda: delivered.append("outer after inner"))

        await service.run_output_operation(outer)
        assert delivered == ["outer", "inner", "outer after inner"]

    asyncio.run(scenario())


def test_output_lifecycle_postcommit_cancellation_keeps_terminal_without_rollback(real_client):
    _, _, player, service = real_client

    async def scenario():
        path = service.queue_manager.queue_repository.path
        records = IdempotencyRepository(path)
        manager = output_manager(service, player, monotonic_clock=lambda: 0.0)
        entered = asyncio.Event()
        release = asyncio.Event()
        restored = []
        captured = []

        async def notification():
            assert await records.get_by_key("confirmed") is not None
            entered.set()
            await release.wait()

        async def operation(lifecycle):
            captured.append(lifecycle)
            lifecycle.on_commit(notification)
            lifecycle.on_rollback(lambda: restored.append("must not roll back"))
            return await create_terminal(records)

        task = asyncio.create_task(manager._run_preserved_operation(operation))
        await asyncio.wait_for(entered.wait(), 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        terminal = await records.get_by_key("confirmed")
        assert terminal.response_status == 200
        assert terminal.response_body == '{"confirmed":true}'
        assert restored == []
        with pytest.raises(RuntimeError):
            captured[0].on_rollback(lambda: restored.append("expired"))
        assert (await manager.get_state()).last_request is None
        assert await records.get_by_key("confirmed") == terminal
        assert restored == []

    asyncio.run(scenario())


@pytest.mark.parametrize("phase", ["no-transaction", "outer-still-active", "next-invocation"])
@pytest.mark.parametrize("hook", ["on_commit", "on_rollback"])
def test_output_lifecycle_rejects_registration_outside_invocation(real_client, phase, hook):
    _, _, _, service = real_client

    async def scenario():
        captured = []
        unexpected = []

        async def capture(lifecycle):
            captured.append(lifecycle)

        def reject():
            with pytest.raises(RuntimeError):
                getattr(captured[0], hook)(lambda: unexpected.append("expired"))

        async def outer(_):
            await service.run_output_operation(capture)
            if phase == "outer-still-active":
                reject()

        await run_transaction(service.queue_manager.queue_repository.path, outer)
        if phase == "no-transaction":
            reject()
        elif phase == "next-invocation":
            async def next_operation(lifecycle):
                assert lifecycle is not captured[0]
                reject()
            await service.run_output_operation(next_operation)
        assert unexpected == []

    asyncio.run(scenario())
