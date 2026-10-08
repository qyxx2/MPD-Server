"""Stock facts through real TCP Adapter/VerifiedPort/Services/SQLite/HTTP/WS.

These proofs catch URI-based adoption, fabricated History, blind retry, early
publication, and read-side recovery. Inputs never certify why MPD advanced.
"""
from __future__ import annotations

import asyncio

import pytest

from server.app.models.library import Song
from server.app.player.ports import PlayerCommandError, PlayerUnavailable
from server.app.repositories.database import run_transaction
from server.tests.support.d6_stock import stock_joint


@pytest.mark.parametrize('cause', [
    'A-B', 'A-C', 'duplicate', 'seek-end', 'seek-remainder', 'errors',
    'external-next', 'playid', 'seekid',
])
def test_stock_adapter_current_queue_history_and_snapshot_joint(tmp_path, cause):
    async def scenario():
        async with stock_joint(tmp_path / 'joint.db', duplicate=cause == 'duplicate') as j:
            before = await j.business()
            authorities = j.authorities()
            outputs = await j.player.outputs()
            binding = await j.service.get_execution_binding()
            target_index = 2 if cause == 'A-C' else len(binding.entries) - 1 if cause == 'duplicate' else 1
            target_item, target_mpd, target_uri = binding.entries[target_index]
            if cause in {'seek-end', 'seek-remainder'}:
                seconds = 180 if cause == 'seek-end' else 20
                await j.external(f'seekcur {seconds}')
                sought = await j.player.read_execution_sample()
                assert sought.status.song_id == binding.entries[0][1]
                assert sought.status.elapsed_seconds == seconds
                assert await j.business() == before
                # Later current facts after endpoint/remaining segment. This
                # protocol next supplies B, never certifies a natural cause.
                await j.external('next')
            elif cause == 'seekid':
                await j.external(f'seekid {target_mpd} 20')
            elif cause == 'external-next':
                await j.external('next')
            else:
                await j.external(f'playid {target_mpd}')
            if cause == 'errors':
                j.fake.error = 'decoder error'
            cutoff = len(j.fake.received)
            # Explicit Service proof precedes the separate no-browser runner proof.
            result = await j.service.maintain_execution()
            assert result.outcome == ('UNKNOWN' if cause == 'errors' else 'APPLIED')
            assert result.reconciliation_required is (cause == 'errors')
            after = await j.business()
            queue, state, history, active, session = after
            current = next(i for i in queue.items if i.position == 0)
            assert current.queue_item_id == target_item
            assert state.song_id == current.song_id
            assert state.playback_context_id == before[1].playback_context_id == 'stock-joint'
            assert state.autoplay_enabled is True
            assert queue.revision == before[0].revision + 1
            assert history == before[2] and active is None and session == before[4]
            assert history and all(event.reason != 'NATURAL_COMPLETION' for event in history)
            old_ids = {i.queue_item_id: (i.song_id, i.source, i.playback_context_id) for i in before[0].items}
            assert {i.queue_item_id: (i.song_id, i.source, i.playback_context_id) for i in queue.items} == old_ids
            old_pending = [i.queue_item_id for i in sorted(before[0].items, key=lambda i: i.position)
                           if i.position > 0 and i.queue_item_id != target_item]
            assert [i.queue_item_id for i in sorted(queue.items, key=lambda i: i.position)
                    if i.position > 0] == old_pending
            assert next(i for i in queue.items if i.queue_item_id == binding.entries[0][0]).position == -1
            sample = await j.player.read_execution_sample()
            assert sample.status.song_id == target_mpd and sample.status.song_position == 0
            assert sample.status.song_uri == target_uri
            assert 'reason' not in sample.model_dump()
            if cause in {'seek-remainder', 'seekid'}:
                assert sample.status.elapsed_seconds == (20 if cause == 'seekid' else 0)
            assert tuple((e.mpd_song_id, e.song_uri) for e in sample.entries) == tuple(
                (mpd_id, uri) for _, mpd_id, uri in (await j.service.get_execution_binding()).entries
            )
            assert not [c for c in j.controls(cutoff) if c.split()[0] in {'playid', 'play', 'next', 'seekcur', 'seekid'}]
            assert not [e for e in j.events if 'natural' in e.event_type.lower()]
            assert j.authorities() == authorities and await j.player.outputs() == outputs
            receipt_id = (next(key for key in j.service._recovery.execution_receipts if key.endswith('/adopt'))
                          if cause == 'errors' else result.transition_id)
            receipt = j.service._recovery.get_execution_receipt(receipt_id)
            assert receipt.outcome == 'REPLAYED'
            committed, controls = await j.business(), list(j.controls(cutoff))
            assert (await j.service.maintain_execution()).outcome == ('UNKNOWN' if cause == 'errors' else 'UNCHANGED')
            assert await j.business() == committed and j.controls(cutoff) == controls
            state = await j.assert_reads_preserved()
            assert state['playback_observation']['actual_current']['entry_id'] == target_mpd
            assert state['playback_observation']['bound_queue_item_id'] == target_item
            assert state['playback_observation']['sync_status'] == ('SYNC_FAILED' if cause == 'errors' else 'CONFIRMED')
            if cause == 'A-B':
                # No HTTP/WS client exists during this tick. A fresh client later sees C.
                bound = await j.service.get_execution_binding()
                c = next(row for row in bound.entries if row[2] == 'c.flac')
                await j.external(f'playid {c[1]}')
                runner_before = await j.business()
                cutoff = len(j.fake.received)
                await j.one_runner_tick()
                assert (await j.business())[0].revision == runner_before[0].revision + 1
                assert (await j.business())[1].song_id == 'c'
                assert (await j.business())[2] == history
                assert not [r for r in j.controls(cutoff) if r.startswith(('playid', 'stop'))]
                assert (await j.assert_reads_preserved())['current_song']['song_id'] == 'c'
    asyncio.run(scenario())


