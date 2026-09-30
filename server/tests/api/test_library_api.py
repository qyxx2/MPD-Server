from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.models.library import ArtworkRef, ScanResult, Song
from server.app.models.playlist import Playlist
from server.app.services.collection_service import Collection


def song(
    song_id: str,
    *,
    title: str = "Alpha",
    availability_status: str = "AVAILABLE",
    artwork: ArtworkRef | None = None,
) -> Song:
    return Song(
        song_id=song_id,
        title=title,
        file_uri=f"/music/{song_id}.flac",
        album_id="album-1",
        album="Album One",
        artists=("Artist One",),
        album_artists=("Album Artist One",),
        genres=("Rock",),
        tag_names=("Live",),
        year=2024,
        track_number=1,
        availability_status=availability_status,
        artwork=artwork,
    )


class FakeLibraryService:
    def __init__(self) -> None:
        self.songs = {
            "song-1": song("song-1"),
            "song-2": song("song-2", title="Beta"),
            "song-missing": song(
                "song-missing",
                title="Missing",
                availability_status="MISSING",
            ),
        }
        self.calls: list[tuple[object, ...]] = []
        self.artwork_data: tuple[bytes, str] = (b"artwork-bytes", "image/jpeg")

    async def get_song(self, song_id: str) -> Song | None:
        self.calls.append(("get_song", song_id))
        return self.songs.get(song_id)

    async def list_songs(self) -> list[Song]:
        self.calls.append(("list_songs",))
        return list(self.songs.values())

    async def list_available_songs(self) -> list[Song]:
        self.calls.append(("list_available_songs",))
        return [song for song in self.songs.values() if song.availability_status == "AVAILABLE"]

    async def search_library(self, query: str) -> list[Song]:
        self.calls.append(("search_library", query))
        normalized = query.strip().casefold()
        if not normalized:
            return []
        return [
            item
            for item in self.songs.values()
            if normalized in item.title.casefold()
            and item.availability_status == "AVAILABLE"
        ]

    async def find_songs_by_album(self, album_id: str) -> list[Song]:
        self.calls.append(("find_songs_by_album", album_id))
        return [item for item in await self.list_available_songs() if item.album_id == album_id]

    async def find_songs_by_artist(self, artist: str) -> list[Song]:
        self.calls.append(("find_songs_by_artist", artist))
        return await self.list_available_songs()

    async def find_songs_by_genre(self, genre: str) -> list[Song]:
        self.calls.append(("find_songs_by_genre", genre))
        return await self.list_available_songs()

    async def find_songs_by_year(self, year: str) -> list[Song]:
        self.calls.append(("find_songs_by_year", year))
        return await self.list_available_songs()

    async def find_songs_by_tag(self, tag: str) -> list[Song]:
        self.calls.append(("find_songs_by_tag", tag))
        return await self.list_available_songs()

    async def read_artwork(self, song_id: str) -> tuple[bytes, str]:
        self.calls.append(("read_artwork", song_id))
        return self.artwork_data


class FakeCollectionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def get_collection(self, **kwargs: object) -> Collection:
        self.calls.append(kwargs)
        source_type = str(kwargs["source_type"])
        source_id = kwargs.get("source_id")
        if source_type == "PLAYLIST" and source_id == "missing":
            raise ValueError("playlist not found")
        if source_type == "SEARCH" and kwargs.get("query", "") == "":
            return Collection(source_type="SEARCH", song_ids=())
        return Collection(
            source_type=source_type,  # type: ignore[arg-type]
            source_id=source_id if isinstance(source_id, str) else None,
            song_ids=("song-1", "song-2"),
        )


class FakePlaylistService:
    def __init__(self) -> None:
        now = datetime(2026, 9, 30, tzinfo=timezone.utc)
        self.playlist = Playlist(
            playlist_id="playlist-1",
            name="Favorites Test",
            created_at=now,
            updated_at=now,
        )
        self.calls: list[tuple[object, ...]] = []

    async def list_playlists(self) -> list[Playlist]:
        self.calls.append(("list_playlists",))
        return [self.playlist]

    async def get_playlist(self, playlist_id: str) -> Playlist | None:
        self.calls.append(("get_playlist", playlist_id))
        return self.playlist if playlist_id == self.playlist.playlist_id else None

    async def list_song_ids(self, playlist_id: str) -> list[str]:
        self.calls.append(("list_song_ids", playlist_id))
        return ["song-1", "song-2"] if playlist_id == self.playlist.playlist_id else []


