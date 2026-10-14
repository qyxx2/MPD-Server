"""B3: an already registered Playback commit must not reacquire the DB mutex."""
from __future__ import annotations

import asyncio
import sys
from collections import Counter

import pytest
from starlette.requests import Request
from starlette.responses import StreamingResponse

from server.app.repositories import database
from server.app.services.idempotency_service import IdempotencyService
from server.tests.invariants.test_playback_song_read_budget import measure, seed_queue
from server.tests.support.d6_stock import stock_joint


def request(key='batch-3'):
    async def receive():
        return {'type': 'http.request', 'body': b'{}', 'more_body': False}
    return Request({'type': 'http', 'method': 'POST', 'path': '/batch-3',
                    'headers': [(b'idempotency-key', key.encode())]}, receive)


def wire(j):
    # Exercise the real composition root's default coordinator-as-publisher path.
    j.coordinator._event_publisher = j
    j.service._event_publisher = j.coordinator
    j.events.clear()
    return j.coordinator.subscribe()


@pytest.mark.parametrize('size', [8, 400])
@pytest.mark.parametrize('operation', ['next', 'song', 'played'])
def test_registered_playback_finishes_while_recovery_holds_mutex(tmp_path, monkeypatch, size, operation):
    """Reintroducing coordinator.publish's registration transaction loses this race."""
    async def scenario():
        async with stock_joint(tmp_path / 'contention.db') as j:
            await seed_queue(j, size)
            if operation == 'played':
                await j.service.next()
            subscriber = wire(j)
            before = j.coordinator.marker()
            snapshot = await j.manager.get_snapshot()
            played = next((i for i in snapshot.items if i.position < 0), None)
            session = j.history_service.session_id
            cutoff = len(j.fake.received)
            counts = measure(j, monkeypatch)
            committed, held, release, reacquired = (asyncio.Event() for _ in range(4))
            roots = Counter()
            lock_for = database._lock_for
            sample = j.player.read_execution_sample
            writer = background = None

            class CountedLock:
                def __init__(self, lock):
                    self.lock = lock
                async def __aenter__(self):
                    if asyncio.current_task() is writer:
                        roots['writer'] += 1
                        if committed.is_set():
                            reacquired.set()
                    await self.lock.acquire()
                async def __aexit__(self, *_):
                    self.lock.release()

            monkeypatch.setattr(database, '_lock_for', lambda path: CountedLock(lock_for(path)))

            transaction = database.run_transaction
            async def counted_transaction(path, operation):
                if asyncio.current_task() is writer:
                    try:
                        database.transaction_identity(path)
                    except RuntimeError:
                        roots['root'] += 1
                    else:
                        roots['nested'] += 1
                    if committed.is_set():
                        roots['post_commit_transaction'] += 1
                return await transaction(path, operation)
            for module in tuple(sys.modules.values()):
                if (module is not None and module.__name__.startswith('server.app.')
                        and getattr(module, 'run_transaction', None) is transaction):
                    monkeypatch.setattr(module, 'run_transaction', counted_transaction)

            async def held_sample():
                if asyncio.current_task() is background:
                    held.set()
                    await release.wait()
                return await sample()
            monkeypatch.setattr(j.player, 'read_execution_sample', held_sample)

            async def recover():
                await committed.wait()
                return await j.service.maintain_execution()
            background = asyncio.create_task(recover())  # Created outside the control owner.

            async def call_next(_):
                # First post-commit hook lets the real recovery operation acquire the lock.
                database.on_transaction_visible(j.path, committed.set)
                database.on_transaction_commit(j.path, held.wait)
                if operation == 'next':
                    await j.service.next()
                elif operation == 'song':
                    await j.service.play_song_now('b')
                else:
                    await j.service.play_now(played.queue_item_id)
                return StreamingResponse(iter([b'{"ok":true}']))

            writer = asyncio.create_task(IdempotencyService(j.terminals).execute(request(), call_next))
            reacquire_wait = asyncio.create_task(reacquired.wait())
            try:
                await asyncio.wait_for(held.wait(), 5)  # Deadlock guard, not a latency threshold.
                done, _ = await asyncio.wait_for(asyncio.wait(
                    (writer, reacquire_wait), return_when=asyncio.FIRST_COMPLETED,
                ), 5)
                assert writer in done, 'post-commit notification reacquired the held DB mutex'
                assert (await writer).status_code == 200
                assert not release.is_set() and not background.done()
                assert roots['writer'] == roots['root'] == 1
                assert roots['post_commit_transaction'] == 0
                print('B3 transaction budget', size, operation, dict(roots))
                assert len(j.events) == 1
                assert subscriber.queue.qsize() == 1
                notification = subscriber.queue.get_nowait()
                assert notification.sequence == before.sequence + 1
                assert notification.epoch == before.epoch
                assert notification.domains == j.events[0].domains
                assert notification.revisions == {'library': before.library_revision,
                                                  'playlist': before.playlist_revision}
                assert counts['get_song'] == counts['full_song'] == 2
                assert counts['batch'] == 3
                assert counts['sample'] == (11 if operation == 'played' else 9)
                assert [c.split()[0] for c in j.fake.received[cutoff:]].count('playid') == 1
            finally:
                release.set()
                if not committed.is_set():
                    background.cancel()
                reacquire_wait.cancel()
                await asyncio.gather(writer, background, reacquire_wait, return_exceptions=True)
            assert await j.terminals.get_by_key('batch-3') is not None
            assert j.history_service.session_id == session
            marker = j.coordinator.marker()
            event_count = len(j.events)
            command_count = len(j.fake.received)
            replay = await IdempotencyService(j.terminals).execute(request(), call_next)
            assert replay.status_code == 200 and replay.body == b'{"ok":true}'
            assert j.coordinator.marker() == marker and len(j.events) == event_count
            assert len(j.fake.received) == command_count
    asyncio.run(scenario())


