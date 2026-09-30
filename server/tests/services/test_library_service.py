from __future__ import annotations

import asyncio

import pytest

from server.app.models.library import Song
from server.app.services.library_service import LibraryService


def run(coro):
    return asyncio.run(coro)


class FakeLibraryRepository:
    def __init__(self, songs: list[Song]) -> None:
        self.songs = {song.song_id: song for song in songs if song.song_id}
        self.calls: list[str] = []

    async def get_song(self, song_id: str) -> Song | None:
        self.calls.append(f"get_song:{song_id}")
        return self.songs.get(song_id)

    async def list_songs(self) -> list[Song]:
        self.calls.append("list_songs")
        return list(self.songs.values())

    async def list_available_songs(self) -> list[Song]:
        self.calls.append("list_available_songs")
        return [
            song
            for song in self.songs.values()
            if song.availability_status == "AVAILABLE"
        ]


def make_songs() -> list[Song]:
    return [
        Song(
            song_id="1",
            title="Alpha",
            file_uri="music/1.flac",
            artists=("Artist A",),
            album="Album A",
            album_artists=("Album Artist A",),
            genres=("Rock",),
            tag_names=("Live",),
            year=2024,
        ),
        Song(
            song_id="2",
            title="Alpine",
            file_uri="music/2.flac",
            artists=("Artist B",),
            album="Album B",
            album_artists=("Album Artist B",),
            genres=("Jazz",),
            tag_names=("Studio",),
            year=2023,
        ),
        Song(
            song_id="3",
            title="The Middle",
            file_uri="music/3.flac",
            artists=("Alpha Artist",),
            album="Alpha Album",
            album_artists=("Alpha Album Artist",),
            genres=("Electronic",),
            tag_names=("Rare",),
            year=2022,
        ),
        Song(
            song_id="4",
            title="Other",
            file_uri="music/4.flac",
            availability_status="MISSING",
        ),
    ]


@pytest.fixture
def service():
    return LibraryService(FakeLibraryRepository(make_songs()))


def test_get_song_delegates_to_repository(service):
    song = run(service.get_song("1"))
    assert song is not None
    assert song.song_id == "1"


def test_list_songs_preserves_known_unavailable_members(service):
    songs = run(service.list_songs())
    by_id = {song.song_id: song for song in songs}
    assert set(by_id) == {"1", "2", "3", "4"}
    assert by_id["4"].availability_status == "MISSING"


def test_available_songs_keep_available_only(service):
    songs = run(service.list_available_songs())
    assert all(song.availability_status == "AVAILABLE" for song in songs)
    assert {song.song_id for song in songs} == {"1", "2", "3"}


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("alpha", ("1", "3")),
        ("Artist A", ("1",)),
        ("Album B", ("2",)),
        ("Album Artist B", ("2",)),
        ("Jazz", ("2",)),
        ("Live", ("1",)),
        ("2024", ("1",)),
    ],
)
def test_search_supports_frozen_fields(
    service, query: str, expected: tuple[str, ...]
):
    results = run(service.search_library(query))
    assert tuple(song.song_id for song in results) == expected


def test_search_is_case_insensitive_and_deduplicated(service):
    results = run(service.search_library("ALPHA"))
    assert len(results) == len({song.song_id for song in results})


def test_artist_collection_matches_album_artist(service):
    results = run(service.find_songs_by_artist("Album Artist B"))
    assert [song.song_id for song in results] == ["2"]


def test_search_empty_query_returns_empty(service):
    assert run(service.search_library("   ")) == []
