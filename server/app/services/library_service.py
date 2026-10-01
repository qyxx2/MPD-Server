from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, TypeVar

from mutagen import MutagenError
from mutagen.flac import FLAC
from mutagen.id3 import APIC
from mutagen.mp3 import MP3

from server.app.models.library import (
    AlbumSummary,
    ArtistSummary,
    GenreSummary,
    Song,
    TagSummary,
    YearSummary,
)


class CollectionSourceNotFoundError(LookupError):
    def __init__(self, source_type: str, source_id: str) -> None:
        self.source_type = source_type
        self.source_id = source_id
        super().__init__(f"collection source not found: {source_type}/{source_id}")


class ArtworkReadError(RuntimeError):
    """Raised when a persisted artwork reference cannot be read safely."""


class ArtworkNotFoundError(LookupError):
    """Raised when a song or album has no persisted artwork reference."""


class LibraryRepositoryReader(Protocol):
    async def get_song(self, song_id: str) -> Song | None: ...

    async def list_songs(self) -> list[Song]: ...
    async def list_available_songs(self) -> list[Song]: ...

    async def get_album_artwork_source_song_id(
        self, song_id: str
    ) -> str | None: ...


def library_entity_id(kind: str, name: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"mpd-server:{kind}:{name.casefold()}",
        )
    )