def test_joint_nested_changes_register_once_and_noop_does_not_deliver(tmp_path):
    """A duplicate post-commit registration or a per-call event leaks intermediate state."""
    async def scenario():
        async with stock_joint(tmp_path / 'joint.db') as j:
            sub = wire(j)
            before = j.coordinator.marker()
            async def joint(connection):
                await j.service.seek(7)
                await database.run_transaction(j.path, lambda _: j.service.pause())
                j.coordinator.stage_change(frozenset({'library', 'playlist'}), (), ('new',))
                assert j.coordinator.marker() == before and sub.pending is None and not j.events
            await database.run_transaction(j.path, joint)
            marker = j.coordinator.marker()
            assert (marker.sequence, marker.library_revision, marker.playlist_revision) == (
                before.sequence + 1, before.library_revision + 1, before.playlist_revision + 1,
            )
            assert sub.queue.qsize() == 1 and len(j.events) == 1
            notification = await sub.receive()
            assert notification.domains == frozenset({'playback', 'library', 'playlist'})
            assert j.events[0].domains == frozenset({'playback'})
            async def noop(_):
                await j.service.seek(9)
                await j.service.seek(7)
            await database.run_transaction(j.path, noop)
            assert j.coordinator.marker() == marker
            assert sub.queue.empty() and len(j.events) == 1
    asyncio.run(scenario())


@pytest.mark.parametrize('failure', ['rollback', 'terminal', 'commit', 'pre-cancel',
                                     'post-cancel', 'publisher', 'visible-before', 'visible-after'])
