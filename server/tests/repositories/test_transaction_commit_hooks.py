from __future__ import annotations

import asyncio
import sqlite3

import pytest

from server.app.repositories import database


def commit_hook(path, callback):
    hook = getattr(database, "on_transaction_commit", None)
    assert callable(hook), "outer-commit notification hook is missing"
    hook(path, callback)


def test_nested_hooks_wait_for_commit_and_release_context_and_lock(tmp_path):
    path = str(tmp_path / "hooks.db")
    delivered = []

    async def scenario():
        await database.initialize_database(path)

        async def notification():
            # A separate task must acquire the same DB lock and see committed data.
            rows = await asyncio.wait_for(
                asyncio.create_task(
                    database.run_transaction(
                        path, lambda c: c.execute("SELECT name FROM artists").fetchall()
                    )
                ),
                timeout=1,
            )
            assert rows == [("committed",)]
            with pytest.raises(RuntimeError, match="active transaction"):
                commit_hook(path, lambda: None)
            with pytest.raises(RuntimeError, match="active transaction"):
                database.on_transaction_rollback(path, lambda: None)
            delivered.append("async")

        async def outer(connection):
            connection.execute(
                "INSERT INTO artists(artist_id, name) VALUES ('a', 'committed')"
            )
            commit_hook(path, lambda: delivered.append("sync"))
            await database.run_transaction(
                path, lambda _: commit_hook(path, notification)
            )
            assert delivered == []
            return "receipt"

        assert await database.run_transaction(path, outer) == "receipt"
        assert delivered == ["sync", "async"]

    asyncio.run(scenario())


def test_registration_requires_own_active_database(tmp_path):
    path = str(tmp_path / "hooks.db")
    with pytest.raises(RuntimeError, match="active transaction"):
        commit_hook(path, lambda: None)

    async def scenario():
        await database.initialize_database(path)

        async def operation(_):
            with pytest.raises(RuntimeError, match="active transaction"):
                commit_hook(str(tmp_path / "other.db"), lambda: None)

        await database.run_transaction(path, operation)

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["operation", "cancel", "commit"])
def test_failed_transaction_discards_hooks_and_can_retry(
    tmp_path, monkeypatch, failure
):
    path = str(tmp_path / "hooks.db")
    delivered = []
    restored = []

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

        async def operation(connection):
            connection.execute("INSERT INTO artists(artist_id, name) VALUES ('a', 'a')")
            database.on_transaction_rollback(path, lambda: restored.append("outer"))

            async def inner(_):
                commit_hook(path, lambda: delivered.append("invalid"))
                database.on_transaction_rollback(path, lambda: restored.append("inner"))

            await database.run_transaction(path, inner)
            if failure == "operation":
                raise RuntimeError("operation rejected")
            if failure == "cancel":
                asyncio.current_task().cancel()
                await asyncio.sleep(0)

        error = {
            "operation": RuntimeError,
            "cancel": asyncio.CancelledError,
            "commit": sqlite3.OperationalError,
        }[failure]
        # Cancellation runs in its own task so retry is a genuinely new operation.
        with pytest.raises(error):
            await asyncio.create_task(database.run_transaction(path, operation))
        assert delivered == []
        assert restored == ["inner", "outer"]
        monkeypatch.setattr(database, "_connect", connect)
        assert (
            await database.run_transaction(
                path, lambda c: c.execute("SELECT name FROM artists").fetchall()
            )
            == []
        )
        await database.run_transaction(
            path, lambda _: commit_hook(path, lambda: delivered.append("retry"))
        )
        assert delivered == ["retry"]

    asyncio.run(scenario())


@pytest.mark.parametrize("asynchronous", [False, True])
def test_notification_failure_is_logged_without_changing_commit(
    tmp_path, caplog, asynchronous
):
    path = str(tmp_path / "hooks.db")
    delivered = []
    restored = []

    def fail():
        raise RuntimeError("notification offline")

    async def async_fail():
        await asyncio.sleep(0)
        fail()

    async def scenario():
        await database.initialize_database(path)

        def operation(connection):
            connection.execute("INSERT INTO artists(artist_id, name) VALUES ('a', 'a')")
            database.on_transaction_rollback(path, lambda: restored.append(True))
            commit_hook(path, async_fail if asynchronous else fail)
            commit_hook(path, lambda: delivered.append("second"))
            return "committed receipt"

        assert await database.run_transaction(path, operation) == "committed receipt"
        assert await database.run_transaction(
            path, lambda c: c.execute("SELECT name FROM artists").fetchall()
        ) == [("a",)]

    asyncio.run(scenario())
    assert restored == []
    assert delivered == ["second"]
    assert "notification offline" in caplog.text
    assert path in caplog.text
