"""B6-B: final full samples become committed observations without another read."""
from __future__ import annotations

import asyncio

import pytest

from server.app.repositories.database import on_transaction_commit, run_transaction
from server.tests.invariants.test_realtime_observation import setup_observation
from server.tests.support.playback import run


@pytest.mark.parametrize('operation', ['next', 'previous', 'song', 'append', 'resume', 'seek'])
def test_final_confirmation_is_available_at_commit_without_observer(real_client, operation):
    service, _, _, _, clock = setup_observation(real_client)

    async def scenario():
        await service.next()  # Prepare a Played occurrence for Previous.
        await service.pause()
        target = (await service.observe()).control_target
        wakes = []
        service.set_observation_request(lambda: wakes.append(True))
        clock.advance(1)
        if operation == 'song':
            await service.play_song_now('c')
        elif operation == 'append':
            await service.add_to_queue('c')
        elif operation == 'resume':
            await service.resume(target)
        elif operation == 'seek':
            await service.seek(7, target=target)
        else:
            await getattr(service, operation)()
        observed = await service.get_observation()
        state = await service.queue_manager.get_playback_state()
        binding = await service.get_execution_binding()
        assert observed.freshness == observed.actual_freshness == 'fresh'
        assert observed.sync_status == 'CONFIRMED' and observed.matches_current is True
        assert observed.control_target is not None
        assert observed.bound_queue_item_id == binding.entries[0][0]
        assert observed.actual_current.entry_id == binding.entries[0][1]
        assert observed.actual_state.value.upper() == state.state
        assert observed.observed_at == clock.now
        assert observed.covered_playback_updated_at == state.updated_at
        assert wakes == []
        if operation == 'seek':
            assert observed.position_seconds == 7
    run(scenario())


def test_handoff_and_control_token_roll_back_with_outer_owner(real_client):
    service, _, library, coordinator, _ = setup_observation(real_client)

    async def scenario():
        before = await service.observe()
        marker = coordinator.marker()
        wakes = []
        service.set_observation_request(lambda: wakes.append(True))

        async def rejected(_):
            await service.next()
            assert (await service.get_observation()).bound_queue_item_id != before.bound_queue_item_id
            raise RuntimeError('reject handoff')

        with pytest.raises(RuntimeError, match='reject handoff'):
            await run_transaction(library.path, rejected)
        after = await service.get_observation()
        assert after.bound_queue_item_id == before.bound_queue_item_id
        assert after.observed_at == before.observed_at
        assert after.control_target is None  # External control cannot be rolled back.
        assert coordinator.marker().sequence <= marker.sequence + 1
        assert wakes == []
    run(scenario())


def test_commit_delay_keeps_sample_time_and_falls_back_to_wakeup(real_client):
    service, _, library, _, clock = setup_observation(real_client)

    async def scenario():
        wakes = []
        service.set_observation_request(lambda: wakes.append(True))
        sampled_at = clock.now

        async def delayed(_):
            await service.next()
            clock.advance(7)

        await run_transaction(library.path, delayed)
        observed = await service.get_observation()
        assert observed.observed_at == sampled_at
        assert observed.actual_freshness == 'stale'
        assert observed.control_target is None
        assert wakes == [True]
    run(scenario())


def test_late_observer_cannot_overwrite_committed_handoff(real_client, monkeypatch):
    service, player, _, _, _ = setup_observation(real_client)
    read = player.read_execution_sample

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        old = None

        async def blocked():
            sample = await read()
            if asyncio.current_task() is old:
                entered.set()
                await release.wait()
            return sample

        monkeypatch.setattr(player, 'read_execution_sample', blocked)
        player._elapsed = 23
        old = asyncio.create_task(service.observe())
        await asyncio.wait_for(entered.wait(), 1)
        try:
            await service.next()  # Repeated URI, different occurrence.
            committed = await service.get_observation()
            assert committed.freshness == 'fresh' and committed.position_seconds == 0
        finally:
            release.set()
        assert await old == committed
        assert await service.get_observation() == committed
    run(scenario())


