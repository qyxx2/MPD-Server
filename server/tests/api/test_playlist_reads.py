from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from server.app.main import app
from server.app.models.playlist import Playlist


class FakePlaylistReader:
    def __init__(self) -> None:
        now = datetime(2026, 9, 30, tzinfo=timezone.utc)
        self.playlist = Playlist(
            playlist_id="playlist-1",
            name="First",
            created_at=now,
            updated_at=now,
        )

    async def list_playlists(self):
        return [self.playlist]

    async def get_playlist(self, playlist_id: str):
        return self.playlist if playlist_id == "playlist-1" else None

    async def list_song_ids(self, playlist_id: str):
        return ["song-1"] if playlist_id == "playlist-1" else []


class FakeLibraryReader:
    async def get_song(self, song_id: str):
        return None


class FakeCollectionReader:
    async def get_collection(self, **kwargs):
        from server.app.services.collection_service import Collection

        return Collection(
            source_type=kwargs["source_type"],
            source_id=kwargs.get("source_id"),
            song_ids=("song-1",),
        )


def test_playlists_and_favorites_are_exposed_as_read_resources():
    playlist_service = FakePlaylistReader()
    collection_service = FakeCollectionReader()
    library_service = FakeLibraryReader()
    with TestClient(app) as client:
        previous = {
            "playlist_service": getattr(app.state, "playlist_service", None),
            "collection_service": getattr(app.state, "collection_service", None),
            "library_service": getattr(app.state, "library_service", None),
        }
        app.state.playlist_service = playlist_service
        app.state.collection_service = collection_service
        app.state.library_service = library_service
        try:
            playlists = client.get("/api/playlists")
            favorite = client.get("/api/favorites")
        finally:
            for name, value in previous.items():
                if value is None:
                    try:
                        delattr(app.state, name)
                    except AttributeError:
                        pass
                else:
                    setattr(app.state, name, value)

    assert playlists.status_code == 200
    assert playlists.json()["items"][0]["playlist_id"] == "playlist-1"
    assert playlists.json()["count"] == 1
    assert playlists.json()["items"][0]["song_ids"] == ["song-1"]
    assert favorite.status_code == 200
    assert favorite.json()["source_type"] == "FAVORITES"


def test_playlist_songs_read_has_stable_song_list_shape():
    from server.app.models.library import Song

    class Library:
        async def get_song(self, song_id: str):
            return Song(
                song_id=song_id,
                title="Song",
                file_uri=f"/music/{song_id}.flac",
                availability_status="AVAILABLE",
            )

    playlist_service = FakePlaylistReader()
    collection_service = FakeCollectionReader()
    library_service = Library()
    with TestClient(app) as client:
        previous = {
            "playlist_service": getattr(app.state, "playlist_service", None),
            "collection_service": getattr(app.state, "collection_service", None),
            "library_service": getattr(app.state, "library_service", None),
        }
        app.state.playlist_service = playlist_service
        app.state.collection_service = collection_service
        app.state.library_service = library_service
        try:
            response = client.get("/api/playlists/playlist-1/songs")
        finally:
            for name, value in previous.items():
                if value is None:
                    try:
                        delattr(app.state, name)
                    except AttributeError:
                        pass
                else:
                    setattr(app.state, name, value)

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["items"][0]["song_id"] == "song-1"
