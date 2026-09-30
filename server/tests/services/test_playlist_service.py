from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from server.app.models.playlist import Playlist
from server.app.repositories.playlist_repository import (
    DuplicatePlaylistSongError,
    PlaylistNotFoundError,
    SystemPlaylistModificationError,
)
from server.app.services.playlist_service import PlaylistService


def run(coro):
    return asyncio.run(coro)


class FakePlaylistRepository:
    def __init__(self) -> None:
        now = datetime(2026, 9, 30, tzinfo=timezone.utc)
        self.playlist = Playlist(
            playlist_id="playlist-1",
            name="Original",
            created_at=now,
            updated_at=now,
        )
        self.playlists = [self.playlist]
        self.song_ids = {"playlist-1": ["song-a", "song-b"]}
        self.favorites = ["song-b"]
        self.calls: list[tuple[object, ...]] = []

    async def create_playlist(self, name: str) -> Playlist:
        self.calls.append(("create_playlist", name))
        return self.playlist.model_copy(update={"name": name})

    async def list_playlists(self) -> list[Playlist]:
        self.calls.append(("list_playlists",))
        return self.playlists

    async def get_playlist(self, playlist_id: str) -> Playlist | None:
        self.calls.append(("get_playlist", playlist_id))
        return self.playlist if playlist_id == self.playlist.playlist_id else None

    async def update_playlist(self, playlist_id: str, name: str) -> Playlist:
        self.calls.append(("update_playlist", playlist_id, name))
        return self.playlist.model_copy(update={"name": name})

    async def delete_playlist(self, playlist_id: str) -> None:
        self.calls.append(("delete_playlist", playlist_id))

    async def add_song(
        self, playlist_id: str, song_id: str, position: int | None = None
    ) -> None:
        self.calls.append(("add_song", playlist_id, song_id, position))

    async def remove_song(self, playlist_id: str, song_id: str) -> None:
        self.calls.append(("remove_song", playlist_id, song_id))

    async def reorder_playlist(
        self, playlist_id: str, ordered_song_ids: list[str]
    ) -> None:
        self.calls.append(
            ("reorder_playlist", playlist_id, tuple(ordered_song_ids))
        )

    async def list_song_ids(self, playlist_id: str) -> list[str]:
        self.calls.append(("list_song_ids", playlist_id))
        return self.song_ids.get(playlist_id, [])

    async def set_favorite(self, song_id: str, is_favorite: bool) -> None:
        self.calls.append(("set_favorite", song_id, is_favorite))

    async def list_favorite_song_ids(self) -> list[str]:
        self.calls.append(("list_favorite_song_ids",))
        return self.favorites


def test_playlist_service_delegates_playlist_crud_and_membership():
    repository = FakePlaylistRepository()
    service = PlaylistService(repository)

    created = run(service.create_playlist("Created"))
    listed = run(service.list_playlists())
    fetched = run(service.get_playlist("playlist-1"))
    updated = run(service.update_playlist("playlist-1", "Renamed"))
    run(service.add_song("playlist-1", "song-c", position=1))
    run(service.remove_song("playlist-1", "song-a"))
    run(service.reorder_playlist("playlist-1", ["song-b", "song-a"]))
    songs = run(service.list_song_ids("playlist-1"))
    run(service.delete_playlist("playlist-1"))

    assert created.name == "Created"
    assert listed == [repository.playlist]
    assert fetched == repository.playlist
    assert updated.name == "Renamed"
    assert songs == ["song-a", "song-b"]
    assert ("add_song", "playlist-1", "song-c", 1) in repository.calls
    assert ("remove_song", "playlist-1", "song-a") in repository.calls
    assert (
        "reorder_playlist",
        "playlist-1",
        ("song-b", "song-a"),
    ) in repository.calls
    assert ("delete_playlist", "playlist-1") in repository.calls


def test_playlist_service_missing_playlist_has_explicit_not_found_for_song_listing():
    repository = FakePlaylistRepository()
    service = PlaylistService(repository)

    with pytest.raises(PlaylistNotFoundError):
        run(service.list_song_ids("missing"))

    assert ("get_playlist", "missing") in repository.calls
    assert not any(call[0] == "list_song_ids" for call in repository.calls)


def test_playlist_service_exposes_favorites_as_independent_persistent_state():
    repository = FakePlaylistRepository()
    service = PlaylistService(repository)

    run(service.set_favorite("song-a", True))
    favorites = run(service.list_favorite_song_ids())

    assert favorites == ["song-b"]
    assert ("set_favorite", "song-a", True) in repository.calls
    assert repository.song_ids["playlist-1"] == ["song-a", "song-b"]


def test_save_queue_as_playlist_preserves_selected_queue_order():
    repository = FakePlaylistRepository()
    service = PlaylistService(repository)

    playlist = run(
        service.save_queue_as_playlist(
            "Saved Queue",
            ["song-c", "song-a", "song-b"],
        )
    )

    assert playlist.name == "Saved Queue"
    assert [
        call
        for call in repository.calls
        if call[0] == "add_song"
    ] == [
        ("add_song", "playlist-1", "song-c", 0),
        ("add_song", "playlist-1", "song-a", 1),
        ("add_song", "playlist-1", "song-b", 2),
    ]


def test_save_queue_as_playlist_rejects_duplicate_song_ids_before_creation():
    repository = FakePlaylistRepository()
    service = PlaylistService(repository)

    with pytest.raises(ValueError, match="duplicate"):
        run(service.save_queue_as_playlist("Saved Queue", ["song-a", "song-a"]))

    assert not any(call[0] == "create_playlist" for call in repository.calls)


def test_playlist_service_does_not_translate_repository_conflicts():
    repository = FakePlaylistRepository()

    async def duplicate(
        playlist_id: str, song_id: str, position: int | None = None
    ) -> None:
        raise DuplicatePlaylistSongError(song_id)

    repository.add_song = duplicate
    service = PlaylistService(repository)

    with pytest.raises(DuplicatePlaylistSongError):
        run(service.add_song("playlist-1", "song-a"))


def test_playlist_service_preserves_system_playlist_protection_errors():
    repository = FakePlaylistRepository()

    async def protected_update(playlist_id: str, name: str) -> Playlist:
        raise SystemPlaylistModificationError(playlist_id)

    repository.update_playlist = protected_update
    service = PlaylistService(repository)

    with pytest.raises(SystemPlaylistModificationError):
        run(service.update_playlist("system", "Renamed"))
