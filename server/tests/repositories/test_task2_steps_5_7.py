from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone

from server.app.models.history import HistoryEvent
from server.app.models.library import Song
from server.app.repositories.database import initialize_database, run_transaction
from server.app.repositories.history_repository import HistoryRepository
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playlist_repository import PlaylistRepository


def run(coro):
    return asyncio.run(coro)


def test_favorite_persists_and_can_be_removed_without_affecting_song_or_playlist(
    tmp_path,
):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))
    library = LibraryRepository(str(path))
    playlists = PlaylistRepository(str(path))

    run(
        library.upsert_song(
            Song(song_id="song-1", title="One", file_uri="one.flac")
        )
    )
    playlist = run(playlists.create_playlist("Keep"))
    run(playlists.add_song(playlist.playlist_id, "song-1"))

    run(playlists.set_favorite("song-1", True))

    reopened = PlaylistRepository(str(path))
    assert run(reopened.list_favorite_song_ids()) == ["song-1"]

    run(reopened.set_favorite("song-1", False))

    assert run(reopened.list_favorite_song_ids()) == []
    assert run(library.get_song("song-1")) is not None
    assert run(playlists.list_song_ids(playlist.playlist_id)) == ["song-1"]


def test_history_records_start_end_reason_and_session_independently_of_queue(
    tmp_path,
):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))
    library = LibraryRepository(str(path))
    history = HistoryRepository(str(path))

    run(
        library.upsert_song(
            Song(song_id="song-1", title="One", file_uri="one.flac")
        )
    )

    started = datetime(2026, 9, 26, 4, 0, tzinfo=timezone.utc)
    ended = started + timedelta(seconds=210)
    event = HistoryEvent(
        song_id="song-1",
        started_at=started,
        ended_at=ended,
        reason="natural_complete",
        session_id="session-1",
    )

    run(history.record_history(event))
    rows = run(history.list_history())

    assert len(rows) == 1
    assert rows[0].song_id == "song-1"
    assert rows[0].started_at == started
    assert rows[0].ended_at == ended
    assert rows[0].reason == "natural_complete"
    assert rows[0].session_id == "session-1"
    assert rows[0].history_id is not None

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM queue_items").fetchone()[0] == 0
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM history WHERE session_id = 'session-1'"
            ).fetchone()[0]
            == 1
        )
    finally:
        connection.close()


def test_critical_transactions_are_serialized_per_database(tmp_path):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))

    active = 0
    max_active = 0
    first_entered = asyncio.Event()

    async def writer(label: str):
        nonlocal active, max_active

        async def operation(connection):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            connection.execute(
                "INSERT INTO artists(artist_id, name) VALUES(?, ?)",
                (label, label),
            )
            if label == "first":
                first_entered.set()
                await asyncio.sleep(0.05)
            active -= 1

        await run_transaction(str(path), operation)

    async def scenario():
        first = asyncio.create_task(writer("first"))
        await first_entered.wait()
        second = asyncio.create_task(writer("second"))
        await asyncio.gather(first, second)

    run(scenario())

    assert max_active == 1

    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT name FROM artists ORDER BY name"
        ).fetchall() == [("first",), ("second",)]
    finally:
        connection.close()
