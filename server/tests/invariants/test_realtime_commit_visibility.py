from __future__ import annotations

import asyncio
import importlib
import importlib.util
import sqlite3

import pytest
from starlette.requests import Request
from starlette.responses import StreamingResponse

from server.app.models.library import ScanResult
from server.app.models.output import OutputSnapshot
from server.app.repositories import database
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.app.services.events import LibraryChangedEvent, OutputChangedEvent
from server.app.services.idempotency_service import IdempotencyService


def coordinator_for(path):
    module = "server.app.services.realtime_coordinator"
    assert importlib.util.find_spec(module) is not None, (
        "committed revision/notification coordinator is missing"
    )
    return importlib.import_module(module).RealtimeCoordinator(path)


async def read_cut(path, coordinator):
    return await database.run_transaction(
        path,
        lambda c: (
            c.execute("SELECT name FROM artists ORDER BY artist_id").fetchall(),
            coordinator.marker(),
        ),
    )


def test_committed_data_and_revision_become_visible_together(tmp_path):
    """Moving version registration into an async commit hook breaks this cut."""
    path = str(tmp_path / "realtime.db")
    coordinator = coordinator_for(path)

    async def scenario():
        await database.initialize_database(path)
        callback_started = asyncio.Event()
        release_callback = asyncio.Event()
        subscriber = coordinator.subscribe()

        async def delayed_notification():
            callback_started.set()
            await release_callback.wait()

        def change(c):
            c.execute("INSERT INTO artists VALUES ('a', 'new')")
            coordinator.stage_change(frozenset({"library"}), (), ("new",))
            database.on_transaction_commit(path, delayed_notification)
            assert coordinator.marker().library_revision == 0
            assert subscriber.pending is None

        writer = asyncio.create_task(database.run_transaction(path, change))
        try:
            await asyncio.wait_for(callback_started.wait(), 1)
            rows, marker = await asyncio.wait_for(read_cut(path, coordinator), 1)
            assert rows == [("new",)]
            assert (marker.sequence, marker.library_revision, marker.playlist_revision) == (
                1, 1, 0
            )
            assert subscriber.pending.sequence == 1
            assert subscriber.pending.domains == frozenset({"library"})
            assert subscriber.pending.revisions == {"library": 1, "playlist": 0}
        finally:
            release_callback.set()
            await writer

    asyncio.run(scenario())


@pytest.mark.parametrize("outcome", ["commit", "rollback"])
def test_child_task_staging_shares_outer_owner_and_does_not_interrupt_runtime_restore(
    tmp_path, outcome,
):
    """HTTP call_next runs in a child task; outer owner must clean up its staging."""
    path = str(tmp_path / "realtime.db")
    coordinator = coordinator_for(path)

    async def scenario():
        await database.initialize_database(path)
        subscriber = coordinator.subscribe()
        restored = []

        async def outer(c):
            database.on_transaction_rollback(path, lambda: restored.append("runtime"))

            async def child():
                def change(connection):
                    connection.execute("INSERT INTO artists VALUES ('a', 'child')")
                    coordinator.stage_change(frozenset({"library"}), (), ("child",))

                await database.run_transaction(path, change)

            await asyncio.create_task(child())
            if outcome == "rollback":
                raise RuntimeError("terminal rejected")
            # Parent and child must aggregate, not each increment independently.
            coordinator.stage_change(frozenset({"library"}), ("child",), ("parent",))
            c.execute("UPDATE artists SET name = 'parent'")

        if outcome == "rollback":
            with pytest.raises(RuntimeError, match="terminal rejected"):
                await database.run_transaction(path, outer)
            assert restored == ["runtime"]
            assert await read_cut(path, coordinator) == ([], coordinator.marker())
            assert coordinator.marker().sequence == 0
            assert subscriber.pending is None
        else:
            await database.run_transaction(path, outer)
            rows, marker = await read_cut(path, coordinator)
            assert rows == [("parent",)]
            assert (marker.sequence, marker.library_revision) == (1, 1)
            assert restored == []
            assert subscriber.valid
            assert subscriber.pending.sequence == 1

        # Another transaction cannot inherit a completed child's staging.
        before = coordinator.marker()
        await database.run_transaction(
            path, lambda _: coordinator.stage_change(frozenset({"playlist"}), (), ("next",))
        )
        after = coordinator.marker()
        assert (after.sequence, after.library_revision, after.playlist_revision) == (
            before.sequence + 1, before.library_revision, 1
        )

    asyncio.run(scenario())


