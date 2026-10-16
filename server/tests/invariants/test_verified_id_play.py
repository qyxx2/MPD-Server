"""B5: fixed occurrence IDs through the real TCP Adapter and journal."""
from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import replace

import pytest

from server.app.models.recovery import ExecutionCommand, ExecutionIntent, RecoveryResult
from server.app.player.ports import PlayerCommandError, PlayerUnavailable
from server.app.repositories.database import run_transaction
from server.app.services.playback_execution import ExecutionSynchronizer
from server.app.services.playback_service import PlaybackReconciliationError
from server.tests.invariants.test_playback_song_read_budget import measure, seed_queue
from server.tests.support.d6_stock import stock_joint


async def play_case(j, source):
    binding = await j.service.get_execution_binding()
    baseline = await j.player.read_execution_sample()
    items = tuple((key, uri) for key, _, uri in binding.entries)
    if source.startswith('add'):
        target, uri = 'b5:new', 'c.flac' if source.endswith('duplicate') else 'd.flac'
        items += ((target, uri),)
        commands = (ExecutionCommand('add', target, uri=uri),)
    else:
        target, _, uri = binding.entries[-1 if source.endswith('duplicate') else 1]
        commands = ()
    # Keep the legacy URI hint: it must never override the fixed occurrence ID.
    commands += (ExecutionCommand('play', target, uri=uri),)
    journal = j.service._recovery
    intent = ExecutionIntent(
        journal.service_epoch, binding.binding_generation, 'b5:play', binding.queue_revision,
        baseline, binding.entries, items, commands, target, 'PLAYING', True,
    )
    return ExecutionSynchronizer(j.player, journal), intent


@pytest.mark.parametrize('size', [8, 400])
@pytest.mark.parametrize('source', ['mapped', 'mapped-duplicate', 'add', 'add-duplicate'])
def test_verified_id_avoids_uri_search_and_replays_without_control(tmp_path, monkeypatch, size, source):
    async def scenario():
        async with stock_joint(tmp_path / 'id-play.db') as j:
            await seed_queue(j, size)
            executor, intent = await play_case(j, source)
            before, authorities = await j.business(), j.authorities()
            counts = measure(j, monkeypatch)
            cutoff = len(j.fake.received)

            async def execute(_):
                result = await executor.execute(intent)
                executor.journal.commit_execution(intent.operation_id, RecoveryResult('APPLIED', None))
                return result

            result = await run_transaction(j.path, execute)
            wire = Counter(c.split()[0] for c in j.fake.received[cutoff:])
            samples = 3 if source.startswith('add') else 2
            assert counts['sample'] == samples  # Entry read plus each command's confirmation.
            assert wire['playlistinfo'] == samples  # No URI lookup outside complete samples.
            assert wire['status'] == 2 * samples
            target_id = executor._id(intent, intent.target_item_id)
            assert j.controls(cutoff) == ([f'addid {intent.items[-1][1]}']
                                         if source.startswith('add') else []) + [f'playid {target_id}']
            assert result.status.song_id == target_id
            assert tuple((e.mpd_song_id, e.song_uri) for e in result.entries) == tuple(
                (mpd_id, uri) for _, mpd_id, uri in executor.mapping(intent)
            )
            assert all(r.phase == 'confirmed' for r in executor.journal.command_receipts[intent.operation_id].values())
            cutoff = len(j.fake.received)
            assert await executor.execute(intent) == result
            assert j.fake.received[cutoff:] == []
            assert executor.journal.get_execution_receipt(intent.operation_id).outcome == 'REPLAYED'
            assert await j.business() == before and j.authorities() == authorities
            assert not j.events
    asyncio.run(scenario())


