from __future__ import annotations

import asyncio
import stat as stat_mode
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

RequestScan = Callable[[tuple[Path, ...] | None, str], Awaitable[str]]


def read_signatures(
    root: Path, identity: tuple[int, int]
) -> dict[Path, tuple[int, int]]:
    """Read metadata only; incomplete/replaced mounts are never deletion evidence."""
    stat = root.stat()
    if (stat.st_dev, stat.st_ino) != identity or not root.is_dir():
        raise OSError("music root unavailable or replaced")
    signatures = {}
    stack = [root]
    while stack:
        for entry in stack.pop().iterdir():
            stat = entry.stat(follow_symlinks=False)
            if stat_mode.S_ISLNK(stat.st_mode):
                continue
            if stat_mode.S_ISDIR(stat.st_mode):
                stack.append(entry)
            elif stat_mode.S_ISREG(stat.st_mode) and entry.suffix.casefold() in {
                ".flac",
                ".mp3",
                ".lrc",
            }:
                signatures[entry] = (stat.st_size, stat.st_mtime_ns)
    stat = root.stat()
    if (stat.st_dev, stat.st_ino) != identity:
        raise OSError("music root changed during detection")
    return signatures


class LibraryChangeDetector:
    def __init__(
        self,
        root: Path,
        request_scan: RequestScan,
        *,
        interval_seconds: float = 2,
        debounce_seconds: float = 0.5,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if interval_seconds <= 0 or debounce_seconds < 0:
            raise ValueError("invalid detector timing")
        self.root = root.resolve()
        stat = self.root.stat()
        self.identity = (stat.st_dev, stat.st_ino)
        self.request_scan = request_scan
        self.interval_seconds = interval_seconds
        self.debounce_seconds = debounce_seconds
        self._clock, self._sleep = clock, sleep
        try:
            self._observed = read_signatures(self.root, self.identity)
        except OSError:
            self._observed = {}
        # Startup reconciliation owns files already present at composition.
        self._accepted = dict(self._observed)
        self._changed_at: dict[Path, float] = {}
        self._closed = False

    async def check_once(self) -> None:
        try:
            current = await asyncio.to_thread(read_signatures, self.root, self.identity)
        except OSError:
            return
        now = self._clock()
        for path in self._observed.keys() | current.keys():
            if self._observed.get(path) != current.get(path):
                self._changed_at[path] = now
        self._observed = current
        changed = {
            path
            for path in self._accepted.keys() | current.keys()
            if self._accepted.get(path) != current.get(path)
        }
        stable = {
            path
            for path in changed
            if now - self._changed_at.get(path, now) >= self.debounce_seconds
        }
        # A deletion full reconciliation waits for every changed entry to settle.
        deleted = stable - current.keys()
        if deleted and stable != changed:
            return
        if stable:
            await self.request_scan(
                None if deleted else tuple(sorted(stable)), "automatic"
            )
            for path in stable:
                if path in current:
                    self._accepted[path] = current[path]
                else:
                    self._accepted.pop(path, None)
                self._changed_at.pop(path, None)

    async def run(self) -> None:
        while not self._closed:
            await self.check_once()
            await self._sleep(self.interval_seconds)

    async def close(self) -> None:
        self._closed = True