def test_reversed_callbacks_reassert_latest_marker_and_keep_all_pending_domains(tmp_path):
    """Late completion payload cannot restore old revisions or erase another domain."""
    path = str(tmp_path / "realtime.db")
    coordinator = coordinator_for(path)
    assert callable(getattr(coordinator, "publish", None)), "event bridge is missing"

    async def scenario():
        await database.initialize_database(path)
        subscriber = coordinator.subscribe()
        first_waiting = asyncio.Event()
        release_first = asyncio.Event()
        old_completion = LibraryChangedEvent(result=ScanResult(added_song_ids=("a",)))
        new_completion = LibraryChangedEvent(result=ScanResult(updated_song_ids=("a",)))

        async def delayed():
            first_waiting.set()
            await release_first.wait()
            await coordinator.publish(old_completion)

        def first(c):
            c.execute("INSERT INTO artists VALUES ('a', 'first')")
            coordinator.stage_change(frozenset({"library"}), (), ("first",))
            database.on_transaction_commit(path, delayed)

        writer = asyncio.create_task(database.run_transaction(path, first))
        try:
            await asyncio.wait_for(first_waiting.wait(), 1)

            def second(c):
                c.execute("UPDATE artists SET name = 'second'")
                coordinator.stage_change(frozenset({"library"}), ("first",), ("second",))
                coordinator.stage_change(frozenset({"playlist"}), (), ("favorite",))
                database.on_transaction_commit(path, lambda: coordinator.publish(new_completion))

            await database.run_transaction(path, second)
            intermediate = coordinator.marker()
            assert (intermediate.library_revision, intermediate.playlist_revision) == (2, 1)
        finally:
            release_first.set()
            await writer
        rows, final = await read_cut(path, coordinator)
        assert rows == [("second",)]
        assert final.sequence > intermediate.sequence
        assert (final.library_revision, final.playlist_revision) == (2, 1)
        assert subscriber.pending.domains == frozenset({"library", "playlist"})
        assert subscriber.pending.sequence == final.sequence
        assert subscriber.pending.revisions == {"library": 2, "playlist": 1}
        # Output event payload remains a domain-owned snapshot, never state authority here.
        event = OutputChangedEvent(snapshot=OutputSnapshot(states=()))
        await coordinator.publish(event)
        assert event.snapshot.states == ()
        assert coordinator.marker().library_revision == 2
        assert subscriber.pending.domains == frozenset({"library", "playlist", "output"})

    asyncio.run(scenario())


def test_cancellation_after_commit_keeps_last_change_registered(tmp_path):
    path = str(tmp_path / "realtime.db")
    coordinator = coordinator_for(path)

    async def scenario():
        await database.initialize_database(path)
        subscriber = coordinator.subscribe()
        waiting = asyncio.Event()

        async def wait_forever():
            waiting.set()
            await asyncio.Event().wait()

        def first(c):
            c.execute("INSERT INTO artists VALUES ('a', 'first')")
            coordinator.stage_change(frozenset({"library"}), (), ("first",))
            database.on_transaction_commit(path, wait_forever)

        writer = asyncio.create_task(database.run_transaction(path, first))
        try:
            await asyncio.wait_for(waiting.wait(), 1)

            def last(c):
                c.execute("UPDATE artists SET name = 'last'")
                coordinator.stage_change(frozenset({"library"}), ("first",), ("last",))

            await database.run_transaction(path, last)
        finally:
            writer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await writer
        rows, marker = await read_cut(path, coordinator)
        assert rows == [("last",)]
        assert (marker.sequence, marker.library_revision, marker.playlist_revision) == (
            2, 2, 0
        )
        assert subscriber.valid
        assert subscriber.pending.sequence == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["operation", "cancel", "commit"])
