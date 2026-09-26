from __future__ import annotations

import inspect
import sqlite3
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

from .migrations import SCHEMA_VERSION, apply_migrations

T = TypeVar("T")


def _connect(path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=5.0)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


async def initialize_database(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
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
