from __future__ import annotations

import asyncio

import pytest

from server.app.models.library import Song
from server.app.models.queue import PlaybackContext
from server.app.services.collection_service import CollectionService
from server.app.services.library_service import LibraryService, library_entity_id


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


class FakePlaylistReader:
    def __init__(self) -> None:
        self.playlists = {"playlist-1": ["song-3", "song-missing", "song-2"]}
        self.favorites = ["song-missing", "song-2", "song-1"]
        self.calls: list[str] = []

    async def list_song_ids(self, playlist_id: str) -> list[str]:
        self.calls.append(f"list_song_ids:{playlist_id}")
        return list(self.playlists.get(playlist_id, []))

    async def list_favorite_song_ids(self) -> list[str]:
        self.calls.append("list_favorite_song_ids")
        return list(self.favorites)


def make_songs() -> list[Song]:
    return [
        Song(
            song_id="song-1",
            title="Bravo",
            file_uri="music/bravo.flac",
            album_id="album-b",
            album="Album B",
            artists=("Artist B",),
            album_artists=("Album Artist B",),
            genres=("Rock",),
            tag_names=("Live",),
            year=2024,
            disc_number=1,
            track_number=2,
        ),
        Song(
            song_id="song-2",
            title="Alpha",
            file_uri="music/alpha-1.flac",
            album_id="album-a",
            album="Album A",
            artists=("Artist A",),
            album_artists=("Album Artist A",),
            genres=("Jazz",),
            tag_names=("Studio",),
            year=2023,
            disc_number=1,
            track_number=1,
        ),
        Song(
            song_id="song-3",
            title="Alpha",
            file_uri="music/alpha-2.flac",
            album_id="album-a",
            album="Album A",
            artists=("Artist A", "Guest"),
            album_artists=("Album Artist A",),
            genres=("Jazz", "Rock"),
            tag_names=("Studio", "Live"),
            year=2023,
            disc_number=2,
            track_number=1,
        ),
        Song(
            song_id="song-4",
            title="Zulu",
            file_uri="music/zulu.flac",
            album_id="album-c",
            album="Album C",
            artists=("Artist C",),
            album_artists=("Album Artist C",),
            genres=("Rock",),
            tag_names=("Live",),
            year=2024,
        ),
        Song(
            song_id="song-missing",
            title="Unavailable",
            file_uri="music/missing.flac",
            album_id="album-a",
            album="Album A",
            artists=("Artist A",),
            genres=("Rock",),
            tag_names=("Live",),
            year=2024,
            availability_status="MISSING",
        ),
    ]


@pytest.fixture
def services():
    repo = FakeLibraryRepository(make_songs())
    library = LibraryService(repo)
    playlists = FakePlaylistReader()
    collections = CollectionService(library, playlists)
    return repo, playlists, library, collections


@pytest.mark.parametrize(
    ("source_type", "source_id", "song_ids"),
    [
        ("ALBUM", "album-a", ("song-2", "song-3")),
        ("ARTIST", "Artist A", ("song-2", "song-3")),
        ("GENRE", "Rock", ("song-3", "song-1", "song-4")),
        ("YEAR", "2024", ("song-1", "song-4")),
        ("TAG", "Live", ("song-3", "song-1", "song-4")),
        ("SEARCH", None, ("song-2", "song-3")),
        ("PLAYLIST", "playlist-1", ("song-3", "song-2")),
        ("FAVORITES", None, ("song-2", "song-1")),
        ("LIBRARY", None, ("song-2", "song-3", "song-1", "song-4")),
        ("SONGS", None, ("song-3", "song-1")),
    ],
)
def test_every_collection_source_is_supported(
    services,
    source_type: str,
    source_id: str | None,
    song_ids: tuple[str, ...],
):
    _, _, _, collections = services
    kwargs: dict[str, object] = {"source_type": source_type, "source_id": source_id}
    if source_type == "SEARCH":
        kwargs["query"] = "alpha"
    if source_type == "SONGS":
        kwargs["song_ids"] = ["song-3", "song-1", "song-3", "song-missing"]
    result = run(collections.get_collection(**kwargs))
    assert result.source_type == source_type
    assert result.song_ids == song_ids
    assert result.unavailable_song_ids == (
        ("song-missing",)
        if source_type != "SEARCH"
        else ()
    )


@pytest.mark.parametrize(
    ("source_type", "source_id", "expected_song_ids"),
    [
        ("ALBUM", "album-a", ("song-2", "song-3")),
        ("ARTIST", "Artist A", ("song-2", "song-3")),
        ("GENRE", "Rock", ("song-3", "song-1", "song-4")),
        ("YEAR", "2024", ("song-1", "song-4")),
        ("TAG", "Live", ("song-3", "song-1", "song-4")),
        ("LIBRARY", None, ("song-2", "song-3", "song-1", "song-4")),
    ],
)
def test_catalog_collection_preserves_known_unavailable_members(
    services,
    source_type: str,
    source_id: str | None,
    expected_song_ids: tuple[str, ...],
):
    _, _, _, collections = services
    result = run(
        collections.get_collection(
            source_type=source_type,
            source_id=source_id,
        )
    )
    assert result.song_ids == expected_song_ids
    assert result.unavailable_song_ids == ("song-missing",)


