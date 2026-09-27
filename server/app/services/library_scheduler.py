from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from server.app.models.library import ScanResult


ScanFullCallback = Callable[[], Awaitable[ScanResult]]


class LibraryScheduler:
    def __init__(
        self,
        scan_full: ScanFullCallback,
        interval_seconds: float = 12 * 60 * 60,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.scan_full = scan_full
        self.interval_seconds = interval_seconds
        self._sleep = sleep
        self._stopped = False

    async def run_once(self) -> ScanResult:
        return await self.scan_full()

    async def run_forever(self) -> None:
        self._stopped = False
        while not self._stopped:
            await self.scan_full()
            if self._stopped:
                break
            await self._sleep(self.interval_seconds)

    def stop(self) -> None:
        self._stopped = True
