from __future__ import annotations

import asyncio

from server.app.models.library import ScanResult


def _run(coro):
    return asyncio.run(coro)


def test_step9_default_interval_is_12_hours():
    from server.app.services.library_scheduler import LibraryScheduler

    scheduler = LibraryScheduler(lambda: asyncio.sleep(0))
    assert scheduler.interval_seconds == 12 * 60 * 60


def test_step9_runs_full_scan_and_uses_injected_interval_without_config_import():
    from server.app.services.library_scheduler import LibraryScheduler

    scans = 0
    sleeps: list[float] = []

    async def scan_full() -> ScanResult:
        nonlocal scans
        scans += 1
        return ScanResult()

    async def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        scheduler.stop()

    scheduler = LibraryScheduler(
        scan_full,
        interval_seconds=123,
        sleep=sleeper,
    )
    _run(scheduler.run_forever())

    assert scans == 1
    assert sleeps == [123]
