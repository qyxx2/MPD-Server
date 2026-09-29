from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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
from server.app.services.queue_manager import QueueManager
from server.tests.integration.support.stateful_fake_mpd import StatefulFakeMPD


@pytest.fixture
def components(tmp_path: Path):
    db_path = str(tmp_path / "integration.db")
    asyncio.run(initialize_database(db_path))

    library = LibraryRepository(db_path)
    queue = QueueRepository(db_path)
    state = PlaybackStateRepository(db_path)
    playlists = PlaylistRepository(db_path)
    history = HistoryRepository(db_path)
    return {
        "library": library,
        "queue": queue,
        "state": state,
        "playlists": playlists,
        "history": history,
    }


async def seed_songs(library: LibraryRepository, *song_ids: str) -> None:
    for song_id in song_ids:
        await library.upsert_song(
            Song(
                song_id=song_id,
                title=f"Track {song_id}",
                file_uri=f"music/{song_id}.mp3",
                identity_key=f"identity-{song_id}",
            )
        )


async def server_queue_song_ids(queue: QueueRepository) -> list[str]:
    return [
        item.song_id
        for item in sorted(
            await queue.list_items(),
            key=lambda item: item.position,
        )
        if item.position >= 0
    ]


@asynccontextmanager
async def mpd_runtime(components) -> AsyncIterator[dict]:
    fake = StatefulFakeMPD()
    await fake.start()
    adapter = MPDAdapter("127.0.0.1", port=fake.port)
    service = PlaybackService(
        queue_manager=QueueManager(
            components["queue"],
            components["state"],
            components["playlists"],
        ),
        history_service=HistoryService(
            components["queue"],
            components["history"],
        ),
        autoplay=AutoPlay(
            components["queue"],
            components["library"],
            components["state"],
        ),
        player=adapter,
        library_repository=components["library"],
    )
    try:
        yield {
            **components,
            "service": service,
            "fake": fake,
            "adapter": adapter,
        }
    finally:
        await adapter.close()
        await fake.close()


def test_start_track_keeps_server_and_mpd_playback_state_in_sync(components):
    async def scenario():
        async with mpd_runtime(components) as runtime:
            await seed_songs(runtime["library"], *"abcdef")

            context = await runtime["service"].start_track("a")

            state = await runtime["state"].get_state()
            assert state is not None
            assert state.song_id == "a"
            assert state.state == "PLAYING"
            assert state.autoplay_enabled is True
            assert state.playback_context_id == context.context_id

            assert await server_queue_song_ids(runtime["queue"]) == list("abcdef")

            snapshot = await runtime["fake"].snapshot()
            assert [entry.song_uri for entry in snapshot.queue] == [
                f"music/{song_id}.mp3" for song_id in "abcdef"
            ]
            assert snapshot.current_song_uri == "music/a.mp3"
            assert snapshot.player_state == "play"

            status = await runtime["adapter"].status()
            assert status.song_uri == "music/a.mp3"
            assert status.state.value == "playing"

    asyncio.run(scenario())


def test_play_next_and_add_to_queue_keep_server_and_mpd_queues_in_sync(
    components,
):
    async def scenario():
        async with mpd_runtime(components) as runtime:
            await seed_songs(runtime["library"], *"abcdefgh")

            await runtime["service"].start_track("a")
            await runtime["service"].play_next("h")
            await runtime["service"].add_to_queue("g")

            assert await server_queue_song_ids(runtime["queue"]) == list(
                "ahbcdefg"
            )
            assert [
                entry.song_uri for entry in await runtime["fake"].queue_entries()
            ] == [
                f"music/{song_id}.mp3" for song_id in "ahbcdefg"
            ]

            fake_status = await runtime["adapter"].status()
            assert fake_status.song_uri == "music/a.mp3"
            assert fake_status.state.value == "playing"

    asyncio.run(scenario())


def test_pause_preserves_autoplay_and_stop_disables_it_with_matching_mpd_state(
    components,
):
    async def scenario():
        async with mpd_runtime(components) as runtime:
            await seed_songs(runtime["library"], *"abc")

            await runtime["service"].start_track("a")

            paused = await runtime["service"].pause()
            assert paused is not None
            assert paused.state == "PAUSED"
            assert paused.autoplay_enabled is True

            fake_paused = await runtime["fake"].snapshot()
            assert fake_paused.player_state == "pause"
            assert fake_paused.current_song_uri == "music/a.mp3"

            stopped = await runtime["service"].stop()
            assert stopped is not None
            assert stopped.state == "STOPPED"
            assert stopped.autoplay_enabled is False

            fake_stopped = await runtime["fake"].snapshot()
            assert fake_stopped.player_state == "stop"
            assert fake_stopped.current_song_uri == "music/a.mp3"

            history = await runtime["history"].list_history()
            assert len(history) == 1
            assert history[0].song_id == "a"
            assert history[0].reason == HistoryService.STOP

    asyncio.run(scenario())


def test_playid_failure_does_not_advance_server_queue_playback_or_history(
    components,
):
    async def scenario():
        async with mpd_runtime(components) as runtime:
            await seed_songs(runtime["library"], *"abc")

            await runtime["service"].start_track("a")
            before_state = await runtime["state"].get_state()
            before_queue = await runtime["queue"].get_snapshot()
            before_history = await runtime["history"].list_history()

            runtime["fake"].fail_next(
                "playid",
                "injected playid failure",
            )

            with pytest.raises(
                PlayerCommandError,
                match="injected playid failure",
            ):
                await runtime["service"].start_track("b")

            assert await runtime["state"].get_state() == before_state
            assert await runtime["queue"].get_snapshot() == before_queue
            assert await runtime["history"].list_history() == before_history

            snapshot = await runtime["fake"].snapshot()
            assert snapshot.current_song_uri == "music/a.mp3"
            assert snapshot.player_state == "play"

            status = await runtime["adapter"].status()
            assert status.song_uri == "music/a.mp3"
            assert status.state.value == "playing"

    asyncio.run(scenario())
