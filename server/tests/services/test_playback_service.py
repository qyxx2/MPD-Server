from __future__ import annotations

import asyncio

import pytest

from server.app.models.queue import PlaybackState
from server.app.player.mock_mpd import MockMPD
from server.app.player.ports import PlayerCommandError
from server.app.repositories.database import initialize_database
from server.app.repositories.history_repository import HistoryRepository
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.repositories.playback_state_repository import PlaybackStateRepository
from server.app.repositories.queue_repository import QueueRepository
from server.app.services.autoplay import AutoPlay
from server.app.services.history_service import HistoryService
from server.app.services.playback_service import PlaybackService
from server.app.services.queue_manager import QueueManager
from server.app.models.library import Song


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def components(tmp_path):
    path = str(tmp_path / "playback-service.db")
    run(initialize_database(path))

    library = LibraryRepository(path)
    queue = QueueRepository(path)
    state = PlaybackStateRepository(path)
    playlists = PlaylistRepository(path)
    history = HistoryRepository(path)
    queue_manager = QueueManager(queue, state, playlists)
    history_service = HistoryService(queue, history)
    autoplay = AutoPlay(queue, library, state)
    player = MockMPD(
        [f"music/{song_id}.mp3" for song_id in "abcdefghij"],
    )
    service = PlaybackService(
        queue_manager=queue_manager,
        history_service=history_service,
        autoplay=autoplay,
        player=player,
        library_repository=library,
    )
    return {
        "library": library,
        "queue": queue,
        "state": state,
        "history": history,
        "history_service": history_service,
        "player": player,
        "service": service,
    }


def seed_songs(library: LibraryRepository, *song_ids: str) -> None:
    for song_id in song_ids:
        run(
            library.upsert_song(
                Song(
                    song_id=song_id,
                    title=f"Track {song_id}",
                    file_uri=f"music/{song_id}.mp3",
                    identity_key=f"identity-{song_id}",
                )
            )
        )


def current_song_id(queue: QueueRepository) -> str | None:
    current = [
        item for item in run(queue.list_items()) if item.position == 0
    ]
    return current[0].song_id if current else None


def test_start_track_orchestrates_queue_mpd_history_and_autoplay(components):
    seed_songs(components["library"], *"abcdef")
    service = components["service"]

    context = run(service.start_track("a"))

    state = run(components["state"].get_state())
    assert state is not None
    assert state.song_id == "a"
    assert state.state == "PLAYING"
    assert state.autoplay_enabled is True
    assert state.playback_context_id == context.context_id
    assert current_song_id(components["queue"]) == "a"

    mpd_queue = run(components["player"].queue_entries())
    assert [entry.song_uri for entry in mpd_queue] == [
        "music/a.mp3",
        "music/b.mp3",
        "music/c.mp3",
        "music/d.mp3",
        "music/e.mp3",
        "music/f.mp3",
    ]

    history = run(components["history"].list_history())
    assert history == []


def test_start_track_failure_does_not_advance_service_state_or_history(
    components,
):
    seed_songs(components["library"], *"abc")
    service = components["service"]
    player = components["player"]

    run(service.start_track("a"))
    before = run(components["state"].get_state())
    assert before is not None

    player.fail_next("play", "injected play failure")

    with pytest.raises(PlayerCommandError, match="injected play failure"):
        run(service.start_track("b"))

    after = run(components["state"].get_state())
    assert after == before
    assert components["history_service"].active_event is not None
    assert components["history_service"].active_event.song_id == "a"
    assert current_song_id(components["queue"]) == "b"

    status = run(player.status())
    assert status.song_uri == "music/a.mp3"
    assert status.state.value == "playing"


def test_play_now_failure_does_not_record_switch_or_advance_state(components):
    seed_songs(components["library"], *"abc")
    service = components["service"]
    player = components["player"]

    run(service.start_track("a"))
    item_b = run(service.add_to_queue("b"))

    before = run(components["state"].get_state())
    assert before is not None
    player.fail_next("play", "injected play failure")

    with pytest.raises(PlayerCommandError, match="injected play failure"):
        run(service.play_now(item_b.queue_item_id))

    assert run(components["state"].get_state()) == before
    assert components["history_service"].active_event is not None
    assert components["history_service"].active_event.song_id == "a"
    assert current_song_id(components["queue"]) == "b"
    assert run(player.status()).song_uri == "music/a.mp3"


