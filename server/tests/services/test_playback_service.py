from __future__ import annotations

import asyncio

import pytest

from server.app.models.library import Song
from server.app.models.queue import PlaybackContext
from server.app.player.mock_mpd import MockMPD
from server.app.player.ports import PlayerCommandError, PlayerUnavailable
from server.app.repositories.database import initialize_database
from server.app.repositories.history_repository import HistoryRepository
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playback_state_repository import PlaybackStateRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.repositories.queue_repository import QueueRepository
from server.app.services.autoplay import AutoPlay
from server.app.services.history_service import HistoryService
from server.app.services.playback_service import PlaybackService
from server.app.services.queue_manager import QueueManager


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
        [f"music/{song_id}.mp3" for song_id in "abcdefghijxyz"],
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
    assert current_song_id(components["queue"]) == "a"

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
    assert current_song_id(components["queue"]) == "a"
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

    player.fail_next("play", "injected next failure")
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

def test_mpd_queue_sync_failure_keeps_server_queue_authoritative(components):
    seed_songs(components["library"], *"abcdefg")
    service = components["service"]
    player = components["player"]

    run(service.start_track("a"))
    before = run(components["state"].get_state())
    assert before is not None

    player.fail_next("queue_add", "injected queue sync failure")
    with pytest.raises(PlayerCommandError, match="injected queue sync failure"):
        run(service.add_to_queue("g"))

    items = run(components["queue"].list_up_next())
    assert [item.song_id for item in items] == list("bcdefg")
    assert run(components["state"].get_state()) == before
    assert [entry.song_uri for entry in run(player.queue_entries())] == [
        "music/a.mp3",
        "music/b.mp3",
        "music/c.mp3",
        "music/d.mp3",
        "music/e.mp3",
        "music/f.mp3",
    ]


def test_player_unavailable_does_not_advance_server_playback_state(components):
    seed_songs(components["library"], *"ab")
    service = components["service"]
    player = components["player"]

    run(service.start_track("a"))
    before_state = run(components["state"].get_state())
    before_queue = run(components["queue"].get_snapshot())

    player.disconnect()
    with pytest.raises(PlayerUnavailable):
        run(service.start_track("b"))

    assert run(components["state"].get_state()) == before_state
    assert run(components["queue"].get_snapshot()) == before_queue


def make_playback_context(
    *song_ids: str,
    context_id: str = "context-1",
    source_type: str = "TEST",
    source_id: str | None = None,
    random_seed: int | None = 42,
) -> PlaybackContext:
    return PlaybackContext(
        context_id=context_id,
        source_type=source_type,
        source_id=source_id,
        ordered_song_ids=tuple(song_ids),
        random_seed=random_seed,
    )


def test_seek_playing_persists_confirmed_position_without_changing_context(
    components,
):
    seed_songs(components["library"], *"ab")
    service = components["service"]

    context = run(service.start_track("a"))
    before = run(components["state"].get_state())
    assert before is not None

    result = run(service.seek(30.0))

    assert result is not None
    assert result.song_id == before.song_id == "a"
    assert result.state == "PLAYING"
    assert result.playback_context_id == context.context_id
    assert result.position_seconds == 30.0
    assert result.autoplay_enabled is True
    status = run(components["player"].status())
    assert status.elapsed_seconds == 30.0


def test_seek_paused_persists_confirmed_position_and_preserves_paused_state(
    components,
):
    seed_songs(components["library"], *"ab")
    service = components["service"]

    context = run(service.start_track("a"))
    paused = run(service.pause())
    assert paused is not None
    assert paused.state == "PAUSED"

    result = run(service.seek(45.0))

    assert result is not None
    assert result.song_id == "a"
    assert result.state == "PAUSED"
    assert result.playback_context_id == context.context_id
    assert result.position_seconds == 45.0
    assert result.autoplay_enabled is True
    assert run(components["player"].status()).elapsed_seconds == 45.0


