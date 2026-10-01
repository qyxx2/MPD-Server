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


def test_catalog_summaries_are_service_owned_and_preserve_contract():
    from server.app.services.library_service import library_entity_id

    first = Song(
        song_id="1",
        title="Z",
        file_uri="a.flac",
        album_id="album",
        album="Album",
        artists=("Artist", "ARTIST"),
        album_artists=("Artist",),
        genres=("Rock", "rock"),
        tag_names=("Live",),
        year=2024,
        track_number=2,
    )
    second = first.model_copy(
        update={"song_id": "2", "file_uri": "b.flac", "track_number": 1, "year": 2023}
    )
    missing = first.model_copy(
        update={
            "song_id": "missing",
            "file_uri": "missing.flac",
            "availability_status": "MISSING",
        }
    )
    service = LibraryService(FakeLibraryRepository([first, second, missing]))
    album = run(service.list_albums())[0]
    assert album.album_id == "album"
    assert album.song_count == 2
    assert album.year == 2023
    assert [item.model_dump() for item in run(service.list_artists())] == [
        {
            "artist_id": library_entity_id("artists", "Artist"),
            "name": "Artist",
            "song_count": 2,
        }
    ]
    assert [item.name for item in run(service.list_genres())] == ["Rock"]
    assert run(service.list_genres())[0].song_count == 2
    assert run(service.list_tags())[0].tag_id == library_entity_id("tags", "Live")
    assert [item.value for item in run(service.list_years())] == [2023, 2024]
