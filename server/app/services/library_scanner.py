from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable
from pathlib import Path

from server.app.models.library import ScanBatch, ScanResult, Song
from server.app.repositories.database import on_transaction_commit, run_transaction
from server.app.repositories.library_repository import LibraryRepository

from .events import EventPublisher, LibraryChangedEvent, MPDDatabaseUpdater
from .library_service import LibraryService
from .media_metadata import MediaMetadataError, ParsedSongMetadata, parse_media_file
from .realtime_coordinator import RealtimeCoordinator

_SUPPORTED_SUFFIXES = {".flac", ".mp3"}
_HASH_CHUNK_SIZE = 1024 * 1024


class LibraryScanError(Exception):
    """Raised when a library root cannot be scanned safely."""


def _root_prefix(root: Path) -> str:
    return str(root.resolve()).rstrip("/") + "/"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _associated_audio_paths(path: Path) -> tuple[Path, ...]:
    try:
        entries = path.parent.iterdir()
    except OSError:
        return ()

    matches: list[Path] = []
    for entry in entries:
        try:
            if (
                entry.is_file(follow_symlinks=False)
                and entry.suffix.casefold() in _SUPPORTED_SUFFIXES
                and entry.stem == path.stem
            ):
                matches.append(entry)
        except OSError:
            continue

    return tuple(sorted(matches, key=str))


def _identity_key(metadata: ParsedSongMetadata) -> str:
    if metadata.title is None or not metadata.title.strip():
        raise MediaMetadataError("required song title is missing")
    value = {
        "title": metadata.title.strip().casefold(),
        "artists": sorted(value.casefold() for value in metadata.artists),
        "album": metadata.album.strip().casefold() if metadata.album else None,
        "album_artists": sorted(
            value.casefold() for value in metadata.album_artists
        ),
        "track_number": metadata.track_number,
        "disc_number": metadata.disc_number,
        "year": metadata.year,
        "date": metadata.date,
    }
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(
        f"identity-v1:{payload}".encode()
    ).hexdigest()


def _walk(root: Path) -> tuple[list[Path], bool]:
    files: list[Path] = []
    complete = True
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = list(directory.iterdir())
        except OSError:
            complete = False
            continue
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry)
                elif (
                    entry.is_file(follow_symlinks=False)
                    and entry.suffix.casefold() in _SUPPORTED_SUFFIXES
                ):
                    files.append(entry)
            except OSError:
                complete = False
    files.sort(key=lambda value: str(value.resolve()))
    return files, complete