@pytest.mark.parametrize('failure', [
    'lost-response', 'partial-add', 'delete', 'move', 'service-restart', 'mpd-restart',
    'unknown-stop', 'foreign', 'queue-race', 'late-sample', 'torn-sample',
])
def test_stock_joint_failure_restart_and_read_only_boundaries(tmp_path, failure):
    async def scenario():
        async with stock_joint(tmp_path / 'fail.db', short=failure in {'lost-response', 'partial-add'}) as j:
            binding = await j.service.get_execution_binding()
            if failure in {'lost-response', 'partial-add'}:
                for song_id in 'efgh':
                    await j.library.upsert_song(Song(song_id=song_id, title=song_id,
                                                    file_uri=f'{song_id}.flac'))
            elif failure not in {'service-restart', 'mpd-restart', 'unknown-stop', 'foreign'}:
                await j.external(f'playid {binding.entries[2][1]}')
            if failure == 'unknown-stop':
                await j.external('stop')
            elif failure == 'foreign':
                lines = await j.external('addid "outside.flac"')
                await j.external(f'playid {lines[0].split(": ")[1]}')
            if failure == 'late-sample':
                old_wire = {command: '\n'.join(await j.external(command)) + '\nOK\n'
                            for command in ('status', 'playlistinfo')}
                # A legitimate writer commits D before delayed, internally
                # consistent old C facts are delivered through the TCP boundary.
                target = next(i for i in (await j.business())[0].items if i.song_id == 'd')
                await j.service.play_now(target.queue_item_id)
                j.events.clear()
                j.fake.response_override = old_wire.get
            before, authorities = await j.business(), j.authorities()
            outputs = await j.player.outputs()
            old_epoch = j.coordinator.marker().epoch
            cutoff = len(j.fake.received)
            if failure == 'service-restart':
                j.rebuild_service()
                assert j.coordinator.marker().epoch != old_epoch
                assert (await j.service.maintain_execution()).outcome == 'UNKNOWN'
                after = await j.business()
                assert after[:3] == before[:3] and after[3:] == (None, None)
                assert j.controls(cutoff) == []
            elif failure == 'mpd-restart':
                old_connection = (await j.player.read_execution_sample()).connection_epoch
                await j.fake.restart()
                assert j.fake.playlist_version == 0
                assert j.fake.current_song_id == 1
                with pytest.raises(PlayerUnavailable):
                    await j.service.maintain_execution()
                assert (await j.service.maintain_execution()).outcome == 'UNKNOWN'
                assert (await j.player.read_execution_sample()).connection_epoch != old_connection
                assert await j.business() == before and j.controls(cutoff) == []
            elif failure in {'unknown-stop', 'foreign'}:
                assert (await j.service.maintain_execution()).outcome == 'UNKNOWN'
                assert await j.business() == before and j.controls(cutoff) == []
            elif failure == 'lost-response':
                j.fake.drop_response = 'addid'
                with pytest.raises(PlayerUnavailable):
                    await j.service.maintain_execution()
                prefix = list(j.controls(cutoff))
                assert len(prefix) == 1 and prefix[0].startswith('addid')
                assert await j.business() == before
                assert not any(key.endswith('/refill') for key in j.service._recovery.execution_receipts)
                assert (await j.service.maintain_execution()).outcome == 'UNKNOWN'
                assert j.controls(cutoff) == prefix and await j.business() == before
                assert len(j.fake.queue) == len(binding.entries) + 1  # side effect retained, no URI guess
            elif failure == 'partial-add':
                adds = 0
                async def reject_second(request):
                    nonlocal adds
                    if request.startswith('addid'):
                        adds += 1
                        if adds == 2:
                            j.fake.fail_next('addid')
                j.fake.before_request = reject_second
                with pytest.raises(PlayerCommandError):
                    await j.service.maintain_execution()
                j.fake.before_request = None
                assert await j.business() == before and adds == 2
                prefix = list(j.controls(cutoff))
                assert (await j.service.maintain_execution()).outcome == 'UNKNOWN'
                assert j.controls(cutoff) == prefix and await j.business() == before
                assert len(j.fake.queue) == len(binding.entries) + 1
                assert not any(key.endswith('/refill') for key in j.service._recovery.execution_receipts)
            elif failure in {'delete', 'move'}:
                command = 'deleteid' if failure == 'delete' else 'moveid'
                j.fake.fail_next(command)
                with pytest.raises(PlayerCommandError):
                    await j.service.maintain_execution()
                assert await j.business() == before
                assert not j.events
                result = await j.service.maintain_execution()
                assert result.outcome == 'APPLIED'
                after = await j.business()
                assert after[0].revision == before[0].revision + 1 and after[1].song_id == 'c'
                assert after[2] == before[2] and after[3] is None
                assert [r.split()[0] for r in j.controls(cutoff)] == (
                    ['deleteid', 'deleteid', 'moveid'] if failure == 'delete'
                    else ['deleteid', 'moveid', 'moveid']
                )
                prefix = list(j.controls(cutoff))
                assert (await j.service.maintain_execution()).outcome == 'UNCHANGED'
                assert j.controls(cutoff) == prefix
            elif failure == 'queue-race':
                entered, release, writer_started = asyncio.Event(), asyncio.Event(), asyncio.Event()
                async def block(request):
                    if request.startswith('deleteid'):
                        entered.set()
                        await release.wait()
                j.fake.before_request = block
                recovery = asyncio.create_task(j.service.maintain_execution())
                await asyncio.wait_for(entered.wait(), 3)
                async def write():
                    writer_started.set()
                    return await j.service.add_to_queue('d')
                writer = asyncio.create_task(write())
                await writer_started.wait()
                assert not writer.done()
                assert j.authorities() == authorities
                release.set()
                assert (await recovery).outcome == 'APPLIED'
                added = await writer
                j.fake.before_request = None
                after = await j.business()
                assert after[0].revision == before[0].revision + 2
                assert after[1].song_id == 'c' and after[2] == before[2]
                assert any(i.queue_item_id == added.queue_item_id for i in after[0].items)
                assert len(after[0].items) == len(before[0].items) + 1
            elif failure == 'late-sample':
                result = await j.service.maintain_execution()
                assert result.outcome == 'UNKNOWN' and result.reconciliation_required
                assert await j.business() == before and before[1].song_id == 'd'
                assert j.controls(cutoff) == [] and j.events == []
                j.fake.response_override = None
            else:
                # A real external writer tears BOTH bounded sample attempts. No
                # monkeypatch of Adapter/Service samples or repair on GET/WS.
                tears = 0
                async def tear(request):
                    nonlocal tears
                    if request == 'playlistinfo':
                        tears += 1
                        await j.external('addid "outside.flac"')
                j.fake.after_request = tear
                with pytest.raises(PlayerCommandError, match='inconsistent execution sample'):
                    await j.service.maintain_execution()
                j.fake.after_request = None
                assert tears == 2 and await j.business() == before
                assert [r for r in j.controls(cutoff) if not r.startswith('addid "outside.flac"')] == []
                assert (await j.service.maintain_execution()).outcome == 'UNKNOWN'
            assert j.authorities() == authorities
            assert await j.player.outputs() == outputs
            assert (await j.business())[2] == before[2]
            assert not [e for e in j.events if 'natural' in e.event_type.lower()]
            state = await j.assert_reads_preserved()
            observation = state['playback_observation']
            assert observation['actual_freshness'] == 'fresh'
            assert observation['actual_current'] is not None
            expected_uri = ('outside.flac' if failure == 'foreign' else
                            'c.flac' if failure in {'delete', 'move', 'queue-race', 'torn-sample'} else
                            'd.flac' if failure == 'late-sample' else 'a.flac')
            assert observation['actual_current']['uri'] == expected_uri
            assert observation['actual_state'] == ('stopped' if failure == 'unknown-stop' else 'playing')
            assert observation['actual_current']['entry_id'] == j.fake.current_song_id
            if failure in {'service-restart', 'mpd-restart', 'foreign', 'unknown-stop'}:
                assert state['current_song']['song_id'] == 'a'
                assert next(i for i in state['queue']['items'] if i['position'] == 0)['song_id'] == 'a'
            if failure in {'service-restart', 'mpd-restart', 'foreign', 'late-sample', 'torn-sample', 'lost-response', 'partial-add'}:
                assert state['playback_observation']['bound_queue_item_id'] is None
                assert state['playback_observation']['sync_status'] != 'CONFIRMED'
            if failure == 'unknown-stop':
                assert state['playback_observation']['sync_status'] == 'UNCONFIRMED_STOP'
                assert state['playback']['autoplay_enabled'] is True
    asyncio.run(scenario())