class FakeScanner:
    def __init__(self) -> None:
        self.calls: list[Path] = []

    async def scan_full(self, root: Path) -> ScanResult:
        self.calls.append(root)
        return ScanResult(
            added_song_ids=("song-1",),
            updated_song_ids=("song-2",),
        )


@pytest.fixture
def services():
    library = FakeLibraryService()
    collections = FakeCollectionService()
    playlists = FakePlaylistService()
    scanner = FakeScanner()

    previous = {}
    for name, value in {
        "library_service": library,
        "collection_service": collections,
        "playlist_service": playlists,
        "library_scanner": scanner,
    }.items():
        previous[name] = getattr(app.state, name, None)
        setattr(app.state, name, value)

    try:
        with TestClient(app) as client:
            yield client, library, collections, playlists, scanner
    finally:
        for name, value in previous.items():
            if value is None:
                try:
                    delattr(app.state, name)
                except AttributeError:
                    pass
            else:
                setattr(app.state, name, value)


def test_list_songs_returns_stable_song_schema(services):
    client, _, _, _, _ = services
    response = client.get("/api/library/songs")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["song_id"] == "song-1"
    assert body["items"][0]["availability_status"] == "AVAILABLE"
    assert "identity_key" not in body["items"][0]


def test_get_song_preserves_unavailable_state_instead_of_faking_absence(services):
    client, _, _, _, _ = services
    response = client.get("/api/library/songs/song-missing")

    assert response.status_code == 200
    assert response.json()["availability_status"] == "MISSING"


def test_get_missing_song_is_404_and_does_not_return_fake_content(services):
    client, _, _, _, _ = services
    response = client.get("/api/library/songs/not-found")

    assert response.status_code == 404
    assert response.json()["code"] == "SONG_NOT_FOUND"


@pytest.mark.parametrize(
    ("path", "expected_source_type", "expected_source_id"),
    [
        ("/api/library", "LIBRARY", None),
        ("/api/library/albums/album-1", "ALBUM", "album-1"),
        ("/api/library/artists/Artist%20One", "ARTIST", "Artist One"),
        ("/api/library/genres/Rock", "GENRE", "Rock"),
        ("/api/library/years/2024", "YEAR", "2024"),
        ("/api/library/tags/Live", "TAG", "Live"),
    ],
)
def test_catalog_routes_use_one_collection_service_contract(
    services,
    path: str,
    expected_source_type: str,
    expected_source_id: str | None,
):
    client, _, collection_service, _, _ = services
    response = client.get(path)

    assert response.status_code == 200
    body = response.json()
    assert body["source_type"] == expected_source_type
    assert body["source_id"] == expected_source_id
    assert body["song_ids"] == ["song-1", "song-2"]
    assert collection_service.calls[-1]["source_type"] == expected_source_type


def test_search_requires_query_and_preserves_empty_query_behavior(services):
    client, _, collection_service, _, _ = services

    missing = client.get("/api/library/search")
    empty = client.get("/api/library/search", params={"q": ""})

    assert missing.status_code == 422
    assert missing.json()["code"] == "VALIDATION_ERROR"
    assert empty.status_code == 200
    assert empty.json()["song_ids"] == []
    assert collection_service.calls[-1]["source_type"] == "SEARCH"
    assert collection_service.calls[-1]["query"] == ""


