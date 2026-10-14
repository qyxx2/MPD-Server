"""Batch 2: real SQLite reads and TCP execution budgets, measured separately."""
from __future__ import annotations

import asyncio
import re
import sqlite3
from collections import Counter
from math import ceil

import pytest

from server.app.models.library import Song
from server.app.models.queue import PlaybackContext
from server.app.repositories import database
from server.tests.support.d6_stock import stock_joint


async def seed_queue(j, size, distinct=False):
    ids = ['a', 'b']
    for index in range(size - 2):
        song_id = f'budget-{index}' if distinct else 'c'
        if distinct:
            await j.library.upsert_song(Song(
                song_id=song_id, title=song_id, file_uri=f'{song_id}.flac',
                album='Budget', artists=('Artist',), tag_names=('Tag',),
            ))
        ids.append(song_id)
    await j.service.play_context(PlaybackContext(
        context_id='batch-2', source_type='SONGS', ordered_song_ids=tuple(ids),
    ))
    binding = await j.service.get_execution_binding()
    assert len(binding.entries) == size
    j.events.clear()
    return binding


def measure(j, monkeypatch, variable_limit=900):
    counts = Counter()
    connect = database._connect
    get_song = j.library.get_song
    build = j.library._song_from_row
    sample = j.player.read_execution_sample

    def trace(sql):
        if not sql.lstrip().upper().startswith('SELECT'):
            return
        counts['all_select'] += 1
        if re.search(r'\b(?:songs|albums|album_art_refs|artists|genres|tags|song_artists|song_album_artists|song_genres|song_tags)\b', sql, re.IGNORECASE):
            counts['library_select'] += 1
        if sql.lstrip().startswith('SELECT song_id, file_uri, availability_status FROM songs'):
            counts['projection_select'] += 1
        if re.search(r'\b(?:albums|album_art_refs|artists|genres|tags)\b', sql, re.IGNORECASE):
            counts['relationship_select'] += 1

    def traced_connect(path):
        connection = connect(path)
        connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, variable_limit)
        connection.set_trace_callback(trace)
        return connection

    async def counted_get(song_id):
        counts['get_song'] += 1
        return await get_song(song_id)

    def counted_build(connection, row):
        counts['full_song'] += 1
        return build(connection, row)

    async def counted_sample():
        counts['sample'] += 1
        return await sample()

    monkeypatch.setattr(database, '_connect', traced_connect)
    monkeypatch.setattr(j.library, 'get_song', counted_get)
    monkeypatch.setattr(j.library, '_song_from_row', counted_build)
    monkeypatch.setattr(j.player, 'read_execution_sample', counted_sample)
    # On the B1 RED baseline the new Repository entry point does not yet exist.
    batch = getattr(j.library, 'get_playback_songs', None)
    if batch is not None:
        async def counted_batch(song_ids):
            counts['batch'] += 1
            return await batch(song_ids)
        monkeypatch.setattr(j.library, 'get_playback_songs', counted_batch)
    return counts


@pytest.mark.parametrize('size', [8, 400])
@pytest.mark.parametrize('operation', ['next', 'song'])
@pytest.mark.parametrize('distinct', [False, True], ids=['repeated', 'distinct'])
@pytest.mark.parametrize('variable_limit', [900, 100], ids=['normal-limit', 'small-limit'])
def test_bound_queue_read_budget_and_execution_identity(tmp_path, monkeypatch, size, operation, distinct, variable_limit):
    async def scenario():
        async with stock_joint(tmp_path / 'budget.db') as j:
            old = await seed_queue(j, size, distinct)
            queue = await j.manager.get_snapshot()
            unique = len({i.song_id for i in queue.items if i.position >= 0})
            before_history = await j.history.list_history()
            session = j.history_service.session_id
            cutoff = len(j.fake.received)
            counts = measure(j, monkeypatch, variable_limit)
            if operation == 'next':
                await j.service.next()
            else:
                await j.service.play_song_now('d')
            controls = Counter(c.split()[0] for c in j.controls(cutoff))
            measured = dict(counts)
            print(f'BATCH2 size={size} unique={unique} operation={operation} distinct={distinct} limit={variable_limit} reads={measured} controls={dict(controls)}')
            new = await j.service.get_execution_binding()
            actual = await j.player.read_execution_sample()
            after = await j.manager.get_snapshot()
            if operation == 'next':
                assert new.entries == old.entries[1:]
                assert controls == {'playid': 1, 'deleteid': 1}
                assert actual.status.song_uri == 'b.flac'
            else:
                assert new.entries[1:] == old.entries[1:]
                assert new.entries[0][1] not in {r[1] for r in old.entries}
                assert controls == {'addid': 1, 'moveid': 1, 'playid': 1, 'deleteid': 1}
                assert actual.status.song_uri == 'd.flac'
            assert tuple(e.mpd_song_id for e in actual.entries) == tuple(r[1] for r in new.entries)
            assert actual.status.song_id == new.entries[0][1]
            assert actual.status.song_position == 0
            assert tuple(i.queue_item_id for i in after.items if i.position >= 0) == tuple(r[0] for r in new.entries)
            assert next(i for i in after.items if i.position == -1).queue_item_id == old.entries[0][0]
            assert j.history_service.session_id == session
            assert len(await j.history.list_history()) == len(before_history) + 1
            assert j.history_service.active_event.song_id == ('b' if operation == 'next' else 'd')
            # Budgets permit necessary target/observation DTO reads, never O(N) DTOs.
            assert measured.get('get_song', 0) <= 2
            assert measured.get('full_song', 0) <= 2
            # Two necessary full reads cost at most 14 SELECTs, plus at most
            # three independently fresh stages, chunked by distinct song IDs.
            assert measured.get('library_select', 0) <= 14 + 3 * ceil((unique + 1) / variable_limit)
            assert measured.get('projection_select', 0) <= 3 * ceil((unique + 1) / variable_limit)
            assert measured.get('relationship_select', 0) <= 12
            assert measured.get('batch', 0) <= 3
            assert measured['sample'] == 9
    asyncio.run(scenario())


