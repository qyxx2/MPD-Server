import asyncio

from server.app.main import app
from server.app.repositories.database import on_transaction_visible, run_transaction
from server.tests.api.test_realtime_state import state_client
from server.tests.invariants.assertions import server_snapshot
from server.tests.support.playback import real_client, run

__all__ = ['real_client', 'state_client']


def test_get_and_initial_ws_export_identical_control_target(state_client, monkeypatch):
    client, _, playback, _, _, coordinator, _, _ = state_client
    monkeypatch.setattr(app.state, 'realtime_coordinator', coordinator)
    target = run(playback.observe()).control_target
    assert target is not None
    get = client.get('/api/state').json()
    with client.websocket_connect('/api/realtime') as socket:
        frame = socket.receive_json()
    assert frame['protocol_version'] == 1
    assert get['playback_observation']['control_target'] == target.model_dump()
    assert frame['state']['playback_observation']['control_target'] == target.model_dump()
    assert get['sequence'] == frame['sequence']


def test_snapshot_target_capture_has_no_player_io(state_client, monkeypatch):
    client, state, playback, player, _, coordinator, _, _ = state_client
    target = run(playback.observe()).control_target
    before, marker = server_snapshot(playback), coordinator.marker()

    async def forbidden(*args, **kwargs):
        raise AssertionError('capture performed player I/O or recovery')

    for name in ('read_execution_sample', 'status', 'queue_entries', 'play', 'seek', 'pause',
                 'stop', 'queue_play', 'queue_add', 'queue_delete', 'queue_move', 'queue_clear'):
        monkeypatch.setattr(player, name, forbidden)
    monkeypatch.setattr(playback, 'reconcile_external_status', forbidden)
    assert run(state.get_full_snapshot()).playback_observation.control_target == target
    assert client.get('/api/state').json()['playback_observation']['control_target'] == target.model_dump()
    assert server_snapshot(playback) == before and coordinator.marker() == marker


def test_target_invalidation_waits_for_outer_visibility(state_client):
    _, state, playback, _, library, coordinator, _, _ = state_client
    target = run(playback.observe()).control_target
    marker = coordinator.marker()

    async def scenario():
        changed, release, attempted = asyncio.Event(), asyncio.Event(), asyncio.Event()
        subscriber = coordinator.subscribe()
        visible_domains = []

        async def outer(_):
            await playback.add_to_queue('c')  # Rebind retains current, invalidates its target.
            assert coordinator.marker() == marker and subscriber.pending is None
            on_transaction_visible(library.path, lambda: visible_domains.append(subscriber.pending.domains))
            changed.set()
            await release.wait()

        async def capture():
            attempted.set()
            return await state.get_full_snapshot()

        writer = asyncio.create_task(run_transaction(library.path, outer))
        await asyncio.wait_for(changed.wait(), 1)
        reader = asyncio.create_task(capture())
        await asyncio.wait_for(attempted.wait(), 1)
        assert not reader.done()
        release.set()
        await asyncio.wait_for(writer, 1)
        assert visible_domains and 'playback' in visible_domains[0]
        assert subscriber.pending is not None and 'playback' in subscriber.pending.domains
        snapshot = await asyncio.wait_for(reader, 1)
        assert snapshot.sequence == coordinator.marker().sequence
        assert snapshot.playback_observation.control_target is None
        fresh = await playback.observe()
        assert fresh.control_target is not None and fresh.control_target != target
        coordinator.unsubscribe(subscriber)

    run(scenario())


def test_stale_snapshot_exports_null_target(state_client):
    client, _, playback, _, _, coordinator, clock, _ = state_client
    target = run(playback.observe()).control_target
    assert target is not None
    marker = coordinator.marker()
    clock.advance(6.01)
    first = client.get('/api/state').json()
    assert first['playback_observation']['control_target'] is None
    assert first['sequence'] == marker.sequence + 1
    assert client.get('/api/state').json()['sequence'] == first['sequence']
    # Same binding may be freshly reconfirmed without elapsed rotating its lifetime.
    assert run(playback.observe()).control_target == target
