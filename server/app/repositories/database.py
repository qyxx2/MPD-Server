from __future__ import annotations

import asyncio
import inspect
import sqlite3
import threading
import weakref
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from pathlib import Path
from typing import TypeVar

from .migrations import apply_migrations

T = TypeVar("T")

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
        try:
            connection.execute("BEGIN")
            result = operation(connection)
            if inspect.isawaitable(result):
                result = await result
            connection.commit()
            return result
        except BaseException:
            connection.rollback()
            for callback in reversed(rollbacks[key]):
                callback()
            raise
        finally:
            _transaction_rollbacks.reset(rollback_token)
            _active_transactions.reset(token)
            connection.close()
