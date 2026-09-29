from __future__ import annotations

import asyncio

import pytest

from server.app.models.library import Song
from server.app.models.queue import PlaybackContext
from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playback_state_repository import PlaybackStateRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.repositories.queue_repository import QueueRepository
from server.app.services.autoplay import AutoPlay
from server.app.services.queue_manager import QueueManager


def run(coro):
    return asyncio.run(coro)


def make_song(song_id: str) -> Song:
    return Song(
        song_id=song_id,
        title=f"Track {song_id}",
        file_uri=f"music/{song_id}.mp3",
        identity_key=f"identity-{song_id}",
    )


@pytest.fixture
def components(tmp_path):
    path = str(tmp_path / "autoplay.db")
    run(initialize_database(path))
    library = LibraryRepository(path)
    queue = QueueRepository(path)
    state = PlaybackStateRepository(path)
    playlists = PlaylistRepository(path)
    manager = QueueManager(queue, state, playlists)
    return library, queue, manager


def seed_songs(library: LibraryRepository, *song_ids: str) -> None:
    for song_id in song_ids:
        run(library.upsert_song(make_song(song_id)))


def current_context(song_id: str = "a") -> PlaybackContext:
    return PlaybackContext(
        context_id=f"context-{song_id}",
        source_type="TRACK",
        source_id=song_id,
        ordered_song_ids=(song_id,),
    )


def up_next(queue: QueueRepository):
    return run(queue.list_up_next())


def test_autoplay_refill_uses_playback_context_before_global_available_candidates(
    components,
):
    library, queue, manager = components
    seed_songs(library, "a", "b", "c", "d", "e", "f", "g")
    started_context = run(manager.start_track("a"))

    context = PlaybackContext(
        context_id=started_context.context_id,
        source_type="ALBUM",
        source_id="album-1",
        ordered_song_ids=("d", "c", "b"),
    )

    generated = run(AutoPlay(queue, library).refill(context))

    assert [item.song_id for item in generated] == ["d", "c", "b", "e", "f"]
    assert all(item.source == "AUTOPLAY" for item in generated)
    assert all(
        item.playback_context_id == context.context_id for item in generated
    )
    assert [item.song_id for item in up_next(queue)] == ["d", "c", "b", "e", "f"]


def test_autoplay_does_nothing_when_up_next_is_at_low_watermark(components):
    library, queue, manager = components
    seed_songs(library, "a", "b", "c", "d", "e", "f", "g")
    context = run(manager.start_track("a"))
    for song_id in "bcdef":
        run(manager.add_to_queue(song_id))

    generated = run(AutoPlay(queue, library).refill(context))

    assert generated == []
    assert [item.song_id for item in up_next(queue)] == list("bcdef")


def test_autoplay_refills_five_when_up_next_is_below_low_watermark(components):
    library, queue, manager = components
    seed_songs(library, "a", "b", "c", "d", "e", "f", "g", "h", "i")
    context = run(manager.start_track("a"))
    for song_id in "bc":
        run(manager.add_to_queue(song_id))

    generated = run(AutoPlay(queue, library).refill(context))

    assert len(generated) == 5
    assert [item.song_id for item in generated] == ["d", "e", "f", "g", "h"]
    assert [item.song_id for item in up_next(queue)] == [
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
    ]


def test_autoplay_never_removes_or_reorders_manual_items(components):
    library, queue, manager = components
    seed_songs(library, "a", "b", "c", "d", "e", "f", "g", "h")
    context = run(manager.start_track("a"))
    manual_b = run(manager.add_to_queue("b"))
    manual_c = run(manager.play_next("c"))

    generated = run(AutoPlay(queue, library).refill(context))

    items = up_next(queue)
    assert [(item.song_id, item.source) for item in items[:2]] == [
        ("c", "MANUAL"),
        ("b", "MANUAL"),
    ]
    assert all(item.source == "AUTOPLAY" for item in generated)
    assert [item.song_id for item in generated] == [
        "d",
        "e",
        "f",
        "g",
        "h",
    ]
    assert items[0].position != items[1].position
    assert all(
        item.source != "MANUAL"
        or item.queue_item_id in {manual_b.queue_item_id, manual_c.queue_item_id}
        for item in items
    )


def test_autoplay_empty_library_returns_no_items(components):
    library, queue, _manager = components
    generated = run(AutoPlay(queue, library).refill(current_context()))

    assert generated == []
    assert up_next(queue) == []


def test_autoplay_one_song_library_reuses_only_available_song_when_needed(components):
    library, queue, manager = components
    seed_songs(library, "a")
    context = run(manager.start_track("a"))

    generated = run(AutoPlay(queue, library).refill(context))

    assert len(generated) == 1
    assert generated[0].song_id == "a"
    assert generated[0].source == "AUTOPLAY"