@pytest.mark.parametrize('status', ['MISSING', 'UNREADABLE', 'ABSENT'])
@pytest.mark.parametrize('operation', ['next', 'song'])
@pytest.mark.parametrize('outer', [False, True], ids=['between-operations', 'same-root'])
def test_pending_freshness_preserves_skip_or_whole_rejection(tmp_path, status, operation, outer):
    from server.app.repositories.database import run_transaction
    from server.app.services.playback_service import (
        PlaybackSongNotFoundError,
        PlaybackSongUnavailableError,
    )

    async def scenario():
        async with stock_joint(tmp_path / 'availability.db') as j:
            old = await seed_queue(j, 8)
            # A previous projection must never become an operation cache.
            assert len(await j.service._desired_song_uris()) == 8
            before = await j.business()
            cutoff = len(j.fake.received)
            if status == 'ABSENT':
                # Model a dangling legacy/corrupt catalog reference in the
                # isolated fixture. Production FK contracts remain enforced.
                with sqlite3.connect(j.path) as fixture_connection:
                    fixture_connection.execute('DELETE FROM songs WHERE song_id = ?', ('b',))

            async def change_and_play(connection):
                if status != 'ABSENT':
                    stored = await j.library.get_song('b')
                    await j.library.upsert_song(stored.model_copy(update={'availability_status': status}))
                if operation == 'song':
                    error = PlaybackSongNotFoundError if status == 'ABSENT' else PlaybackSongUnavailableError
                    with pytest.raises(error):
                        await j.service.play_song_now('d')
                    assert await j.business() == before
                    assert j.controls(cutoff) == []
                    assert not j.events
                else:
                    await j.service.next()
                    binding = await j.service.get_execution_binding()
                    assert binding.entries == old.entries[2:]
                    assert (await j.player.read_execution_sample()).status.song_id == old.entries[2][1]
                    snapshot = await j.manager.get_snapshot()
                    assert old.entries[1][0] not in {i.queue_item_id for i in snapshot.items}
                    assert j.history_service.active_event.song_id == 'c'

            if outer:
                await run_transaction(j.path, change_and_play)
            else:
                async def change(connection):
                    if status != 'ABSENT':
                        stored = await j.library.get_song('b')
                        await j.library.upsert_song(stored.model_copy(update={'availability_status': status}))
                await run_transaction(j.path, change)
                # Same mutation is a no-op; operation has an independent root.
                await run_transaction(j.path, change_and_play)
    asyncio.run(scenario())


@pytest.mark.parametrize('status', ['MISSING', 'UNREADABLE'])
def test_unavailable_confirmed_current_is_retained_without_replay(tmp_path, status):
    async def scenario():
        async with stock_joint(tmp_path / 'current.db') as j:
            old = await seed_queue(j, 8)
            song = await j.library.get_song('a')
            await j.library.upsert_song(song.model_copy(update={'availability_status': status}))
            cutoff = len(j.fake.received)
            await j.service.add_to_queue('d')
            binding = await j.service.get_execution_binding()
            assert binding.entries[:8] == old.entries
            assert j.controls(cutoff) == ['addid d.flac']
            assert (await j.player.read_execution_sample()).status.song_id == old.entries[0][1]
            assert j.history_service.active_event.song_id == 'a'
    asyncio.run(scenario())