def test_rollback_discards_staging_and_retry_registers_once(tmp_path, monkeypatch, failure):
    path = str(tmp_path / "realtime.db")
    coordinator = coordinator_for(path)

    async def scenario():
        await database.initialize_database(path)
        before = coordinator.marker()
        subscriber = coordinator.subscribe()
        original_connect = database._connect

        class RejectCommit(sqlite3.Connection):
            def commit(self):
                raise sqlite3.OperationalError("commit rejected")

        if failure == "commit":
            monkeypatch.setattr(
                database, "_connect", lambda p: sqlite3.connect(p, factory=RejectCommit)
            )

        async def rejected(c):
            c.execute("INSERT INTO artists VALUES ('a', 'rejected')")
            coordinator.stage_change(frozenset({"library"}), (), ("rejected",))
            if failure == "cancel":
                asyncio.current_task().cancel()
                await asyncio.sleep(0)
            if failure == "operation":
                raise RuntimeError("operation rejected")

        error = {"operation": RuntimeError, "cancel": asyncio.CancelledError,
                 "commit": sqlite3.OperationalError}[failure]
        with pytest.raises(error):
            await asyncio.create_task(database.run_transaction(path, rejected))
        monkeypatch.setattr(database, "_connect", original_connect)
        assert await read_cut(path, coordinator) == ([], before)
        assert subscriber.pending is None

        def retry(c):
            c.execute("INSERT INTO artists VALUES ('a', 'retry')")
            coordinator.stage_change(frozenset({"library"}), (), ("retry",))

        await database.run_transaction(path, retry)
        rows, marker = await read_cut(path, coordinator)
        assert rows == [("retry",)]
        assert (marker.sequence, marker.library_revision, marker.playlist_revision) == (
            1, 1, 0
        )

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
def test_registration_failure_invalidates_subscriptions_and_marker_without_rollback(
    tmp_path, monkeypatch, caplog, failure,
):
    """Post-commit registration cannot leave a trusted old marker or undo terminal."""
    path = str(tmp_path / "realtime.db")
    coordinator = coordinator_for(path)
    restored = []

    async def scenario():
        await database.initialize_database(path)
        subscriber = coordinator.subscribe()
        records = IdempotencyRepository(path)

        def reject_registration(_domains):
            raise failure("registration unavailable")

        monkeypatch.setattr(coordinator, "_register", reject_registration)

        async def change(c):
            c.execute("INSERT INTO artists VALUES ('a', 'committed')")
            database.on_transaction_rollback(path, lambda: restored.append(True))
            coordinator.stage_change(frozenset({"library"}), (), ("committed",))
            await records.create(
                operation_scope="POST /example", idempotency_key="committed",
                payload_hash="payload", response_status=200, response_body='{"ok":true}',
            )
            return "success"

        assert await database.run_transaction(path, change) == "success"
        assert restored == []
        assert not subscriber.valid
        assert subscriber.pending is None
        with pytest.raises(RuntimeError, match="unavailable"):
            coordinator.marker()
        with pytest.raises(RuntimeError, match="unavailable"):
            coordinator.subscribe()
        assert await database.run_transaction(
            path, lambda c: c.execute("SELECT name FROM artists").fetchall()
        ) == [("committed",)]
        assert (await records.get_by_key("committed")).response_status == 200
        # Recovery initializes a new process-local epoch against committed data.
        fresh = coordinator_for(path)
        assert fresh.marker().epoch != coordinator._marker.epoch
        rows, marker = await read_cut(path, fresh)
        assert rows == [("committed",)]
        assert (marker.sequence, marker.library_revision, marker.playlist_revision) == (
            0, 0, 0
        )

    asyncio.run(scenario())
    assert "registration unavailable" in caplog.text
    assert path in caplog.text


def test_outer_delta_is_once_per_domain_and_reverted_content_is_noop(tmp_path):
    """Counting calls instead of first-before/final-after consumes false versions."""
    path = str(tmp_path / "realtime.db")
    coordinator = coordinator_for(path)

    async def scenario():
        await database.initialize_database(path)
        subscriber = coordinator.subscribe()

        async def change(c):
            c.execute("INSERT INTO artists VALUES ('a', 'final')")
            coordinator.stage_change(frozenset({"library"}), [], ["intermediate"])
            await database.run_transaction(
                path,
                lambda _: coordinator.stage_change(
                    frozenset({"library"}), ["intermediate"], ["final"]
                ),
            )
            coordinator.stage_change(frozenset({"playlist"}), [], ["favorite"])

        await database.run_transaction(path, change)
        marker = coordinator.marker()
        assert (marker.sequence, marker.library_revision, marker.playlist_revision) == (
            1, 1, 1
        )
        assert subscriber.pending.domains == frozenset({"library", "playlist"})

        def reverted(c):
            c.execute("UPDATE artists SET name = 'temporary'")
            coordinator.stage_change(frozenset({"library"}), ["final"], ["temporary"])
            c.execute("UPDATE artists SET name = 'final'")
            coordinator.stage_change(frozenset({"library"}), ["temporary"], ["final"])
            coordinator.stage_change(frozenset({"playlist"}), ["favorite"], ["favorite"])

        await database.run_transaction(path, reverted)
        assert coordinator.marker() == marker
        assert (await read_cut(path, coordinator))[0] == [("final",)]

    asyncio.run(scenario())


def test_staging_owns_content_and_marker_and_notifications_are_independent(tmp_path):
    """Aliasing caller snapshots can erase a real delta or corrupt another reader."""
    path = str(tmp_path / "realtime.db")
    coordinator = coordinator_for(path)

    async def scenario():
        await database.initialize_database(path)
        first = coordinator.subscribe()
        second = coordinator.subscribe()
        before, after = [], ["new"]

        def change(c):
            c.execute("INSERT INTO artists VALUES ('a', 'new')")
            coordinator.stage_change(frozenset({"library"}), before, after)
            after.clear()

        await database.run_transaction(path, change)
        assert coordinator.marker().library_revision == 1
        first.pending.revisions["library"] = 99
        assert second.pending.revisions["library"] == 1
        assert coordinator.marker().library_revision == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("order", ["before", "after", "comparison"])