def test_play_next_and_add_to_queue_sync_mpd_without_restarting_current(
    components,
):
    seed_songs(components["library"], *"abcdefgh")
    service = components["service"]

    run(service.start_track("a"))
    added = run(service.add_to_queue("g"))
    next_item = run(service.play_next("h"))

    assert added.song_id == "g"
    assert next_item.song_id == "h"
    assert current_song_id(components["queue"]) == "a"
    assert run(components["state"].get_state()).song_id == "a"
    assert run(components["player"].status()).song_uri == "music/a.mp3"

    mpd_queue = run(components["player"].queue_entries())
    assert [entry.song_uri for entry in mpd_queue] == [
        "music/a.mp3",
        "music/h.mp3",
        "music/b.mp3",
        "music/c.mp3",
        "music/d.mp3",
        "music/e.mp3",
        "music/f.mp3",
        "music/g.mp3",
    ]


def test_pause_and_stop_commit_service_state_only_after_mpd_success(components):
    seed_songs(components["library"], *"ab")
    service = components["service"]
    player = components["player"]

    run(service.start_track("a"))

    before = run(components["state"].get_state())
    assert before is not None
    player.fail_next("pause", "injected pause failure")
    with pytest.raises(PlayerCommandError, match="injected pause failure"):
        run(service.pause())
    assert run(components["state"].get_state()) == before

    paused = run(service.pause())
    assert paused.state == "PAUSED"
    assert paused.autoplay_enabled is True

    player.fail_next("stop", "injected stop failure")
    with pytest.raises(PlayerCommandError, match="injected stop failure"):
        run(service.stop())
    assert run(components["state"].get_state()) == paused

    stopped = run(service.stop())
    assert stopped.state == "STOPPED"
    assert stopped.autoplay_enabled is False

    history = run(components["history"].list_history())
    assert len(history) == 1
    assert history[0].song_id == "a"
    assert history[0].reason == HistoryService.STOP


def test_reconcile_external_status_updates_service_state_but_not_server_queue(
    components,
):
    seed_songs(components["library"], *"abc")
    service = components["service"]
    player = components["player"]

    run(service.start_track("a"))
    run(player.play("music/b.mp3"))

    run(service.reconcile_external_status())

    state = run(components["state"].get_state())
    assert state is not None
    assert state.song_id == "b"
    assert state.state == "PLAYING"
    assert current_song_id(components["queue"]) == "a"
    assert components["history_service"].active_event is not None
    assert components["history_service"].active_event.song_id == "b"


def test_successful_next_promotes_server_queue_and_records_switch(
    components,
):
    seed_songs(components["library"], *"abcdefg")
    service = components["service"]

    run(service.start_track("a"))
    state = run(service.next())

    assert state.song_id == "b"
    assert state.state == "PLAYING"
    assert current_song_id(components["queue"]) == "b"

    history = run(components["history"].list_history())
    assert len(history) == 1
    assert history[0].song_id == "a"
    assert history[0].reason == HistoryService.SWITCH_AWAY

    mpd_queue = run(components["player"].queue_entries())
    assert mpd_queue[0].song_uri == "music/b.mp3"


def test_next_failure_does_not_advance_service_state(components):
    seed_songs(components["library"], *"abc")
    service = components["service"]
    player = components["player"]

    run(service.start_track("a"))
    before = run(components["state"].get_state())
    assert before is not None

    player.fail_next("next", "injected next failure")
    with pytest.raises(PlayerCommandError, match="injected next failure"):
        run(service.next())

    assert run(components["state"].get_state()) == before
    assert current_song_id(components["queue"]) == "a"

def test_playback_service_reconciles_status_after_successful_play(components):
    seed_songs(components["library"], *"ab")
    service = components["service"]
    player = components["player"]

    original_status = player.status
    calls = 0

    async def status():
        nonlocal calls
        calls += 1
        return await original_status()

    player.status = status
    run(service.start_track("a"))

    assert calls >= 1
