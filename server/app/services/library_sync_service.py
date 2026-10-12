from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from server.app.logging_config import log_context, log_event
from server.app.models.library_sync import LibrarySyncState
from server.app.player.ports import PlayerPort
from server.app.repositories.database import (
    on_transaction_commit,
    on_transaction_visible,
    run_transaction,
)
from server.app.services.events import EventPublisher, LibrarySyncChangedEvent
from server.app.services.library_change_detector import read_signatures
from server.app.services.library_scanner import LibraryScanError, LibraryScanner


@dataclass(frozen=True)
class _ScanJob:
    activity_id: str
    paths: tuple[Path, ...] | None
    trigger: str


class LibrarySyncService:
    """One scanner/update/confirmation owner; never owns a playback mutation."""

    def __init__(
        self,
        scanner: LibraryScanner,
        player: PlayerPort,
        root: Path,
        *,
        confirmation_seconds: float = 60,
        poll_seconds: float = 1,
        retry_seconds: tuple[float, ...] = (2, 5, 15, 30),
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        if (
            confirmation_seconds <= 0
            or poll_seconds <= 0
            or not retry_seconds
            or min(retry_seconds) <= 0
        ):
            raise ValueError("invalid sync timing")
        self.scanner, self.player = scanner, player
        self.root = root.resolve()
        stat = self.root.stat()
        self._root_identity = (stat.st_dev, stat.st_ino)
        self.confirmation_seconds, self.poll_seconds = (
            confirmation_seconds,
            poll_seconds,
        )
        self.retry_seconds = retry_seconds
        self._clock, self._sleep = clock, sleep
        self.event_publisher = event_publisher
        self._state = LibrarySyncState()
        self._logged_phase = None
        self._jobs: asyncio.Queue[_ScanJob] = asyncio.Queue()
        self._wake = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._closed = False
        self._deadline = 0.0
        self._update_accepted = False
        self._update_error: Exception | None = None
        self._targets: dict[str, bool] = {}
        self._unconfirmed_targets: dict[str, bool] = {}
        self._scan_incomplete = False
        scanner.mpd_updater = self
        scanner.batch_observer = self._observe_batch

    def _observe_batch(self, batch, result) -> None:
        self._scan_incomplete = bool(batch.unreadable_file_uris)

    def get_state(self) -> LibrarySyncState:
        return self._state.model_copy(deep=True)

    def _set(self, **values) -> None:
        self._state = self._state.model_copy(
            update={**values, "updated_at": datetime.now(timezone.utc)}
        )

    def _log_phase(self) -> None:
        state = self._state
        phase = (state.generation, state.status, state.pending_count,
                 state.confirmed_count, state.failed_count, state.error_code)
        if phase != self._logged_phase:
            log_event('library_sync_phase', generation=state.generation,
                      status=state.status, pending_count=state.pending_count,
                      confirmed_count=state.confirmed_count, failed_count=state.failed_count,
                      error_code=state.error_code)
            self._logged_phase = phase

    async def _notify(self) -> None:
        self._log_phase()
        if self.event_publisher is not None:
            await self.event_publisher.publish(
                LibrarySyncChangedEvent(state=self.get_state())
            )

    async def request_scan(self, paths: tuple[Path, ...] | None, trigger: str) -> str:
        if self._closed:
            raise RuntimeError("library sync is closed")
        if paths is not None:
            paths = tuple(path.resolve() for path in paths)
            if any(not path.is_relative_to(self.root) for path in paths):
                raise ValueError("scan path is outside the configured music root")
        job = _ScanJob(uuid4().hex, paths, trigger)

        def accept(_):
            def enqueue():
                self._jobs.put_nowait(job)
                self._wake.set()

            on_transaction_commit(self.scanner.repository.path, enqueue)

        await run_transaction(self.scanner.repository.path, accept)
        return job.activity_id

    async def _bounded(self, callback):
        remaining = self._deadline - self._clock()
        if remaining <= 0:
            raise TimeoutError()
        return await asyncio.wait_for(callback(), timeout=remaining)

    async def update_database(self) -> None:
        self._deadline = self._clock() + self.confirmation_seconds
        self._update_accepted = False
        self._update_error = None
        try:
            await self._notify()
            await self._bounded(self.player.update_database)
            self._update_accepted = True
        except Exception as exc:
            self._update_error = exc
            raise

    async def _scan(self, job: _ScanJob) -> None:
        self._scan_incomplete = False
        log_event('library_scan_started', generation=self._state.generation)
        # Do not reconcile an incomplete/replaced mount as an empty library.
        await asyncio.to_thread(read_signatures, self.root, self._root_identity)

        # A vanished media path needs reconciliation; an unavailable requested
        # root is a scan failure, never an empty successful incremental batch.
        missing_media = False
        for path in job.paths or ():
            if not path.is_dir() and path.suffix.casefold() not in {
                ".flac",
                ".mp3",
                ".lrc",
            }:
                raise LibraryScanError("requested scan root is unavailable")
            missing_media |= not path.exists()

        async def operation(_):
            before = await self.scanner.repository.list_songs()
            if job.paths is None or missing_media:
                result = await self.scanner.scan_full(self.root)
            elif len(job.paths) == 1 and job.paths[0].is_dir():
                result = await self.scanner.scan_full(
                    self.root if job.paths is None else job.paths[0]
                )
            else:
                result = await self.scanner.scan_paths(list(job.paths))
            # Recheck mount completeness before allowing the outer commit.
            read_signatures(self.root, self._root_identity)
            after = await self.scanner.repository.list_songs()
            changed_ids = set(
                result.added_song_ids
                + result.updated_song_ids
                + result.moved_song_ids
                + result.missing_song_ids
            )
            requested = set(map(str, job.paths or ()))
            available_uris = {
                song.file_uri
                for song in after
                if song.availability_status == "AVAILABLE"
            }
            # Keep old deletion/move expectations until they are proven. New
            # committed facts below supersede expectations for the same URI.
            self._targets = {
                **self._unconfirmed_targets,
                **{
                    song.file_uri: False
                    for song in before
                    if song.song_id in changed_ids
                    and song.file_uri not in available_uris
                },
            }
            for song in after:
                relevant = (
                    job.paths is None
                    or song.song_id in changed_ids
                    or song.file_uri in requested
                    or any(
                        Path(song.file_uri).is_relative_to(p)
                        for p in job.paths or ()
                        if p.is_dir()
                    )
                    or str(Path(song.file_uri).with_suffix(".lrc")) in requested
                )
                if relevant and Path(song.file_uri).is_relative_to(self.root):
                    if song.availability_status == "AVAILABLE":
                        self._targets[song.file_uri] = True
                    elif song.availability_status == "MISSING":
                        self._targets[song.file_uri] = False

            state = self._state.model_copy(update={
                "status": "SYNCING", "pending_count": len(self._targets),
                "confirmed_count": 0, "failed_count": 0,
                "error_code": None, "reason": None,
                "updated_at": datetime.now(timezone.utc),
            })
            if self.scanner.coordinator is not None:
                self.scanner.coordinator.stage_library_sync(state)
            on_transaction_visible(
                self.scanner.repository.path, lambda: setattr(self, "_state", state),
            )

        await run_transaction(self.scanner.repository.path, operation)
        if self._scan_incomplete:
            raise OSError("scan contains unreadable media")

    async def _confirm(self) -> None:
        if not self._update_accepted:
            raise self._update_error or RuntimeError("update not accepted")
        while True:
            updating = await self._bounded(self.player.database_update_status)
            confirmed = 0
            if not updating.updating:
                for uri, expected in self._targets.items():
                    found = await self._bounded(
                        lambda uri=uri: self.player.has_library_uri(uri)
                    )
                    confirmed += found == expected
            self._set(
                confirmed_count=confirmed, pending_count=len(self._targets) - confirmed
            )
            if not updating.updating and confirmed == len(self._targets):
                self._unconfirmed_targets.clear()
                self._set(status="SYNCED", failed_count=0, error_code=None, reason=None)
                await self._notify()
                return
            await self._notify()
            remaining = self._deadline - self._clock()
            if remaining <= 0:
                raise TimeoutError()
            await self._sleep(min(self.poll_seconds, remaining))

    async def _retry_wait(self, delay: float) -> None:
        self._wake.clear()
        if not self._jobs.empty():
            return
        timer = asyncio.create_task(self._sleep(delay))
        changed = asyncio.create_task(self._wake.wait())
        try:
            await asyncio.wait({timer, changed}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            timer.cancel()
            changed.cancel()
            await asyncio.gather(timer, changed, return_exceptions=True)

    async def run(self) -> None:
        if self._task is not None:
            raise RuntimeError("library sync owner already running")
        self._task = asyncio.current_task()
        carry: _ScanJob | None = None
        try:
            while not self._closed:
                job = await self._jobs.get()
                if carry is not None:
                    paths = (
                        None
                        if carry.paths is None or job.paths is None
                        else tuple(sorted(set(carry.paths) | set(job.paths)))
                    )
                    job = replace(job, paths=paths)
                    carry = None
                self._set(
                    generation=self._state.generation + 1,
                    activity_id=job.activity_id,
                    trigger=job.trigger,
                    status="SYNCING",
                    pending_count=0,
                    confirmed_count=0,
                    failed_count=0,
                    error_code=None,
                    reason=None,
                )
                with log_context(generation=self._state.generation):
                    scanned = False
                    attempt = 0
                    while not self._closed:
                        try:
                            if not scanned:
                                await self._scan(job)
                                scanned = True
                            else:
                                self._set(status="SYNCING", error_code=None, reason=None)
                                await self.update_database()
                            await self._confirm()
                            break
                        except Exception as exc:  # noqa: BLE001 - background failures remain retryable
                            self._set(
                                status="FAILED",
                                failed_count=max(
                                    1, len(self._targets) - self._state.confirmed_count
                                ),
                                error_code="MPD_SYNC_TIMEOUT"
                                if isinstance(exc, TimeoutError)
                                else "LIBRARY_SYNC_FAILED",
                                reason="Library synchronization could not be confirmed",
                            )
                            await self._notify()
                            log_event('library_sync_retry', generation=self._state.generation,
                                      attempt=attempt + 1)
                            await self._retry_wait(
                                self.retry_seconds[
                                    min(attempt, len(self.retry_seconds) - 1)
                                ]
                            )
                            attempt += 1
                            if not self._jobs.empty():
                                carry = job
                                self._unconfirmed_targets = dict(self._targets)
                                break
        except asyncio.CancelledError:
            if self._state.status == "SYNCING":
                self._set(
                    status="FAILED",
                    error_code="LIBRARY_SYNC_CANCELLED",
                    reason="Synchronization stopped",
                )
                self._log_phase()
            if not self._closed:
                raise
        finally:
            self._task = None

    async def close(self) -> None:
        self._closed = True
        if self._task is not None and self._task is not asyncio.current_task():
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
