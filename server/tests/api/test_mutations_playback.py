from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.models.playlist import Playlist
from server.app.models.queue import PlaybackContext, PlaybackState, QueueItem
from server.app.services.collection_service import Collection


@contextmanager
def app_services(**services):
    previous = {}
    missing = object()
    for name, service in services.items():
        previous[name] = getattr(app.state, name, missing)
        setattr(app.state, name, service)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is missing:
                try:
                    delattr(app.state, name)
                except AttributeError:
                    pass
            else:
                setattr(app.state, name, value)


class FakePlaybackService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.context = PlaybackContext(
            context_id="context-1",
            source_type="TRACK",
            source_id="song-1",
            ordered_song_ids=("song-1",),
        )
        self.state = PlaybackState(
            song_id="song-1",
            state="PLAYING",
            playback_context_id="context-1",
            position_seconds=12.5,
            autoplay_enabled=True,
            updated_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
        )
        self.queue_item = QueueItem(
            queue_item_id="queue-1",
            song_id="song-2",
            position=1,
            source="MANUAL",
            playback_context_id="context-1",
        )
        self.queue_manager = None

    async def start_track(self, song_id: str) -> PlaybackContext:
        self.calls.append(("start_track", song_id))
        return self.context.model_copy(update={"source_id": song_id})

    async def play_context(self, context: PlaybackContext) -> PlaybackState:
        self.calls.append(("play_context", context))
        return self.state

    async def play_now(self, queue_item_id: str) -> QueueItem:
        self.calls.append(("play_now", queue_item_id))
        return self.queue_item

    async def play_next(self, song_id: str) -> QueueItem:
        self.calls.append(("play_next", song_id))
        return self.queue_item.model_copy(update={"song_id": song_id})

    async def add_to_queue(self, song_id: str) -> QueueItem:
        self.calls.append(("add_to_queue", song_id))
        return self.queue_item.model_copy(update={"song_id": song_id})

    async def pause(self) -> PlaybackState:
        self.calls.append(("pause", None))
        return self.state.model_copy(update={"state": "PAUSED"})

    async def stop(self) -> PlaybackState:
        self.calls.append(("stop", None))
        return self.state.model_copy(
            update={"state": "STOPPED", "autoplay_enabled": False}
        )

    async def next(self) -> PlaybackState:
        self.calls.append(("next", None))
        return self.state

    async def previous(self) -> PlaybackState:
        self.calls.append(("previous", None))
        return self.state

    async def seek(self, seconds: float) -> PlaybackState:
        self.calls.append(("seek", seconds))
        return self.state.model_copy(update={"position_seconds": seconds})


class FakeQueueManager:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.items = [
            QueueItem(
                queue_item_id="current",
                song_id="song-1",
                position=0,
                source="MANUAL",
                playback_context_id="context-1",
            ),
            QueueItem(
                queue_item_id="up-next",
                song_id="song-2",
                position=1,
                source="MANUAL",
                playback_context_id="context-1",
            ),
        ]
        now = datetime(2026, 9, 30, tzinfo=timezone.utc)
        self.playlist = Playlist(
            playlist_id="playlist-1",
            name="Queue",
            created_at=now,
            updated_at=now,
        )

    async def list_items(self) -> list[QueueItem]:
        self.calls.append(("list_items", None))
        return self.items

    async def reorder(
        self,
        queue_item_id: str,
        before_queue_item_id: str | None = None,
        *,
        expected_revision: int | None = None,
    ) -> list[QueueItem]:
        self.calls.append(
            (
                "reorder",
                (queue_item_id, before_queue_item_id, expected_revision),
            )
        )
        return self.items

    async def delete(
        self,
        queue_item_id: str,
        *,
        expected_revision: int | None = None,
    ) -> QueueItem | None:
        self.calls.append(("delete", (queue_item_id, expected_revision)))
        return None

    async def clear(self, *, expected_revision: int | None = None) -> None:
        self.calls.append(("clear", expected_revision))

    async def save_as_playlist(self, name: str) -> Playlist:
        self.calls.append(("save_as_playlist", name))
        return self.playlist


