from __future__ import annotations

import asyncio
import inspect
import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from server.app.models.library import ScanBatch, ScanResult
from server.app.models.library_scan import PreparedScan, ScanBaseline
from server.app.repositories.database import (
    on_transaction_commit,
    on_transaction_rollback,
    run_transaction,
    transaction_identity,
)
from server.app.repositories.library_repository import LibraryRepository

from . import library_scan_prepare as media
from .events import EventPublisher, LibraryChangedEvent, MPDDatabaseUpdater
from .library_scan_prepare import LibraryScanError
from .library_service import LibraryService
from .media_metadata import MediaMetadataError
from .realtime_coordinator import RealtimeCoordinator


class LibraryScanConflict(LibraryScanError):
    """Prepared facts refer to an obsolete committed Library baseline."""


def _outer(path: str):
    try:
        return transaction_identity(path)
    except RuntimeError:
        return None


class LibraryScanner:
    def __init__(
        self,
        repository: LibraryRepository,
        event_publisher: EventPublisher | None = None,
        mpd_updater: MPDDatabaseUpdater | None = None,
        *,
        coordinator: RealtimeCoordinator | None = None,
        batch_observer: Callable[[ScanBatch, ScanResult], None] | None = None,
    ) -> None:
        self.repository = repository
        self.event_publisher = event_publisher
        self.mpd_updater = mpd_updater
        self.coordinator = coordinator
        self.batch_observer = batch_observer
        self._library_service = LibraryService(repository)

        self._validated_outers: dict[object, str] = {}

    async def _worker(self, callback, *args, **kwargs):
        cancelled = threading.Event()
        task = asyncio.create_task(
            asyncio.to_thread(callback, *args, cancelled=cancelled, **kwargs)
        )
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled.set()
            await asyncio.gather(task, return_exceptions=True)
            raise

    async def prepare(
        self,
        root: Path,
        paths: tuple[Path, ...] | None = None,
        *,
        deep: bool = False,
        identity: tuple[int, int] | None = None,
    ) -> PreparedScan:
        if _outer(self.repository.path) is not None:
            raise LibraryScanError("prepare must run outside an outer transaction")
        baseline = await self.repository.read_scan_baseline()
        return await self._worker(
            media.prepare_scan, root, baseline, paths, deep=deep, identity=identity
        )

    async def precheck(self, prepared: PreparedScan) -> PreparedScan:
        if _outer(self.repository.path) is not None:
            raise LibraryScanError("precheck must run outside an outer transaction")
        return await self._worker(media.validate_prepared, prepared)

    async def commit(
        self,
        prepared: PreparedScan,
        *,
        stage_sync: Callable[[ScanResult], None] | None = None,
        finalize: bool = True,
    ) -> ScanResult:
        if stage_sync is not None and inspect.iscoroutinefunction(stage_sync):
            raise TypeError("stage_sync must be synchronous")
        outer = _outer(self.repository.path)
        if outer is None:
            prepared = await self.precheck(prepared)
        elif not prepared.checked:
            raise LibraryScanError("outer commit requires a prechecked prepared scan")

        async def operation(_):
            owner = transaction_identity(self.repository.path)
            original = self._validated_outers.get(owner)
            if original is None:
                baseline = await self.repository.read_scan_baseline()
                if baseline.fingerprint != prepared.baseline.fingerprint:
                    raise LibraryScanConflict("Library baseline changed before commit")
                self._validated_outers[owner] = baseline.fingerprint
                cleanup = lambda: self._validated_outers.pop(owner, None)
                on_transaction_commit(self.repository.path, cleanup)
                on_transaction_rollback(self.repository.path, cleanup)
            elif original != prepared.baseline.fingerprint:
                raise LibraryScanConflict(
                    "prepared scan does not share outer original baseline"
                )
            result = await self._apply_batch(prepared.batch, finalize=finalize)
            if stage_sync is not None:
                staged = stage_sync(result)
                if inspect.isawaitable(staged):
                    if inspect.iscoroutine(staged):
                        staged.close()
                    raise TypeError("stage_sync must be synchronous")
            return result

        return await run_transaction(self.repository.path, operation)

    async def _finalize(
        self, result: ScanResult, *, update: bool = True, mpd_update_error: str | None = None,
    ) -> ScanResult:
        if update and self.mpd_updater is not None:
            try:
                await self.mpd_updater.update_database()
            except Exception as exc:  # noqa: BLE001
                mpd_update_error = str(exc)
        if self.event_publisher is not None:
            await self.event_publisher.publish(
                LibraryChangedEvent(
                    result=result,
                    mpd_update_error=mpd_update_error,
                )
            )
        return result

    async def _apply_batch(self, batch: ScanBatch, *, finalize: bool = True) -> ScanResult:
        async def operation(_):
            before = (
                await self._library_service.revision_content()
                if self.coordinator is not None
                else None
            )
            result = await self.repository.apply_scan_batch(batch)
            if self.batch_observer is not None:
                self.batch_observer(batch, result)
            if self.coordinator is not None:
                self.coordinator.stage_change(
                    frozenset({"library"}),
                    before,
                    await self._library_service.revision_content(),
                )
            if finalize:
                on_transaction_commit(
                    self.repository.path,
                    lambda: self._finalize(result),
                )
            return result

        return await run_transaction(self.repository.path, operation)

    async def _scan(
        self, root: Path, paths: tuple[Path, ...] | None, *, deep=False
    ) -> ScanResult:
        prepared = await self.prepare(root, paths, deep=deep)
        for attempt in range(3):
            try:
                if (
                    prepared.metadata_failed
                    and not prepared.batch.songs
                    and not prepared.batch.observed_file_uris
                    and not any(
                        s.file_uri in prepared.batch.unreadable_file_uris
                        for s in prepared.baseline.songs
                    )
                ):
                    raise MediaMetadataError(
                        "required song title is missing or unreadable media"
                    )
                result = await self.commit(prepared)
                if prepared.metadata_failed and not prepared.batch.songs:
                    raise MediaMetadataError("scan contains unreadable media")
                return result
            except LibraryScanConflict:
                if attempt == 2:
                    raise
                prepared = await self.rebase(prepared, root, deep=deep)
        raise AssertionError("unreachable")

    async def rebase(
        self, prepared: PreparedScan, root: Path, *, deep=False, paths: tuple[Path, ...] | None = None,
    ) -> PreparedScan:
        # Reuse successful media whose DB facts are still the same;
        # only conflict paths are reparsed under a fresh baseline.
        baseline = await self.repository.read_scan_baseline()
        old = {s.file_uri: s for s in prepared.baseline.songs}
        new = {s.file_uri: s for s in baseline.songs}
        old_sidecars = dict(prepared.baseline.sidecars)
        new_sidecars = dict(baseline.sidecars)

        def facts(song):
            return (
                song.model_dump(exclude={"last_seen_at", "last_scanned_at"})
                if song
                else None
            )

        old_sources = dict(prepared.baseline.artwork_sources)
        new_sources = dict(baseline.artwork_sources)
        changed_albums = {
            album_id
            for album_id in old_sources.keys() | new_sources.keys()
            if old_sources.get(album_id) != new_sources.get(album_id)
        }
        conflicts = tuple(
            Path(uri)
            for uri in old.keys() | new.keys()
            if facts(old.get(uri)) != facts(new.get(uri))
            or (old.get(uri) and old[uri].album_id in changed_albums)
            or (new.get(uri) and new[uri].album_id in changed_albums)
            or old_sidecars.get(old[uri].song_id if uri in old else None)
            != new_sidecars.get(new[uri].song_id if uri in new else None)
        )
        # Use successful detached facts as a comparison cache, never as the
        # database commit baseline. A fresh inventory must compare against the
        # signatures that produced those cached facts, not silently bless old
        # metadata with newer filesystem signatures.
        changed = set(map(str, conflicts))
        cached = {song.file_uri: song for song in prepared.batch.songs
                  if song.file_uri not in changed}
        projected_songs = {song.song_id: song for song in baseline.songs}
        projected_songs.update({song.song_id: song for song in cached.values()})
        projected_sidecars = dict(baseline.sidecars)
        ids = {song.file_uri: song.song_id for song in projected_songs.values()}
        for uri, signature in prepared.batch.sidecar_signatures.items():
            if uri not in changed and uri in ids:
                projected_sidecars[ids[uri]] = signature
        projected = ScanBaseline(tuple(projected_songs.values()), tuple(projected_sidecars.items()),
                                 baseline.fingerprint, baseline.artwork_sources)
        fresh = await self._worker(
            media.prepare_scan, root, projected, None, deep=False,
            identity=prepared.inventory.identity,
        )
        # Manual/deep work still forces conflict or newly requested paths whose
        # stat did not change. Already parsed facts and stable cached successes
        # must not be hashed twice.
        requested = set()
        for entry in fresh.inventory.entries:
            path = Path(entry.file_uri)
            if path.suffix.casefold() not in {".flac", ".mp3"}:
                continue
            if paths is None or any(path == target or path.is_relative_to(target)
                                    or path.with_suffix(".lrc") == target for target in paths):
                requested.add(path)
        forced = set(conflicts) | requested
        parsed = {song.file_uri for song in fresh.batch.songs}
        present = {entry.file_uri for entry in fresh.inventory.entries}
        forced = tuple(path for path in forced if str(path) in present
                       and str(path) not in parsed and str(path) not in cached)
        if deep and forced:
            extra = await self._worker(media.prepare_scan, root, projected, forced,
                                       deep=True, identity=prepared.inventory.identity)
            fresh = replace(fresh, batch=fresh.batch.model_copy(update={
                "songs": fresh.batch.songs + extra.batch.songs,
                "sidecar_signatures": {**fresh.batch.sidecar_signatures, **extra.batch.sidecar_signatures},
                "unreadable_file_uris": tuple(set(fresh.batch.unreadable_file_uris) | set(extra.batch.unreadable_file_uris)),
            }))
        failed = set(fresh.batch.unreadable_file_uris)
        present = {entry.file_uri for entry in fresh.inventory.entries}
        songs = {uri: song for uri, song in cached.items() if uri in present and uri not in failed}
        songs.update({song.file_uri: song for song in fresh.batch.songs})
        deltas = {uri: value for uri, value in prepared.batch.sidecar_signatures.items()
                  if uri not in changed and uri in present and uri not in failed}
        deltas.update(fresh.batch.sidecar_signatures)
        batch = fresh.batch.model_copy(update={
            "songs": tuple(songs.values()),
            "observed_file_uris": tuple(uri for uri in fresh.batch.observed_file_uris if uri not in songs),
            "sidecar_signatures": deltas,
        })
        return replace(fresh, baseline=baseline, batch=batch,
                       audio_index_changed=media._audio_changed(batch, baseline),
                       failed_paths=tuple(Path(uri) for uri in batch.unreadable_file_uris),
                       metadata_failed=prepared.metadata_failed or fresh.metadata_failed)

    async def scan_full(self, root: Path) -> ScanResult:
        return await self._scan(root, None)

    async def scan_paths(self, paths: list[Path]) -> ScanResult:
        if _outer(self.repository.path) is not None:
            raise LibraryScanError("prepare must run outside an outer transaction")
        if not paths:
            return await self._apply_batch(ScanBatch())

        # Root inference is filesystem work too: do it in a worker.
        def common_root():
            import os

            roots = [p if p.is_dir() else p.parent for p in paths]
            return Path(os.path.commonpath(roots))

        root = await asyncio.to_thread(common_root)
        return await self._scan(root, tuple(paths))
