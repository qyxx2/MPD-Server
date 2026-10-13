from __future__ import annotations

import asyncio
from pathlib import Path

from server.app.services.library_change_detector import LibraryChangeDetector
from server.app.services.library_scheduler import LibraryScheduler
from server.app.services.library_sync_service import LibrarySyncService


class LibraryRuntime:
    """Own the single worker plus detection and periodic reconciliation tasks."""

    def __init__(
        self,
        sync: LibrarySyncService,
        root: Path,
        *,
        scan_interval_seconds: float = 12 * 60 * 60,
        debounce_seconds: float = 0.5,
        check_interval_seconds: float = 2,
    ) -> None:
        self.sync = sync
        self.detector = LibraryChangeDetector(
            root,
            sync.request_scan,
            interval_seconds=check_interval_seconds,
            debounce_seconds=debounce_seconds,
        )

        async def scheduled():
            return await sync.request_scan(None, "scheduled")

        self.scheduler = LibraryScheduler(
            scheduled, interval_seconds=scan_interval_seconds
        )
        self._owner = None
        self._tasks: list[asyncio.Task] = []
        self._closed = False

    async def _periodic(self):
        # The existing scheduler executes immediately; startup already did that.
        await asyncio.sleep(self.scheduler.interval_seconds)
        await self.scheduler.run_forever()

    async def _detect(self):
        await self.sync.startup_ready.wait()
        self.detector.seed(self.sync.startup_inventory)
        await self.detector.run()

    async def run(self) -> None:
        if self._owner is not None:
            raise RuntimeError("library runtime owner already running")
        if self._closed:
            return
        self._owner = asyncio.current_task()
        try:
            await self.sync.request_scan(None, "startup")
            self._tasks = [
                asyncio.create_task(self.sync.run(), name="library-sync"),
                asyncio.create_task(self._detect(), name="library-detector"),
                asyncio.create_task(self._periodic(), name="library-scheduler"),
            ]
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            if not self._closed:
                raise
        finally:
            await self.close()
            self._owner = None

    async def close(self) -> None:
        self._closed = True
        await self.detector.close()
        self.scheduler.stop()
        await self.sync.close()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