class LibraryService:
    """Application-level read service for the persisted music library."""

    def __init__(self, repository: LibraryRepositoryReader) -> None:
        self._repository = repository

    async def get_song(self, song_id: str) -> Song | None:
        return await self._repository.get_song(song_id)

    async def list_songs(self) -> list[Song]:
        return await self._repository.list_songs()

    async def list_available_songs(self) -> list[Song]:
        songs = await self._repository.list_available_songs()
        return [song for song in songs if song.availability_status == "AVAILABLE"]

    async def search_library(self, query: str) -> list[Song]:
        normalized_query = query.strip().casefold()
        if not normalized_query:
            return []

        songs = await self.list_available_songs()
        ranked: list[tuple[int, Song]] = []
        for song in songs:
            match_rank = _search_rank(song, normalized_query)
            if match_rank is not None:
                ranked.append((match_rank, song))

        ranked.sort(key=lambda item: _search_sort_key(item[0], item[1]))
        return _deduplicate_songs(song for _, song in ranked)

    async def find_songs_by_album(self, album_id: str) -> list[Song]:
        songs = await self.list_available_songs()
        return _sort_album(song for song in songs if song.album_id == album_id)

    async def find_songs_by_artist(self, artist: str) -> list[Song]:
        normalized = artist.strip().casefold()
        songs = await self.list_available_songs()
        matched = [
            song
            for song in songs
            if any(
                value.casefold() == normalized
                for value in (*song.artists, *song.album_artists)
            )
        ]
        return _sort_standard(matched)

    async def find_songs_by_genre(self, genre: str) -> list[Song]:
        normalized = genre.strip().casefold()
        songs = await self.list_available_songs()
        matched = [
            song
            for song in songs
            if any(value.casefold() == normalized for value in song.genres)
        ]
        return _sort_standard(matched)

    async def find_songs_by_year(self, year: str) -> list[Song]:
        normalized = year.strip()
        songs = await self.list_available_songs()
        matched = [song for song in songs if str(song.year) == normalized]
        return _sort_standard(matched)

    async def find_songs_by_tag(self, tag: str) -> list[Song]:
        normalized = tag.strip().casefold()
        songs = await self.list_available_songs()
        matched = [
            song
            for song in songs
            if any(value.casefold() == normalized for value in song.tag_names)
        ]
        return _sort_standard(matched)

    async def category_members(self, source_type: str, source_id: str) -> list[Song]:
        songs = await self.list_songs()
        normalized = source_id.strip().casefold()
        matched = []
        for song in songs:
            values = _category_values(song, source_type)
            if source_id == unknown_category_id(source_type):
                matches = not values
            elif source_type in {"ALBUM", "YEAR"}:
                matches = source_id.strip() in values
            else:
                kind = _CATEGORY_KINDS[source_type]
                matches = any(
                    value.casefold() == normalized
                    or library_entity_id(kind, value) == source_id
                    for value in values
                )
            if matches:
                matched.append(song)
        if not matched:
            raise CollectionSourceNotFoundError(source_type, source_id)
        return (
            _sort_album(matched) if source_type == "ALBUM" else _sort_standard(matched)
        )

    async def list_albums(self) -> list[AlbumSummary]:
        groups: dict[str, list[Song]] = {}
        for song in await self.list_available_songs():
            values = _category_values(song, "ALBUM")
            album_id = values[0] if values else unknown_category_id("ALBUM")
            groups.setdefault(album_id, []).append(song)
        items = []
        for album_id, members in sorted(
            groups.items(),
            key=lambda item: (
                min(
                    (
                        member.album if _category_values(member, "ALBUM") else "未知"
                    ).casefold()
                    for member in item[1]
                ),
                item[0],
            ),
        ):
            representative = _sort_album(members)[0]
            unknown = album_id == unknown_category_id("ALBUM")
            items.append(
                AlbumSummary(
                    album_id=album_id,
                    title="未知" if unknown else representative.album,
                    album_artists=() if unknown else representative.album_artists,
                    year=None if unknown else representative.year,
                    date=None if unknown else representative.date,
                    song_count=len({song.song_id for song in members if song.song_id}),
                    artwork=None if unknown else representative.artwork,
                )
            )
        return items

    async def list_artists(self) -> list[ArtistSummary]:
        songs = sorted(
            await self.list_available_songs(),
            key=lambda song: (song.file_uri, song.song_id or ""),
        )
        return _name_summary(songs, "ARTIST", ArtistSummary)

    async def list_genres(self) -> list[GenreSummary]:
        return _name_summary(await self.list_available_songs(), "GENRE", GenreSummary)

    async def list_years(self) -> list[YearSummary]:
        counts: dict[int | None, set[str]] = {}
        for song in await self.list_available_songs():
            if song.song_id is not None:
                counts.setdefault(song.year, set()).add(song.song_id)
        return [
            YearSummary(
                value=year,
                source_id=str(year) if year is not None else "unknown",
                song_count=len(song_ids),
            )
            for year, song_ids in sorted(
                counts.items(),
                key=lambda item: (
                    item[0] is None,
                    item[0] if item[0] is not None else 0,
                ),
            )
        ]

    async def list_tags(self) -> list[TagSummary]:
        return _name_summary(await self.list_available_songs(), "TAG", TagSummary)

    async def read_artwork(self, song_id: str) -> tuple[bytes, str]:
        song = await self._repository.get_song(song_id)
        if song is None:
            raise KeyError(song_id)

        artwork = song.artwork
        if artwork is None:
            raise ArtworkNotFoundError(song_id)

        if song.availability_status != "AVAILABLE":
            raise ArtworkReadError(
                f"artwork source song is not available: {song_id}"
            )

        source_song_id = await self._repository.get_album_artwork_source_song_id(
            song_id
        )
        if source_song_id is None:
            raise ArtworkReadError(
                f"artwork source song is missing: {song_id}"
            )

        source_song = await self._repository.get_song(source_song_id)
        if source_song is None:
            raise ArtworkReadError(
                f"artwork source song not found: {source_song_id}"
            )
        if source_song.availability_status != "AVAILABLE":
            raise ArtworkReadError(
                f"artwork source song is not available: {source_song_id}"
            )

        path = Path(source_song.file_uri)
        try:
            if path.suffix.casefold() == ".flac":
                audio = FLAC(path)
                pictures = list(audio.pictures)
            elif path.suffix.casefold() == ".mp3":
                audio = MP3(path)
                pictures = [
                    frame
                    for frame in (audio.tags.values() if audio.tags else ())
                    if isinstance(frame, APIC)
                ]
            else:
                raise ArtworkReadError(
                    f"unsupported artwork source format: {path.suffix or '<none>'}"
                )
        except (MutagenError, OSError, UnicodeError, ValueError) as exc:
            raise ArtworkReadError(
                f"artwork source read failed: {exc}"
            ) from exc

        index = artwork.picture_index
        if index >= len(pictures):
            raise ArtworkReadError(
                f"artwork picture index is unavailable: {index}"
            )

        try:
            data = bytes(pictures[index].data)
        except (OSError, UnicodeError, ValueError) as exc:
            raise ArtworkReadError(
                f"artwork data read failed: {exc}"
            ) from exc
        if artwork.content_sha256 is not None:
            digest = hashlib.sha256(data).hexdigest()
            if digest != artwork.content_sha256:
                raise ArtworkReadError(
                    "artwork content does not match persisted reference"
                )

        mime_type = artwork.mime_type or getattr(pictures[index], "mime", None)
        if not mime_type:
            mime_type = "application/octet-stream"
        return data, mime_type


