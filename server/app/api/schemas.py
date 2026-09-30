from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CollectionSourceType = Literal[
    "ALBUM",
    "ARTIST",
    "GENRE",
    "YEAR",
    "TAG",
    "SEARCH",
    "PLAYLIST",
    "FAVORITES",
    "LIBRARY",
    "SONGS",
]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ArtworkResponse(BaseModel):
    artwork_id: str
    source: Literal["EMBEDDED"]
    picture_index: int
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    content_sha256: str | None = None


class SongResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    song_id: str | None = None
    title: str
    file_uri: str
    artists: tuple[str, ...] = ()
    album_id: str | None = None
    album: str | None = None
    album_artists: tuple[str, ...] = ()
    track_number: int | None = None
    disc_number: int | None = None
    year: int | None = None
    date: str | None = None
    genres: tuple[str, ...] = ()
    tag_names: tuple[str, ...] = ()
    duration: float | None = None
    lyrics: str | None = None
    lyrics_format: str | None = None
    lyrics_source: str | None = None
    lyrics_status: str = "missing"
    bit_depth: int | None = None
    sample_rate_hz: int | None = None
    channel_count: int | None = None
    codec: str | None = None
    metadata_status: str | None = None
    last_scanned_at: datetime | None = None
    file_size: int | None = None
    file_mtime_ns: int | None = None
    content_hash: str | None = None
    availability_status: Literal["AVAILABLE", "MISSING", "UNREADABLE"] = "AVAILABLE"
    last_seen_at: datetime | None = None
    artwork: ArtworkResponse | None = None


class SongListResponse(BaseModel):
    items: list[SongResponse] = Field(default_factory=list)
    count: int = 0


class CollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: CollectionSourceType
    source_id: str | None = None
    query: str | None = None
    song_ids: list[str] = Field(default_factory=list)
    randomize: bool = False
    random_seed: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_source_contract(self) -> CollectionRequest:
        id_sources = {"ALBUM", "ARTIST", "GENRE", "YEAR", "TAG", "PLAYLIST"}
        if self.source_type in id_sources and not self.source_id:
            raise ValueError(f"source_id is required for {self.source_type}")
        if self.source_type not in id_sources and self.source_id is not None:
            raise ValueError(f"source_id is not allowed for {self.source_type}")
        if self.source_type == "SEARCH":
            if self.query is None:
                raise ValueError("query is required for SEARCH")
        elif self.query is not None:
            raise ValueError("query is only allowed for SEARCH")
        if self.source_type != "SONGS" and self.song_ids:
            raise ValueError("song_ids are only allowed for SONGS")
        return self


class CollectionResponse(BaseModel):
    source_type: CollectionSourceType
    source_id: str | None = None
    song_ids: list[str] = Field(default_factory=list)
    unavailable_song_ids: list[str] = Field(default_factory=list)
    random_seed: int | None = None


class AlbumSummaryResponse(BaseModel):
    album_id: str
    title: str
    album_artists: tuple[str, ...] = ()
    year: int | None = None
    date: str | None = None
    song_count: int
    artwork: ArtworkResponse | None = None


class ArtistSummaryResponse(BaseModel):
    artist_id: str
    name: str
    song_count: int


class GenreSummaryResponse(BaseModel):
    genre_id: str
    name: str
    song_count: int


class YearSummaryResponse(BaseModel):
    value: int
    song_count: int


class TagSummaryResponse(BaseModel):
    tag_id: str
    name: str
    song_count: int


class AlbumListResponse(BaseModel):
    items: list[AlbumSummaryResponse] = Field(default_factory=list)
    count: int = 0


class ArtistListResponse(BaseModel):
    items: list[ArtistSummaryResponse] = Field(default_factory=list)
    count: int = 0


class GenreListResponse(BaseModel):
    items: list[GenreSummaryResponse] = Field(default_factory=list)
    count: int = 0


class YearListResponse(BaseModel):
    items: list[YearSummaryResponse] = Field(default_factory=list)
    count: int = 0


class TagListResponse(BaseModel):
    items: list[TagSummaryResponse] = Field(default_factory=list)
    count: int = 0


class PlaylistResponse(BaseModel):
    playlist_id: str
    name: str
    created_at: datetime
    updated_at: datetime
    is_system: bool = False
    song_ids: list[str] = Field(default_factory=list)


class PlaylistListResponse(BaseModel):
    items: list[PlaylistResponse] = Field(default_factory=list)
    count: int = 0


class ScanResultResponse(BaseModel):
    added_song_ids: list[str] = Field(default_factory=list)
    updated_song_ids: list[str] = Field(default_factory=list)
    moved_song_ids: list[str] = Field(default_factory=list)
    missing_song_ids: list[str] = Field(default_factory=list)
    unreadable_song_ids: list[str] = Field(default_factory=list)


class ScanRequest(BaseModel):
    root: str = Field(min_length=1)
