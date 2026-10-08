from __future__ import annotations

import pytest

from server.app.main import app
from server.app.models.library import Song
from server.app.services.playback_service import PlaybackService
from server.app.services.state_service import StateService
from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_d6_autoplay import prepare, seed_candidates
from server.tests.invariants.test_d6_recovery import capture_controls
from server.tests.invariants.test_realtime_observation import setup_observation
from server.tests.invariants.test_realtime_snapshot import cached_output
from server.tests.support.playback import run


def test_actual_identity_is_separate_from_persisted_current(real_client, monkeypatch):
    """A fresh foreign MPD entry must not replace the committed business Song."""
    playback, player, _, coordinator, _ = setup_observation(real_client)
    run(playback.observe())
    before = server_snapshot(playback)
    output = cached_output(playback, player)

    foreign_id = run(player.queue_add("d.flac"))
    run(player.queue_play(foreign_id))

    async def forbidden(*args, **kwargs):
        raise AssertionError("read-only actual-state propagation performed control or recovery")

    for name in (
        "play",
        "pause",
        "stop",
        "next",
        "previous",
        "seek",
        "queue_add",
        "queue_delete",
        "queue_move",
        "queue_clear",
        "queue_play",
    ):
        monkeypatch.setattr(player, name, forbidden)
    monkeypatch.setattr(playback, "reconcile_external_status", forbidden)
    monkeypatch.setattr(playback, "maintain_execution", forbidden)

    observed = run(playback.observe())
    state = StateService(
        coordinator=coordinator,
        queue_manager=playback.queue_manager,
        history_service=playback.history_service,
        library_service=app.state.library_service,
        output_snapshot=lambda: output,
        playback_service=playback,
    )
    snapshot = run(state.get_full_snapshot())

    assert snapshot.current_song.song_id == "a"
    assert snapshot.playback.song_id == "a"
    assert snapshot.playback_observation == observed
    assert observed.actual_current.model_dump() == {
        "entry_id": foreign_id,
        "uri": "d.flac",
        "position": len(player._queue) - 1,
    }
    assert observed.actual_freshness == "fresh"
    assert observed.bound_queue_item_id is None
    assert observed.sync_status == "EXTERNAL_DRIFT"
    assert observed.matches_current is False
    assert observed.position_seconds is None
    assert server_snapshot(playback) == before


@pytest.mark.parametrize("diagnostic", ["NO_CANDIDATES", "SYNC_FAILED"])
def test_maintenance_diagnostic_is_exposed_without_read_side_effects(
    real_client, monkeypatch, diagnostic,
):
    """The last owned maintenance result is representation state, not read-time recovery."""
    player, playback = prepare(real_client)
    run(playback.observe())
    if diagnostic == "NO_CANDIDATES":
        for song in run(playback.library_repository.list_available_songs()):
            run(playback.library_repository.upsert_song(
                song.model_copy(update={"availability_status": "MISSING"}),
            ))
    else:
        seed_candidates(player, playback)
        read = player.read_execution_sample

        async def errored():
            return (await read()).model_copy(update={"error": "decoder error"})

        monkeypatch.setattr(player, "read_execution_sample", errored)

    controls = capture_controls(monkeypatch, player)
    result = run(playback.maintain_execution())
    maintain = playback.maintain_execution
    prefix = list(controls)
    before = server_snapshot(playback)

    async def forbidden(*args, **kwargs):
        raise AssertionError("observation read retried maintenance or controlled MPD")

    monkeypatch.setattr(playback, "maintain_execution", forbidden)
    observation = run(playback.get_observation())

    assert result.diagnostic == diagnostic
    assert observation.sync_status == diagnostic
    assert observation.reconciliation_required is (diagnostic == "SYNC_FAILED")
    assert list(controls) == prefix
    assert server_snapshot(playback) == before
    assert run(playback.observe()).sync_status == diagnostic

    if diagnostic == "NO_CANDIDATES":
        seed_candidates(player, playback)
        completed = run(maintain())
        assert completed.diagnostic is None
        assert run(playback.get_observation()).sync_status == "CONFIRMED"


def test_empty_actual_sample_becomes_stale_after_disconnect(real_client):
    """A confirmed empty MPD sample remains known-but-stale after transport loss."""
    playback, player, _, _, _ = setup_observation(real_client)
    before = server_snapshot(playback)
    run(player.queue_clear())

    empty = run(playback.observe())
    assert empty.actual_current is None
    assert empty.actual_freshness == "fresh"
    assert empty.observed_at is not None

    player.disconnect()
    stale = run(playback.observe())
    assert stale.actual_current is None
    assert stale.actual_freshness == "stale"
    assert stale.observed_at == empty.observed_at
    assert server_snapshot(playback) == before


