from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from server.app.main import app


class EmptyLibrary:
    async def list_songs(self):
        return []

    async def list_available_songs(self):
        return []

    async def get_song(self, song_id: str):
        return None

    async def search_library(self, query: str):
        return []


class EmptyPlaylist:
    async def list_playlists(self):
        return []

    async def get_playlist(self, playlist_id: str):
        return None


class EmptyCollections:
    async def get_collection(self, **kwargs):
        from server.app.services.collection_service import Collection

        return Collection(source_type=kwargs["source_type"], song_ids=())


def test_empty_library_and_playlists_are_explicitly_empty():
    previous = {
        "library_service": getattr(app.state, "library_service", None),
        "playlist_service": getattr(app.state, "playlist_service", None),
        "collection_service": getattr(app.state, "collection_service", None),
    }
    app.state.library_service = EmptyLibrary()
    app.state.playlist_service = EmptyPlaylist()
    app.state.collection_service = EmptyCollections()
    try:
        with TestClient(app) as client:
            library = client.post(
                "/api/library/collections",
                json={"source_type": "LIBRARY"},
            )
            songs = client.get("/api/library/songs")
            playlists = client.get("/api/playlists")
    finally:
        for name, value in previous.items():
            if value is None:
                try:
                    delattr(app.state, name)
                except AttributeError:
                    pass
            else:
                setattr(app.state, name, value)

    assert library.status_code == 200
    assert library.json()["source_type"] == "LIBRARY"
    assert library.json()["song_ids"] == []
    assert songs.status_code == 200
    assert songs.json()["items"] == []
    assert songs.json()["count"] == 0
    assert playlists.status_code == 200
    assert playlists.json()["items"] == []
    assert playlists.json()["count"] == 0


def test_validation_error_schema_is_stable():
    with TestClient(app) as client:
        response = client.get("/api/library/search")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"] is None
    assert response.json()["error"]["message"]
