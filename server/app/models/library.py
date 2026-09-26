from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Song(BaseModel):
    song_id: str | None = None
    title: str
    file_uri: str
    identity_key: str | None = None
    artists: tuple[str, ...] = ()
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
    lyrics_format: str | None = None
    bit_depth: int | None = Field(default=None, ge=1)
    sample_rate_hz: int | None = Field(default=None, ge=1)
    channel_count: int | None = Field(default=None, ge=1)
    codec: str | None = None
    metadata_status: str | None = None
    last_scanned_at: datetime | None = None

    @property
    def artist_names(self) -> tuple[str, ...]:
        return self.artists

    @property
    def album_artist(self) -> tuple[str, ...]:
        return self.album_artists

    @property
    def genre(self) -> tuple[str, ...]:
        return self.genres


class Playlist(BaseModel):
    playlist_id: str
    name: str
    created_at: datetime
    updated_at: datetime
    is_system: bool = False