@pytest.mark.parametrize('outer', [False, True])
def test_changed_uri_is_read_before_preflight_and_exact_occurrence_rebuilt(tmp_path, outer):
    from server.app.repositories.database import run_transaction

    async def scenario():
        async with stock_joint(tmp_path / 'uri.db') as j:
            old = await seed_queue(j, 8)
            await j.service._desired_song_uris()
            stored = await j.library.get_song('c')
            async def change(connection):
                await j.library.upsert_song(stored.model_copy(update={'file_uri': 'new-c.flac'}))
            cutoff = len(j.fake.received)
            if outer:
                async def change_then_play(connection):
                    await change(connection)
                    await j.service.play_song_now('d')
                await run_transaction(j.path, change_then_play)
            else:
                await run_transaction(j.path, change)
                await j.service.play_song_now('d')
            assert j.controls(cutoff)[0] == 'clear'
            binding = await j.service.get_execution_binding()
            assert [r[0] for r in binding.entries[1:]] == [r[0] for r in old.entries[1:]]
            assert [r[2] for r in binding.entries] == ['d.flac', 'b.flac', *(['new-c.flac'] * 6)]
            assert len({r[1] for r in binding.entries}) == 8
            assert not {r[1] for r in binding.entries} & {r[1] for r in old.entries}
            actual = await j.player.read_execution_sample()
            assert [e.song_uri for e in actual.entries] == [r[2] for r in binding.entries]
            assert actual.status.song_id == binding.entries[0][1]
    asyncio.run(scenario())


def test_phase_projection_is_discarded_after_library_write(tmp_path, monkeypatch):
    from server.app.services.playback_service import PlaybackSongUnavailableError

    async def scenario():
        async with stock_joint(tmp_path / 'phase.db') as j:
            await seed_queue(j, 8)
            before = await j.business()
            preflight = j.service._verify_user_queue_baseline
            cutoff = len(j.fake.received)
            async def write_after_preflight(*args, **kwargs):
                await preflight(*args, **kwargs)
                stored = await j.library.get_song('c')
                await j.library.upsert_song(stored.model_copy(update={'availability_status': 'MISSING'}))
            monkeypatch.setattr(j.service, '_verify_user_queue_baseline', write_after_preflight)
            with pytest.raises(PlaybackSongUnavailableError):
                await j.service.play_song_now('d')
            assert await j.business() == before
            assert j.controls(cutoff) == []
            assert (await j.library.get_song('c')).availability_status == 'AVAILABLE'
    asyncio.run(scenario())


def test_refill_new_songs_are_fresh_and_all_occurrences_are_mapped(tmp_path, monkeypatch):
    async def scenario():
        async with stock_joint(tmp_path / 'refill.db') as j:
            await seed_queue(j, 8)
            # Explicitly empty pending: refill inserts songs not in the phase's old set.
            before = await j.manager.get_snapshot()
            current = next(i for i in before.items if i.position == 0)
            # Make z the only unqueued AVAILABLE candidate, independent of the
            # existing randomized AutoPlay order, so its fresh URI must be used.
            for song_id in 'bcdefghi':
                song = await j.library.get_song(song_id)
                await j.library.upsert_song(song.model_copy(update={'availability_status': 'MISSING'}))
            refill = j.autoplay.refill
            async def add_then_refill(context):
                await j.library.upsert_song(Song(song_id='z', title='Z', file_uri='z.flac'))
                return await refill(context)
            monkeypatch.setattr(j.autoplay, 'refill', add_then_refill)
            await j.service.clear()
            queue = await j.manager.get_snapshot()
            binding = await j.service.get_execution_binding()
            assert binding.entries[0][0] == current.queue_item_id
            assert len(binding.entries) == 2
            assert binding.entries[1][2] == 'z.flac'
            assert next(i for i in queue.items if i.position == 1).song_id == 'z'
            assert tuple(i.queue_item_id for i in queue.items if i.position >= 0) == tuple(r[0] for r in binding.entries)
            assert all(i.source == 'AUTOPLAY' for i in queue.items if i.position > 0)
            for item, row in zip((i for i in queue.items if i.position >= 0), binding.entries, strict=True):
                assert (await j.library.get_song(item.song_id)).file_uri == row[2]
            actual = await j.player.read_execution_sample()
            assert tuple(e.mpd_song_id for e in actual.entries) == tuple(r[1] for r in binding.entries)
            assert actual.status.song_id == binding.entries[0][1]
    asyncio.run(scenario())