@pytest.mark.parametrize('fault', ['deleted', 'reconnect', 'lost-response', 'reconnect-after-ack', 'rejected-id'])
def test_id_play_fails_closed_without_uri_fallback_or_blind_retry(tmp_path, monkeypatch, fault):
    async def scenario():
        async with stock_joint(tmp_path / 'id-fault.db') as j:
            await seed_queue(j, 8)
            executor, intent = await play_case(j, 'mapped')
            before, authorities = await j.business(), j.authorities()
            target_id = next(mpd_id for key, mpd_id, _ in intent.entries if key == intent.target_item_id)
            if fault == 'deleted':
                await j.external(f'deleteid {target_id}')
            elif fault == 'reconnect':
                await j.adapter.close()
            elif fault == 'lost-response':
                j.fake.drop_response = 'playid'
            elif fault == 'reconnect-after-ack':
                play = j.adapter.queue_play

                async def reconnect(mpd_id, **kwargs):
                    await play(mpd_id, **kwargs)
                    await j.adapter.close()

                monkeypatch.setattr(j.adapter, 'queue_play', reconnect)
            else:
                # Delete after the fresh verification, before MPD handles playid.
                async def delete_on_send(request):
                    if request.startswith('playid '):
                        await j.external(f'deleteid {target_id}')

                j.fake.before_request = delete_on_send
            cutoff = len(j.fake.received)

            async def execute(_):
                return await executor.execute(intent)

            error = (PlayerUnavailable if fault == 'lost-response' else
                     PlayerCommandError if fault == 'rejected-id' else PlaybackReconciliationError)
            with pytest.raises(error):
                await run_transaction(j.path, execute)
            if fault == 'rejected-id':
                assert executor.journal.command_receipts[intent.operation_id][0].phase == 'rejected'
            first_controls = j.controls(cutoff)
            assert sum(c.startswith('playid ') for c in first_controls) == (
                0 if fault in {'deleted', 'reconnect'} else 1
            )
            cutoff = len(j.fake.received)
            with pytest.raises(PlaybackReconciliationError, match='UNKNOWN'):
                await run_transaction(j.path, execute)
            assert j.controls(cutoff) == []
            assert await j.business() == before and j.authorities() == authorities
            assert executor.journal.get_execution_receipt(intent.operation_id) is None
            assert not j.events
    asyncio.run(scenario())


@pytest.mark.parametrize('boundary', ['closed', 'reconnected', 'send-task'])
def test_reconnect_between_verification_and_send_never_plays_recycled_id(tmp_path, monkeypatch, boundary):
    async def scenario():
        async with stock_joint(tmp_path / 'id-reconnect.db') as j:
            await seed_queue(j, 8)
            executor, intent = await play_case(j, 'mapped')
            before = await j.business()
            send = executor._send
            cutoff = None

            async def recycle_id():
                nonlocal cutoff
                await j.adapter.close()
                # A new daemon can reuse IDs for different URIs. The fake keeps
                # these IDs but changes their URI, with a fresh connection epoch.
                j.fake.queue = [replace(entry, song_uri='z.flac')
                                if entry.mpd_song_id == intent.entries[1][1] else entry
                                for entry in j.fake.queue]
                if boundary == 'reconnected':
                    await j.player.read_execution_sample()
                elif boundary == 'send-task':
                    # Already inside the Adapter lock: restore a writable new
                    # connection so only the epoch fence can reject the old ID.
                    await j.adapter._ensure_connected()
                cutoff = len(j.fake.received)

            async def reconnect_before_send(fixed_intent, command):
                await recycle_id()
                return await send(fixed_intent, command)

            if boundary == 'send-task':
                execute_command = j.adapter._execute

                async def reconnect_in_send_task(command, *args, **kwargs):
                    if command == 'playid':
                        await recycle_id()
                    return await execute_command(command, *args, **kwargs)

                monkeypatch.setattr(j.adapter, '_execute', reconnect_in_send_task)
            else:
                monkeypatch.setattr(executor, '_send', reconnect_before_send)

            async def execute(_):
                return await executor.execute(intent)

            with pytest.raises((PlayerUnavailable, PlaybackReconciliationError)):
                await run_transaction(j.path, execute)
            assert j.controls(cutoff) == []
            assert j.fake.current_song_id == intent.entries[0][1]
            assert await j.business() == before
            assert not j.events
            assert executor.journal.get_execution_receipt(intent.operation_id) is None
            with pytest.raises(PlaybackReconciliationError, match='UNKNOWN'):
                await run_transaction(j.path, execute)
            assert j.controls(cutoff) == []
    asyncio.run(scenario())
