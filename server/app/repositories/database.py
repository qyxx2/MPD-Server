from __future__ import annotations

import asyncio
import inspect
import logging
import sqlite3
import threading
import weakref
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from pathlib import Path
from typing import TypeVar

from .migrations import apply_migrations

T = TypeVar("T")
logger = logging.getLogger(__name__)

_database_locks: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, dict[str, asyncio.Lock]
] = weakref.WeakKeyDictionary()
_database_locks_guard = threading.Lock()
_active_transactions: ContextVar[dict[str, sqlite3.Connection] | None] = ContextVar(
    "active_database_transactions",
    default=None,
)

_transaction_rollbacks: ContextVar[dict[str, list[Callable[[], None]]] | None] = ContextVar(
    "database_transaction_rollbacks", default=None,
)

CommitCallback = Callable[[], object | Awaitable[object]]
_transaction_commits: ContextVar[dict[str, list[CommitCallback]] | None] = ContextVar(
    "database_transaction_commits", default=None,
)

_transaction_visible: ContextVar[dict[str, list[Callable[[], None]]] | None] = ContextVar(
    "database_transaction_visible", default=None,
)
_visibility_failures: ContextVar[dict[str, list[Callable[[], None]]] | None] = ContextVar(
    "database_visibility_failures", default=None,
)


def transaction_identity(path: str) -> object:
    """Opaque outer owner shared by nested calls, including inherited child tasks."""
    transactions = _active_transactions.get()
    key = _database_key(path)
    if transactions is None or key not in transactions:
        raise RuntimeError("transaction identity requires an active transaction")
    connection = transactions[key]
    try:
        active = connection.in_transaction
    except sqlite3.ProgrammingError:
        active = False
    if not active:
        raise RuntimeError("transaction identity requires an active transaction")
    return connection


def on_transaction_visibility_failure(path: str, callback: Callable[[], None]) -> None:
    """Fail closed if any registration in this outer commit fails, without rollback."""
    callbacks = _visibility_failures.get()
    key = _database_key(path)
    if callbacks is None or key not in callbacks:
        raise RuntimeError("visibility failure callback requires an active transaction")
    callbacks[key].append(callback)


def on_transaction_visible(path: str, callback: Callable[[], None]) -> None:
    """Register committed in-memory state before releasing the outer DB lock.

    Callbacks must be synchronous and perform no I/O. State owners register
    on_transaction_visibility_failure to invalidate their state on any failure.
    """
    callbacks = _transaction_visible.get()
    key = _database_key(path)
    if callbacks is None or key not in callbacks:
        raise RuntimeError("visibility callback requires an active transaction")
    callbacks[key].append(callback)


def on_transaction_commit(path: str, callback: CommitCallback) -> None:
    """Notify after the owning outer transaction commits and releases its lock."""
    callbacks = _transaction_commits.get()
    key = _database_key(path)
    if callbacks is None or key not in callbacks:
        raise RuntimeError("commit callback requires an active transaction")
    callbacks[key].append(callback)


def on_transaction_rollback(path: str, callback: Callable[[], None]) -> None:
    """Restore application state if the owning (possibly outer) transaction fails."""
    callbacks = _transaction_rollbacks.get()
    key = _database_key(path)
    if callbacks is None or key not in callbacks:
        raise RuntimeError("rollback callback requires an active transaction")
    callbacks[key].append(callback)


def _database_key(path: str) -> str:
    return str(Path(path).resolve())


def _lock_for(path: str) -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    key = _database_key(path)
    with _database_locks_guard:
        locks = _database_locks.get(loop)
        if locks is None:
            locks = {}
            _database_locks[loop] = locks
        lock = locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            locks[key] = lock
        return lock


def _connect(path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=5.0)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


async def initialize_database(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    async with _lock_for(path):
        connection = _connect(path)
        try:
            apply_migrations(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


async def check_integrity(path: str) -> bool:
    connection = _connect(path)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
        return result is not None and result[0] == "ok"
    finally:
        connection.close()


async def run_transaction(
    path: str,
    operation: Callable[[sqlite3.Connection], T | Awaitable[T]],
) -> T:
    key = _database_key(path)
    active_transactions = _active_transactions.get()
    if active_transactions is not None and key in active_transactions:
        result = operation(active_transactions[key])
        if inspect.isawaitable(result):
            result = await result
        return result

    async with _lock_for(path):
        connection = _connect(path)
        nested_transactions = dict(active_transactions or {})
        nested_transactions[key] = connection
        token = _active_transactions.set(nested_transactions)
        rollbacks = dict(_transaction_rollbacks.get() or {})
        rollbacks[key] = []
        rollback_token = _transaction_rollbacks.set(rollbacks)
        commits = dict(_transaction_commits.get() or {})
        commits[key] = []
        commit_token = _transaction_commits.set(commits)
        visible = dict(_transaction_visible.get() or {})
        visible[key] = []
        visible_token = _transaction_visible.set(visible)
        failures = dict(_visibility_failures.get() or {})
        failures[key] = []
        failure_token = _visibility_failures.set(failures)
        try:
            connection.execute("BEGIN")
            result = operation(connection)
            if inspect.isawaitable(result):
                result = await result
            connection.commit()
        except BaseException:
            connection.rollback()
            for callback in reversed(rollbacks[key]):
                callback()
            raise
        else:
            # A visibility failure is post-commit: never run rollback hooks.
            visibility_failed = False
            for callback in visible[key]:
                try:
                    callback()
                except BaseException:
                    visibility_failed = True
                    logger.exception("Commit visibility registration failed for database %s", key)
            if visibility_failed:
                for callback in failures[key]:
                    try:
                        callback()
                    except BaseException:
                        logger.exception("Commit visibility failure handler failed for database %s", key)
        finally:
            _visibility_failures.reset(failure_token)
            _transaction_visible.reset(visible_token)
            _transaction_commits.reset(commit_token)
            _transaction_rollbacks.reset(rollback_token)
            _active_transactions.reset(token)
            connection.close()

    for callback in commits[key]:
        try:
            notification = callback()
            if inspect.isawaitable(notification):
                await notification
        except Exception:
            logger.exception("Post-commit notification failed for database %s", key)
    return result