def test_any_visibility_registration_failure_blocks_trusted_state(tmp_path, caplog, order):
    path = str(tmp_path / "realtime.db")
    coordinator = coordinator_for(path)

    class Uncomparable:
        def __eq__(self, other):
            raise RuntimeError("comparison unavailable")

    def broken_hook():
        raise RuntimeError("shared registration unavailable")

    async def scenario():
        await database.initialize_database(path)
        subscriber = coordinator.subscribe()

        def change(c):
            c.execute("INSERT INTO artists VALUES ('a', 'committed')")
            if order == "before":
                database.on_transaction_visible(path, broken_hook)
            coordinator.stage_change(
                frozenset({"library"}),
                Uncomparable() if order == "comparison" else (), ("committed",),
            )
            if order == "after":
                database.on_transaction_visible(path, broken_hook)

        await database.run_transaction(path, change)
        assert not subscriber.valid
        with pytest.raises(RuntimeError, match="unavailable"):
            coordinator.marker()
        assert await database.run_transaction(
            path, lambda c: c.execute("SELECT name FROM artists").fetchall()
        ) == [("committed",)]

    asyncio.run(scenario())
    assert "unavailable" in caplog.text


def test_terminal_failure_and_success_replay_preserve_committed_versions(tmp_path):
    """Real terminal rollback/replay must not leak or repeat coordinator changes."""
    path = str(tmp_path / "realtime.db")
    coordinator = coordinator_for(path)

    async def scenario():
        await database.initialize_database(path)
        subscriber = coordinator.subscribe()
        records = IdempotencyRepository(path)
        idempotency = IdempotencyService(records)

        async def receive():
            return {"type": "http.request", "body": b"{}", "more_body": False}

        def request():
            return Request({
                "type": "http", "method": "POST", "path": "/example",
                "headers": [(b"idempotency-key", b"realtime")],
            }, receive)

        async def call_next(_):
            def change(c):
                c.execute("INSERT INTO artists VALUES ('a', 'committed')")
                coordinator.stage_change(frozenset({"library"}), (), ("committed",))

            await database.run_transaction(path, change)
            return StreamingResponse(iter([b'{"ok":true}']), media_type="application/json")

        await database.run_transaction(path, lambda c: c.execute("""
            CREATE TRIGGER reject_terminal BEFORE INSERT ON idempotency_records
            BEGIN SELECT RAISE(ABORT, 'terminal rejected'); END
        """))
        with pytest.raises(sqlite3.IntegrityError, match="terminal rejected"):
            await idempotency.execute(request(), call_next)
        assert coordinator.marker().sequence == 0
        assert subscriber.pending is None
        assert (await read_cut(path, coordinator))[0] == []
        assert await records.get_by_key("realtime") is None
        await database.run_transaction(path, lambda c: c.execute("DROP TRIGGER reject_terminal"))
        receipt = await idempotency.execute(request(), call_next)
        rows, marker = await read_cut(path, coordinator)
        notification = subscriber.pending.model_copy(deep=True)
        replay = await idempotency.execute(request(), call_next)
        assert receipt.status_code == replay.status_code == 200
        assert receipt.body == replay.body == b'{"ok":true}'
        assert rows == [("committed",)]
        assert (marker.sequence, marker.library_revision, marker.playlist_revision) == (1, 1, 0)
        assert await read_cut(path, coordinator) == (rows, marker)
        assert subscriber.pending == notification

    asyncio.run(scenario())


def test_visibility_registration_requires_own_transaction_and_preserves_other_state(tmp_path):
    path = str(tmp_path / "realtime.db")
    coordinator = coordinator_for(path)
    with pytest.raises(RuntimeError, match="active transaction"):
        coordinator.stage_change(frozenset({"library"}), (), ("outside",))
    with pytest.raises(RuntimeError, match="active transaction"):
        database.on_transaction_visible(path, lambda: None)
    with pytest.raises(RuntimeError, match="active transaction"):
        database.on_transaction_visibility_failure(path, lambda: None)

    async def scenario():
        await database.initialize_database(path)
        other = str(tmp_path / "other.db")
        await database.initialize_database(other)

        def protected_state(c):
            return tuple(
                (table, c.execute(f"SELECT * FROM {table}").fetchall())
                for table in ("queue_items", "history", "playlists", "playlist_items",
                              "favorites", "playback_state")
            )

        before = await database.run_transaction(path, protected_state)

        def foreign(_):
            with pytest.raises(RuntimeError, match="active transaction"):
                coordinator.stage_change(frozenset({"library"}), (), ("foreign",))

        await database.run_transaction(other, foreign)
        await database.run_transaction(
            path, lambda _: coordinator.stage_change(frozenset({"library"}), (), ("new",))
        )
        assert await database.run_transaction(path, protected_state) == before
        assert coordinator.marker().playlist_revision == 0

    asyncio.run(scenario())
