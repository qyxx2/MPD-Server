"""B05: committed scanner facts share the existing snapshot/delivery boundary."""
import asyncio

from server.app.main import app
from server.app.models.library_sync import LibrarySyncState
from server.app.player.mock_mpd import MockMPD
from server.app.player.models import DatabaseUpdateStatus
from server.app.repositories.database import run_transaction
from server.app.services.events import LibrarySyncChangedEvent
from server.app.services.library_scanner import LibraryScanner
from server.app.services.library_sync_service import LibrarySyncService


def install_sync(client, repository, root, target):
    cached_output = app.state.output_manager.get_cached_state()
    app.state.state_service._output_snapshot = lambda: cached_output
    coordinator = app.state.realtime_coordinator
    entered, release, completed, failed = (asyncio.Event() for _ in range(4))

    class Player(MockMPD):
        async def update_database(self):
            entered.set()
            await release.wait()
            if self.disconnected:
                raise OSError('test disconnected')

        async def database_update_status(self):
            if self.disconnected:
                raise OSError('test disconnected')
            return DatabaseUpdateStatus(updating=False)

    class Publisher:
        async def publish(self, event):
            await coordinator.publish(event)
            if isinstance(event, LibrarySyncChangedEvent):
                if event.state.status == 'SYNCED':
                    completed.set()
                elif event.state.status == 'FAILED':
                    failed.set()

    player = Player(library_uris=(str(target),))
    player.disconnected = False
    scanner = LibraryScanner(repository, coordinator, coordinator=coordinator)
    sync = LibrarySyncService(scanner, player, root, event_publisher=Publisher())
    return sync, player, coordinator, entered, release, completed, failed


def wait(client, event):
    client.portal.call(asyncio.wait_for, event.wait(), 2)


def test_sync_sequence_does_not_change_library_revision(real_client, media_fixture_dir):
    client, repo, _, _ = real_client
    target = media_fixture_dir / 'metadata.flac'
    sync, _, coordinator, entered, release, completed, _ = install_sync(client, repo, media_fixture_dir, target)
    before = client.get('/api/state').json()
    client.portal.call(sync.request_scan, (target,), 'manual')
    task = client.portal.start_task_soon(sync.run)
    try:
        wait(client, entered)
        syncing = client.get('/api/state').json()
        assert syncing['library_sync']['status'] == 'SYNCING'
        assert syncing['library_sync']['pending_count'] == 1
        assert client.get('/api/library/songs').json()['count'] == 4
        assert syncing['revisions']['library'] == before['revisions']['library'] + 1
        assert coordinator._subscriptions == set()
        client.portal.call(release.set)
        wait(client, completed)
        synced = client.get('/api/state').json()
        assert synced['library_sync']['status'] == 'SYNCED'
        assert synced['sequence'] > syncing['sequence']
        assert synced['revisions'] == syncing['revisions']
        for field in ('queue', 'history', 'playback', 'output'):
            assert synced[field] == syncing[field] == before[field]
        assert client.portal.call(sync.player.queue_entries) == []
    finally:
        client.portal.call(sync.close)
        task.result(timeout=2)


def test_old_generation_disconnect_and_initial_snapshot_recover(real_client, media_fixture_dir):
    client, repo, _, _ = real_client
    target = media_fixture_dir / 'metadata.flac'
    sync, player, coordinator, entered, release, completed, failed = install_sync(client, repo, media_fixture_dir, target)
    client.portal.call(sync.request_scan, (target,), 'automatic')
    task = client.portal.start_task_soon(sync.run)
    try:
        wait(client, entered)
        with client.websocket_connect('/api/realtime') as first, client.websocket_connect('/api/realtime') as second:
            initial = first.receive_json()
            assert initial['state']['library_sync']['status'] == 'SYNCING'
            other = second.receive_json()
            assert other['state']['library_sync'] == initial['state']['library_sync']
            assert other['sequence'] == initial['sequence']
            assert len(coordinator._subscriptions) == 2
            player.disconnected = True
            client.portal.call(release.set)
            wait(client, failed)
            for socket in (first, second):
                while True:
                    frame = socket.receive_json()
                    if 'library_sync' in frame['domains']:
                        break
                assert frame['sequence'] == coordinator.marker().sequence
        failed_state = client.get('/api/state').json()
        assert failed_state['library_sync']['status'] == 'FAILED'
        player.disconnected = False
        completed.clear()
        client.portal.call(sync.request_scan, (target,), 'manual')
        wait(client, completed)
        recovered = client.get('/api/state').json()
        assert recovered['library_sync']['generation'] == 2
        assert recovered['revisions'] == failed_state['revisions']  # no-op scan
        before = coordinator.marker()
        late = LibrarySyncState(status='FAILED', generation=1, activity_id='late')
        client.portal.call(coordinator.publish, LibrarySyncChangedEvent(state=late))
        assert coordinator.marker() == before
        with client.websocket_connect('/api/realtime') as reconnected:
            frame = reconnected.receive_json()
            assert frame['type'] == 'snapshot'
            assert frame['state']['library_sync'] == recovered['library_sync']
            assert frame['sequence'] == recovered['sequence']
        assert not coordinator._subscriptions
        async def rollback(_):
            coordinator.stage_library_sync(LibrarySyncState(status='SYNCING', generation=3))
            raise RuntimeError('rollback')
        try:
            client.portal.call(run_transaction, repo.path, rollback)
        except RuntimeError:
            pass
        assert client.get('/api/state').json()['library_sync'] == recovered['library_sync']
    finally:
        client.portal.call(sync.close)
        task.result(timeout=2)


def test_partial_confirmation_changes_only_sequence_and_duplicate_poll_is_noop(
    real_client, media_fixture_dir,
):
    client, repo, _, _ = real_client
    first, second = (media_fixture_dir / name for name in ('metadata.flac', 'sidecar.mp3'))
    sync, player, coordinator, entered, release, completed, _ = install_sync(client, repo, media_fixture_dir, first)
    polling, resume = asyncio.Event(), asyncio.Event()

    async def sleep(_):
        polling.set()
        await resume.wait()

    sync._sleep = sleep
    subscription = client.portal.call(coordinator.subscribe_committed)
    client.portal.call(sync.request_scan, (first, second), 'automatic')
    task = client.portal.start_task_soon(sync.run)
    try:
        wait(client, entered)
        syncing = client.get('/api/state').json()
        assert subscription.pending.domains == frozenset({'library', 'library_sync'})
        client.portal.call(release.set)
        wait(client, polling)
        partial = client.get('/api/state').json()
        assert partial['library_sync']['confirmed_count'] == 1
        assert partial['library_sync']['pending_count'] == 1
        assert partial['library_sync']['status'] == 'SYNCING'
        assert partial['sequence'] > syncing['sequence']
        assert partial['revisions'] == syncing['revisions']
        marker = coordinator.marker()
        client.portal.call(sync._notify)
        assert coordinator.marker() == marker
        player.library_uris.add(str(second))
        client.portal.call(resume.set)
        wait(client, completed)
        synced = client.get('/api/state').json()
        assert synced['library_sync']['confirmed_count'] == 2
        assert synced['library_sync']['status'] == 'SYNCED'
        assert synced['revisions'] == partial['revisions']
    finally:
        client.portal.call(coordinator.unsubscribe, subscription)
        client.portal.call(sync.close)
        task.result(timeout=2)