def test_random_order_is_seeded_and_stable(services):
    _, _, _, collections = services
    first = run(
        collections.get_collection(
            source_type="LIBRARY", randomize=True, random_seed=42
        )
    )
    second = run(
        collections.get_collection(
            source_type="LIBRARY", randomize=True, random_seed=42
        )
    )
    assert first.random_seed == 42
    assert first.song_ids == second.song_ids

    context = PlaybackContext(
        context_id="context-1",
        source_type=first.source_type,
        source_id=first.source_id,
        ordered_song_ids=first.song_ids,
        random_seed=first.random_seed,
    )
    refreshed = run(
        collections.get_collection(source_type="LIBRARY", playback_context=context)
    )
    assert refreshed.song_ids == first.song_ids
    assert refreshed.random_seed == first.random_seed


def test_playback_context_carries_collection_order_and_seed(services):
    _, _, _, collections = services
    collection = run(
        collections.get_collection(
            source_type="LIBRARY", randomize=True, random_seed=42
        )
    )
    context = collections.create_playback_context(collection, context_id="context-42")
    assert context.context_id == "context-42"
    assert context.source_type == "LIBRARY"
    assert context.ordered_song_ids == collection.song_ids
    assert context.random_seed == 42


def test_existing_playback_context_keeps_order_when_a_song_becomes_unavailable(services):
    repo, _, _, collections = services
    collection = run(
        collections.get_collection(
            source_type="LIBRARY", randomize=True, random_seed=42
        )
    )
    context = collections.create_playback_context(collection, context_id="context-42")
    repo.songs["song-3"] = repo.songs["song-3"].model_copy(
        update={"availability_status": "MISSING"}
    )
    refreshed = run(
        collections.get_collection(
            source_type="LIBRARY", playback_context=context, randomize=True
        )
    )
    assert refreshed.song_ids == tuple(
        song_id for song_id in context.ordered_song_ids if song_id != "song-3"
    )
    assert refreshed.unavailable_song_ids == ("song-3",)
    assert refreshed.random_seed == context.random_seed


def test_new_context_can_use_a_new_seed(services):
    _, _, _, collections = services
    first = run(
        collections.get_collection(
            source_type="LIBRARY", randomize=True, random_seed=1
        )
    )
    second = run(
        collections.get_collection(
            source_type="LIBRARY", randomize=True, random_seed=2
        )
    )
    assert first.random_seed == 1
    assert second.random_seed == 2
    assert first.song_ids != second.song_ids


def test_explicit_empty_collection_never_falls_back_to_random_songs(services):
    _, _, _, collections = services
    result = run(
        collections.get_collection(
            source_type="SONGS", song_ids=[], randomize=True, random_seed=7
        )
    )
    assert result.song_ids == ()
    assert result.unavailable_song_ids == ()
    assert result.random_seed is None


def test_empty_search_is_an_empty_collection(services):
    _, _, _, collections = services
    result = run(
        collections.get_collection(
            source_type="SEARCH", query="does-not-exist", randomize=True, random_seed=7
        )
    )
    assert result.song_ids == ()
    assert result.unavailable_song_ids == ()


def test_empty_library_is_an_empty_collection(services):
    repo, _, _, collections = services
    repo.songs.clear()
    result = run(
        collections.get_collection(
            source_type="LIBRARY", randomize=True, random_seed=7
        )
    )
    assert result.song_ids == ()
    assert result.unavailable_song_ids == ()


def test_explicit_selection_deduplicates_first_occurrence_and_preserves_unavailable(
    services,
):
    _, _, _, collections = services
    result = run(
        collections.get_collection(
            source_type="SONGS",
            song_ids=["song-3", "song-1", "song-3", "song-missing", "song-1"],
        )
    )
    assert result.song_ids == ("song-3", "song-1")
    assert result.unavailable_song_ids == ("song-missing",)


def test_service_uses_repository_contract_and_not_sqlite(services):
    repo, playlists, library, collections = services
    run(library.list_available_songs())
    run(collections.get_collection(source_type="FAVORITES"))
    assert "list_available_songs" in repo.calls
    assert "list_favorite_song_ids" in playlists.calls
    assert not hasattr(library, "connection")
    assert not hasattr(collections, "connection")
    assert not hasattr(library, "path")
    assert not hasattr(collections, "path")


@pytest.mark.parametrize(
    ("source_type", "kind", "name", "expected"),
    [
        ("ARTIST", "artists", "Artist A", ("song-2", "song-3")),
        ("GENRE", "genres", "Rock", ("song-3", "song-1", "song-4")),
        ("TAG", "tags", "Live", ("song-3", "song-1", "song-4")),
    ],
)
def test_catalog_collection_accepts_stable_entity_ids(
    services,
    source_type: str,
    kind: str,
    name: str,
    expected: tuple[str, ...],
):
    _, _, _, collections = services
    result = run(
        collections.get_collection(
            source_type=source_type,
            source_id=library_entity_id(kind, name),
        )
    )
    assert result.source_id == library_entity_id(kind, name)
    assert result.song_ids == expected