@pytest.mark.parametrize('boundary', ['refill', 'outer-rollback', 'precommit-cancel', 'publisher-failure'])
def test_stock_joint_refill_commit_receipt_and_realtime_boundary(tmp_path, boundary):
    """Catch early publication/receipts, lost fixed IDs, and commit rollback on send failure."""
    async def scenario():
        async with stock_joint(tmp_path / 'commit.db', short=True) as j:
            for song_id in 'efgh':
                await j.library.upsert_song(Song(song_id=song_id, title=song_id,
                                                file_uri=f'{song_id}.flac'))
            before, authorities = await j.business(), j.authorities()
            binding = await j.service.get_execution_binding()
            cutoff = len(j.fake.received)
            marker = j.coordinator.marker()
            subscriber = j.coordinator.subscribe()
            if boundary == 'publisher-failure':
                async def failed(event):
                    raise RuntimeError('injected committed publisher failure')
                j.service._event_publisher.publish = failed
            async with j.socket() as frame:
                first = await frame()
                assert first['type'] == 'snapshot'
                if boundary in {'outer-rollback', 'precommit-cancel'}:
                    async def abort(_):
                        result = await j.service.maintain_execution()
                        assert result.outcome == 'APPLIED'
                        assert j.service._recovery.get_execution_receipt(result.transition_id) is None
                        assert subscriber.pending is None and j.events == []
                        assert j.coordinator.marker() == marker
                        if boundary == 'precommit-cancel':
                            raise asyncio.CancelledError()
                        raise RuntimeError('injected outer rollback')
                    with pytest.raises(asyncio.CancelledError if boundary == 'precommit-cancel' else RuntimeError):
                        await run_transaction(j.path, abort)
                    assert await j.business() == before
                    assert j.service._recovery.binding == binding
                    assert subscriber.pending is None and j.events == []
                    assert j.coordinator.marker() == marker
                    intent = next(v for k, v in j.service._recovery.execution_intents.items()
                                  if k.endswith('/refill'))
                    fixed_ids = tuple(i.queue_item_id for i in j.service._recovery.refill_items[intent.operation_id])
                    prefix = list(j.controls(cutoff))
                    result = await j.service.maintain_execution()
                    assert j.controls(cutoff) == prefix  # ACK/confirmed prefix is never sent twice
                elif boundary == 'refill':
                    # With no browser attached, the separate success scenario proves
                    # runner current adoption; here the connected socket proves commit propagation.
                    result = await j.service.maintain_execution()
                    fixed_ids = None
                else:
                    result = await j.service.maintain_execution()
                    fixed_ids = None
                assert result.outcome == 'APPLIED'
                notification = await frame()
                assert notification['type'] == 'invalidate'
                assert notification['sequence'] > first['sequence']
                assert 'queue' in notification['domains']
            after = await j.business()
            assert after[0].revision == before[0].revision + 1
            assert after[1:] == before[1:]
            added = [i for i in sorted(after[0].items, key=lambda i: i.position)
                     if i.queue_item_id not in {old.queue_item_id for old in before[0].items}]
            assert len(added) == 4
            assert {i.song_id for i in added} == set('efgh')
            assert all(i.source == 'AUTOPLAY' and i.playback_context_id == 'stock-joint' for i in added)
            if fixed_ids is not None:
                assert tuple(i.queue_item_id for i in added) == fixed_ids
            assert [r.split()[0] for r in j.controls(cutoff)] == ['addid'] * 4
            sample = await j.player.read_execution_sample()
            bound = await j.service.get_execution_binding()
            assert sample.status.song_id == binding.entries[0][1]
            assert tuple((e.mpd_song_id, e.song_uri) for e in sample.entries) == tuple(
                (mpd_id, uri) for _, mpd_id, uri in bound.entries
            )
            assert j.service._recovery.get_execution_receipt(result.transition_id).outcome == 'REPLAYED'
            controls = list(j.controls(cutoff))
            assert (await j.service.maintain_execution()).outcome == 'UNCHANGED'
            assert j.controls(cutoff) == controls and await j.business() == after
            assert j.authorities() == authorities
            await j.assert_reads_preserved()
            j.coordinator.unsubscribe(subscriber)
    asyncio.run(scenario())
