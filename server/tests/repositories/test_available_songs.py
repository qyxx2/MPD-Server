from __future__ import annotations

import asyncio

import pytest

from server.app.models.library import ScanBatch, Song
from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository


def run(coro):
    return asyncio.run(coro)


def make_song(file_uri: str, status: str = "AVAILABLE") -> Song:
    return Song(
        song_id=file_uri.replace("/", "_") + "-id",
        title=file_uri.rsplit("/", 1)[-1],
        file_uri=file_uri,
        identity_key=file_uri,
        availability_status=status,
    )


@pytest.fixture
def repository(tmp_path):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))
    return LibraryRepository(str(path))


def test_list_songs_includes_available_and_unavailable(repository):
    run(repository.upsert_song(make_song("music/available.mp3", "AVAILABLE")))
    run(repository.upsert_song(make_song("music/missing.mp3", "MISSING")))
    run(repository.upsert_song(make_song("music/unreadable.mp3", "UNREADABLE")))

    songs = run(repository.list_songs())

    assert [(song.file_uri, song.availability_status) for song in songs] == [
        ("music/available.mp3", "AVAILABLE"),
        ("music/missing.mp3", "MISSING"),
        ("music/unreadable.mp3", "UNREADABLE"),
    ]


def test_list_available_songs_includes_only_available(repository):
    run(repository.upsert_song(make_song("music/available.mp3", "AVAILABLE")))
    run(repository.upsert_song(make_song("music/missing.mp3", "MISSING")))
    run(repository.upsert_song(make_song("music/unreadable.mp3", "UNREADABLE")))

    songs = run(repository.list_available_songs())

    assert [song.file_uri for song in songs] == ["music/available.mp3"]
    assert all(song.availability_status == "AVAILABLE" for song in songs)


def test_list_available_songs_returns_empty_for_empty_library(repository):
    assert run(repository.list_available_songs()) == []


def test_list_available_songs_has_stable_file_uri_order(repository):
    for uri in (
        "music/zeta.mp3",
        "music/alpha.mp3",
        "music/middle.mp3",
    ):
        run(repository.upsert_song(make_song(uri)))

    songs = run(repository.list_available_songs())

    assert [song.file_uri for song in songs] == [
        "music/alpha.mp3",
        "music/middle.mp3",
        "music/zeta.mp3",
    ]


def test_song_becoming_missing_is_excluded_on_next_query(repository):
    song = make_song("music/track.mp3")
    run(
        repository.apply_scan_batch(
            ScanBatch(songs=(song,), reconciled_root_uri_prefix="music/")
        )
    )
    assert [item.file_uri for item in run(repository.list_available_songs())] == [
        "music/track.mp3"
    ]

    result = run(
        repository.apply_scan_batch(
            ScanBatch(reconciled_root_uri_prefix="music/")
        )
    )

    assert result.missing_song_ids == (song.song_id,)
    assert run(repository.list_available_songs()) == []


@pytest.mark.parametrize("status", ["MISSING", "UNREADABLE"])
def test_song_becoming_available_is_included_on_next_query(repository, status):
    song = make_song("music/track.mp3", status)
    run(repository.upsert_song(song))
    assert run(repository.list_available_songs()) == []

    run(repository.apply_scan_batch(ScanBatch(songs=(song,))))

    songs = run(repository.list_available_songs())
    assert [item.file_uri for item in songs] == ["music/track.mp3"]
    assert songs[0].availability_status == "AVAILABLE"
