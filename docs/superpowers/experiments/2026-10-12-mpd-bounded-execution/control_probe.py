"""THROWAWAY destructive live probe; requires --authorize-clear-existing.

Backs up current MPD queue before ONE clear, then operates only owned IDs.
Restores URI order/modes/state/elapsed; MPD original IDs cannot be restored.
Never accesses MS databases or music files. Existing .venv only.
"""
import argparse
import asyncio
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--authorize-clear-existing', action='store_true', required=True)
parser.add_argument('--repo', type=Path, default=Path('/home/Gold/WorkSpace/MPD-Server/mpd-bounded-experiment'))
parser.add_argument('--out', type=Path, default=Path(__file__).parent / 'controlled-run')
parser.add_argument('--host', default='192.168.3.94')
parser.add_argument('--resume-owned-run', type=Path, help='Resume a failed probe only if actual queue IDs/modes match its owned entries; reuse its original backup')
parser.add_argument('--trials', type=int, default=5)
parser.add_argument('--playing-seek-tolerance', type=float, default=1.0, help='Measured live status granularity/buffering tolerance, seconds; paused tolerance remains 0.6')
args = parser.parse_args()
sys.path.insert(0, str(args.repo))
from server.app.player.mpd_adapter import MPDAdapter

args.out.mkdir(parents=True, exist_ok=True)
logfile = (args.out / 'events.jsonl').open('w')
metrics = defaultdict(list)
result = {'started_utc': datetime.now(timezone.utc).isoformat(), 'trials': [],
          'authorization': 'User: 清空队列再测试',
          'playing_seek_tolerance_seconds': args.playing_seek_tolerance, 'natural_end_method': 'pause, seek to duration-3 with progress confirmation, resume, then let MPD finish; no next or playid B at transition'}
owned = []
expected = []
modes = ('random', 'repeat', 'single', 'consume')
active_tasks = []


def log(event, **data):
    record = {'event': event, 'at': time.perf_counter(), 'utc': datetime.now(timezone.utc).isoformat(), **data}
    logfile.write(json.dumps(record, ensure_ascii=False) + '\n')
    logfile.flush()
    if event != 'command':
        print(json.dumps(record, ensure_ascii=False), flush=True)


def client(idle=False):
    return MPDAdapter(args.host, connection_timeout=3, command_timeout=10 if idle else 5)


async def raw(a, cmd, *params, metric=None):
    started = time.perf_counter()
    value = await a._command(cmd, *map(str, params))
    elapsed = (time.perf_counter() - started) * 1000
    if metric:
        metrics[metric].append(elapsed)
    log('command', command=cmd, args=params, ack_ms=elapsed, response=value.as_dict() if cmd == 'status' else None)
    return value


def rows(response):
    entries = []
    for k, v in response.pairs:
        if k == 'file':
            entries.append({})
        if entries:
            entries[-1][k] = v
    return entries


async def sample(a, bounded=True):
    sample_started = time.perf_counter()
    for _ in range(2):
        s1 = (await raw(a, 'status')).as_dict()
        epoch = a._connection_epoch
        p = rows(await raw(a, 'playlistinfo', *(['0:4'] if bounded else [])))
        s2 = (await raw(a, 'status')).as_dict()
        keys = ('songid', 'song', 'state', 'playlist', 'playlistlength', 'partition', *modes)
        if epoch == a._connection_epoch and all(s1.get(k) == s2.get(k) for k in keys):
            current = next((r for r in p if r.get('Id') == s2.get('songid')), None)
            pos = int(s2.get('song', '-1'))
            future = [r for r in p if int(r['Pos']) > pos]
            if bounded:
                metrics['bounded_consistent_sample'].append((time.perf_counter() - sample_started) * 1000)
            return {'status': s2, 'entries': p, 'current': current, 'next': future[:2]}
    raise RuntimeError('inconsistent sample')


async def fence(a, current_id=None):
    value = await sample(a)
    assert [r['Id'] for r in value['entries']] == expected, 'foreign queue drift; stop writes'
    assert all(value['status'].get(m) == '0' for m in modes), 'foreign mode drift; stop writes'
    assert len(expected) <= 4
    if current_id and value['status'].get('songid') != current_id:
        log('unexpected_current_evidence', expected=current_id, actual=value)
        raise AssertionError('unexpected current; stop writes')
    return value


async def add(a, uri, pos=None):
    await fence(a)
    began = time.perf_counter()
    response = await raw(a, 'addid', uri, *([] if pos is None else [pos]), metric='addid_ack')
    song_id = response.as_dict()['Id']
    owned.append(song_id)
    expected.insert(len(expected) if pos is None else pos, song_id)
    value = await fence(a)
    assert next(r for r in value['entries'] if r['Id'] == song_id)['file'] == uri
    metrics['addid_confirm_total'].append((time.perf_counter()-began)*1000)
    return song_id


