from __future__ import annotations

import asyncio
import inspect
import sqlite3
import threading
import weakref
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

from .migrations import apply_migrations

T = TypeVar("T")

_database_locks: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, dict[str, asyncio.Lock]
] = weakref.WeakKeyDictionary()
_database_locks_guard = threading.Lock()


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
    async with _lock_for(path):
        connection = _connect(path)
        try:
            connection.execute("BEGIN")
            result = operation(connection)
            if inspect.isawaitable(result):
                result = await result
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
