from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from shutil import copy2
from typing import AsyncIterator

import pytest

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
from server.app.services.library_scanner import LibraryScanner
from server.app.services.playback_service import PlaybackService
from server.app.services.queue_manager import QueueManager

from server.tests.integration.support.stateful_fake_mpd import StatefulFakeMPD


@pytest.fixture
def components(tmp_path: Path) -> dict[str, object]:
    db_path = str(tmp_path / "integration.db")
    asyncio.run(initialize_database(db_path))

    return {
        "db_path": db_path,
        "library": LibraryRepository(db_path),
        "queue": QueueRepository(db_path),
        "state": PlaybackStateRepository(db_path),
        "playlists": PlaylistRepository(db_path),
        "history": HistoryRepository(db_path),
    }


def run(coro):
    return asyncio.run(coro)


def scan_fixture_files(
    tmp_path: Path,
    media_fixture_dir: Path,
    count: int,
) -> tuple[Path, Path]:
    root = tmp_path / "library"
    root.mkdir()

    for index in range(count):
        copy2(
            media_fixture_dir / "metadata.flac",
            root / f"track-{index:02d}.flac",
        )

    return root, root / "track-00.flac"


def build_service(components: dict[str, object], adapter: MPDAdapter):
    return PlaybackService(
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


def server_queue_items(queue: QueueRepository):
    return run(queue.list_items())


def server_queue_song_ids(queue: QueueRepository) -> list[str]:
    return [
        item.song_id
        for item in sorted(
            server_queue_items(queue),
            key=lambda item: item.position,
        )
        if item.position >= 0
    ]


def server_queue_sources(queue: QueueRepository) -> list[tuple[str, str]]:
    return [
        (item.song_id, item.source)
        for item in sorted(
            server_queue_items(queue),
            key=lambda item: item.position,
        )
        if item.position >= 0
    ]


@asynccontextmanager
async def mpd_runtime(
    components: dict[str, object],
) -> AsyncIterator[dict[str, object]]:
    fake = StatefulFakeMPD()
    await fake.start()
    adapter = MPDAdapter("127.0.0.1", port=fake.port)
    try:
        yield {
            **components,
            "fake": fake,
            "adapter": adapter,
            "service": build_service(components, adapter),
        }
    finally:
        await adapter.close()
        await fake.close()


def scanned_song_ids(
    repository: LibraryRepository,
    root: Path,
) -> list[str]:
    songs = run(repository.list_songs_in_root(str(root.resolve()) + "/"))
    return [song.song_id for song in songs if song.song_id is not None]


def test_scanned_real_song_enters_playback_service_and_reaches_mpd(
    components: dict[str, object],
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    async def scenario() -> None:
        root, _ = scan_fixture_files(tmp_path, media_fixture_dir, 2)
        scanner = LibraryScanner(components["library"])
        result = await scanner.scan_full(root)

        assert len(result.added_song_ids) == 2
        songs = [
            await components["library"].get_song(song_id)
            for song_id in result.added_song_ids
        ]
        assert all(song is not None for song in songs)
        song = next(
            song
            for song in songs
            if song is not None and song.file_uri.endswith("track-00.flac")
        )
        song_id = song.song_id
        assert song_id is not None
        assert song.file_uri.startswith(str(root))
        assert song.availability_status == "AVAILABLE"
        assert song.title == "Test Song"

        async with mpd_runtime(components) as runtime:
            context = await runtime["service"].start_track(song_id)

            state = await runtime["state"].get_state()
            assert state is not None
            assert state.song_id == song_id
            assert state.state == "PLAYING"
            assert state.autoplay_enabled is True
            assert state.playback_context_id == context.context_id

            assert server_queue_song_ids(runtime["queue"]) == [
                song_id,
                next(
                    other.song_id
                    for other in songs
                    if other is not None and other.song_id != song_id
                ),
            ]

            snapshot = await runtime["fake"].snapshot()
            assert len(snapshot.queue) == 2
            assert snapshot.queue[0].song_uri == song.file_uri
            assert snapshot.current_song_uri == song.file_uri
            assert snapshot.player_state == "play"

            status = await runtime["adapter"].status()
            assert status.song_uri == song.file_uri
            assert status.state.value == "playing"

    run(scenario())


def test_next_keeps_server_current_mpd_current_and_history_consistent(
    components: dict[str, object],
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    async def scenario() -> None:
        root, _ = scan_fixture_files(tmp_path, media_fixture_dir, 3)
        scanner = LibraryScanner(components["library"])
        result = await scanner.scan_full(root)
        song_ids = list(result.added_song_ids)

        async with mpd_runtime(components) as runtime:
            await runtime["service"].start_track(song_ids[0])
            next_state = await runtime["service"].next()

            assert next_state is not None
            assert next_state.song_id == song_ids[1]
            assert next_state.state == "PLAYING"
            assert next_state.autoplay_enabled is True

            items = server_queue_items(runtime["queue"])
            current = [item for item in items if item.position == 0]
            played = [item for item in items if item.position < 0]
            up_next = [item for item in items if item.position > 0]

            assert [item.song_id for item in current] == [song_ids[1]]
            assert [item.song_id for item in played] == [song_ids[0]]
            assert [item.song_id for item in up_next] == [song_ids[2]]

            snapshot = await runtime["fake"].snapshot()
            assert snapshot.current_song_uri == (
                await runtime["library"].get_song(song_ids[1])
            ).file_uri
            assert snapshot.player_state == "play"

            history = await runtime["history"].list_history()
            assert len(history) == 1
            assert history[0].song_id == song_ids[0]
            assert history[0].reason == HistoryService.SWITCH_AWAY

    run(scenario())


def test_autoplay_play_next_and_add_to_queue_match_server_and_mpd_queue(
    components: dict[str, object],
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    async def scenario() -> None:
        root, _ = scan_fixture_files(tmp_path, media_fixture_dir, 8)
        scanner = LibraryScanner(components["library"])
        result = await scanner.scan_full(root)
        song_ids = list(result.added_song_ids)
        assert len(song_ids) == 8

        async with mpd_runtime(components) as runtime:
            await runtime["service"].start_track(song_ids[0])
            await runtime["service"].play_next(song_ids[6])
            await runtime["service"].add_to_queue(song_ids[7])

            expected = [
                song_ids[0],
                song_ids[6],
                *song_ids[1:6],
                song_ids[7],
            ]

            assert server_queue_song_ids(runtime["queue"]) == expected
            assert [
                entry.song_uri
                for entry in await runtime["fake"].queue_entries()
            ] == [
                (
                    await runtime["library"].get_song(song_id)
                ).file_uri
                for song_id in expected
            ]

            sources = server_queue_sources(runtime["queue"])
            assert sources[0] == (song_ids[0], "MANUAL")
            assert sources[1] == (song_ids[6], "MANUAL")
            assert sources[-1] == (song_ids[7], "MANUAL")
            assert all(
                source == "AUTOPLAY"
                for _, source in sources[2:-1]
            )

            snapshot = await runtime["fake"].snapshot()
            assert snapshot.current_song_uri == (
                await runtime["library"].get_song(song_ids[0])
            ).file_uri
            assert snapshot.player_state == "play"

    run(scenario())


def test_missing_scanned_song_is_rejected_before_mpd_play(
    components: dict[str, object],
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    async def scenario() -> None:
        root, target = scan_fixture_files(tmp_path, media_fixture_dir, 1)
        scanner = LibraryScanner(components["library"])

        first = await scanner.scan_full(root)
        song_id = first.added_song_ids[0]

        target.unlink()
        missing = await scanner.scan_full(root)
        assert missing.missing_song_ids == (song_id,)

        stored = await components["library"].get_song(song_id)
        assert stored is not None
        assert stored.availability_status == "MISSING"

        async with mpd_runtime(components) as runtime:
            with pytest.raises(
                ValueError,
                match=f"song is not available: {song_id}",
            ):
                await runtime["service"].start_track(song_id)

            snapshot = await runtime["fake"].snapshot()
            assert snapshot.queue == ()
            assert snapshot.current_song_uri is None
            assert snapshot.player_state == "stop"

            state = await runtime["state"].get_state()
            assert state is None

            history = await runtime["history"].list_history()
            assert history == []

    run(scenario())


def test_missing_song_does_not_consume_mpd_play_failure_injection(
    components: dict[str, object],
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    async def scenario() -> None:
        root, target = scan_fixture_files(tmp_path, media_fixture_dir, 1)
        scanner = LibraryScanner(components["library"])

        first = await scanner.scan_full(root)
        song_id = first.added_song_ids[0]

        target.unlink()
        await scanner.scan_full(root)

        async with mpd_runtime(components) as runtime:
            runtime["fake"].fail_next(
                "playid",
                "play should never be reached for a missing Song",
            )

            with pytest.raises(
                ValueError,
                match=f"song is not available: {song_id}",
            ):
                await runtime["service"].start_track(song_id)

            mpd_song_id = await runtime["adapter"].queue_add(
                "unreachable-before.mp3"
            )
            with pytest.raises(
                PlayerCommandError,
                match="play should never be reached for a missing Song",
            ):
                await runtime["adapter"].queue_play(mpd_song_id)

    run(scenario())
