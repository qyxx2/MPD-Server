from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from server.app.models.library import Song
from server.app.player.mpd_adapter import MPDAdapter
from server.app.player.ports import PlayerCommandError
from server.app.repositories.database import initialize_database
from server.app.repositories.history_repository import HistoryRepository
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playback_state_repository import PlaybackStateRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.repositories.queue_repository import QueueRepository
from server.app.services.autoplay import AutoPlay
from server.app.services.history_service import HistoryService
from server.app.services.playback_service import PlaybackService

from server.tests.integration.support.stateful_fake_mpd import StatefulFakeMPD


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def components(tmp_path: Path):
    db_path = str(tmp_path / "integration.db")
    run(initialize_database(db_path))

    library = LibraryRepository(db_path)
    queue = QueueRepository(db_path)
    state = PlaybackStateRepository(db_path)
    playlists = PlaylistRepository(db_path)
    history = HistoryRepository(db_path)
    service = PlaybackService(
        queue_manager=__import__(
            "server.app.services.queue_manager",
            fromlist=["QueueManager"],
        ).QueueManager(queue, state, playlists),
        history_service=HistoryService(queue, history),
        autoplay=AutoPlay(queue, library, state),
        player=None,  # replaced by the real MPDAdapter below
        library_repository=library,
    )

    fake = StatefulFakeMPD()
    run(fake.start())
    adapter = MPDAdapter("127.0.0.1", port=fake.port)
    service.player = adapter

    try:
        yield {
            "library": library,
            "queue": queue,
            "state": state,
            "history": history,
            "service": service,
            "fake": fake,
            "adapter": adapter,
        }
    finally:
        run(adapter.close())
        run(fake.close())


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


def server_queue_song_ids(queue: QueueRepository) -> list[str]:
    return [
        item.song_id
        for item in sorted(
            run(queue.list_items()),
            key=lambda item: item.position,
        )
        if item.position >= 0
    ]


def server_up_next_song_ids(queue: QueueRepository) -> list[str]:
    return [item.song_id for item in run(queue.list_up_next())]


def fake_queue_uris(fake: StatefulFakeMPD) -> list[str]:
    return [entry.song_uri for entry in run(fake.queue_entries())]


def test_start_track_keeps_server_and_mpd_playback_state_in_sync(components):
    seed_songs(components["library"], *"abcdef")

    context = run(components["service"].start_track("a"))

    state = run(components["state"].get_state())
    assert state is not None
    assert state.song_id == "a"
    assert state.state == "PLAYING"
    assert state.autoplay_enabled is True
    assert state.playback_context_id == context.context_id

    assert server_queue_song_ids(components["queue"]) == list("abcdef")

    fake = components["fake"]
    snapshot = run(fake.snapshot())
    assert [entry.song_uri for entry in snapshot.queue] == [
        f"music/{song_id}.mp3" for song_id in "abcdef"
    ]
    assert snapshot.current_song_uri == "music/a.mp3"
    assert snapshot.player_state == "play"
    assert run(components["adapter"].status()).song_uri == "music/a.mp3"


def test_play_next_and_add_to_queue_keep_server_and_mpd_queues_in_sync(
    components,
):
    seed_songs(components["library"], *"abcdefgh")

    run(components["service"].start_track("a"))
    run(components["service"].play_next("h"))
    run(components["service"].add_to_queue("g"))

    assert server_queue_song_ids(components["queue"]) == list("ahbcdefg")

    assert fake_queue_uris(components["fake"]) == [
        f"music/{song_id}.mp3" for song_id in "ahbcdefg"
    ]
    fake_status = run(components["adapter"].status())
    assert fake_status.song_uri == "music/a.mp3"
    assert fake_status.state.value == "playing"


def test_pause_preserves_autoplay_and_stop_disables_it_with_matching_mpd_state(
    components,
):
    seed_songs(components["library"], *"abc")

    run(components["service"].start_track("a"))

    paused = run(components["service"].pause())
    assert paused is not None
    assert paused.state == "PAUSED"
    assert paused.autoplay_enabled is True

    fake_paused = run(components["fake"].snapshot())
    assert fake_paused.player_state == "pause"
    assert fake_paused.current_song_uri == "music/a.mp3"

    stopped = run(components["service"].stop())
    assert stopped is not None
    assert stopped.state == "STOPPED"
    assert stopped.autoplay_enabled is False

    fake_stopped = run(components["fake"].snapshot())
    assert fake_stopped.player_state == "stop"
    assert fake_stopped.current_song_uri == "music/a.mp3"

    history = run(components["history"].list_history())
    assert len(history) == 1
    assert history[0].song_id == "a"
    assert history[0].reason == HistoryService.STOP


def test_playid_failure_does_not_advance_server_queue_playback_or_history(
    components,
):
    seed_songs(components["library"], *"abc")

    run(components["service"].start_track("a"))
    before_state = run(components["state"].get_state())
    before_queue = run(components["queue"].get_snapshot())
    before_history = run(components["history"].list_history())

    components["fake"].fail_next(
        "playid",
        "injected playid failure",
    )

    with pytest.raises(PlayerCommandError, match="injected playid failure"):
        run(components["service"].start_track("b"))

    assert run(components["state"].get_state()) == before_state
    assert run(components["queue"].get_snapshot()) == before_queue
    assert run(components["history"].list_history()) == before_history

    fake = components["fake"]
    snapshot = run(fake.snapshot())
    assert snapshot.current_song_uri == "music/a.mp3"
    assert snapshot.player_state == "play"
    assert run(components["adapter"].status()).song_uri == "music/a.mp3"
