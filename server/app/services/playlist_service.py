from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from functools import wraps
from typing import Protocol, TypeVar

from server.app.models.playlist import Playlist
from server.app.repositories.database import (
    on_transaction_commit,
    on_transaction_rollback,
    on_transaction_visible,
    run_transaction,
    transaction_identity,
)
from server.app.repositories.playlist_repository import (
    DuplicatePlaylistSongError,
    MutationRunner,
    PlaylistNotFoundError,
    PlaylistReorderMemberMismatchError,
    SongNotFoundError,
    SystemPlaylistModificationError,
)
from server.app.services.events import EventPublisher, PlaylistChangedEvent
from server.app.services.realtime_coordinator import RealtimeCoordinator

T = TypeVar("T")

__all__ = [
    "DuplicatePlaylistSongError",
    "PlaylistNotFoundError",
    "PlaylistReorderMemberMismatchError",
    "PlaylistRepositoryPort",
    "PlaylistService",
    "SongNotFoundError",
    "SystemPlaylistModificationError",
]


class PlaylistRepositoryPort(Protocol):
    def set_mutation_runner(self, runner: MutationRunner) -> None: ...
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


def _mutation(method):
    @wraps(method)
    async def wrapped(self, *args, **kwargs):
        async def operation():
            return await method(self, *args, **kwargs)

        return await self._run_mutation(operation)

    return wrapped


class PlaylistService:
    """Application service for persistent Playlists and Favorites."""

    def __init__(
        self,
        repository: PlaylistRepositoryPort,
        event_publisher: EventPublisher | None = None,
        *,
        coordinator: RealtimeCoordinator | None = None,
    ) -> None:
        self._repository = repository
        self._path = getattr(repository, "path", None)
        if self._path is None and (coordinator is not None or event_publisher is not None):
            raise ValueError("Playlist propagation requires a transactional repository")
        self._event_publisher = event_publisher
        self._coordinator = coordinator
        self._changes: dict[object, list[object]] = {}
        if coordinator is not None or event_publisher is not None:
            repository.set_mutation_runner(self._run_mutation)

    async def revision_content(self) -> tuple[object, ...]:
        """Playlist identity/name/membership/order, excluding audit timestamps."""
        async def read(_):
            playlists = sorted(
                await self.list_playlists(), key=lambda playlist: playlist.playlist_id,
            )
            return (
                tuple([
                    (playlist.playlist_id, playlist.name,
                     tuple(await self.list_song_ids(playlist.playlist_id)))
                    for playlist in playlists
                ]),
                tuple(await self.list_favorite_song_ids()),
            )

        return await run_transaction(self._path, read) if self._path else await read(None)

    async def _run_mutation(self, mutation: Callable[[], Awaitable[T]]) -> T:
        if self._path is None:
            return await mutation()

        async def operation(_):
            propagate = self._coordinator is not None or self._event_publisher is not None
            before = await self.revision_content() if propagate else None
            result = await mutation()
            if propagate:
                after = await self.revision_content()
                if self._coordinator is not None:
                    self._coordinator.stage_change(frozenset({"playlist"}), before, after)
                if self._event_publisher is not None:
                    owner = transaction_identity(self._path)
                    delta = self._changes.get(owner)
                    if delta is None:
                        delta = [before, after]
                        self._changes[owner] = delta

                        async def committed():
                            first, last = delta
                            if first != last:
                                await self._event_publisher.publish(PlaylistChangedEvent())

                        on_transaction_commit(self._path, committed)
                        # Release the owner before any earlier async callback can be canceled.
                        on_transaction_visible(self._path, lambda: self._changes.pop(owner, None))
                        on_transaction_rollback(self._path, lambda: self._changes.pop(owner, None))
                    delta[1] = after
            return result

        return await run_transaction(self._path, operation)

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

    @_mutation
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