def test_seek_command_error_does_not_advance_playback_state(components):
    seed_songs(components["library"], *"ab")
    service = components["service"]
    player = components["player"]

    context = run(service.start_track("a"))
    before = run(components["state"].get_state())
    assert before is not None
    player.fail_next("seek", "injected seek failure")

    with pytest.raises(PlayerCommandError, match="injected seek failure"):
        run(service.seek(30.0))

    assert run(components["state"].get_state()) == before
    assert context.context_id == before.playback_context_id


def test_seek_player_unavailable_does_not_advance_playback_state(components):
    seed_songs(components["library"], *"ab")
    service = components["service"]
    player = components["player"]

    run(service.start_track("a"))
    before = run(components["state"].get_state())
    assert before is not None

    player.disconnect()
    with pytest.raises(PlayerUnavailable):
        run(service.seek(30.0))

    assert run(components["state"].get_state()) == before


def test_seek_stopped_or_without_current_state_follows_existing_noop_semantics(
    components,
):
    service = components["service"]
    player = components["player"]

    assert run(service.seek(30.0)) is None

    seed_songs(components["library"], "a")
    run(service.start_track("a"))
    stopped = run(service.stop())
    assert stopped is not None
    before = run(components["state"].get_state())

    player.fail_next("seek", "seek must not be called while stopped")
    result = run(service.seek(30.0))

    assert result == before
    assert run(components["state"].get_state()) == before


def test_play_context_replaces_queue_and_keeps_supplied_order(
    components,
):
    seed_songs(components["library"], *"abcdefgh")
    service = components["service"]

    context = make_playback_context("a", "b", "c")
    state = run(service.play_context(context))

    assert state is not None
    assert state.song_id == "a"
    assert state.state == "PLAYING"
    assert state.playback_context_id == context.context_id
    assert current_song_id(components["queue"]) == "a"

    items = [
        item
        for item in run(components["queue"].list_items())
        if item.position >= 0
    ]
    assert [item.song_id for item in items[:3]] == ["a", "b", "c"]
    assert items[0].position == 0
    assert run(components["player"].status()).song_uri == "music/a.mp3"

    up_next = [item.song_id for item in items if item.position > 0]
    assert up_next[:2] == ["b", "c"]
    assert any(item.source == "AUTOPLAY" for item in items[3:])


def test_play_context_assigns_same_playback_context_id_to_all_queue_items(
    components,
):
    seed_songs(components["library"], *"abcdefgh")
    service = components["service"]

    context = make_playback_context("a", "b", "c")
    run(service.play_context(context))

    items = [
        item
        for item in run(components["queue"].list_items())
        if item.position >= 0
    ]

    assert [item.playback_context_id for item in items] == [
        context.context_id
    ] * len(items)


def test_play_context_replaces_old_queue_without_retaining_old_pending_items(
    components,
):
    seed_songs(components["library"], *"abcdefghxyz")
    service = components["service"]
    queue_manager = service.queue_manager

    run(service.start_track("x"))
    run(queue_manager.clear())
    run(queue_manager.add_to_queue("y"))
    run(queue_manager.add_to_queue("z"))

    context = make_playback_context("a", "b", "c")
    run(service.play_context(context))

    items = run(components["queue"].list_items())
    current = [item for item in items if item.position == 0]
    up_next = [item for item in items if item.position > 0]
    played = [item for item in items if item.position < 0]

    assert [item.song_id for item in current] == ["a"]
    assert [item.song_id for item in up_next][:2] == ["b", "c"]
    assert "y" not in [item.song_id for item in up_next]
    assert "z" not in [item.song_id for item in up_next]
    assert [item.song_id for item in played] == ["x"]


def test_play_context_preserves_non_natural_order_and_does_not_reorder_by_seed(
    components,
):
    seed_songs(components["library"], *"abcdefgh")
    service = components["service"]

    context = make_playback_context("c", "a", "b", random_seed=9876)
    run(service.play_context(context))

    items = [
        item
        for item in run(components["queue"].list_items())
        if item.position >= 0
    ]
    assert [item.song_id for item in items[:3]] == ["c", "a", "b"]
    assert run(components["state"].get_state()).playback_context_id == (
        context.context_id
    )
    assert run(components["player"].status()).song_uri == "music/c.mp3"