@pytest.mark.parametrize('operation', ['played', 'previous', 'occurrence'])
def test_occurrence_navigation_keeps_b1_ids_and_bounded_full_reads(tmp_path, monkeypatch, operation):
    async def scenario():
        async with stock_joint(tmp_path / 'occurrence.db') as j:
            await seed_queue(j, 8)
            await j.service.next()
            old = await j.service.get_execution_binding()
            queue = await j.manager.get_snapshot()
            target = next(i for i in queue.items if i.position == (-1 if operation != 'occurrence' else 2))
            counts = measure(j, monkeypatch)
            cutoff = len(j.fake.received)
            if operation == 'previous':
                await j.service.previous()
            else:
                await j.service.play_now(target.queue_item_id)
            measured = dict(counts)
            new = await j.service.get_execution_binding()
            assert new.entries[0][0] == target.queue_item_id
            unaffected = tuple(r for r in old.entries[1:] if r[0] != target.queue_item_id)
            assert new.entries[1:] == unaffected
            assert measured['get_song'] <= 2 and measured['full_song'] <= 2
            assert measured['batch'] <= 3 and measured['library_select'] <= 17
            assert measured['sample'] == (11 if operation != 'occurrence' else 10)
            controls = Counter(c.split()[0] for c in j.controls(cutoff))
            assert controls == ({'addid': 1, 'playid': 1, 'moveid': 1, 'deleteid': 1}
                                if operation != 'occurrence' else {'playid': 1, 'moveid': 1, 'deleteid': 1})
    asyncio.run(scenario())


@pytest.mark.parametrize('status', ['MISSING', 'UNREADABLE'])
def test_scan_availability_changes_are_seen_by_next(tmp_path, status):
    from server.app.models.library import ScanBatch

    async def scenario():
        async with stock_joint(tmp_path / 'scan.db') as j:
            old = await seed_queue(j, 8)
            await j.service._desired_song_uris()
            batch = (ScanBatch(reconciled_root_uri_prefix='b') if status == 'MISSING'
                     else ScanBatch(unreadable_file_uris=('b.flac',)))
            await j.library.apply_scan_batch(batch)
            await j.service.next()
            assert (await j.service.get_execution_binding()).entries == old.entries[2:]
            assert (await j.library.get_song('b')).availability_status == status
    asyncio.run(scenario())


def test_rollback_retry_reads_changed_uri_and_rejects_fixed_identity_conflict(tmp_path, monkeypatch):
    from server.app.repositories.database import run_transaction
    from server.app.services.playback_service import PlaybackReconciliationError

    async def scenario():
        async with stock_joint(tmp_path / 'retry.db') as j:
            await seed_queue(j, 8)
            before = await j.business()
            async def outer_failure(connection):
                await j.service.play_song_now('d', request_id='fixed-b2', request_payload='d')
                raise RuntimeError('outer failure')
            with pytest.raises(RuntimeError, match='outer failure'):
                await run_transaction(j.path, outer_failure)
            assert await j.business() == before
            assert not j.events
            stored = await j.library.get_song('c')
            await j.library.upsert_song(stored.model_copy(update={'file_uri': 'changed-c.flac'}))
            cutoff = len(j.fake.received)
            with pytest.raises(PlaybackReconciliationError, match='fixed Queue changed'):
                await j.service.play_song_now('d', request_id='fixed-b2', request_payload='d')
            assert j.controls(cutoff) == []
            assert await j.business() == before
            assert not j.events
    asyncio.run(scenario())


def test_cancelled_selection_discards_phase_reads_before_retry(tmp_path, monkeypatch):
    async def scenario():
        async with stock_joint(tmp_path / 'cancel.db') as j:
            old = await seed_queue(j, 8)
            before = await j.business()
            prepare = j.service._prepare_play
            cutoff = len(j.fake.received)
            async def cancel(*args, **kwargs):
                raise asyncio.CancelledError()
            monkeypatch.setattr(j.service, '_prepare_play', cancel)
            with pytest.raises(asyncio.CancelledError):
                await j.service.next()
            assert await j.business() == before
            assert j.controls(cutoff) == []
            assert not j.events
            stored = await j.library.get_song('b')
            await j.library.upsert_song(stored.model_copy(update={'availability_status': 'UNREADABLE'}))
            monkeypatch.setattr(j.service, '_prepare_play', prepare)
            await j.service.next()
            assert (await j.service.get_execution_binding()).entries == old.entries[2:]
    asyncio.run(scenario())


def test_independent_operations_in_one_root_do_not_share_projection(tmp_path):
    from server.app.repositories.database import run_transaction

    async def scenario():
        async with stock_joint(tmp_path / 'independent.db') as j:
            await seed_queue(j, 8)
            async def two_operations(connection):
                # First operation reads all c occurrences while AVAILABLE.
                await j.service.add_to_queue('d')
                old = await j.service.get_execution_binding()
                song = await j.library.get_song('c')
                await j.library.upsert_song(song.model_copy(update={'availability_status': 'UNREADABLE'}))
                await j.service.next()
                binding = await j.service.get_execution_binding()
                assert binding.entries == (old.entries[1], old.entries[-1])
                assert (await j.player.read_execution_sample()).status.song_id == old.entries[1][1]
                assert not any(i.song_id == 'c' for i in await j.manager.list_items())
            await run_transaction(j.path, two_operations)
    asyncio.run(scenario())