async def delete(a, song_id, current_id=None):
    await fence(a, current_id)
    assert song_id in owned and song_id != current_id
    began = time.perf_counter()
    await raw(a, 'deleteid', song_id, metric='deleteid_ack')
    expected.remove(song_id)
    value = await fence(a, current_id)
    metrics['delete_prepared_or_departed_total'].append((time.perf_counter()-began)*1000)
    return value


async def control(a, cmd, target, state, *params):
    await fence(a, target if cmd != 'playid' else None)
    began = time.perf_counter()
    await raw(a, cmd, *params, metric=cmd + '_ack')
    deadline = time.perf_counter()+3
    while time.perf_counter() < deadline:
        value = await fence(a, target)
        if value['status']['state'] == state:
            metrics[cmd + '_' + state + '_confirm_total'].append((time.perf_counter()-began)*1000)
            return value
        await asyncio.sleep(.02)
    raise RuntimeError('actual state confirmation timeout')


async def seek(a, target, seconds):
    await fence(a, target)
    began = time.perf_counter()
    await raw(a, 'seekid', target, seconds, metric='seek_ack')
    deadline = time.perf_counter()+3
    while time.perf_counter() < deadline:
        value = await fence(a, target)
        playing = value['status']['state'] == 'play'
        advanced = time.perf_counter() - began if playing else 0
        projected = seconds + advanced
        tolerance = args.playing_seek_tolerance if playing else .6
        error = float(value['status']['elapsed']) - projected
        if abs(error) < tolerance:
            metrics['seek_confirm_total'].append((time.perf_counter()-began)*1000)
            log('seek_confirmed', requested=seconds, projected=projected, tolerance=tolerance, error_seconds=error, actual=value['status'])
            return value
        await asyncio.sleep(.02)
    log('seek_confirmation_timeout', target_seconds=seconds, actual=value)
    raise RuntimeError('seek confirmation timeout')


async def natural(a, aid, bid, duration):
    # Confirm seek while paused, before A can naturally leave during confirmation.
    await control(a, 'pause', aid, 'pause', 1)
    await seek(a, aid, duration - 3)
    idle, query, poll, reference = client(True), client(), client(), client()
    found = {}
    await idle._ensure_connected()
    await poll._ensure_connected()
    await reference._ensure_connected()

    async def listen():
        while True:
            response = await raw(idle, 'idle', 'player', 'playlist', 'options')
            signal = time.perf_counter()
            value = await sample(query)
            if value['status'].get('songid') == bid:
                found['idle'] = {'signal': signal, 'confirmed': time.perf_counter(), 'sample': value, 'changes': response.as_dict()}
                return

    async def polling():
        while True:
            value = (await raw(poll, 'status')).as_dict()
            if value.get('songid') == bid:
                value2 = await sample(poll)
                found['poll'] = {'confirmed': time.perf_counter(), 'sample': value2}
                return
            await asyncio.sleep(1)

    async def precise():
        last_start = None
        while True:
            started = time.perf_counter()
            state = (await raw(reference, 'status')).as_dict()
            ended = time.perf_counter()
            if state.get('songid') == bid:
                found['bracket'] = [last_start, ended]
                return
            assert state.get('songid') == aid, 'unexpected natural target'
            last_start = started
            await asyncio.sleep(.02)

    tasks = [asyncio.create_task(f()) for f in (listen, polling, precise)]
    active_tasks.extend(tasks)
    try:
        await control(a, 'pause', aid, 'play', 0)
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=12)
        value = await fence(a, bid)
        assert value['status']['state'] == 'play' and value['current']['Pos'] == '1'
        assert value['current']['Id'] == bid
        low, high = found['bracket']
        for source in ('idle', 'poll'):
            at = found[source]['confirmed']
            interval = [max(0,(at-high)*1000), max(0,(at-low)*1000)]
            found[source]['delay_interval_ms'] = interval
            metrics['natural_' + source + '_delay_upper_ms'].append(interval[1])
        found['bracket_width_ms'] = (high-low)*1000
        found['position_1_confirmed'] = True
        found['no_replay_B'] = True
        log('natural_transition', **found)
        return found
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.gather(idle.close(), query.close(), poll.close(), reference.close())