def test_autoplay_insufficient_candidates_does_not_duplicate_within_batch(components):
    library, queue, manager = components
    seed_songs(library, "a", "b", "c")
    context = run(manager.start_track("a"))

    generated = run(AutoPlay(queue, library).refill(context))

    assert [item.song_id for item in generated] == ["b", "c"]
    assert len({item.song_id for item in generated}) == len(generated)
    assert all(item.source == "AUTOPLAY" for item in generated)


class CoordinatedQueueRepository(QueueRepository):
    def __init__(
        self,
        path: str,
        first_autoplay_started: asyncio.Event,
        release_first_autoplay: asyncio.Event,
    ) -> None:
        super().__init__(path)
        self.first_autoplay_started = first_autoplay_started
        self.release_first_autoplay = release_first_autoplay
        self.autoplay_attempts = 0

    async def add_autoplay_batch(
        self,
        song_ids: list[str],
        *,
        playback_context_id: str | None = None,
        max_items: int = 5,
        allow_current_repeat: bool = False,
        expected_revision: int | None = None,
    ):
        self.autoplay_attempts += 1
        if self.autoplay_attempts == 1:
            self.first_autoplay_started.set()
            await self.release_first_autoplay.wait()
        return await super().add_autoplay_batch(
            song_ids,
            playback_context_id=playback_context_id,
            max_items=max_items,
            allow_current_repeat=allow_current_repeat,
            expected_revision=expected_revision,
        )


def test_autoplay_preserves_manual_queue_mutation_during_refill(components):
    library, _queue, _manager = components
    seed_songs(library, "a", "b", "c", "d", "e", "f", "g", "h", "i", "j")
    path = library.path
    started = asyncio.Event()
    release = asyncio.Event()
    queue = CoordinatedQueueRepository(path, started, release)
    state = PlaybackStateRepository(path)
    playlists = PlaylistRepository(path)
    manager = QueueManager(queue, state, playlists)
    context = run(manager.start_track("a"))

    async def exercise():
        autoplay = AutoPlay(queue, library, state)
        task = asyncio.create_task(autoplay.refill(context))
        await started.wait()
        manual = await queue.add_to_queue(
            "j",
            playback_context_id="context-a",
            source="MANUAL",
        )
        release.set()
        generated = await task
        return manual, generated, await queue.list_up_next()

    manual, generated, items = run(exercise())

    assert manual.source == "MANUAL"
    assert [item.song_id for item in generated] == ["b", "c", "d", "e", "f"]
    assert [item.song_id for item in items] == ["j", "b", "c", "d", "e", "f"]
    assert items[0].source == "MANUAL"



def test_autoplay_aborts_when_playback_context_changes_during_refill(components):
    library, _queue, _manager = components
    seed_songs(library, "a", "b", "c", "d", "e", "f", "g")
    path = library.path
    started = asyncio.Event()
    release = asyncio.Event()
    queue = CoordinatedQueueRepository(path, started, release)
    state = PlaybackStateRepository(path)
    playlists = PlaylistRepository(path)
    manager = QueueManager(queue, state, playlists)
    old_context = run(manager.start_track("a"))

    async def exercise():
        autoplay = AutoPlay(queue, library, state)
        task = asyncio.create_task(autoplay.refill(old_context))
        await started.wait()
        new_context = await queue.start_track(
            "g",
            playback_context_id="context-g",
        )
        release.set()
        generated = await task
        return new_context, generated, await queue.list_items()

    new_context, generated, items = run(exercise())

    assert new_context.song_id == "g"
    assert generated == []
    items_by_song = {item.song_id: item for item in items}
    assert (
        items_by_song["g"].position,
        items_by_song["g"].playback_context_id,
    ) == (0, "context-g")
    assert (
        items_by_song["a"].position,
        items_by_song["a"].playback_context_id,
    ) == (-1, old_context.context_id)


def test_autoplay_does_not_refill_after_stop(components):
    library, queue, manager = components
    seed_songs(library, "a", "b", "c")
    context = run(manager.start_track("a"))
    run(manager.stop())

    generated = run(
        AutoPlay(queue, library, manager.playback_state_repository).refill(
            context
        )
    )

    assert generated == []
    assert up_next(queue) == []


def test_queue_exhaustion_does_not_turn_playback_terminal(components):
    library, queue, manager = components
    seed_songs(library, "a", "b", "c", "d")
    context = run(manager.start_track("a"))
    run(queue.clear_pending())

    before = run(manager.playback_state_repository.get_state())
    assert before is not None
    assert before.state == "PLAYING"
    assert before.autoplay_enabled is True

    generated = run(
        AutoPlay(queue, library, manager.playback_state_repository).refill(context)
    )

    after = run(manager.playback_state_repository.get_state())
    assert after == before
    assert [item.song_id for item in generated] == ["b", "c", "d"]
    assert after.state != "STOPPED"