@pytest.mark.parametrize('mismatch', ['epoch', 'partition', 'version', 'entries', 'current', 'mode', 'error', 'expired', 'quarantine', 'player'])
def test_ineligible_complete_sample_never_publishes_a_handoff(real_client, mismatch):
    service, player, library, coordinator, clock = setup_observation(real_client)

    async def scenario():
        before = await service.observe()
        sample = await player.read_execution_sample()
        sampled_at = clock.now
        if mismatch == 'epoch':
            sample = sample.model_copy(update={'connection_epoch': 'other'})
        elif mismatch == 'partition':
            sample = sample.model_copy(update={'partition': 'other'})
        elif mismatch == 'version':
            sample = sample.model_copy(update={'playlist_version': sample.playlist_version + 1})
        elif mismatch == 'entries':
            sample = sample.model_copy(update={'entries': sample.entries[:-1]})
        elif mismatch == 'current':
            sample = sample.model_copy(update={'status': sample.status.model_copy(update={'song_id': 999})})
        elif mismatch == 'mode':
            sample = sample.model_copy(update={'single': '1'})
        elif mismatch == 'error':
            sample = sample.model_copy(update={'error': 'failed'})
        elif mismatch == 'expired':
            clock.advance(7)
            before = await service.get_observation()
        elif mismatch == 'quarantine':
            service._recovery.quarantined = True
        elif mismatch == 'player':
            # Matching IDs/URIs/epoch are insufficient if the Port owner changed
            # after the final read but before the observation handoff.
            from copy import copy

            service.player = copy(player)
            service._observations._confirmed_identity = await service._observations._identity()
        marker = coordinator.marker()
        accepted = await run_transaction(library.path, lambda _: service._observations.handoff(sample, sampled_at, player))
        assert accepted is False
        assert await service.get_observation() == before
        assert coordinator.marker() == marker
    run(scenario())


@pytest.mark.parametrize('failure', ['commit', 'cancel'])
def test_failed_commit_never_exposes_handoff_or_new_token(real_client, monkeypatch, failure):
    import sqlite3

    from server.app.repositories import database

    service, _, library, coordinator, _ = setup_observation(real_client)

    async def scenario():
        before = await service.observe()
        marker = coordinator.marker()
        wakes = []
        service.set_observation_request(lambda: wakes.append(True))

        class RejectCommit(sqlite3.Connection):
            def commit(self):
                raise sqlite3.OperationalError('reject handoff commit')

        async def outer(_):
            await service.next()
            assert (await service.get_observation()).bound_queue_item_id != before.bound_queue_item_id
            if failure == 'cancel':
                raise asyncio.CancelledError()

        with monkeypatch.context() as patch:
            if failure == 'commit':
                patch.setattr(database, '_connect', lambda path: sqlite3.connect(path, factory=RejectCommit))
            with pytest.raises(sqlite3.OperationalError if failure == 'commit' else asyncio.CancelledError):
                await run_transaction(library.path, outer)
        assert coordinator.marker() == marker
        after = await service.get_observation()
        assert after == before.model_copy(update={'control_target': None})
        assert wakes == []
    run(scenario())


def test_first_committed_snapshot_has_handoff_before_async_delivery(real_client):
    from server.app.main import app
    from server.app.models.output import OutputSnapshot
    from server.app.services.state_service import StateService

    service, _, library, coordinator, _ = setup_observation(real_client)
    state = StateService(
        coordinator=coordinator, queue_manager=service.queue_manager,
        history_service=service.history_service, library_service=app.state.library_service,
        output_snapshot=lambda: OutputSnapshot(states=()), playback_service=service,
    )

    async def scenario():
        before = await state.get_full_snapshot()
        staged, commit, delivering, finish = (asyncio.Event() for _ in range(4))

        async def delivery():
            delivering.set()
            await finish.wait()

        async def outer(_):
            on_transaction_commit(library.path, delivery)
            await service.next()
            staged.set()
            await commit.wait()

        writer = asyncio.create_task(run_transaction(library.path, outer))
        try:
            await asyncio.wait_for(staged.wait(), 1)
            assert coordinator.marker().sequence == before.sequence
            commit.set()
            await asyncio.wait_for(delivering.wait(), 1)
            snapshot = await asyncio.wait_for(state.get_full_snapshot(), 1)
            assert not writer.done()
            assert snapshot.sequence > before.sequence
            assert snapshot.playback_observation.sync_status == 'CONFIRMED'
            assert snapshot.playback_observation.covered_playback_updated_at == snapshot.playback.updated_at
            current = next(item for item in snapshot.queue.items if item.position == 0)
            assert snapshot.playback_observation.control_target.queue_item_id == current.queue_item_id
            assert current.queue_item_id != before.playback_observation.bound_queue_item_id
        finally:
            commit.set()
            finish.set()
            await writer
    run(scenario())