def test_registered_delivery_preserves_failure_and_terminal_boundaries(tmp_path, monkeypatch, caplog, failure):
    """Bypassing registration must not bypass commit/fail-closed or resurrect rollback hooks."""
    import sqlite3
    async def scenario():
        async with stock_joint(tmp_path / 'failures.db') as j:
            sub = wire(j)
            before = await j.business()
            marker = j.coordinator.marker()
            records = j.terminals
            rolled_back = []
            connect = database._connect
            class RejectCommit(sqlite3.Connection):
                def commit(self):
                    raise sqlite3.OperationalError('B3 commit rejected')
            if failure == 'commit':
                monkeypatch.setattr(database, '_connect', lambda p: sqlite3.connect(p, factory=RejectCommit))
            def bad_visibility():
                raise RuntimeError('B3 visibility failed')
            async def bad_publisher(event):
                j.events.append(event)
                if failure == 'post-cancel':
                    raise asyncio.CancelledError()
                raise RuntimeError('B3 publisher failed')
            if failure in {'post-cancel', 'publisher'}:
                monkeypatch.setattr(j, 'publish', bad_publisher)
            original_create = records.create
            async def reject_terminal(**kwargs):
                raise RuntimeError('B3 terminal rejected')
            if failure == 'terminal':
                monkeypatch.setattr(records, 'create', reject_terminal)
            async def operation(_):
                database.on_transaction_rollback(j.path, lambda: rolled_back.append(True))
                if failure == 'visible-before':
                    database.on_transaction_visible(j.path, bad_visibility)
                await j.service.pause()
                if failure == 'visible-after':
                    database.on_transaction_visible(j.path, bad_visibility)
                if failure == 'rollback':
                    raise RuntimeError('B3 outer rejected')
                if failure == 'pre-cancel':
                    raise asyncio.CancelledError()
                return StreamingResponse(iter([b'{"ok":true}']))
            service = IdempotencyService(records)
            errors = {'rollback': RuntimeError, 'terminal': RuntimeError, 'commit': sqlite3.OperationalError,
                      'pre-cancel': asyncio.CancelledError, 'post-cancel': asyncio.CancelledError}
            if failure in errors:
                with pytest.raises(errors[failure]):
                    await asyncio.create_task(service.execute(request(), operation))
            else:
                assert (await service.execute(request(), operation)).status_code == 200
            monkeypatch.setattr(database, '_connect', connect)
            monkeypatch.setattr(records, 'create', original_create)
            committed = failure in {'post-cancel', 'publisher', 'visible-before', 'visible-after'}
            assert bool(await records.get_by_key('batch-3')) == committed
            assert rolled_back == ([] if committed else [True])
            assert not j.service._transport_changes and not j.coordinator._staged
            if not committed:
                assert await j.business() == before
                assert j.coordinator.marker() == marker
                assert sub.pending is None and not j.events
                await service.execute(request(), operation if failure == 'commit' else success)
            elif failure.startswith('visible'):
                assert not sub.valid and not j.events
                with pytest.raises(RuntimeError, match='unavailable'):
                    j.coordinator.marker()
                with pytest.raises(RuntimeError, match='unavailable'):
                    await j.state.get_full_snapshot()
            else:
                assert (await j.manager.get_playback_state()).state == 'PAUSED'
                assert j.coordinator.marker().sequence == marker.sequence + 1
                assert sub.queue.qsize() == 1 and len(j.events) == 1
            command_count, event_count = len(j.fake.received), len(j.events)
            terminal = await records.get_by_key('batch-3')
            assert (await service.execute(request(), success)).body == b'{"ok":true}'
            assert await records.get_by_key('batch-3') == terminal
            assert len(j.fake.received) == command_count and len(j.events) == event_count

    async def success(_):
        # Defined separately to avoid rerunning injected failures on a failed intent.
        return StreamingResponse(iter([b'{"ok":true}']))
    asyncio.run(scenario())


def test_delayed_domain_delivery_keeps_commit_waterlines_and_ws_order(tmp_path, monkeypatch):
    """An old delivery must not mint a newer marker or reassert domains from a later commit."""
    async def scenario():
        async with stock_joint(tmp_path / 'order.db') as j:
            sub = wire(j)
            marker = j.coordinator.marker()
            entered, release = asyncio.Event(), asyncio.Event()
            async def publisher(event):
                if event.domains == frozenset({'playback'}):
                    entered.set()
                    await release.wait()
                j.events.append(event)
            monkeypatch.setattr(j, 'publish', publisher)
            first = asyncio.create_task(j.service.seek(7))
            try:
                await asyncio.wait_for(entered.wait(), 5)
                await j.service.stop()
                assert sub.queue.qsize() == 2
                one, two = await sub.receive(), await sub.receive()
                assert (one.sequence, two.sequence) == (marker.sequence + 1, marker.sequence + 2)
                assert one.domains == frozenset({'playback'})
                assert two.domains == frozenset({'playback', 'history'})
                snapshot = await j.state.get_full_snapshot()
                assert snapshot.sequence == two.sequence
                assert snapshot.epoch == two.epoch
                assert snapshot.playback.state == 'STOPPED'
                assert snapshot.revisions == two.revisions
                release.set()
                await first
                assert j.coordinator.marker().sequence == two.sequence
                assert sub.queue.empty()
                assert [event.domains for event in j.events] == [two.domains, one.domains]
            finally:
                release.set()
                await asyncio.gather(first, return_exceptions=True)
    asyncio.run(scenario())
