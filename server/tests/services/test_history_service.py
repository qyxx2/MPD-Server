from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from server.app.models.library import Song
from server.app.repositories.database import initialize_database
from server.app.repositories.history_repository import HistoryRepository
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.queue_repository import QueueRepository
from server.app.services.history_service import HistoryService


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def components(tmp_path):
    path = str(tmp_path / "history.db")
    run(initialize_database(path))

    library = LibraryRepository(path)
    queue = QueueRepository(path)
    history = HistoryRepository(path)

    for song_id in "abcd":
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

    return queue, history, HistoryService(queue, history)


def test_played_view_and_persistent_history_are_independent(components):
    queue, history, service = components
    started_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    switched_at = datetime(2026, 1, 1, 10, 3, tzinfo=timezone.utc)

    run(queue.start_track("a", playback_context_id="context-a"))
    run(service.start_track("a", started_at=started_at, session_id="session-1"))

    item_b = run(
        queue.add_to_queue(
            "b",
            playback_context_id="context-a",
        )
    )
    run(queue.play_now(item_b.queue_item_id))
    run(service.start_track("b", started_at=switched_at))

    played = run(service.list_played())
    persistent = run(service.list_history())

    assert [item.song_id for item in played] == ["a"]
    assert len(persistent) == 1
    assert persistent[0].song_id == "a"
    assert persistent[0].started_at == started_at
    assert persistent[0].ended_at == switched_at
    assert persistent[0].reason == HistoryService.SWITCH_AWAY
    assert persistent[0].session_id == "session-1"

    run(queue.delete_item(played[0].queue_item_id))

    assert run(service.list_played()) == []
    assert len(run(service.list_history())) == 1


def test_persistent_history_does_not_create_a_played_queue_entry(components):
    queue, history, service = components
    started_at = datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc)
    ended_at = datetime(2026, 1, 1, 11, 4, tzinfo=timezone.utc)

    run(service.start_track("c", started_at=started_at, session_id="session-2"))
    run(service.complete_naturally(ended_at=ended_at))

    assert run(service.list_played()) == []

    entries = run(history.list_history())
    assert len(entries) == 1
    assert entries[0].song_id == "c"
    assert entries[0].reason == HistoryService.NATURAL_COMPLETION
    assert entries[0].started_at == started_at
    assert entries[0].ended_at == ended_at
    assert entries[0].session_id == "session-2"


@pytest.mark.parametrize(
    ("finalizer", "expected_reason"),
    [
        ("complete_naturally", HistoryService.NATURAL_COMPLETION),
        ("skip", HistoryService.SKIP),
        ("stop", HistoryService.STOP),
        ("switch_away", HistoryService.SWITCH_AWAY),
    ],
)
def test_playback_end_reason_is_recorded_distinctly(
    components,
    finalizer,
    expected_reason,
):
    _, _, service = components
    started_at = datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc)
    ended_at = datetime(2026, 1, 2, 9, 5, tzinfo=timezone.utc)

    run(service.start_track("a", started_at=started_at, session_id="session-3"))
    recorded = run(getattr(service, finalizer)(ended_at=ended_at))

    assert recorded is not None
    assert recorded.reason == expected_reason
    assert recorded.song_id == "a"
    assert recorded.started_at == started_at
    assert recorded.ended_at == ended_at
    assert recorded.session_id == "session-3"


def test_stop_ends_the_session_before_the_next_track(components):
    _, _, service = components
    first_start = datetime(2026, 1, 3, 12, 0, tzinfo=timezone.utc)
    stop_at = datetime(2026, 1, 3, 12, 2, tzinfo=timezone.utc)
    second_start = datetime(2026, 1, 3, 13, 0, tzinfo=timezone.utc)

    run(service.start_track("a", started_at=first_start, session_id="session-4"))
    run(service.stop(ended_at=stop_at))
    assert service.session_id is None

    second = run(service.start_track("b", started_at=second_start))

    assert second.session_id is not None
    assert second.session_id != "session-4"


def test_starting_another_track_records_the_previous_track_as_switch_away(
    components,
):
    _, history, service = components
    first_start = datetime(2026, 1, 4, 15, 0, tzinfo=timezone.utc)
    second_start = datetime(2026, 1, 4, 15, 2, tzinfo=timezone.utc)

    first = run(service.start_track("a", started_at=first_start, session_id="session-5"))
    second = run(service.start_track("b", started_at=second_start))

    assert first.ended_at is None
    assert second.ended_at is None
    assert second.session_id == "session-5"

    entries = run(history.list_history())
    assert len(entries) == 1
    assert entries[0].song_id == "a"
    assert entries[0].reason == HistoryService.SWITCH_AWAY
    assert entries[0].ended_at == second_start
