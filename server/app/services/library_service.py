from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from server.app.models.library import Song


class LibraryRepositoryReader(Protocol):
    async def get_song(self, song_id: str) -> Song | None: ...

    async def list_songs(self) -> list[Song]: ...
    async def list_available_songs(self) -> list[Song]: ...


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
