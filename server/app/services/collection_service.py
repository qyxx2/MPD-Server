from __future__ import annotations

import random
import secrets
import uuid
from typing import Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict

from server.app.models.library import Song
from server.app.models.queue import PlaybackContext
from server.app.services.library_service import LibraryService

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


class Collection(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_type: CollectionSourceType
    source_id: str | None = None
    song_ids: tuple[str, ...]
    unavailable_song_ids: tuple[str, ...] = ()
    random_seed: int | None = None


class PlaylistCollectionReader(Protocol):
    async def list_song_ids(self, playlist_id: str) -> list[str]: ...

    async def list_favorite_song_ids(self) -> list[str]: ...


class CollectionService:
    """Builds uniform, deterministic collections from library/playlist sources."""

    def __init__(
        self,
        library_service: LibraryService,
        playlist_reader: PlaylistCollectionReader,
    ) -> None:
        self._library = library_service
        self._playlist_reader = playlist_reader

    async def get_collection(
        self,
        *,
        source_type: CollectionSourceType | None = None,
        source_id: str | None = None,
        query: str | None = None,
        song_ids: list[str] | tuple[str, ...] | None = None,
        randomize: bool = False,
        random_seed: int | None = None,
        playback_context: PlaybackContext | None = None,
    ) -> Collection:
        if playback_context is not None:
            if source_type is None:
                source_type = _validate_source_type(playback_context.source_type)
            elif source_type != playback_context.source_type:
                raise ValueError("playback context source_type does not match request")
            if source_id is None:
                source_id = playback_context.source_id
            elif source_id != playback_context.source_id:
                raise ValueError("playback context source_id does not match request")

        if source_type is None:
            raise ValueError("source_type is required")
        source_type = _validate_source_type(source_type)

        base_songs, unavailable = await self._resolve_source(
            source_type,
            source_id=source_id,
            query=query,
            song_ids=song_ids,
            playback_context=playback_context,
        )
        base_songs = _deduplicate(base_songs)

        if playback_context is not None:
            return self._from_playback_context(
                playback_context,
                base_songs,
                unavailable,
            )

        seed: int | None = None
        ordered_ids = [
            song.song_id for song in base_songs if song.song_id is not None
        ]
        if randomize and ordered_ids:
            seed = random_seed if random_seed is not None else secrets.randbits(63)
            random.Random(seed).shuffle(ordered_ids)

        return Collection(
            source_type=source_type,
            source_id=source_id,
            song_ids=tuple(ordered_ids),
            unavailable_song_ids=tuple(unavailable),
            random_seed=seed,
        )

    def create_playback_context(
        self,
        collection: Collection,
        context_id: str | None = None,
    ) -> PlaybackContext:
        return PlaybackContext(
            context_id=context_id or str(uuid.uuid4()),
            source_type=collection.source_type,
            source_id=collection.source_id,
            ordered_song_ids=collection.song_ids,
            random_seed=collection.random_seed,
        )

    async def _resolve_source(
        self,
        source_type: CollectionSourceType,
        *,
        source_id: str | None,
        query: str | None,
        song_ids: list[str] | tuple[str, ...] | None,
        playback_context: PlaybackContext | None,
    ) -> tuple[list[Song], list[str]]:
        if playback_context is not None:
            return await self._resolve_members(playback_context.ordered_song_ids)

        if source_type == "ALBUM":
            if source_id is None:
                raise ValueError("source_id is required for ALBUM")
            return await self._library.find_songs_by_album(source_id), []
        if source_type == "ARTIST":
            if source_id is None:
                raise ValueError("source_id is required for ARTIST")
            return await self._library.find_songs_by_artist(source_id), []
        if source_type == "GENRE":
            if source_id is None:
                raise ValueError("source_id is required for GENRE")
            return await self._library.find_songs_by_genre(source_id), []
        if source_type == "YEAR":
            if source_id is None:
                raise ValueError("source_id is required for YEAR")
            return await self._library.find_songs_by_year(source_id), []
        if source_type == "TAG":
            if source_id is None:
                raise ValueError("source_id is required for TAG")
            return await self._library.find_songs_by_tag(source_id), []
        if source_type == "SEARCH":
            return await self._library.search_library(query or source_id or ""), []
        if source_type == "PLAYLIST":
            if source_id is None:
                raise ValueError("source_id is required for PLAYLIST")
            ids = await self._playlist_reader.list_song_ids(source_id)
            return await self._resolve_members(ids)
        if source_type == "FAVORITES":
            ids = await self._playlist_reader.list_favorite_song_ids()
            return await self._resolve_members(ids)
        if source_type == "LIBRARY":
            songs = await self._library.list_available_songs()
            return _sort_standard(songs), []
        return await self._resolve_members(song_ids or [])

    async def _resolve_members(
        self,
        song_ids: list[str] | tuple[str, ...],
    ) -> tuple[list[Song], list[str]]:
        songs: list[Song] = []
        unavailable: list[str] = []
        seen: set[str] = set()
        for song_id in song_ids:
            if song_id in seen:
                continue
            seen.add(song_id)
            song = await self._library.get_song(song_id)
            if song is None or song.availability_status != "AVAILABLE":
                unavailable.append(song_id)
                continue
            songs.append(song)
        return songs, unavailable

    def _from_playback_context(
        self,
        context: PlaybackContext,
        current_songs: list[Song],
        unavailable: list[str],
    ) -> Collection:
        by_id = {
            song.song_id: song
            for song in current_songs
            if song.song_id is not None
        }
        ordered_ids = tuple(
            song_id
            for song_id in context.ordered_song_ids
            if song_id in by_id
        )
        return Collection(
            source_type=_validate_source_type(context.source_type),
            source_id=context.source_id,
            song_ids=ordered_ids,
            unavailable_song_ids=tuple(unavailable),
            random_seed=context.random_seed,
        )


def _validate_source_type(value: str) -> CollectionSourceType:
    allowed = {
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
    }
    if value not in allowed:
        raise ValueError(f"unsupported collection source_type: {value}")
    return cast(CollectionSourceType, value)


def _deduplicate(songs: list[Song]) -> list[Song]:
    seen: set[str] = set()
    result: list[Song] = []
    for song in songs:
        if song.song_id is None or song.song_id in seen:
            continue
        seen.add(song.song_id)
        result.append(song)
    return result


def _sort_standard(songs: list[Song]) -> list[Song]:
    return sorted(
        songs,
        key=lambda song: (
            song.title.casefold(),
            (song.album or "").casefold(),
            song.file_uri,
            song.song_id or "",
        ),
    )