def test_collection_route_rejects_missing_required_source_id_before_service(services):
    client, _, collection_service, _, _ = services

    response = client.get(
        "/api/library/collections/ALBUM",
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert collection_service.calls == []


def test_collection_route_supports_explicit_song_selection_as_read_contract(
    services,
):
    client, _, collection_service, _, _ = services

    response = client.get(
        "/api/library/collections/SONGS",
        params=[("song_id", "song-1"), ("song_id", "song-2")],
    )

    assert response.status_code == 200
    assert response.json()["source_type"] == "SONGS"
    assert collection_service.calls[-1]["song_ids"] == ["song-1", "song-2"]


def test_playlist_read_uses_playlist_and_collection_services(services):
    client, _, collection_service, playlist_service, _ = services

    response = client.get("/api/playlists/playlist-1")

    assert response.status_code == 200
    body = response.json()
    assert body["playlist_id"] == "playlist-1"
    assert body["song_ids"] == ["song-1", "song-2"]
    assert playlist_service.calls[-1] == ("get_playlist", "playlist-1")
    assert collection_service.calls[-1]["source_type"] == "PLAYLIST"


def test_missing_playlist_is_404(services):
    client, _, _, _, _ = services

    response = client.get("/api/playlists/missing")

    assert response.status_code == 404
    assert response.json()["code"] == "PLAYLIST_NOT_FOUND"


def test_favorites_read_is_a_collection_and_not_a_queue(services):
    client, _, collection_service, _, _ = services

    response = client.get("/api/favorites")

    assert response.status_code == 200
    assert response.json()["source_type"] == "FAVORITES"
    assert collection_service.calls[-1]["source_type"] == "FAVORITES"


def test_album_artwork_read_failure_is_observable(services):
    client, library, _, _, _ = services

    async def failing_read_artwork(song_id: str):
        library.calls.append(("read_artwork", song_id))
        raise RuntimeError("artwork source read failed")

    library.read_artwork = failing_read_artwork
    response = client.get("/api/library/songs/song-1/artwork")

    assert response.status_code == 500
    assert response.json() == {
        "code": "ARTWORK_READ_ERROR",
        "message": "artwork source read failed",
    }


def test_album_artwork_is_raw_read_only_bytes_with_mime_type(services):
    artwork = ArtworkRef(
        artwork_id="art-1",
        source="EMBEDDED",
        picture_index=0,
        mime_type="image/jpeg",
        content_sha256="dummy",
    )
    client, library, _, _, _ = services
    library.songs["song-1"] = library.songs["song-1"].model_copy(
        update={"artwork": artwork}
    )

    response = client.get("/api/library/songs/song-1/artwork")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.content == b"artwork-bytes"


def test_manual_scan_delegates_to_existing_scanner_service(services):
    client, _, _, _, scanner = services

    response = client.post("/api/library/scan", json={"root": "/music"})

    assert response.status_code == 200
    assert response.json() == {
        "added_song_ids": ["song-1"],
        "updated_song_ids": ["song-2"],
        "moved_song_ids": [],
        "missing_song_ids": [],
        "unreadable_song_ids": [],
    }
    assert scanner.calls == [Path("/music")]


def test_service_boundary_is_explicit(services):
    client, library, collection_service, playlist_service, _ = services

    client.get("/api/library/songs/song-1")
    client.get("/api/library/collections/LIBRARY")
    client.get("/api/playlists")

    assert all(call[0] == "get_song" for call in library.calls[:1])
    assert collection_service.calls
    assert playlist_service.calls
    assert not hasattr(library, "connection")


def test_catalog_list_routes_expose_stable_summary_resources(services):
    client, _, _, _, _ = services

    for path, key in (
        ("/api/library/albums", "album_id"),
        ("/api/library/artists", "name"),
        ("/api/library/genres", "name"),
        ("/api/library/years", "value"),
        ("/api/library/tags", "name"),
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert isinstance(response.json()["items"], list)
        assert key in response.json()["items"][0]


def test_playlist_list_response_has_only_playlist_resource_shape(services):
    client, _, _, _, _ = services

    response = client.get("/api/playlists")

    assert response.status_code == 200
    assert response.json()["items"][0].keys() == {
        "playlist_id",
        "name",
        "created_at",
        "updated_at",
        "is_system",
        "song_ids",
    }
    assert response.json()["items"][0]["song_ids"] == ["song-1", "song-2"]
