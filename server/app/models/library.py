from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AvailabilityStatus = Literal["AVAILABLE", "MISSING", "UNREADABLE"]
LyricsFormat = Literal["lrc", "text"] | None
LyricsSource = Literal["sidecar", "embedded"] | None
LyricsStatus = Literal["available", "missing", "read_error"]


class ArtworkRef(BaseModel):
    artwork_id: str
    source: Literal["EMBEDDED"]
    picture_index: int = Field(ge=0)
    mime_type: str | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    content_sha256: str | None = None


class Song(BaseModel):
    song_id: str | None = None
    title: str
    file_uri: str
    identity_key: str | None = None
    artists: tuple[str, ...] = ()
    album_id: str | None = None
    album: str | None = None
    album_artists: tuple[str, ...] = ()
    track_number: int | None = Field(default=None, ge=0)
    disc_number: int | None = Field(default=None, ge=0)
    year: int | None = Field(default=None, ge=0)
    date: str | None = None
    genres: tuple[str, ...] = ()
    tag_names: tuple[str, ...] = ()
    duration: float | None = Field(default=None, ge=0)
    lyrics: str | None = None
    lyrics_format: LyricsFormat = None
    lyrics_source: LyricsSource = None
    lyrics_status: LyricsStatus = "missing"
    bit_depth: int | None = Field(default=None, ge=1)
    sample_rate_hz: int | None = Field(default=None, ge=1)
    channel_count: int | None = Field(default=None, ge=1)
    codec: str | None = None
    metadata_status: str | None = None
    last_scanned_at: datetime | None = None
    file_size: int | None = Field(default=None, ge=0)
    file_mtime_ns: int | None = Field(default=None, ge=0)
    content_hash: str | None = None
    availability_status: AvailabilityStatus = "AVAILABLE"
    last_seen_at: datetime | None = None
    artwork: ArtworkRef | None = None

    @property
    def artist_names(self) -> tuple[str, ...]:
        return self.artists

    @property
    def album_artist(self) -> tuple[str, ...]:
        return self.album_artists

    @property
    def genre(self) -> tuple[str, ...]:
        return self.genres


class ScanBatch(BaseModel):
    songs: tuple[Song, ...] = ()
    unreadable_file_uris: tuple[str, ...] = ()
    reconciled_root_uri_prefix: str | None = None


class ScanResult(BaseModel):
    added_song_ids: tuple[str, ...] = ()
    updated_song_ids: tuple[str, ...] = ()
    moved_song_ids: tuple[str, ...] = ()
    missing_song_ids: tuple[str, ...] = ()
    unreadable_song_ids: tuple[str, ...] = ()


class AlbumSummary(BaseModel):
    album_id: str
    title: str
    album_artists: tuple[str, ...] = ()
    year: int | None = None
    date: str | None = None
    song_count: int
    artwork: ArtworkRef | None = None


class ArtistSummary(BaseModel):
    artist_id: str
    name: str
    song_count: int


class GenreSummary(BaseModel):
    genre_id: str
    name: str
    song_count: int


class YearSummary(BaseModel):
    source_id: str
    value: int | None
    song_count: int


class TagSummary(BaseModel):
    tag_id: str
    name: str
    song_count: int
