from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from server.app.models.library import ScanResult


ScanPathsCallback = Callable[[list[Path]], Awaitable[ScanResult]]


class LibraryWatch:
    def __init__(
        self,
        scan_paths: ScanPathsCallback,
        debounce_seconds: float = 0.5,
    ) -> None:
        if debounce_seconds < 0:
            raise ValueError("debounce_seconds must be non-negative")
        self.scan_paths = scan_paths
        self.debounce_seconds = debounce_seconds
        self._pending: set[Path] = set()
        self._timer_task: asyncio.Task[None] | None = None

    async def notify(self, path: Path) -> None:
        self._pending.add(path.resolve())
        if self._timer_task is not None:
            self._timer_task.cancel()
        self._timer_task = asyncio.create_task(self._debounced_scan())

    async def _debounced_scan(self) -> None:
        try:
            await asyncio.sleep(self.debounce_seconds)
        except asyncio.CancelledError:
            return
        paths = sorted(self._pending, key=str)
        self._pending.clear()
        self._timer_task = None
        if paths:
            await self.scan_paths(paths)

    async def flush(self) -> ScanResult | None:
        if self._timer_task is not None:
            self._timer_task.cancel()
            self._timer_task = None
        paths = sorted(self._pending, key=str)
        self._pending.clear()
        if not paths:
            return None
        return await self.scan_paths(paths)

    async def close(self) -> None:
        if self._timer_task is not None:
            self._timer_task.cancel()
            self._timer_task = None
        self._pending.clear()