async def main():
    a = client()
    backup = None
    cleared = False
    competition = False
    try:
        actual_start = await sample(a, False)
        resume_ids = None
        if args.resume_owned_run:
            previous = json.loads((args.resume_owned_run / 'results.json').read_text())
            resume_ids = [r['Id'] for r in previous['restoration']['actual']['entries']]
            assert [r['Id'] for r in actual_start['entries']] == resume_ids, 'foreign resume queue drift'
            assert all(actual_start['status'].get(m) == '0' for m in modes), 'foreign resume mode drift'
            backup = json.loads((args.resume_owned_run / 'original.json').read_text())
            result['resume_owned_run'] = str(args.resume_owned_run)
        else:
            backup = actual_start
        backup['commands'] = (await raw(a, 'commands')).as_dict()
        backup['outputs'] = (await raw(a, 'outputs')).as_dict()
        (args.out / 'original.json').write_text(json.dumps(backup, ensure_ascii=False, indent=2))
        result['original_status'] = backup['status']
        selected = []
        for row in backup['entries']:
            if float(row.get('duration', 0)) > 30 and row['file'] not in [r['file'] for r in selected]:
                selected.append(row)
            if len(selected) == 5:
                break
        assert len(selected) == 5, 'need 5 existing songs'
        result['selected_songs'] = selected
        log('backup_before_authorized_clear', status=backup['status'], count=len(backup['entries']))
        if resume_ids is None:
            await raw(a, 'clear')  # ONE explicit human-authorized destructive takeover.
        else:
            await raw(a, 'stop')
            for song_id in resume_ids:
                await raw(a, 'deleteid', song_id)
        cleared = True
        assert (await raw(a, 'status')).as_dict()['playlistlength'] == '0'
        for mode in modes:
            await raw(a, mode, '0')
        await fence(a)
        for trial in range(args.trials):
            aid = await add(a, selected[0]['file'])
            bid = await add(a, selected[1]['file'])
            cid = await add(a, selected[2]['file'])
            value = await control(a, 'playid', aid, 'play', aid)
            log('three_track_start', trial=trial, sample=value)
            progress1 = await fence(a, aid)
            await asyncio.sleep(1.2)
            progress2 = await fence(a, aid)
            assert float(progress2['status']['elapsed']) > float(progress1['status']['elapsed']) + .5
            await control(a, 'pause', aid, 'pause', 1)
            paused1 = await fence(a, aid)
            await asyncio.sleep(1.2)
            paused2 = await fence(a, aid)
            assert abs(float(paused1['status']['elapsed'])-float(paused2['status']['elapsed'])) < .1
            resumed = await control(a, 'pause', aid, 'play', 0)
            assert float(resumed['status']['elapsed']) >= float(paused2['status']['elapsed']) - .1
            await seek(a, aid, 10)
            transition = await natural(a, aid, bid, float(selected[0]['duration']))
            b_before = await fence(a, bid)
            await delete(a, aid, bid)
            did = await add(a, selected[3]['file'])
            b_after = await fence(a, bid)
            assert len(expected) == 3 and b_after['current']['Pos'] == '0'
            assert float(b_after['status']['elapsed']) >= float(b_before['status']['elapsed']) - .1
            # Insert next, replacing old next, transient 4 -> steady 3.
            began = time.perf_counter()
            eid = await add(a, selected[4]['file'], 1)
            await delete(a, cid, bid)
            metrics['insert_next_replace_total'].append((time.perf_counter()-began)*1000)
            assert expected == [bid, eid, did]
            # Change next-next to a duplicate URI; IDs must remain distinct.
            began = time.perf_counter()
            duplicate = await add(a, selected[1]['file'])
            await delete(a, did, bid)
            metrics['replace_next_next_total'].append((time.perf_counter()-began)*1000)
            value = await fence(a, bid)
            matching = [r['Id'] for r in value['entries'] if r['file'] == selected[1]['file']]
            assert matching == [bid, duplicate] and bid != duplicate
            assert value['current']['Id'] == bid
            # Move by ID and actual destination; never URI-first selection.
            began = time.perf_counter()
            await fence(a, bid)
            await raw(a, 'moveid', duplicate, 1, metric='moveid_ack')
            expected[:] = [bid, duplicate, eid]
            await fence(a, bid)
            metrics['move_prepared_total'].append((time.perf_counter()-began)*1000)
            await delete(a, eid, bid)
            replacement = await add(a, selected[2]['file'])
            assert len(expected) == 3
            dup_played = await control(a, 'playid', duplicate, 'play', duplicate)
            assert dup_played['current']['file'] == selected[1]['file'] and dup_played['current']['Id'] != bid
            result['trials'].append({'trial': trial, 'natural': transition,
                'playing_progress_delta': float(progress2['status']['elapsed'])-float(progress1['status']['elapsed']),
                'paused_progress_delta': float(paused2['status']['elapsed'])-float(paused1['status']['elapsed']),
                'resume_did_not_restart': True, 'duplicate_uri_different_id_confirmed': True,
                'after_departed_cleanup_and_refill': b_after,
                'insert_replace_delete_move_confirmed': True, 'steady_3_transient_4': True})
            log('trial_passed', trial=trial, current=dup_played['current'], expected=expected)
            await raw(a, 'stop')
            for song_id in [bid, duplicate, replacement]:
                await delete(a, song_id)
        result['control_status'] = 'PASSED'
    except (RuntimeError, ValueError, AssertionError, OSError) as exc:
        result['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        competition = 'foreign' in str(exc) or 'unexpected' in str(exc)
        log('failure', **result['error'])
    finally:
        # Restoration runs only when actual queue still consists exclusively of owned IDs.
        try:
            if cleared and backup:
                actual = await sample(a, False)
                actual_ids = [r['Id'] for r in actual['entries']]
                safe = not competition and all(i in owned for i in actual_ids)
                if not safe:
                    result['restoration'] = {'status': 'BLOCKED_COMPETITION', 'actual': actual,
                        'note': 'Stopped writes; original backup retained for explicit recovery.'}
                else:
                    await raw(a, 'stop')
                    for song_id in actual_ids:
                        await a.queue_delete(int(song_id))
                    restored = []
                    for index, entry in enumerate(backup['entries']):
                        response = await raw(a, 'addid', entry['file'])
                        restored.append(response.as_dict()['Id'])
                        if index % 25 == 0:
                            check = (await raw(a, 'status')).as_dict()
                            assert int(check['playlistlength']) == len(restored), 'foreign restoration queue drift'
                            assert all(check.get(m) == '0' for m in modes), 'foreign restoration mode drift'
                    result['restored_ids'] = restored
                    # Restore modes after queue population; no clear and no writes to DB.
                    original = backup['status']
                    for mode in modes:
                        await raw(a, mode, original[mode])
                    if original.get('song') is not None:
                        target = restored[int(original['song'])]
                        if original['state'] in ('play', 'pause'):
                            # Pause-before-seek reduces audible start during restoration.
                            await raw(a, 'pause', 1)
                            await raw(a, 'playid', target)
                            await raw(a, 'pause', 1)
                            await raw(a, 'seekid', target, original.get('elapsed', '0'))
                            if original['state'] == 'play':
                                await raw(a, 'pause', 0)
                    final = await sample(a, False)
                    uri_order_ok = [r['file'] for r in final['entries']] == [r['file'] for r in backup['entries']]
                    modes_ok = all(final['status'].get(m) == original.get(m) for m in modes)
                    current_ok = final['status']['state'] == original['state']
                    if original['state'] in ('play', 'pause'):
                        original_uri = backup['entries'][int(original['song'])]['file']
                        current_ok = current_ok and final['current']['file'] == original_uri
                        current_ok = current_ok and abs(float(final['status']['elapsed'])-float(original['elapsed'])) < 1
                    result['restoration'] = {'status': 'CONFIRMED' if uri_order_ok and modes_ok and current_ok else 'FAILED',
                        'uri_order_ok': uri_order_ok, 'modes_ok': modes_ok, 'current_state_position_ok': current_ok,
                        'original_ids_restored': False, 'final_status': final['status'],
                        'warning': 'Clear destroys original IDs. MS old bindings become untrusted; no database was modified.'}
                    (args.out / 'final.json').write_text(json.dumps(final, ensure_ascii=False, indent=2))
                    log('restoration', **result['restoration'])
        except (RuntimeError, ValueError, AssertionError, OSError) as exc:
            result['restoration_error'] = str(exc)
            log('restoration_failure', error=str(exc))
        await a.close()
        result['metrics'] = {k: {'n': len(v), 'mean_ms': statistics.mean(v),
            'p95_ms': sorted(v)[math.ceil(.95*len(v))-1], 'max_ms': max(v), 'samples_ms': v}
            for k, v in metrics.items()}
        result['statistics_limit'] = 'Nearest-rank P95; 5 trials insufficient for stable tail estimate. Natural delays are upper bounds from reference intervals, not exact event timestamps.'
        (args.out / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        log('summary', metrics={k:{a:b for a,b in v.items() if a != 'samples_ms'} for k,v in result['metrics'].items()})
        logfile.close()
    return 1 if 'error' in result or result.get('restoration',{}).get('status') != 'CONFIRMED' else 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
