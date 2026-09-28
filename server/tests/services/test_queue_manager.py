from __future__ import annotations

import asyncio

import pytest

from server.app.models.library import Song
from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playback_state_repository import PlaybackStateRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.repositories.queue_repository import (
    CurrentTrackDeletionError,
    QueueRepository,
)
from server.app.services.queue_manager import QueueManager


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def components(tmp_path):
    path = str(tmp_path / "queue.db")
    run(initialize_database(path))
    library = LibraryRepository(path)
    queue = QueueRepository(path)
    playback_state = PlaybackStateRepository(path)
    playlists = PlaylistRepository(path)
    manager = QueueManager(queue, playback_state, playlists)

    for song_id in "abcdef":
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

    return manager, queue, playback_state, playlists


def current_item(queue):
    items = [item for item in run(queue.list_items()) if item.position == 0]
    assert len(items) == 1
    return items[0]


def played_song_ids(queue) -> list[str]:
    return [
        item.song_id
        for item in run(queue.list_items())
        if item.position < 0
    ]


def up_next_song_ids(queue) -> list[str]:
    return [
        item.song_id
        for item in run(queue.list_up_next())
    ]


def test_start_track_replaces_pending_up_next_and_creates_playback_context(
    components,
):
    manager, queue, state, _ = components

    first_context = run(manager.start_track("a"))
    run(manager.add_to_queue("b"))
    run(manager.add_to_queue("c"))

    second_context = run(manager.start_track("d"))

    assert first_context.source_type == "TRACK"
    assert first_context.source_id == "a"
    assert first_context.ordered_song_ids == ("a",)
    assert second_context.context_id != first_context.context_id
    assert second_context.source_type == "TRACK"
    assert second_context.source_id == "d"
    assert second_context.ordered_song_ids == ("d",)
    assert current_item(queue).song_id == "d"
    assert up_next_song_ids(queue) == []
    assert played_song_ids(queue) == ["a"]

    playback = run(state.get_state())
    assert playback is not None
    assert playback.song_id == "d"
    assert playback.state == "PLAYING"
    assert playback.playback_context_id == second_context.context_id
    assert playback.autoplay_enabled is True


def test_queue_play_now_preserves_prior_pending_items_after_selected_song(
    components,
):
    manager, queue, state, _ = components

    context = run(manager.start_track("a"))
    run(manager.add_to_queue("b"))
    item_c = run(manager.add_to_queue("c"))
    run(manager.add_to_queue("d"))

    selected = run(manager.play_now(item_c.queue_item_id))

    assert selected.song_id == "c"
    assert selected.position == 0
    assert selected.source == "MANUAL"
    assert current_item(queue).queue_item_id == item_c.queue_item_id
    assert up_next_song_ids(queue) == ["b", "d"]
    assert played_song_ids(queue) == ["a"]

    playback = run(state.get_state())
    assert playback is not None
    assert playback.song_id == "c"
    assert playback.playback_context_id == context.context_id


def test_play_next_inserts_immediately_after_current_and_add_to_queue_appends(
    components,
):
    manager, queue, state, _ = components

    context = run(manager.start_track("a"))
    first = run(manager.add_to_queue("b"))
    next_item = run(manager.play_next("c"))
    appended = run(manager.add_to_queue("d"))

    assert next_item.source == "MANUAL"
    assert next_item.position == 1
    assert next_item.playback_context_id == context.context_id
    assert appended.playback_context_id == context.context_id
    assert first.position != appended.position
    assert up_next_song_ids(queue) == ["c", "b", "d"]
    assert run(state.get_state()).playback_context_id == context.context_id


def test_reorder_changes_only_up_next_order(components):
    manager, queue, _, _ = components

    run(manager.start_track("a"))
    item_b = run(manager.add_to_queue("b"))
    run(manager.add_to_queue("c"))
    item_d = run(manager.add_to_queue("d"))

    run(manager.reorder(item_d.queue_item_id, item_b.queue_item_id))

    assert current_item(queue).song_id == "a"
    assert up_next_song_ids(queue) == ["d", "b", "c"]


def test_delete_up_next_compacts_order_without_touching_current(components):
    manager, queue, _, _ = components

    run(manager.start_track("a"))
    run(manager.add_to_queue("b"))
    item_c = run(manager.add_to_queue("c"))
    run(manager.add_to_queue("d"))

    run(manager.delete(item_c.queue_item_id))

    assert current_item(queue).song_id == "a"
    assert up_next_song_ids(queue) == ["b", "d"]


def test_delete_current_promotes_next_and_keeps_previous_current_in_played(
    components,
):
    manager, queue, state, _ = components

    run(manager.start_track("a"))
    item_b = run(manager.add_to_queue("b"))
    run(manager.add_to_queue("c"))

    promoted = run(manager.delete(current_item(queue).queue_item_id))

    assert promoted is not None
    assert promoted.queue_item_id == item_b.queue_item_id
    assert current_item(queue).song_id == "b"
    assert up_next_song_ids(queue) == ["c"]
    assert played_song_ids(queue) == ["a"]

    playback = run(state.get_state())
    assert playback is not None
    assert playback.song_id == "b"
    assert playback.state == "PLAYING"
    assert playback.playback_context_id == promoted.playback_context_id


def test_delete_current_without_successor_is_rejected_without_mutation(components):
    manager, queue, state, _ = components

    run(manager.start_track("a"))
    before = [
        (item.queue_item_id, item.song_id, item.position)
        for item in run(queue.list_items())
    ]
    before_state = run(state.get_state())

    with pytest.raises(CurrentTrackDeletionError):
        run(manager.delete(current_item(queue).queue_item_id))

    after = [
        (item.queue_item_id, item.song_id, item.position)
        for item in run(queue.list_items())
    ]
    assert after == before
    assert run(state.get_state()) == before_state


def test_clear_removes_only_up_next(components):
    manager, queue, _, _ = components

    run(manager.start_track("a"))
    run(manager.add_to_queue("b"))
    item_c = run(manager.add_to_queue("c"))
    run(manager.play_now(item_c.queue_item_id))
    run(manager.add_to_queue("d"))

    run(manager.clear())

    assert current_item(queue).song_id == "c"
    assert played_song_ids(queue) == ["a"]
    assert up_next_song_ids(queue) == []


def test_save_as_playlist_contains_only_up_next_and_does_not_change_queue(
    components,
):
    manager, queue, state, playlists = components

    context = run(manager.start_track("a"))
    item_b = run(manager.add_to_queue("b"))
    item_c = run(manager.add_to_queue("c"))
    run(manager.play_now(item_c.queue_item_id))
    before_queue = [
        (item.queue_item_id, item.song_id, item.position, item.source)
        for item in run(queue.list_items())
    ]
    before_state = run(state.get_state())

    playlist = run(manager.save_as_playlist("Queue snapshot"))

    assert run(playlists.list_song_ids(playlist.playlist_id)) == ["b"]
    assert [
        (item.queue_item_id, item.song_id, item.position, item.source)
        for item in run(queue.list_items())
    ] == before_queue
    assert run(state.get_state()) == before_state
    assert before_state is not None
    assert before_state.playback_context_id == context.context_id
    assert item_b.song_id == "b"
