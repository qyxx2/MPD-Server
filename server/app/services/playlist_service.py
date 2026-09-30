from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from server.app.models.playlist import Playlist
from server.app.repositories.playlist_repository import PlaylistNotFoundError


class PlaylistRepositoryPort(Protocol):
    async def create_playlist(self, name: str) -> Playlist: ...
    async def list_playlists(self) -> list[Playlist]: ...
    async def get_playlist(self, playlist_id: str) -> Playlist | None: ...
    async def update_playlist(self, playlist_id: str, name: str) -> Playlist: ...
    async def delete_playlist(self, playlist_id: str) -> None: ...
    async def add_song(
        self, playlist_id: str, song_id: str, position: int | None = None
    ) -> None: ...
    async def remove_song(self, playlist_id: str, song_id: str) -> None: ...
    async def reorder_playlist(
        self, playlist_id: str, ordered_song_ids: list[str]
    ) -> None: ...
    async def list_song_ids(self, playlist_id: str) -> list[str]: ...
    async def set_favorite(self, song_id: str, is_favorite: bool) -> None: ...
    async def list_favorite_song_ids(self) -> list[str]: ...


class PlaylistService:
    """Application service for persistent Playlists and Favorites."""

    def __init__(self, repository: PlaylistRepositoryPort) -> None:
        self._repository = repository

    async def create_playlist(self, name: str) -> Playlist:
        return await self._repository.create_playlist(name)

    async def list_playlists(self) -> list[Playlist]:
        return await self._repository.list_playlists()

    async def get_playlist(self, playlist_id: str) -> Playlist | None:
        return await self._repository.get_playlist(playlist_id)

    async def update_playlist(self, playlist_id: str, name: str) -> Playlist:
        return await self._repository.update_playlist(playlist_id, name)

    async def delete_playlist(self, playlist_id: str) -> None:
        await self._repository.delete_playlist(playlist_id)

    async def list_song_ids(self, playlist_id: str) -> list[str]:
        playlist = await self._repository.get_playlist(playlist_id)
        if playlist is None:
            raise PlaylistNotFoundError(playlist_id)
        return await self._repository.list_song_ids(playlist_id)

    async def add_song(
        self, playlist_id: str, song_id: str, position: int | None = None
    ) -> None:
        await self._repository.add_song(playlist_id, song_id, position=position)

    async def remove_song(self, playlist_id: str, song_id: str) -> None:
        await self._repository.remove_song(playlist_id, song_id)

    async def reorder_playlist(
        self, playlist_id: str, ordered_song_ids: list[str]
    ) -> None:
        await self._repository.reorder_playlist(playlist_id, ordered_song_ids)

    async def set_favorite(self, song_id: str, is_favorite: bool) -> None:
        await self._repository.set_favorite(song_id, is_favorite)

    async def list_favorite_song_ids(self) -> list[str]:
        return await self._repository.list_favorite_song_ids()

    async def save_queue_as_playlist(
        self, name: str, song_ids: Iterable[str]
    ) -> Playlist:
        ordered_song_ids = list(song_ids)
        if len(ordered_song_ids) != len(set(ordered_song_ids)):
            raise ValueError("Queue selection contains duplicate songs")

        playlist = await self._repository.create_playlist(name)
        for position, song_id in enumerate(ordered_song_ids):
            await self._repository.add_song(
                playlist.playlist_id,
                song_id,
                position=position,
            )
        return playlist
