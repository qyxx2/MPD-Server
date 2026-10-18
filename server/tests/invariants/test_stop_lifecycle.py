from __future__ import annotations

import asyncio
import sqlite3

import pytest

from server.app.api.realtime_schemas import FullStateSnapshotResponse
from server.app.main import app
from server.app.repositories import database
from server.app.repositories.database import run_transaction
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.app.services.state_service import StateService
from server.tests.invariants.test_realtime_snapshot import cached_output
from server.tests.support.playback import mutate, run, start


def capture(real_client):
    _, library, player, service = real_client
    coordinator = RealtimeCoordinator(library.path)
    service._coordinator = coordinator
    output = cached_output(service, player)
    state = StateService(coordinator=coordinator, queue_manager=service.queue_manager,
                         history_service=service.history_service,
                         library_service=app.state.library_service,
                         output_snapshot=lambda: output,
                         playback_service=service)
    return state, coordinator


def payload(state):
    return FullStateSnapshotResponse.model_validate(
        run(state.get_full_snapshot()).model_dump()).model_dump(mode='json')


def test_stop_generation_survives_start_and_terminal_replay(real_client):
    client, _, _, service = real_client
    start(client)
    state, coordinator = capture(real_client)
    assert payload(state).get('explicit_stop_generation') == 0
    response = mutate(client, 'POST', '/api/playback/stop', key='stop-once')
    assert response.status_code == 200, response.text
    assert payload(state)['explicit_stop_generation'] == 1
    run(service.play_song_now('b'))
    combined = payload(state)
    assert combined['explicit_stop_generation'] == 1
    assert combined['playback']['state'] == 'PLAYING'
    marker = coordinator.marker()
    assert mutate(client, 'POST', '/api/playback/stop', key='stop-once').json() == response.json()
    assert payload(state)['explicit_stop_generation'] == 1
    assert coordinator.marker() == marker
    assert mutate(client, 'POST', '/api/playback/stop', key='stop-new').status_code == 200
    subscriber = coordinator.subscribe()
    # A fresh Stop intent while already stopped still has observable provenance.
    assert mutate(client, 'POST', '/api/playback/stop', key='stop-again').status_code == 200
    assert payload(state)['explicit_stop_generation'] == 3
    assert 'playback' in subscriber.pending.domains


def test_unknown_stop_and_session_end_do_not_certify_user_stop(real_client):
    client, _, player, service = real_client
    start(client)
    state, _ = capture(real_client)
    run(player.stop())
    run(service.observe())
    assert payload(state).get('explicit_stop_generation') == 0
    run(service.play_song_now('b'))
    # Ending History is deliberately independent of user Stop provenance.
    run(service.history_service.stop())
    assert payload(state)['history']['session_id'] is None
    assert payload(state)['explicit_stop_generation'] == 0


def test_stop_counter_is_hidden_until_outer_commit_and_restored_on_rollback(real_client):
    client, _, _, service = real_client
    start(client)
    state, coordinator = capture(real_client)
    assert payload(state).get('explicit_stop_generation') == 0

    async def scenario():
        staged, release = asyncio.Event(), asyncio.Event()
        async def outer(_):
            await service.stop()
            staged.set()
            await release.wait()
            raise RuntimeError('outer rollback')
        task = asyncio.create_task(run_transaction(service.queue_manager.queue_repository.path, outer))
        await staged.wait()
        reader = asyncio.create_task(state.get_full_snapshot())
        await asyncio.sleep(0)
        assert not reader.done()
        release.set()
        with pytest.raises(RuntimeError, match='outer rollback'):
            await task
        snapshot = await reader
        assert snapshot.explicit_stop_generation == 0
    run(scenario())
    assert payload(state)['explicit_stop_generation'] == 0
    assert coordinator.marker().sequence >= 0
    run(service.stop())
    assert payload(state)['explicit_stop_generation'] == 1


@pytest.mark.parametrize('failure', ['command', 'terminal', 'commit'])
def test_failed_stop_never_publishes_generation(real_client, monkeypatch, failure):
    client, library, player, _service = real_client
    start(client)
    state, coordinator = capture(real_client)
    assert payload(state).get('explicit_stop_generation') == 0
    subscriber = coordinator.subscribe()
    original_connect = database._connect
    if failure == 'command':
        player.fail_next('stop')
    elif failure == 'terminal':
        with sqlite3.connect(library.path) as connection:
            connection.executescript("CREATE TRIGGER fail_stop_terminal BEFORE INSERT ON idempotency_records BEGIN SELECT RAISE(ABORT, 'stop terminal'); END;")
    else:
        class RejectCommit(sqlite3.Connection):
            def commit(self):
                raise sqlite3.OperationalError('stop commit')
        monkeypatch.setattr(database, '_connect', lambda path: sqlite3.connect(path, factory=RejectCommit))
    if failure == 'command':
        response = mutate(client, 'POST', '/api/playback/stop', key='failed-stop')
        assert response.status_code == 502
    else:
        with pytest.raises(sqlite3.DatabaseError, match='stop terminal|stop commit'):
            mutate(client, 'POST', '/api/playback/stop', key='failed-stop')
    monkeypatch.setattr(database, '_connect', original_connect)
    after = payload(state)
    assert after['explicit_stop_generation'] == 0
    assert after['playback']['state'] == 'PLAYING'
    assert after['playback_observation']['control_target'] is None
    # The rolled-back Stop cannot publish success; retiring its old control
    # token is a safety invalidation of the prior committed observation.
    assert subscriber.pending.domains == frozenset({'playback'})


def test_delete_without_successor_is_not_explicit_stop(real_client):
    client, _, _, service = real_client
    start(client)
    state, _ = capture(real_client)
    playback = run(service.queue_manager.get_playback_state())
    run(service.queue_manager.set_playback_state(playback.model_copy(update={'autoplay_enabled': False})))
    run(service.clear())
    current = next(item for item in run(service.queue_manager.list_items()) if item.position == 0)
    run(service.delete(current.queue_item_id))
    snapshot = payload(state)
    assert snapshot['playback']['state'] == 'STOPPED'
    assert snapshot['history']['session_id'] is None
    assert snapshot['explicit_stop_generation'] == 0


@pytest.mark.parametrize('after_commit', [False, True])
def test_stop_cancellation_preserves_generation_commit_boundary(real_client, after_commit):
    client, library, _, service = real_client
    start(client)
    state, _ = capture(real_client)
    class Publisher:
        async def publish(self, event):
            asyncio.current_task().cancel()
            await asyncio.sleep(0)
    if after_commit:
        service._event_publisher = Publisher()
    async def scenario():
        async def outer(_):
            await service.stop()
            if not after_commit:
                asyncio.current_task().cancel()
                await asyncio.sleep(0)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.create_task(run_transaction(library.path, outer))
    run(scenario())
    assert payload(state)['explicit_stop_generation'] == (1 if after_commit else 0)