def test_unbound_actual_freshness_expires_and_registers_sequence(real_client):
    """Actual identity age is independent from the legacy bound-progress freshness."""
    playback, player, _, coordinator, clock = setup_observation(real_client)
    run(playback.observe())
    foreign_id = run(player.queue_add("d.flac"))
    run(player.queue_play(foreign_id))
    fresh = run(playback.observe())
    assert fresh.freshness == "unknown"
    assert fresh.actual_freshness == "fresh"
    marker = coordinator.marker()

    clock.advance(6.01)
    stale = run(playback.get_observation())
    assert stale.freshness == "unknown"
    assert stale.actual_freshness == "stale"
    assert stale.actual_current == fresh.actual_current
    assert stale.sync_status == "UNBOUND"
    assert coordinator.marker().sequence == marker.sequence + 1


@pytest.mark.parametrize("restart", ["none", "mpd", "service", "foreign"])
def test_only_owned_stop_continuity_is_confirmed(real_client, restart):
    """Persisted STOPPED plus a stopped sample cannot prove a post-restart binding."""
    playback, player, library, coordinator, clock = setup_observation(real_client)
    run(playback.observe())
    run(playback.stop())

    if restart == "mpd":
        player.reconnect()
    elif restart == "service":
        playback = PlaybackService(
            queue_manager=playback.queue_manager,
            history_service=playback.history_service,
            autoplay=playback.autoplay,
            player=player,
            library_repository=library,
            coordinator=coordinator,
            observation_clock=clock,
        )
    elif restart == "foreign":
        foreign_id = run(player.queue_add("d.flac"))
        run(player.queue_play(foreign_id))
        run(player.stop())

    observed = run(playback.observe())
    expected = "CONFIRMED" if restart == "none" else "UNBOUND"
    assert observed.sync_status == expected
    assert observed.reconciliation_required is (restart != "none")


def test_late_maintenance_diagnostic_cannot_overwrite_new_current_generation(
    real_client, monkeypatch,
):
    """A committed Stop between maintenance and diagnostic publication wins."""
    _, playback = prepare(real_client)
    run(playback.observe())
    for song in run(playback.library_repository.list_available_songs()):
        run(playback.library_repository.upsert_song(
            song.model_copy(update={"availability_status": "MISSING"}),
        ))
    plan = playback.autoplay.plan_refill

    async def scenario():
        import asyncio

        from server.app.repositories.database import on_transaction_commit

        committed = asyncio.Event()
        release = asyncio.Event()

        async def barrier():
            committed.set()
            await release.wait()

        async def plan_with_post_commit_barrier(context, snapshot):
            result = await plan(context, snapshot)
            on_transaction_commit(playback._recovery.path, barrier)
            return result

        monkeypatch.setattr(playback.autoplay, "plan_refill", plan_with_post_commit_barrier)
        maintenance = asyncio.create_task(playback.maintain_execution())
        await asyncio.wait_for(committed.wait(), 1)
        await asyncio.wait_for(playback.stop(), 1)
        release.set()
        result = await asyncio.wait_for(maintenance, 1)
        return result, await playback.get_observation()

    result, observation = run(scenario())

    assert result.diagnostic == "NO_CANDIDATES"
    assert run(playback.queue_manager.get_playback_state()).state == "STOPPED"
    assert observation.sync_status == "UNBOUND"


def test_late_maintenance_diagnostic_cannot_overwrite_newer_refill(
    real_client, monkeypatch,
):
    """A delayed older maintenance result cannot replace a newer committed result."""
    player, playback = prepare(real_client)
    run(playback.observe())
    for song in run(playback.library_repository.list_available_songs()):
        run(playback.library_repository.upsert_song(
            song.model_copy(update={"availability_status": "MISSING"}),
        ))
    plan = playback.autoplay.plan_refill

    async def scenario():
        import asyncio

        from server.app.repositories.database import on_transaction_commit

        committed = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        async def barrier():
            committed.set()
            await release.wait()

        async def plan_with_first_post_commit_barrier(context, snapshot):
            nonlocal calls
            calls += 1
            result = await plan(context, snapshot)
            if calls == 1:
                on_transaction_commit(playback._recovery.path, barrier)
            return result

        monkeypatch.setattr(
            playback.autoplay, "plan_refill", plan_with_first_post_commit_barrier,
        )
        older = asyncio.create_task(playback.maintain_execution())
        await asyncio.wait_for(committed.wait(), 1)
        for song_id in "ghijklmn":
            await playback.library_repository.upsert_song(Song(
                song_id=song_id, title=song_id, file_uri=f"{song_id}.flac",
            ))
            player._songs.append(f"{song_id}.flac")
            player._durations[f"{song_id}.flac"] = 180
        newer = await asyncio.wait_for(playback.maintain_execution(), 1)
        before_release = await playback.get_observation()
        release.set()
        older_result = await asyncio.wait_for(older, 1)
        return older_result, newer, before_release, await playback.get_observation()

    older, newer, before_release, final = run(scenario())

    assert older.diagnostic == "NO_CANDIDATES"
    assert newer.outcome == "APPLIED"
    assert newer.diagnostic is None
    assert before_release.sync_status == "CONFIRMED"
    assert final.sync_status == "CONFIRMED"
