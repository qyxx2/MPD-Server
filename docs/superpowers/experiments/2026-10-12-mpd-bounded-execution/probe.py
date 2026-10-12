"""THROWAWAY live MPD probe. Read-only: never clears, plays or changes modes.

Uses the frozen branch's real MPDAdapter and protocol parser, not MockMPD.
Run with the existing checkout's .venv/bin/python; see --help.
Large/playing/foreign queue means control experiments are BLOCKED by design.
"""
import argparse
import asyncio
import json
import math
import statistics
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from itertools import pairwise
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, default=Path('/home/Gold/WorkSpace/MPD-Server/mpd-bounded-experiment'))
parser.add_argument('--host', default='192.168.3.94')
parser.add_argument('--port', type=int, default=6600)
parser.add_argument('--samples', type=int, default=50)
parser.add_argument('--observe-seconds', type=float, default=300)
parser.add_argument('--out', type=Path, default=Path(__file__).parent / 'run')
args = parser.parse_args()
sys.path.insert(0, str(args.repo))
from server.app.player.mpd_adapter import MPDAdapter, _parse_greeting

args.out.mkdir(parents=True, exist_ok=True)
logfile = (args.out / 'events.jsonl').open('w')
timings = defaultdict(list)
report = {'kind': 'READ_ONLY_LIVE_MPD', 'host': args.host, 'port': args.port,
          'adapter': str(args.repo / 'server/app/player/mpd_adapter.py'),
          'python': sys.executable, 'started_utc': datetime.now(timezone.utc).isoformat()}
allowed = {'status', 'playlistinfo', 'commands', 'stats', 'outputs', 'listpartitions', 'idle', 'currentsong'}
keys = ('playlist', 'playlistlength', 'songid', 'song', 'state', 'partition', 'random', 'repeat', 'single', 'consume')


def log(event, **data):
    row = {'event': event, 'perf_counter': time.perf_counter(),
           'utc': datetime.now(timezone.utc).isoformat(), **data}
    logfile.write(json.dumps(row, ensure_ascii=False) + '\n')
    logfile.flush()
    if event not in {'command', 'poll', 'reference'}:
        print(json.dumps(row, ensure_ascii=False), flush=True)
    return row['perf_counter']


async def connection(host, port):
    reader, writer = await asyncio.open_connection(host, port)
    # Let the actual Adapter consume and validate the greeting, while recording it.
    # StreamReader has no public peek: read it once and return a wrapper for first read.
    greeting = await asyncio.wait_for(reader.readline(), 3)
    version = _parse_greeting(greeting)
    report['mpd_version'] = version
    log('connected', version=version)

    class Reader:
        first = True

        async def readline(self):
            if self.first:
                self.first = False
                return greeting
            return await reader.readline()

    return Reader(), writer


def adapter(idle=False):
    return MPDAdapter(args.host, args.port, connection_timeout=3,
                      command_timeout=15 if idle else 5, connection_factory=connection)


async def command(client, name, *params, metric=None):
    assert name in allowed, f'write command forbidden: {name}'
    started = time.perf_counter()
    response = await client._command(name, *params)
    ended = time.perf_counter()
    ms = (ended - started) * 1000
    if metric:
        timings[metric].append(ms)
    log('command', name=name, params=params, elapsed_ms=ms,
        pairs=len(response.pairs), start=started, end=ended)
    return response


def entries(response):
    rows = []
    for key, value in response.pairs:
        if key == 'file':
            rows.append({})
        if rows:
            rows[-1][key] = value
    return rows


async def sample(client, start=0, metric=None):
    began = time.perf_counter()
    for attempt in range(2):
        before = (await command(client, 'status')).as_dict()
        epoch = client._connection_epoch
        # Foreign queue: actual-current window, not a claim of bounded ownership.
        pos = int(before.get('song', '0')) if start is None else start
        rows = entries(await command(client, 'playlistinfo', f'{pos}:{pos + 4}'))
        after = (await command(client, 'status')).as_dict()
        if epoch == client._connection_epoch and all(before.get(k) == after.get(k) for k in keys):
            current = next((r for r in rows if r.get('Id') == after.get('songid')), None)
            actual_pos = int(after.get('song', '-1'))
            future = [r for r in rows if int(r.get('Pos', '-1')) > actual_pos]
            if after.get('songid') and start is None:
                assert current and int(current['Pos']) == actual_pos
            result = {'status': after, 'rows': rows, 'current': current,
                      'next': future[:2], 'epoch': epoch, 'attempt': attempt + 1}
            if metric:
                timings[metric].append((time.perf_counter() - began) * 1000)
            return result
    raise RuntimeError('inconsistent status/playlist/status after bounded retry')