def test_play_context_does_not_fake_state_or_history_when_play_fails(
    components,
):
    seed_songs(components["library"], *"abcdefghx")
    service = components["service"]
    player = components["player"]

    run(service.start_track("x"))
    before_state = run(components["state"].get_state())
    before_history = components["history_service"].active_event
    assert before_state is not None
    assert before_history is not None

    player.fail_next("play", "injected collection play failure")
    context = make_playback_context("a", "b", "c")

    with pytest.raises(PlayerCommandError, match="injected collection play failure"):
        run(service.play_context(context))

    assert run(components["state"].get_state()) == before_state
    assert components["history_service"].active_event == before_history
    queue_items = [
        item
        for item in run(components["queue"].list_items())
        if item.position >= 0
    ]
    assert [item.song_id for item in queue_items] == ["a", "b", "c"]
    assert all(
        item.playback_context_id == context.context_id
        for item in queue_items
    )


def test_play_context_does_not_fake_state_or_history_when_player_unavailable(
    components,
):
    seed_songs(components["library"], *"abcx")
    service = components["service"]
    player = components["player"]

    run(service.start_track("x"))
    before_state = run(components["state"].get_state())
    before_history = components["history_service"].active_event
    assert before_state is not None
    assert before_history is not None

    player.disconnect()
    context = make_playback_context("a", "b", "c")

    with pytest.raises(PlayerUnavailable):
        run(service.play_context(context))

    assert run(components["state"].get_state()) == before_state
    assert components["history_service"].active_event == before_history


def test_play_context_uses_existing_availability_contract_before_queue_mutation(
    components,
):
    seed_songs(components["library"], *"abcx")
    service = components["service"]

    stored = run(components["library"].get_song("b"))
    assert stored is not None
    run(
        components["library"].upsert_song(
            stored.model_copy(update={"availability_status": "MISSING"})
        )
    )
    run(service.start_track("x"))

    before_state = run(components["state"].get_state())
    before_queue = run(components["queue"].get_snapshot())
    before_history = components["history_service"].active_event
    context = make_playback_context("a", "b", "c")

    with pytest.raises(ValueError, match="song is not available: b"):
        run(service.play_context(context))

    assert run(components["state"].get_state()) == before_state
    assert run(components["queue"].get_snapshot()) == before_queue
    assert components["history_service"].active_event == before_history


def test_play_context_empty_is_a_noop_without_random_replacement(components):
    seed_songs(components["library"], *"abc")
    service = components["service"]
    player = components["player"]

    run(service.start_track("a"))
    before_state = run(components["state"].get_state())
    before_queue = run(components["queue"].get_snapshot())
    before_status = run(player.status())
    before_history = components["history_service"].active_event

    result = run(
        service.play_context(
            make_playback_context(
                context_id="empty-context",
            )
        )
    )

    assert result == before_state
    assert run(components["state"].get_state()) == before_state
    assert run(components["queue"].get_snapshot()) == before_queue
    assert run(player.status()) == before_status
    assert components["history_service"].active_event == before_history


def test_play_context_switches_history_through_history_service(
    components,
):
    seed_songs(components["library"], *"abcx")
    service = components["service"]

    run(service.start_track("x"))
    context = make_playback_context("a", "b", "c")
    run(service.play_context(context))

    history = run(components["history"].list_history())
    assert len(history) == 1
    assert history[0].song_id == "x"
    assert history[0].reason == HistoryService.SWITCH_AWAY
    assert components["history_service"].active_event is not None
    assert components["history_service"].active_event.song_id == "a"


def test_play_context_refills_autoplay_from_the_same_playback_context(
    components,
):
    seed_songs(components["library"], *"abcdefgh")
    service = components["service"]

    context = make_playback_context("a", "b", "c")
    run(service.play_context(context))

    items = [
        item
        for item in run(components["queue"].list_items())
        if item.position >= 0
    ]
    assert items
    assert all(
        item.playback_context_id == context.context_id
        for item in items
    )
    assert [item.song_id for item in items[:3]] == ["a", "b", "c"]
    assert all(
        item.source == "AUTOPLAY"
        for item in items[3:]
    )