class FakeCollectionService:
    def __init__(self) -> None:
        self.calls: list[Collection] = []
        self.collection = Collection(
            source_type="LIBRARY",
            song_ids=("song-1", "song-2"),
        )

    async def get_collection(self, **kwargs):
        self.calls.append(kwargs)
        return self.collection

    def create_playback_context(self, collection: Collection) -> PlaybackContext:
        return PlaybackContext(
            context_id="context-collection",
            source_type=collection.source_type,
            source_id=collection.source_id,
            ordered_song_ids=collection.song_ids,
            random_seed=collection.random_seed,
        )


class FakePlaylistService:
    def __init__(self) -> None:
        now = datetime(2026, 9, 30, tzinfo=timezone.utc)
        self.playlist = Playlist(
            playlist_id="playlist-1",
            name="First",
            created_at=now,
            updated_at=now,
        )
        self.calls: list[tuple[str, object]] = []

    async def create_playlist(self, name: str) -> Playlist:
        self.calls.append(("create_playlist", name))
        return self.playlist.model_copy(update={"name": name})

    async def get_playlist(self, playlist_id: str) -> Playlist | None:
        self.calls.append(("get_playlist", playlist_id))
        return self.playlist if playlist_id == self.playlist.playlist_id else None

    async def list_song_ids(self, playlist_id: str) -> list[str]:
        self.calls.append(("list_song_ids", playlist_id))
        return ["song-1", "song-2"]

    async def update_playlist(self, playlist_id: str, name: str) -> Playlist:
        self.calls.append(("update_playlist", (playlist_id, name)))
        return self.playlist.model_copy(update={"name": name})

    async def delete_playlist(self, playlist_id: str) -> None:
        self.calls.append(("delete_playlist", playlist_id))

    async def add_song(
        self, playlist_id: str, song_id: str, position: int | None = None
    ) -> None:
        self.calls.append(("add_song", (playlist_id, song_id, position)))

    async def remove_song(self, playlist_id: str, song_id: str) -> None:
        self.calls.append(("remove_song", (playlist_id, song_id)))

    async def reorder_playlist(
        self, playlist_id: str, ordered_song_ids: list[str]
    ) -> None:
        self.calls.append(("reorder_playlist", (playlist_id, ordered_song_ids)))

    async def set_favorite(self, song_id: str, is_favorite: bool) -> None:
        self.calls.append(("set_favorite", (song_id, is_favorite)))

    async def list_favorite_song_ids(self) -> list[str]:
        self.calls.append(("list_favorite_song_ids", None))
        return ["song-1"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "api.db"))
    with TestClient(app) as client:
        yield client


def test_playback_mutation_endpoints_delegate_to_services(client):
    playback = FakePlaybackService()
    queue = FakeQueueManager()
    with app_services(
        playback_service=playback,
        queue_manager=queue,
    ):
        assert client.post("/api/playback/tracks/song-1/play").status_code == 200
        assert client.post(
            "/api/playback/queue/items/queue-1/play"
        ).status_code == 200
        assert client.post(
            "/api/playback/songs/song-2/play-next"
        ).status_code == 200
        assert client.post(
            "/api/playback/songs/song-2/queue"
        ).status_code == 200
        assert client.post("/api/playback/pause").status_code == 200
        assert client.post("/api/playback/stop").status_code == 200
        assert client.post("/api/playback/next").status_code == 200
        assert client.post("/api/playback/previous").status_code == 200
        assert client.post(
            "/api/playback/seek",
            json={"seconds": 30.0},
        ).status_code == 200
        assert [call[0] for call in playback.calls] == [
            "start_track",
            "play_now",
            "play_next",
            "add_to_queue",
            "pause",
            "stop",
            "next",
            "previous",
            "seek",
        ]
        assert queue.calls == []


