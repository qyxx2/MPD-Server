from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from dataclasses import replace
from pathlib import Path

from server.app.models.library import ScanBatch, SidecarSignature, Song
from server.app.models.library_scan import (
    FileSignature,
    LibraryInventory,
    PreparedScan,
    ScanBaseline,
)

from .media_metadata import MediaMetadataError, ParsedSongMetadata, parse_media_file

_SUPPORTED_SUFFIXES = {".flac", ".mp3"}
_HASH_CHUNK_SIZE = 1024 * 1024


class LibraryScanError(Exception):
    """Raised when a library root cannot be scanned safely."""


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _identity_key(metadata: ParsedSongMetadata) -> str:
    if metadata.title is None or not metadata.title.strip():
        raise MediaMetadataError("required song title is missing")
    value = {
        "title": metadata.title.strip().casefold(),
        "artists": sorted(value.casefold() for value in metadata.artists),
        "album": metadata.album.strip().casefold() if metadata.album else None,
        "album_artists": sorted(value.casefold() for value in metadata.album_artists),
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
    return hashlib.sha256(f"identity-v1:{payload}".encode()).hexdigest()


def _walk(root: Path) -> tuple[list[Path], bool]:
    files: list[Path] = []
    complete = True
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = list(iterator)
        except OSError:
            complete = False
            continue
        for entry in entries:
            try:
                # DirEntry preserves the enumerated type even when a later
                # media stat fails. Path.is_dir/is_file swallow those failures.
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                elif entry.is_file(
                    follow_symlinks=False
                ) and Path(entry.name).suffix.casefold() in _SUPPORTED_SUFFIXES | {".lrc"}:
                    files.append(Path(entry.path))
            except OSError:
                complete = False
    files.sort(key=lambda value: str(value.resolve()))
    return files, complete


def _signature(path: Path) -> FileSignature:
    stat = path.stat()
    return FileSignature(str(path), stat.st_size, stat.st_mtime_ns)


def _sidecar(path: Path) -> SidecarSignature:
    path = path.with_suffix(".lrc")
    try:
        stat = path.stat()
    except FileNotFoundError:
        return SidecarSignature(lrc_uri=str(path))
    return SidecarSignature(
        lrc_uri=str(path), file_size=stat.st_size, file_mtime_ns=stat.st_mtime_ns
    )


def _check_cancel(cancelled: threading.Event) -> None:
    if cancelled.is_set():
        raise LibraryScanError("scan preparation cancelled")


def _root_identity(root: Path, *, readable: bool = False) -> tuple[int, int]:
    if not root.is_dir() or (readable and not os.access(root, os.R_OK | os.X_OK)):
        raise LibraryScanError(f"library root is not a directory: {root}")
    stat = root.stat()
    return stat.st_dev, stat.st_ino


def _match(baseline, path, identity, content_hash):
    exact = next((s for s in baseline.songs if s.file_uri == str(path)), None)
    if exact is not None:
        return exact
    candidates = [s for s in baseline.songs if s.identity_key == identity]
    if len(candidates) == 1:
        try:
            Path(candidates[0].file_uri).stat()
        except FileNotFoundError:
            return candidates[0]
        except OSError:
            pass
    candidates = [
        s
        for s in baseline.songs
        if s.content_hash == content_hash and s.availability_status == "MISSING"
    ]
    return candidates[0] if len(candidates) == 1 else None


def prepare_scan(
    root: Path,
    baseline: ScanBaseline,
    paths: tuple[Path, ...] | None,
    *,
    deep: bool,
    identity: tuple[int, int] | None,
    cancelled: threading.Event,
) -> PreparedScan:
    """Only detached values enter this worker; all music I/O happens here."""
    _check_cancel(cancelled)
    root = root.resolve()
    actual_identity = _root_identity(root, readable=True)
    if identity is not None and identity != actual_identity:
        raise LibraryScanError("library root identity changed")
    all_paths, complete = _walk(root)
    if not complete:
        raise LibraryScanError("library inventory is incomplete")
    entries = []
    inventory_failures = set()
    for path in all_paths:
        _check_cancel(cancelled)
        try:
            entries.append(_signature(path))
        except OSError:
            inventory_failures.add(path)
    files = [
        path for path in all_paths if path.suffix.casefold() in _SUPPORTED_SUFFIXES
    ]
    inventory = LibraryInventory(root, actual_identity, tuple(entries), complete)
    indexed = {s.file_uri: s for s in baseline.songs}
    sidecars = dict(baseline.sidecars)
    requested = tuple(p.resolve() for p in paths) if paths is not None else None
    if requested is not None and any(
        not p.is_dir() and p.suffix.casefold() not in {".flac", ".mp3", ".lrc"}
        for p in requested
    ):
        raise LibraryScanError("requested scan root is unavailable")
    # Missing requests require full absence reconciliation, but still only read
    # media whose persisted signature differs.
    reconcile = requested is None or any(not p.exists() for p in requested)
    if requested is not None and any(p.is_dir() for p in requested):
        reconcile = True
    selected = {
        p
        for p in files
        if reconcile
        or any(
            p == q
            or (q.suffix.casefold() == ".lrc" and p.with_suffix(".lrc") == q)
            or p.is_relative_to(q)
            for q in requested or ()
        )
    }
    songs, failures, observed, deltas = [], sorted(inventory_failures), [], {}
    metadata_failed = False
    reserved = set()
    signature_map = {entry.file_uri: entry for entry in entries}
    visited = set()
    deep_candidates = set()
    pending = sorted(selected, key=str)
    while pending:
        _check_cancel(cancelled)
        path = pending.pop(0)
        if path in visited or path in inventory_failures:
            continue
        visited.add(path)
        uri = str(path)
        existing = indexed.get(uri)
        try:
            stat = signature_map.get(uri) or _signature(path)
            lrc = _sidecar(path)
            old_sidecar = sidecars.get(existing.song_id) if existing else None
            same_audio = bool(
                existing
                and existing.content_hash
                and (existing.file_size, existing.file_mtime_ns)
                == (stat.file_size, stat.file_mtime_ns)
            )
            sidecar_changed = old_sidecar != lrc
            unknown_absence = bool(
                existing
                and old_sidecar is None
                and lrc.file_size is None
                and existing.lyrics_source != "sidecar"
            )
            if (
                same_audio
                and existing.availability_status == "AVAILABLE"
                and not deep
                and path not in deep_candidates
                and (not sidecar_changed or unknown_absence)
            ):
                observed.append(uri)
                if unknown_absence:
                    deltas[uri] = lrc
                continue
            metadata = parse_media_file(path)
            _check_cancel(cancelled)
            content_hash = (
                existing.content_hash
                if same_audio
                and existing.availability_status == "AVAILABLE"
                and not deep
                else _hash_file(path)
            )
            if _signature(path) != stat or _sidecar(path) != lrc:
                raise OSError("media changed during preparation")
            if metadata.title is None or not metadata.title.strip():
                if existing is None or not existing.title.strip():
                    raise MediaMetadataError("required song title is missing")
                title, identity_key = existing.title, existing.identity_key
                matched = existing
            else:
                title, identity_key = metadata.title, _identity_key(metadata)
                matched = existing or _match(baseline, path, identity_key, content_hash)
            song_id = matched.song_id if matched else str(uuid.uuid4())
            if song_id in reserved:
                song_id = str(uuid.uuid4())
            reserved.add(song_id)
            values = {
                key: getattr(metadata, key)
                for key in (
                    "artists",
                    "album",
                    "album_artists",
                    "track_number",
                    "disc_number",
                    "year",
                    "date",
                    "genres",
                    "duration",
                    "lyrics",
                    "lyrics_format",
                    "lyrics_source",
                    "lyrics_status",
                    "bit_depth",
                    "sample_rate_hz",
                    "channel_count",
                    "codec",
                    "metadata_status",
                    "artwork",
                )
            }
            song = Song(
                song_id=song_id,
                title=title,
                file_uri=uri,
                identity_key=identity_key,
                file_size=stat.file_size,
                file_mtime_ns=stat.file_mtime_ns,
                content_hash=content_hash,
                availability_status="AVAILABLE",
                **values,
            )
            songs.append(song)
            if metadata.lyrics_status == "read_error":
                failures.append(path)
            else:
                deltas[uri] = lrc
            # The persisted album artwork may come from this song. Re-read only
            # same-album candidates when its picture disappears, to find fallback.
            if (
                existing
                and dict(baseline.artwork_sources).get(existing.album_id)
                == existing.song_id
                and metadata.artwork is None
            ):
                candidates = [
                    Path(s.file_uri)
                    for s in baseline.songs
                    if s.album_id == existing.album_id
                    and s.file_uri != uri
                    and s.file_uri in signature_map
                ]
                prepared_uris = {song.file_uri for song in songs}
                for candidate in candidates:
                    if str(candidate) in prepared_uris or candidate in failures:
                        continue
                    # An earlier signature-only observation carries no per-song
                    # picture. Revisit it once when its album source disappears.
                    visited.discard(candidate)
                    if str(candidate) in observed:
                        observed.remove(str(candidate))
                    deep_candidates.add(candidate)
                    pending.append(candidate)
        except (MediaMetadataError, OSError) as exc:
            metadata_failed |= isinstance(exc, MediaMetadataError)
            failures.append(path)
    batch = ScanBatch(
        songs=tuple(songs),
        observed_file_uris=tuple(observed),
        sidecar_signatures=deltas,
        unreadable_file_uris=tuple(str(p) for p in failures),
        reconciled_root_uri_prefix=str(root).rstrip("/") + "/" if reconcile else None,
    )
    return validate_prepared(
        PreparedScan(
            batch,
            inventory,
            baseline,
            tuple(failures),
            False,
            metadata_failed=metadata_failed,
        ),
        cancelled,
    )


def _audio_changed(batch: ScanBatch, baseline: ScanBaseline) -> bool:
    indexed = {song.file_uri: song for song in baseline.songs}
    if any(uri in indexed and indexed[uri].availability_status != "UNREADABLE"
           for uri in batch.unreadable_file_uris):
        return True
    for song in batch.songs:
        old = indexed.get(song.file_uri)
        if old is None or (
            old.file_size,
            old.file_mtime_ns,
            old.content_hash,
            old.availability_status,
        ) != (
            song.file_size,
            song.file_mtime_ns,
            song.content_hash,
            song.availability_status,
        ):
            return True
    retained = (
        set(batch.observed_file_uris)
        | set(batch.unreadable_file_uris)
        | {song.file_uri for song in batch.songs}
    )
    return bool(
        batch.reconciled_root_uri_prefix
        and any(
            song.availability_status == "AVAILABLE"
            and song.file_uri.startswith(batch.reconciled_root_uri_prefix)
            and song.file_uri not in retained
            for song in baseline.songs
        )
    )


def validate_prepared(
    prepared: PreparedScan, cancelled: threading.Event
) -> PreparedScan:
    """Recheck captured paths, never walk the tree at the commit boundary."""
    _check_cancel(cancelled)
    if _root_identity(prepared.inventory.root) != prepared.inventory.identity:
        raise LibraryScanError("library root identity changed before commit")
    if prepared.batch.reconciled_root_uri_prefix is not None:
        captured = {entry.file_uri for entry in prepared.inventory.entries} | set(
            prepared.batch.unreadable_file_uris
        )
        for song in prepared.baseline.songs:
            if (
                song.file_uri.startswith(prepared.batch.reconciled_root_uri_prefix)
                and song.file_uri not in captured
            ):
                _check_cancel(cancelled)
                try:
                    Path(song.file_uri).stat()
                except FileNotFoundError:
                    continue
                raise LibraryScanError("absent media reappeared before commit")
    failed = set(prepared.failed_paths)
    entries = {s.file_uri: s for s in prepared.inventory.entries}
    deltas = dict(prepared.batch.sidecar_signatures)
    accepted = []
    observed = []
    for uri in [s.file_uri for s in prepared.batch.songs] + list(
        prepared.batch.observed_file_uris
    ):
        _check_cancel(cancelled)
        try:
            if _signature(Path(uri)) != entries[uri]:
                raise OSError("audio changed before commit")
            expected = deltas.get(uri) or dict(prepared.baseline.sidecars).get(
                next(
                    (s.song_id for s in prepared.baseline.songs if s.file_uri == uri),
                    None,
                )
            )
            if expected is not None and _sidecar(Path(uri)) != expected:
                raise OSError("sidecar changed before commit")
        except OSError:
            failed.add(Path(uri))
            deltas.pop(uri, None)
            continue
        song = next((s for s in prepared.batch.songs if s.file_uri == uri), None)
        if song is None:
            observed.append(uri)
        else:
            accepted.append(song)
    batch = prepared.batch.model_copy(
        update={
            "songs": tuple(accepted),
            "observed_file_uris": tuple(observed),
            "sidecar_signatures": deltas,
            "unreadable_file_uris": tuple(sorted(map(str, failed))),
        }
    )
    return replace(
        prepared,
        batch=batch,
        failed_paths=tuple(sorted(failed)),
        checked=True,
        audio_index_changed=_audio_changed(batch, prepared.baseline),
    )
