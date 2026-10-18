from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from time import monotonic

from server.app.services.output_manager import OutputManager
from server.app.services.playback_service import PlaybackService

logger = logging.getLogger(__name__)


class StateObserver:
    """One process-owned, read-only sampler, independent of client connections."""

    def __init__(
        self, *, playback: PlaybackService, output: OutputManager,
        interval: float = 1, read_budget: float = 5,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic_clock: Callable[[], float] = monotonic,
    ) -> None:
        self._playback = playback
        self._output = output
        self._interval = interval
        self._budget = read_budget
        self._sleep = sleep
        self._clock = monotonic_clock
        self._task: asyncio.Task | None = None
        self._closed = False
        self._requested = asyncio.Event()
        self._request_generation = 0

    def request_observation(self) -> None:
        """Coalesce committed refreshes without starting another sampler."""
        if not self._closed:
            self._request_generation += 1
            self._requested.set()

    async def _wait(self) -> None:
        periodic = asyncio.create_task(self._sleep(self._interval))
        requested = asyncio.create_task(self._requested.wait())
        try:
            done, _ = await asyncio.wait(
                (periodic, requested), return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                task.result()
        finally:
            for task in (periodic, requested):
                task.cancel()
            await asyncio.gather(periodic, requested, return_exceptions=True)

    async def run(self) -> None:
        if self._task is not None:
            raise RuntimeError('StateObserver is already running')
        if self._closed:
            return
        self._task = asyncio.current_task()
        try:
            while True:
                generation = self._request_generation
                started = self._clock()
                for sample in (self._playback.observe, self._output.get_state):
                    try:
                        await sample(read_timeout=max(0, self._budget - (self._clock() - started)))
                    except Exception:
                        logger.exception('State observation failed')
                # Expiry also runs in the Service's shared capture boundary.
                for cached in (self._playback.get_observation, self._output.get_observation):
                    try:
                        await cached()
                    except Exception:
                        logger.exception('State observation cache refresh failed')
                # A request arriving during this round requires a newer sample.
                if generation != self._request_generation:
                    continue
                # No await between comparison and clear: a later request wakes wait.
                self._requested.clear()
                await self._wait()
        finally:
            self._task = None

    async def close(self) -> None:
        self._closed = True
        task = self._task
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
