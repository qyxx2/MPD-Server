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
from server.app.player.ports import PlayerCommandError, PlayerPort
from server.app.repositories.database import (
    on_transaction_commit,
    on_transaction_visible,
    run_transaction,
)
from server.app.services.events import EventPublisher, LibrarySyncChangedEvent
from server.app.services.library_scanner import LibraryScanConflict, LibraryScanner


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
        self.root = root.absolute()
        self._root_identity: tuple[int, int] | None = None
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
        self._update_unknown = False
        self._audio_update_required = False
        self._failed_paths: tuple[Path, ...] = ()
        self._conflicted = None
        self._pending_results = []
        self.startup_inventory = None
        self.startup_ready = asyncio.Event()
        self._targets: dict[str, bool] = {}
        self._unconfirmed_targets: dict[str, bool] = {}
        self._scan_incomplete = False
        self._observed_batch = None
        self._deep_prepared_activity: str | None = None
        scanner.mpd_updater = self
        scanner.batch_observer = self._observe_batch

    def _observe_batch(self, batch, result) -> None:
        self._observed_batch = batch

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
            paths = await asyncio.to_thread(lambda: tuple(path.resolve() for path in paths))
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
        if self._closed:
            raise asyncio.CancelledError()
        remaining = self._deadline - self._clock()
        if remaining <= 0:
            raise TimeoutError()
        return await asyncio.wait_for(callback(), timeout=remaining)

    async def update_database(self) -> None:
        # Compatibility for scanner wrappers; the owner confirms after its
        # short commit and suppresses the wrapper's automatic finalization.
        if self._closed:
            raise RuntimeError("library sync is closed")
        await self._confirm()

    async def _issue_update(self) -> None:
        try:
            await self._bounded(self.player.update_database)
        except PlayerCommandError:
            # An explicit rejection is the only failure allowing a blind
            # command retry, still preceded by fresh status/URI reads.
            self._update_unknown = False
            raise
        except Exception:
            self._update_unknown = True
            raise
        self._update_accepted = True
        self._update_unknown = False
        self._audio_update_required = False
        await self._complete_scans()

    async def _complete_scans(self, error: str | None = None) -> None:
        while self._pending_results and not self._closed:
            result = self._pending_results.pop(0)
            await self.scanner._finalize(result, update=False, mpd_update_error=error)

    async def _scan(self, job: _ScanJob) -> None:
        self._scan_incomplete = False
        log_event('library_scan_started', generation=self._state.generation)
        deep = job.trigger in {"deep", "scheduled", "manual"} and self._deep_prepared_activity != job.activity_id
        if self._conflicted is None:
            prepared = await self.scanner.prepare(
                self.root, job.paths, identity=self._root_identity, deep=deep,
            )
        else:
            prepared = await self.scanner.rebase(self._conflicted, self.root, deep=deep, paths=job.paths)
        if self._root_identity is None:
            self._root_identity = prepared.inventory.identity
            self.root = prepared.inventory.root
        before = prepared.baseline.songs

        def stage_sync(result):
            after = {song.song_id: song for song in before}
            accepted_ids = set(result.added_song_ids + result.updated_song_ids)
            after.update({song.song_id: song for song in prepared.batch.songs
                          if song.song_id in accepted_ids})
            for song_id in result.missing_song_ids:
                after[song_id] = after[song_id].model_copy(update={"availability_status": "MISSING"})
            for song_id in result.unreadable_song_ids:
                if song_id in after:
                    after[song_id] = after[song_id].model_copy(update={"availability_status": "UNREADABLE"})
            changed_ids = set(result.added_song_ids + result.updated_song_ids + result.moved_song_ids)
            prior = {song.song_id: song for song in before}

            def audio_facts(song):
                return (song.file_uri, song.file_size, song.file_mtime_ns,
                        song.content_hash, song.availability_status) if song else None

            audio_changed = any(audio_facts(prior.get(song_id)) != audio_facts(song)
                                for song_id, song in after.items())
            changed_ids.update(song_id for song_id in result.missing_song_ids + result.unreadable_song_ids
                               if audio_facts(prior.get(song_id)) != audio_facts(after.get(song_id)))
            requested = set(map(str, job.paths or ()))
            available_uris = {song.file_uri for song in after.values()
                              if song.availability_status == "AVAILABLE"}
            targets = {
                **self._unconfirmed_targets,
                **{song.file_uri: False for song in before
                   if song.song_id in changed_ids and song.file_uri not in available_uris},
            }
            for song in after.values():
                relevant = (job.paths is None or song.song_id in changed_ids
                            or song.file_uri in requested
                            or any(Path(song.file_uri).is_relative_to(p) for p in job.paths or ())
                            or str(Path(song.file_uri).with_suffix(".lrc")) in requested)
                if relevant and Path(song.file_uri).is_relative_to(self.root):
                    if song.availability_status == "AVAILABLE":
                        targets[song.file_uri] = True
                    elif song.availability_status == "MISSING":
                        targets[song.file_uri] = False
            state = self._state.model_copy(update={
                "status": "SYNCING", "pending_count": len(targets),
                "confirmed_count": 0, "failed_count": 0, "error_code": None,
                "reason": None, "updated_at": datetime.now(timezone.utc),
            })
            if self.scanner.coordinator is not None:
                self.scanner.coordinator.stage_library_sync(state)

            def visible():
                self._failed_paths = tuple(Path(uri) for uri in self._observed_batch.unreadable_file_uris)
                self._scan_incomplete = bool(self._failed_paths)
                self._targets = targets
                self._unconfirmed_targets = dict(targets)
                self._state = state
                if audio_changed:
                    self._audio_update_required = True
                    self._update_accepted = False
                    self._update_unknown = False

            on_transaction_visible(self.scanner.repository.path, visible)

        prepared = await self.scanner.precheck(prepared)
        if self._closed:
            raise asyncio.CancelledError()
        try:
            result = await self.scanner.commit(prepared, stage_sync=stage_sync, finalize=False)
        except LibraryScanConflict:
            self._conflicted = prepared
            raise
        self._conflicted = None
        self._pending_results.append(result)
        if self.startup_inventory is None:
            # Path retries don't process every newly inventoried file. Keep
            # the initial safe snapshot so detection still discovers those
            # files after startup, instead of accepting uncommitted additions.
            self.startup_inventory = prepared.inventory
        # A deep pass is once per job, including a partially successful commit.
        # Persisted signatures keep successful paths out of subsequent retries.
        self._deep_prepared_activity = job.activity_id
        if self._scan_incomplete:
            raise OSError("scan contains unreadable media")

    async def _confirm(self) -> None:
        self._deadline = self._clock() + self.confirmation_seconds
        while True:
            updating = await self._bounded(self.player.database_update_status)
            if type(updating.updating) is not bool:
                raise RuntimeError("unknown MPD update status")
            confirmed = 0
            for uri, expected in self._targets.items():
                found = await self._bounded(lambda uri=uri: self.player.has_library_uri(uri))
                if type(found) is not bool:
                    raise RuntimeError("unknown MPD URI confirmation")
                confirmed += found == expected
            consistent = confirmed == len(self._targets)
            if not updating.updating:
                if consistent and (not self._audio_update_required or self._update_accepted or self._update_unknown):
                    await self._complete_scans()
                    self._unconfirmed_targets.clear()
                    self._audio_update_required = False
                    self._update_unknown = False
                    self._update_accepted = False
                    self._set(status="SYNCED", confirmed_count=confirmed, pending_count=0,
                              failed_count=0, error_code=None, reason=None)
                    await self._notify()
                    if not self.startup_ready.is_set() and self.startup_inventory is not None:
                        self.startup_ready.set()
                    return
                if not self._update_accepted and (not self._update_unknown or not consistent):
                    # Complete precheck evidence, then one update, then a fresh
                    # status and exact URI postcheck. Reads failing above never
                    # reach this command.
                    await self._issue_update()
                    continue
            self._set(confirmed_count=confirmed if not updating.updating else 0,
                      pending_count=len(self._targets) - (confirmed if not updating.updating else 0))
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
                        if job.paths is None or (carry.paths is None and not self._failed_paths and self._conflicted is None)
                        else tuple(sorted(set(self._failed_paths or carry.paths or ()) | set(job.paths)))
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
                    self._log_phase()
                    scanned = False
                    attempt = 0
                    while not self._closed:
                        try:
                            if not scanned:
                                await self._scan(job)
                                scanned = True
                            else:
                                self._set(status="SYNCING", error_code=None, reason=None)
                                self._log_phase()
                            await self._confirm()
                            break
                        except Exception as exc:  # noqa: BLE001 - background failures remain retryable
                            await self._complete_scans(str(exc))
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
                            if self._failed_paths and self._conflicted is None:
                                job = replace(job, paths=self._failed_paths)
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