def test_collection_play_creates_context_before_playback(client):
    playback = FakePlaybackService()
    collection = FakeCollectionService()
    with app_services(
        playback_service=playback,
        collection_service=collection,
    ):
        response = client.post(
            "/api/playback/collections/play",
            json={"source_type": "LIBRARY"},
        )

    assert response.status_code == 200
    assert playback.calls[0][0] == "play_context"
    context = playback.calls[0][1]
    assert context.context_id == "context-collection"
    assert context.ordered_song_ids == ("song-1", "song-2")


def test_queue_mutations_and_save_as_playlist(client):
    playback = FakePlaybackService()
    queue = FakeQueueManager()
    playlists = FakePlaylistService()
    with app_services(
        playback_service=playback,
        queue_manager=queue,
        playlist_service=playlists,
    ):
        queue_response = client.get("/api/playback/queue")
        reorder = client.put(
            "/api/playback/queue/items/up-next",
            json={"before_queue_item_id": "current"},
        )
        delete = client.delete("/api/playback/queue/items/up-next")
        clear = client.delete("/api/playback/queue")
        saved = client.post(
            "/api/playback/queue/save-as-playlist",
            json={"name": "Saved Queue"},
        )

    assert queue_response.status_code == 200
    assert queue_response.json()["count"] == 2
    assert reorder.status_code == 200
    assert reorder.json()["count"] == 2
    assert delete.status_code == 204
    assert clear.status_code == 204
    assert saved.status_code == 200
    assert saved.json()["playlist_id"] == "playlist-1"
    assert [call[0] for call in queue.calls] == [
        "list_items",
        "reorder",
        "delete",
        "clear",
        "save_as_playlist",
    ]


def test_playlist_and_favorite_mutations_delegate_to_playlist_service(client):
    service = FakePlaylistService()
    collection = FakeCollectionService()
    with app_services(
        playlist_service=service,
        collection_service=collection,
    ):
        created = client.post(
            "/api/playlists",
            json={"name": "New"},
        )
        updated = client.patch(
            "/api/playlists/playlist-1",
            json={"name": "Renamed"},
        )
        added = client.post(
            "/api/playlists/playlist-1/songs",
            json={"song_id": "song-3"},
        )
        reordered = client.put(
            "/api/playlists/playlist-1/songs/order",
            json={"ordered_song_ids": ["song-2", "song-1"]},
        )
        removed = client.delete(
            "/api/playlists/playlist-1/songs/song-1",
        )
        deleted = client.delete("/api/playlists/playlist-1")
        favorited = client.put("/api/favorites/song-1")
        unfavorited = client.delete("/api/favorites/song-1")

    assert created.status_code == 201
    assert updated.status_code == 200
    assert added.status_code == 200
    assert reordered.status_code == 200
    assert removed.status_code == 204
    assert deleted.status_code == 204
    assert favorited.status_code == 200
    assert unfavorited.status_code == 204
    assert [call[0] for call in service.calls] == [
        "create_playlist",
        "get_playlist",
        "list_song_ids",
        "update_playlist",
        "get_playlist",
        "list_song_ids",
        "add_song",
        "get_playlist",
        "list_song_ids",
        "reorder_playlist",
        "get_playlist",
        "list_song_ids",
        "remove_song",
        "delete_playlist",
        "set_favorite",
        "set_favorite",
    ]


def test_playback_player_unavailable_maps_to_503(client):
    from server.app.player.ports import PlayerUnavailable

    class Unavailable(FakePlaybackService):
        async def pause(self):
            raise PlayerUnavailable("player unavailable")

    with app_services(playback_service=Unavailable()):
        response = client.post("/api/playback/pause")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PLAYER_UNAVAILABLE"


def test_queue_revision_conflict_maps_to_409(client):
    from server.app.repositories.queue_repository import QueueRevisionConflictError

    class ConflictingQueue(FakeQueueManager):
        async def reorder(
            self,
            queue_item_id: str,
            before_queue_item_id: str | None = None,
            *,
            expected_revision: int | None = None,
        ):
            raise QueueRevisionConflictError(4, 5)

    with app_services(queue_manager=ConflictingQueue()):
        response = client.put(
            "/api/playback/queue/items/up-next",
            json={"before_queue_item_id": "current"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "QUEUE_REVISION_CONFLICT"
