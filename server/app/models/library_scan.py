from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ConfigDict

from .library import ArtworkRef, ScanBatch, SidecarSignature, Song


class _BaselineArtwork(ArtworkRef):
    model_config = ConfigDict(frozen=True)


class _BaselineSong(Song):
    model_config = ConfigDict(frozen=True)


@dataclass(frozen=True)
class ScanBaseline:
    """Detached immutable facts consumed by scan preparation, without DB handles."""

    songs: tuple[Song, ...]
    sidecars: tuple[tuple[str, SidecarSignature], ...]
    fingerprint: str
    artwork_sources: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        snapshots = tuple(
            _BaselineSong.model_validate(song.model_dump()).model_copy(update={
                "artwork": (
                    _BaselineArtwork.model_validate(song.artwork.model_dump())
                    if song.artwork is not None else None
                ),
            })
            for song in self.songs
        )
        object.__setattr__(self, "songs", snapshots)


@dataclass(frozen=True)
class FileSignature:
    file_uri: str
    file_size: int
    file_mtime_ns: int


@dataclass(frozen=True)
class LibraryInventory:
    root: Path
    identity: tuple[int, int]
    entries: tuple[FileSignature, ...]
    complete: bool


@dataclass(frozen=True)
class PreparedScan:
    batch: ScanBatch
    inventory: LibraryInventory
    baseline: ScanBaseline
    failed_paths: tuple[Path, ...]
    audio_index_changed: bool
    checked: bool = False
    metadata_failed: bool = False
