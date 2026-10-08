from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from time import monotonic
from weakref import WeakKeyDictionary

from server.app.services.playback_service import PlaybackService

logger = logging.getLogger(__name__)


class PlaybackRecoveryRunner:
    """One serial recovery loop, controlling playback only through its facade."""

    _owners: WeakKeyDictionary[PlaybackService, PlaybackRecoveryRunner] = WeakKeyDictionary()

    def __init__(
        self, playback: PlaybackService, *, interval: float = 1, budget: float = 5,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if interval <= 0 or budget <= 0:
            raise ValueError('interval and budget must be positive')
        self._playback = playback
        self._interval = interval
        self._budget = budget
        self._sleep = sleep
        self._clock = clock
        self._task: asyncio.Task | None = None
        self._closed = False

    async def run(self) -> None:
        if self._closed:
            return
        if self._task is not None or self._playback in self._owners:
            raise RuntimeError('Playback recovery control owner is already running')
        self._owners[self._playback] = self
        self._task = asyncio.current_task()
        failures = 0
        try:
            while True:
                started = self._clock()
                try:
                    async with asyncio.timeout(self._budget):
                        result = await self._playback.maintain_execution(
                            read_timeout=max(0, self._budget - (self._clock() - started)),
                        )
                        failed = result.reconciliation_required
                        if failed:
                            # UNKNOWN never retries a control itself. Refresh only
                            # external facts through the Service's read-only facade.
                            await self._playback.observe(
                                read_timeout=max(0, self._budget - (self._clock() - started)),
                            )
                except Exception:
                    logger.exception('Playback recovery failed')
                    failed = True
                if failed:
                    failures = min(failures + 1, 6)
                    delay = min(2 ** (failures - 1), 30)
                else:
                    failures = 0
                    delay = self._interval
                await self._sleep(delay)
        except asyncio.CancelledError:
            if not self._closed:
                raise
        finally:
            self._task = None
            del self._owners[self._playback]

    async def close(self) -> None:
        self._closed = True
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