class LibraryScanner:
    def __init__(
        self,
        repository: LibraryRepository,
        event_publisher: EventPublisher | None = None,
        mpd_updater: MPDDatabaseUpdater | None = None,
        *,
        coordinator: RealtimeCoordinator | None = None,
    ) -> None:
        self.repository = repository
        self.event_publisher = event_publisher
        self.mpd_updater = mpd_updater
        self.coordinator = coordinator
        self._library_service = LibraryService(repository)

    async def _match_song_id(
        self,
        path: Path,
        identity_key: str,
        content_hash: str,
    ) -> str | None:
        exact = await self.repository.find_song_by_file_uri(str(path))
        if exact is not None:
            return exact.song_id

        identity_candidates = [
            candidate
            for candidate in await self.repository.find_song_candidates_by_identity(
                identity_key
            )
            if candidate.song_id is not None
        ]
        if len(identity_candidates) == 1:
            candidate = identity_candidates[0]
            if candidate.file_uri != str(path):
                try:
                    Path(candidate.file_uri).stat()
                    old_exists = True
                except FileNotFoundError:
                    old_exists = False
                except OSError:
                    old_exists = True
                if not old_exists:
                    return candidate.song_id

        content_candidates = [
            candidate
            for candidate in await self.repository.find_song_candidates_by_content_hash(
                content_hash
            )
            if (
                candidate.song_id is not None
                and candidate.availability_status == "MISSING"
            )
        ]
        if len(content_candidates) == 1:
            return content_candidates[0].song_id
        return None

    async def _scan_files(self, paths: Iterable[Path]) -> ScanBatch:
        songs: list[Song] = []
        unreadable: list[str] = []
        reserved_ids: set[str] = set()
        for raw_path in paths:
            path = raw_path.resolve()
            if path.suffix.casefold() not in _SUPPORTED_SUFFIXES:
                continue
            try:
                metadata = parse_media_file(path)
                stat = path.stat()
                content_hash = _hash_file(path)
                existing = await self.repository.find_song_by_file_uri(
                    str(path)
                )
                if metadata.title is None or not metadata.title.strip():
                    if existing is None or not existing.title.strip():
                        raise MediaMetadataError(
                            "required song title is missing"
                        )
                    identity_key = existing.identity_key
                    song_title = existing.title
                    matched_song_id = existing.song_id
                else:
                    identity_key = _identity_key(metadata)
                    song_title = metadata.title
                    matched_song_id = (
                        existing.song_id
                        if existing is not None
                        else await self._match_song_id(
                            path, identity_key, content_hash
                        )
                    )
                song_id = matched_song_id or str(uuid.uuid4())
                if song_id in reserved_ids:
                    song_id = str(uuid.uuid4())
                reserved_ids.add(song_id)
                songs.append(
                    Song(
                        song_id=song_id,
                        title=song_title,
                        file_uri=str(path),
                        identity_key=identity_key,
                        artists=metadata.artists,
                        album=metadata.album,
                        album_artists=metadata.album_artists,
                        track_number=metadata.track_number,
                        disc_number=metadata.disc_number,
                        year=metadata.year,
                        date=metadata.date,
                        genres=metadata.genres,
                        duration=metadata.duration,
                        lyrics=metadata.lyrics,
                        lyrics_format=metadata.lyrics_format,
                        lyrics_source=metadata.lyrics_source,
                        lyrics_status=metadata.lyrics_status,
                        bit_depth=metadata.bit_depth,
                        sample_rate_hz=metadata.sample_rate_hz,
                        channel_count=metadata.channel_count,
                        codec=metadata.codec,
                        metadata_status=metadata.metadata_status,
                        artwork=metadata.artwork,
                        file_size=stat.st_size,
                        file_mtime_ns=stat.st_mtime_ns,
                        content_hash=content_hash,
                        availability_status="AVAILABLE",
                    )
                )
            except (PermissionError, OSError):
                unreadable.append(str(path))
        return ScanBatch(
            songs=tuple(songs),
            unreadable_file_uris=tuple(unreadable),
        )

    async def _finalize(self, result: ScanResult) -> ScanResult:
        mpd_update_error: str | None = None
        if self.mpd_updater is not None:
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

    async def _apply_batch(self, batch: ScanBatch) -> ScanResult:
        async def operation(_):
            before = (
                await self._library_service.revision_content()
                if self.coordinator is not None else None
            )
            result = await self.repository.apply_scan_batch(batch)
            if self.coordinator is not None:
                self.coordinator.stage_change(
                    frozenset({"library"}), before,
                    await self._library_service.revision_content(),
                )
            on_transaction_commit(
                self.repository.path, lambda: self._finalize(result),
            )
            return result

        return await run_transaction(self.repository.path, operation)

    async def scan_full(self, root: Path) -> ScanResult:
        root = root.resolve()
        if not root.is_dir():
            raise LibraryScanError(
                f"library root is not a directory: {root}"
            )
        files, complete = _walk(root)
        batch = await self._scan_files(files)
        if complete:
            batch = batch.model_copy(
                update={"reconciled_root_uri_prefix": _root_prefix(root)}
            )
        return await self._apply_batch(batch)

    async def scan_paths(self, paths: list[Path]) -> ScanResult:
        expanded: list[Path] = []
        for raw_path in paths:
            path = raw_path.resolve()
            if path.suffix.casefold() == ".lrc":
                expanded.extend(_associated_audio_paths(path))
            elif path.is_dir() and not path.is_symlink():
                files, _ = _walk(path)
                expanded.extend(files)
            elif path.is_file() and not path.is_symlink():
                expanded.append(path)
        deduped = {path for path in expanded}
        batch = await self._scan_files(sorted(deduped, key=str))
        extra_paths: set[Path] = set()
        for song in batch.songs:
            if song.song_id is None or song.artwork is not None:
                continue
            source_song_id = (
                await self.repository.get_album_artwork_source_song_id(
                    song.song_id
                )
            )
            if source_song_id != song.song_id:
                continue
            for candidate_song_id, file_uri in (
                await self.repository.list_song_file_uris_in_album(
                    song.song_id
                )
            ):
                if candidate_song_id == song.song_id:
                    continue
                candidate = Path(file_uri)
                if candidate in deduped:
                    continue
                try:
                    if candidate.is_file() and not candidate.is_symlink():
                        extra_paths.add(candidate)
                except OSError:
                    continue

        if extra_paths:
            extra_batch = await self._scan_files(
                sorted(extra_paths, key=str)
            )
            songs_by_uri = {song.file_uri: song for song in batch.songs}
            songs_by_uri.update(
                {song.file_uri: song for song in extra_batch.songs}
            )
            batch = ScanBatch(
                songs=tuple(songs_by_uri.values()),
                unreadable_file_uris=tuple(
                    sorted(
                        set(batch.unreadable_file_uris)
                        | set(extra_batch.unreadable_file_uris)
                    )
                ),
            )
        return await self._apply_batch(batch)
