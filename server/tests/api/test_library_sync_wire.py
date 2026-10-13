"""Real scanner/SQLite -> public REST/WS golden for B05 Web verification."""
import json
from pathlib import Path

from server.tests.invariants.test_library_sync_wire import install_sync, wait
from server.tests.support.playback import real_client

FIXTURE = Path(__file__).resolve().parents[3] / 'web/tests/fixtures/library-sync.json'


def build_fixture(real_client, media_fixture_dir):
    client, repo, _, _ = real_client
    # Golden starts from explicit read-only samples, never a startup scheduling race.
    client.portal.call(client.app.state.playback_service.observe)
    client.portal.call(client.app.state.output_manager.get_state)
    target = media_fixture_dir / 'metadata.flac'
    sync, player, _, entered, release, completed, failed = install_sync(client, repo, media_fixture_dir, target)
    phases = [client.get('/api/state').json()]
    client.portal.call(sync.request_scan, (target,), 'automatic')
    task = client.portal.start_task_soon(sync.run)
    try:
        wait(client, entered)
        with client.websocket_connect('/api/realtime') as socket:
            initial = socket.receive_json()
            phases.append(initial['state'])
            client.portal.call(release.set)
            wait(client, completed)
            phases.append(client.get('/api/state').json())
            while True:
                synced_invalidation = socket.receive_json()
                if synced_invalidation['sequence'] >= phases[-1]['sequence']:
                    break
            player.disconnected = True
            entered.clear()
            client.portal.call(sync.request_scan, (target,), 'manual')
            wait(client, failed)
            phases.append(client.get('/api/state').json())
            # Consume through this committed terminal watermark, not a prior round.
            while True:
                failure_invalidation = socket.receive_json()
                if failure_invalidation['sequence'] >= phases[-1]['sequence']:
                    break
        assert [s['library_sync']['status'] for s in phases] == ['IDLE', 'SYNCING', 'SYNCED', 'FAILED']
    finally:
        client.portal.call(sync.close)
        task.result(timeout=2)
    identities = {}
    def normalize(value, key=''):
        if isinstance(value, dict):
            return {k: normalize(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [normalize(v, key) for v in value]
        if isinstance(value, str):
            if key.endswith('_at'):
                return '2026-10-12T00:00:00Z'
            if key in ('epoch', 'activity_id'):
                return identities.setdefault(value, f'{key}-{len(identities)}')
        return value
    return normalize({'phases': phases, 'initial': initial, 'synced_invalidation': synced_invalidation,
                      'failure_invalidation': failure_invalidation})


def test_library_sync_server_golden_uses_real_scanner_and_public_wire(real_client, media_fixture_dir):
    assert build_fixture(real_client, media_fixture_dir) == json.loads(FIXTURE.read_text())


if __name__ == '__main__':
    from tempfile import TemporaryDirectory

    from pytest import MonkeyPatch

    from server.tests.conftest import isolate_application_observer, media_fixture_dir
    from server.tests.support.playback import real_client

    with TemporaryDirectory() as directory, MonkeyPatch.context() as patch:
        isolate_application_observer.__wrapped__(patch)
        media = Path(directory) / 'media'
        media.mkdir()
        media_fixture_dir.__wrapped__(media)
        fixture = real_client.__wrapped__(Path(directory), patch)
        try:
            FIXTURE.write_text(json.dumps(build_fixture(next(fixture), media), ensure_ascii=False, indent=2) + '\n')
        finally:
            fixture.close()
