from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone

import pytest

from server.app.models.library import Song
from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playlist_repository import (
    PlaylistNotFoundError,
    PlaylistRepository,
    SystemPlaylistModificationError,
)


def run(coro):
    return asyncio.run(coro)


def test_playlist_crud_and_list_order_preserve_songs(tmp_path):
    path = str(tmp_path / "playlist.db")
    run(initialize_database(path))
    library = LibraryRepository(path)
    playlists = PlaylistRepository(path)

    for song_id in ("song-a", "song-b"):
        run(
            library.upsert_song(
                Song(
                    song_id=song_id,
                    title=song_id,
                    file_uri=f"music/{song_id}.flac",
                )
            )
        )

    first = run(playlists.create_playlist("First"))
    run(playlists.create_playlist("Second"))

    listed = run(playlists.list_playlists())
    assert [item.name for item in listed] == ["First", "Second"]
    fetched = run(playlists.get_playlist(first.playlist_id))
    assert fetched == first

    run(playlists.add_song(first.playlist_id, "song-a"))
    run(playlists.add_song(first.playlist_id, "song-b"))

    updated = run(playlists.update_playlist(first.playlist_id, "Renamed"))
    assert updated.name == "Renamed"
    assert run(playlists.list_song_ids(first.playlist_id)) == ["song-a", "song-b"]

    run(playlists.delete_playlist(first.playlist_id))

    assert run(playlists.get_playlist(first.playlist_id)) is None
    with pytest.raises(PlaylistNotFoundError):
        run(playlists.list_song_ids(first.playlist_id))
    assert run(library.get_song("song-a")) is not None
    assert run(library.get_song("song-b")) is not None
    assert [item.name for item in run(playlists.list_playlists())] == ["Second"]


def test_playlist_mutations_report_missing_playlist_explicitly(tmp_path):
    path = str(tmp_path / "playlist-missing.db")
    run(initialize_database(path))
    playlists = PlaylistRepository(path)

    with pytest.raises(PlaylistNotFoundError):
        run(playlists.add_song("missing", "song-a"))

    with pytest.raises(PlaylistNotFoundError):
        run(playlists.remove_song("missing", "song-a"))

    with pytest.raises(PlaylistNotFoundError):
        run(playlists.reorder_playlist("missing", []))


def test_system_playlist_cannot_be_renamed_or_deleted(tmp_path):
    path = str(tmp_path / "playlist-system.db")
    run(initialize_database(path))
    playlists = PlaylistRepository(path)

    now = datetime.now(timezone.utc).isoformat()
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            INSERT INTO playlists(
                playlist_id, name, created_at, updated_at, is_system
            ) VALUES(?, ?, ?, ?, 1)
            """,
            ("system-1", "Favorites System", now, now),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(SystemPlaylistModificationError):
        run(playlists.update_playlist("system-1", "Renamed"))

    with pytest.raises(SystemPlaylistModificationError):
        run(playlists.delete_playlist("system-1"))

    system_playlist = run(playlists.get_playlist("system-1"))
    assert system_playlist is not None
    assert system_playlist.name == "Favorites System"
