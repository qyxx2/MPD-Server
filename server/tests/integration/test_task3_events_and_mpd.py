from __future__ import annotations

import asyncio
from pathlib import Path
from shutil import copy2

import pytest

from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository
from server.app.services.events import LibraryChangedEvent
from server.app.services.library_scanner import LibraryScanner


def run(coro):
    return asyncio.run(coro)


def test_task3_events_follow_committed_sqlite_state(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    db_path = tmp_path / "library.db"
    root = tmp_path / "library"
    root.mkdir()
    target = root / "track.flac"
    copy2(media_fixture_dir / "metadata.flac", target)
    run(initialize_database(str(db_path)))

    order: list[str] = []
    read_repository = LibraryRepository(str(db_path))

    class RecordingRepository(LibraryRepository):
        async def apply_scan_batch(self, batch):
            result = await super().apply_scan_batch(batch)
            order.append("commit")
            return result

    repository = RecordingRepository(str(db_path))
    observed_by_mpd: list[str] = []
    observed_by_event: list[str] = []

    class Updater:
        async def update_database(self) -> None:
            song = await read_repository.find_song_by_file_uri(str(target))
            assert song is not None
            assert song.title == "Test Song"
            observed_by_mpd.append(song.song_id or "")
            order.append("update")

    class Publisher:
        async def publish(self, event) -> None:
            assert isinstance(event, LibraryChangedEvent)
            song_id = event.result.added_song_ids[0]
            song = await read_repository.get_song(song_id)
            assert song is not None
            assert song.title == "Test Song"
            observed_by_event.append(song.song_id or "")
            order.append("publish")

    result = run(
        LibraryScanner(
            repository,
            event_publisher=Publisher(),
            mpd_updater=Updater(),
        ).scan_full(root)
    )

    assert len(result.added_song_ids) == 1
    song_id = result.added_song_ids[0]
    assert order == ["commit", "update", "publish"]
    assert observed_by_mpd == [song_id]
    assert observed_by_event == [song_id]


def test_task3_mpd_update_failure_keeps_committed_song_and_publishes_error(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    db_path = tmp_path / "library.db"
    root = tmp_path / "library"
    root.mkdir()
    target = root / "track.flac"
    copy2(media_fixture_dir / "metadata.flac", target)
    run(initialize_database(str(db_path)))

    repository = LibraryRepository(str(db_path))
    published: list[LibraryChangedEvent] = []
    update_calls: list[bool] = []

    class Updater:
        async def update_database(self) -> None:
            update_calls.append(True)
            raise RuntimeError("MPD unavailable")

    class Publisher:
        async def publish(self, event) -> None:
            assert isinstance(event, LibraryChangedEvent)
            song = await repository.find_song_by_file_uri(str(target))
            assert song is not None
            assert song.title == "Test Song"
            published.append(event)

    result = run(
        LibraryScanner(
            repository,
            event_publisher=Publisher(),
            mpd_updater=Updater(),
        ).scan_full(root)
    )

    assert len(result.added_song_ids) == 1
    assert update_calls == [True]
    assert len(published) == 1
    assert published[0].result == result
    assert published[0].mpd_update_error == "MPD unavailable"

    committed = run(repository.get_song(result.added_song_ids[0]))
    assert committed is not None
    assert committed.title == "Test Song"


def test_task3_repository_transaction_failure_blocks_mpd_and_event(
    tmp_path: Path,
    media_fixture_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "library.db"
    root = tmp_path / "library"
    root.mkdir()
    target = root / "track.flac"
    copy2(media_fixture_dir / "metadata.flac", target)
    run(initialize_database(str(db_path)))

    repository = LibraryRepository(str(db_path))
    original_upsert = repository._upsert_song
    mpd_calls: list[bool] = []
    published: list[bool] = []

    def failing_upsert(
        connection,
        song,
        song_id,
        scanned_at,
        *,
        persist_artwork=True,
    ) -> None:
        original_upsert(
            connection,
            song,
            song_id,
            scanned_at,
            persist_artwork=persist_artwork,
        )
        raise RuntimeError("db failed")

    monkeypatch.setattr(repository, "_upsert_song", failing_upsert)

    class Updater:
        async def update_database(self) -> None:
            mpd_calls.append(True)

    class Publisher:
        async def publish(self, event) -> None:
            published.append(True)

    with pytest.raises(RuntimeError, match="db failed"):
        run(
            LibraryScanner(
                repository,
                event_publisher=Publisher(),
                mpd_updater=Updater(),
            ).scan_full(root)
        )

    assert mpd_calls == []
    assert published == []

    rollback_visible = run(repository.find_song_by_file_uri(str(target)))
    assert rollback_visible is None