def _search_rank(song: Song, query: str) -> int | None:
    values: list[str] = [song.title]
    values.extend(song.artists)
    if song.album is not None:
        values.append(song.album)
    values.extend(song.album_artists)
    values.extend(song.genres)
    values.extend(song.tag_names)
    if song.year is not None:
        values.append(str(song.year))

    ranks: list[int] = []
    for value in values:
        normalized = value.casefold()
        if normalized == query:
            ranks.append(0)
        elif normalized.startswith(query):
            ranks.append(1)
        elif query in normalized:
            ranks.append(2)
    return min(ranks) if ranks else None


def _search_sort_key(rank: int, song: Song) -> tuple[object, ...]:
    return (
        rank,
        song.title.casefold(),
        (song.album or "").casefold(),
        song.file_uri,
        song.song_id or "",
    )


def _sort_album(songs: Iterable[Song]) -> list[Song]:
    return sorted(songs, key=_album_sort_key)


def _album_sort_key(song: Song) -> tuple[object, ...]:
    return (
        song.disc_number is None,
        song.disc_number if song.disc_number is not None else 0,
        song.track_number is None,
        song.track_number if song.track_number is not None else 0,
        song.file_uri,
        song.song_id or "",
    )


def _sort_standard(songs: Iterable[Song]) -> list[Song]:
    return sorted(
        songs,
        key=lambda song: (
            song.title.casefold(),
            (song.album or "").casefold(),
            song.file_uri,
            song.song_id or "",
        ),
    )


def _deduplicate_songs(songs: Iterable[Song]) -> list[Song]:
    seen: set[str] = set()
    result: list[Song] = []
    for song in songs:
        if song.song_id is None:
            continue
        if song.song_id in seen:
            continue
        seen.add(song.song_id)
        result.append(song)
    return result


_CATEGORY_KINDS = {
    "ALBUM": "albums",
    "ARTIST": "artists",
    "GENRE": "genres",
    "TAG": "tags",
}


def unknown_category_id(source_type: str) -> str:
    if source_type == "YEAR":
        return "unknown"
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL, f"mpd-server:unknown:{_CATEGORY_KINDS[source_type]}"
        )
    )


def _category_values(song: Song, source_type: str) -> tuple[str, ...]:
    if source_type == "ALBUM":
        return (
            (song.album_id,)
            if song.album_id and song.album and song.album.strip()
            else ()
        )
    if source_type == "YEAR":
        return (str(song.year),) if song.year is not None else ()
    values = {
        "ARTIST": (*song.artists, *song.album_artists),
        "GENRE": song.genres,
        "TAG": song.tag_names,
    }[source_type]
    return tuple(value for value in values if value.strip())


SummaryType = TypeVar("SummaryType", ArtistSummary, GenreSummary, TagSummary)


def _name_summary(
    songs: list[Song],
    source_type: str,
    model: type[SummaryType],
) -> list[SummaryType]:
    groups: dict[str | None, tuple[str, set[str]]] = {}
    for song in songs:
        if song.song_id is None:
            continue
        values = _category_values(song, source_type)
        for name in values or (None,):
            normalized = name.casefold() if name is not None else None
            current = groups.get(normalized)
            if current is None:
                groups[normalized] = (name or "未知", {song.song_id})
            else:
                current[1].add(song.song_id)
    kind = _CATEGORY_KINDS[source_type]
    return [
        model(
            **{
                f"{kind[:-1]}_id": unknown_category_id(source_type)
                if key is None
                else library_entity_id(kind, name),
                "name": name,
                "song_count": len(song_ids),
            }
        )
        for key, (name, song_ids) in sorted(
            groups.items(),
            key=lambda item: (
                item[1][0].casefold(),
                item[0] is None,
            ),
        )
    ]
