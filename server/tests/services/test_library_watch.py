from __future__ import annotations

import asyncio
from pathlib import Path

from server.app.models.library import ScanResult


def _run(coro):
    return asyncio.run(coro)


def test_step8_default_debounce_is_500ms():
    from server.app.services.library_watch import LibraryWatch

    watch = LibraryWatch(lambda _paths: asyncio.sleep(0))
    assert watch.debounce_seconds == 0.5


def test_step8_debounces_events_and_scans_one_deduplicated_batch():
    from server.app.services.library_watch import LibraryWatch

    calls: list[list[Path]] = []

    async def scan_paths(paths: list[Path]) -> ScanResult:
        calls.append(paths)
        return ScanResult()

    async def scenario():
        watch = LibraryWatch(scan_paths, debounce_seconds=0.02)
        await watch.notify(Path("/music/a.mp3"))
        await watch.notify(Path("/music/a.mp3"))
        await watch.notify(Path("/music/b.mp3"))
        await asyncio.sleep(0.05)
        await watch.close()

    _run(scenario())
    assert calls == [[Path("/music/a.mp3"), Path("/music/b.mp3")]]