def health():
    try:
        with urllib.request.urlopen(f'http://{args.host}:8000/api/health', timeout=3) as response:
            return {'url': response.url, 'status': response.status,
                    'body': response.read(4096).decode(errors='replace')}
    except (OSError, ValueError, RuntimeError, AssertionError) as exc:
        return {'error': str(exc), 'meaning': 'controller absence NOT proven'}


async def main():
    client, idle, reference = adapter(), adapter(True), adapter()
    tasks = []
    try:
        # First network failure is explicit, never substituted with a fake.
        original = (await command(client, 'status')).as_dict()
        commands = (await command(client, 'commands')).as_dict()
        full = await command(client, 'playlistinfo', metric='playlistinfo_full')
        original_rows = entries(full)
        backup = {'status': original, 'playlist_pairs': full.pairs, 'entries': original_rows,
                  'commands': commands,
                  'outputs': (await command(client, 'outputs')).as_dict(),
                  'partitions': (await command(client, 'listpartitions')).as_dict(),
                  'stats': (await command(client, 'stats')).as_dict()}
        (args.out / 'original.json').write_text(json.dumps(backup, ensure_ascii=False, indent=2))
        report['original_status'] = original
        report['remote_ms_health'] = await asyncio.to_thread(health)
        report['controller_check'] = 'Local server uses MockMPD; remote health only proves service reachable, not exclusive ownership. MPD has no advertised clients command.'
        report['control_experiments'] = {'status': 'BLOCKED',
            'reason': 'Existing default queue is not isolated and is playing; preserving original IDs/order/modes. New partition with no output would not validate real playback; moving active output would interfere.',
            'not_run': ['3-track buffer', 'addid', 'playid', 'pause/resume', 'seek',
                        'insert/replace/delete prepared songs', 'controlled duplicate URI', 'position-1 natural B with consume=0']}
        log('preflight', status=original, entries=len(original_rows),
            remote_ms_health=report['remote_ms_health'], controls=report['control_experiments'])
        by_uri = defaultdict(list)
        for row in original_rows:
            by_uri[row['file']].append(row['Id'])
        duplicates = [{'uri': uri, 'ids': ids} for uri, ids in by_uri.items() if len(ids) > 1]
        report['duplicate_uri_groups'] = len(duplicates)
        report['duplicate_examples'] = duplicates[:3]
        for i in range(args.samples):
            await command(client, 'status', metric='status_wire')
            await command(client, 'playlistinfo', '0:4', metric='playlistinfo_0_4')
            await sample(client, None, metric='consistent_current_window')
            await command(client, 'playlistinfo', metric='playlistinfo_full')
            started = time.perf_counter()
            await client.status()  # Existing public API includes currentsong.
            timings['adapter_status'].append((time.perf_counter() - started) * 1000)
            started = time.perf_counter()
            await client.read_execution_sample()  # Existing full-list API comparison.
            timings['adapter_full_execution_sample'].append((time.perf_counter() - started) * 1000)
        log('benchmarks_finished', samples=args.samples)
        observed = {'idle': [], 'poll': [], 'reference': [], 'progress': []}
        stop_at = time.perf_counter() + args.observe_seconds

        async def observe_idle():
            while time.perf_counter() < stop_at:
                try:
                    response = await command(idle, 'idle', 'player', 'playlist', 'options')
                    received = time.perf_counter()
                    value = await sample(client, None)
                    confirmed = time.perf_counter()
                    observed['idle'].append({'received': received, 'confirmed': confirmed,
                        'changes': response.as_dict(), 'status': value['status']})
                    timings['idle_signal_to_consistent_confirmation'].append((confirmed - received) * 1000)
                    log('idle_change', changes=response.as_dict(), sample=value,
                        signal_to_confirm_ms=(confirmed - received) * 1000)
                except (OSError, ValueError, RuntimeError, AssertionError) as exc:
                    # Quiet idle legitimately times out; adapter closes, reconnect with backoff.
                    log('idle_timeout_or_error', error=str(exc))
                    await asyncio.sleep(.25)

        async def observe_poll():
            last = None
            while time.perf_counter() < stop_at:
                started = time.perf_counter()
                state = (await command(client, 'status', metric='status_poll')).as_dict()
                ended = time.perf_counter()
                record = {'started': started, 'ended': ended, 'status': state}
                observed['poll'].append(record)
                observed['progress'].append({'at': ended, 'state': state.get('state'),
                    'id': state.get('songid'), 'elapsed': state.get('elapsed')})
                log('poll', **record)
                signature = tuple(state.get(k) for k in keys)
                if signature != last:
                    value = await sample(client, None)
                    log('actual_state_change', sample=value)
                last = signature
                await asyncio.sleep(1)  # Spec: one second after completed cycle.

        async def reference_transition():
            # Fine probe only near expected track end; establishes interval, not exact timestamp.
            while time.perf_counter() < stop_at:
                started = time.perf_counter()
                state = (await command(reference, 'status')).as_dict()
                ended = time.perf_counter()
                observed['reference'].append({'started': started, 'ended': ended, 'status': state})
                log('reference', start=started, end=ended, status=state)
                remaining = float(state.get('duration', 0)) - float(state.get('elapsed', 0))
                await asyncio.sleep(.02 if state.get('state') == 'play' and 0 <= remaining <= 3 else 1)

        tasks = [asyncio.create_task(f()) for f in (observe_idle, observe_poll, reference_transition)]
        await asyncio.sleep(args.observe_seconds)
        for task in tasks:
            task.cancel()
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        report['observer_errors'] = [str(r) for r in task_results if isinstance(r, BaseException) and not isinstance(r, asyncio.CancelledError)]
        report['observations'] = observed
        transitions = []
        refs = observed['reference']
        for old, new in pairwise(refs):
            if old['status'].get('songid') != new['status'].get('songid'):
                # True transition bracket includes status request/response uncertainty.
                low, high = old['started'], new['ended']
                transition = {'from': old['status'].get('songid'), 'to': new['status'].get('songid'),
                              'actual_transition_bracket': [low, high], 'bracket_width_ms': (high-low)*1000,
                              'cause': 'uncommanded by probe; natural completion compatible, external cause not excluded'}
                for source in ('idle', 'poll'):
                    candidates = [r for r in observed[source] if r['status'].get('songid') == new['status'].get('songid')
                                  and r.get('confirmed', r.get('ended')) >= low]
                    if candidates:
                        first = candidates[0]
                        at = first.get('confirmed', first.get('ended'))
                        transition[source + '_confirmation_delay_interval_ms'] = [max(0, (at-high)*1000), max(0, (at-low)*1000)]
                        if source == 'idle':
                            transition['idle_signal_delay_interval_ms'] = [max(0,(first['received']-high)*1000), max(0,(first['received']-low)*1000)]
                transitions.append(transition)
                log('transition_interval', **transition)
        report['transitions'] = transitions
        final = (await command(client, 'status')).as_dict()
        final_rows = entries(await command(client, 'playlistinfo'))
        original_ids = [r['Id'] for r in original_rows]
        final_ids = [r['Id'] for r in final_rows]
        report['final_status'] = final
        report['safety'] = {'write_commands_sent': 0, 'restoration_needed': False,
            'modes_unchanged': all(original.get(k) == final.get(k) for k in ('random','repeat','single','consume')),
            'removed_original_ids': [i for i in original_ids if i not in set(final_ids)],
            'added_ids': [i for i in final_ids if i not in set(original_ids)],
            'surviving_order_preserved': [i for i in original_ids if i in set(final_ids)] == [i for i in final_ids if i in set(original_ids)],
            'note': 'Existing consume=1 can delete completed entries without probe writes.'}
        (args.out / 'final.json').write_text(json.dumps({'status': final, 'entries': final_rows}, ensure_ascii=False, indent=2))
        log('safety', **report['safety'])
    except (OSError, ValueError, RuntimeError, AssertionError) as exc:
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        log('failure', **report['error'])
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.gather(client.close(), idle.close(), reference.close())
        summary = {}
        for metric, values in timings.items():
            ordered = sorted(values)
            summary[metric] = {'n': len(values), 'mean_ms': statistics.mean(values),
                'p95_ms': ordered[math.ceil(len(values)*.95)-1], 'max_ms': max(values),
                'p95_method': 'nearest rank; descriptive only, LAN single session, not a production guarantee',
                'samples_ms': values}
        report['timings'] = summary
        (args.out / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        log('summary', timings={k: {a:b for a,b in v.items() if a != 'samples_ms'} for k,v in summary.items()})
        logfile.close()
    return 1 if 'error' in report else 0


async def bounded():
    return await asyncio.wait_for(main(), timeout=args.observe_seconds + args.samples * 30 + 60)


if __name__ == '__main__':
    raise SystemExit(asyncio.run(bounded()))
