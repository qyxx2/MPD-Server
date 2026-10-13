"""MIN-LOG: real activity phases, failure correlation and safe console output."""

import asyncio
import io
import json
import logging

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.player.mock_mpd import MockMPD
from server.app.player.models import DatabaseUpdateStatus
from server.app.player.ports import PlayerUnavailable
from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository
from server.app.services.library_scanner import LibraryScanner
from server.app.services.library_sync_service import LibrarySyncService


@pytest.fixture(autouse=True)
def isolate_console_handler():
    logger = logging.getLogger('server.app')
    original = list(logger.handlers)
    original_propagate = logger.propagate
    logger.handlers.clear()
    try:
        yield
    finally:
        logger.handlers[:] = original
        logger.propagate = original_propagate


def test_activity_phase_and_errors_are_correlated_without_secrets(tmp_path, media_fixture_dir):
    from server.app.logging_config import configure_logging

    stream = io.StringIO()
    handler = configure_logging(stream=stream)
    try:
        assert configure_logging() is handler
        assert configure_logging() is handler

        async def run():
            path = str(tmp_path / 'log.db')
            await initialize_database(path)
            file = media_fixture_dir / 'metadata.flac'
            waits = []

            class Player(MockMPD):
                async def update_database(self):
                    if not waits:
                        raise PlayerUnavailable('password=secret-password body=secret-body')
                    await super().update_database()

                async def database_update_status(self):
                    return DatabaseUpdateStatus(updating=False)

            async def retry(delay):
                waits.append(delay)
                await asyncio.sleep(0)

            service = LibrarySyncService(
                LibraryScanner(LibraryRepository(path)), Player(library_uris=(str(file),)),
                media_fixture_dir, sleep=retry,
            )
            await service.request_scan((file,), 'manual')
            task = asyncio.create_task(service.run())
            try:
                for _ in range(1000):
                    if service.get_state().status == 'SYNCED':
                        break
                    await asyncio.sleep(0.001)
                assert service.get_state().status == 'SYNCED'
                await service._notify()  # Same facts/poll must produce no duplicate phase.
                return service.get_state().generation
            finally:
                await service.close()
                await task

        generation = asyncio.run(run())
        rows = [json.loads(line) for line in stream.getvalue().splitlines()]
        phases = [row for row in rows if row['event'] == 'library_sync_phase']
        assert [row['status'] for row in phases] == ['SYNCING', 'FAILED', 'SYNCING', 'SYNCED']
        assert {row['generation'] for row in phases} == {generation}
        assert len([row for row in rows if row['event'] == 'library_sync_retry']) == 1
        assert any(row['event'] == 'library_scan_started' for row in rows)
        assert 'secret-password' not in stream.getvalue()
        assert 'secret-body' not in stream.getvalue()
    finally:
        logging.getLogger('server.app').removeHandler(handler)
        handler.close()


def test_api_and_legacy_failures_are_safe_and_logging_failure_does_not_change_result(
    tmp_path, monkeypatch,
):
    from server.app.logging_config import configure_logging

    stream = io.StringIO()
    handler = configure_logging(stream=stream)
    secret = 'FULL-PRIVATE-KEY-password-secret-body'
    class BrokenReader:
        async def get_state(self):
            raise RuntimeError(secret)

    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'api.db'))
    monkeypatch.setattr(app.state, 'player', MockMPD(), raising=False)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            monkeypatch.setattr(app.state, 'output_manager', BrokenReader())
            for _ in range(2):
                response = client.put('/api/system/output', json={'mode': 'bad', 'body': secret},
                                      headers={'Idempotency-Key': secret})
                assert response.status_code == 422
            assert client.get('/api/system/output').status_code == 500
            try:
                raise RuntimeError(secret)
            except RuntimeError:
                logging.getLogger('server.app.repositories.database').exception('legacy %s', secret)
            text = stream.getvalue()
            assert secret not in text
            rows = [json.loads(line) for line in text.splitlines()]
            failures = [row for row in rows if row['event'] == 'api_failed']
            assert [row['status_code'] for row in failures] == [422, 422, 500]
            assert failures[0]['operation_id'] == failures[1]['operation_id']
            assert any(row.get('error_type') == 'RuntimeError' and row.get('frames') for row in rows)
            assert any(row['event'] == 'application_started' for row in rows)
            def broken_emit(record):
                raise OSError(secret)
            monkeypatch.setattr(handler, 'emit', broken_emit)
            assert client.get('/api/health').status_code == 200
            assert client.get('/api/system/output').status_code == 500
    finally:
        logging.getLogger('server.app').removeHandler(handler)
        handler.close()


def test_mpd_connection_control_and_failure_logs_keep_correlation_without_poll_noise():
    from server.app.logging_config import configure_logging, log_context
    from server.app.player.mpd_adapter import MPDAdapter
    from server.tests.player.test_mpd_adapter_errors import FakeReader, FakeWriter

    stream = io.StringIO()
    handler = configure_logging(stream=stream)
    async def run():
        reader = FakeReader([
            b'OK MPD 0.23.5\n', b'OK\n',  # password
            b'state: stop\n', b'OK\n', b'state: stop\n', b'OK\n',
            b'ACK [50@0] {play} private-password-private-body\n', b'OK\n',
        ])
        writer = FakeWriter()
        async def connect(host, port):
            return reader, writer
        adapter = MPDAdapter('test-host', password='private-password', connection_factory=connect)
        try:
            with log_context(operation_id='op-123'):
                await adapter.status()
                await adapter.status()
                from server.app.player.ports import PlayerCommandError
                with pytest.raises(PlayerCommandError):
                    await adapter.play()
                await adapter.pause()
        finally:
            await adapter.close()
    try:
        asyncio.run(run())
        rows = [json.loads(line) for line in stream.getvalue().splitlines()]
        assert [row['event'] for row in rows] == [
            'mpd_connected', 'mpd_command_failed', 'mpd_control_accepted',
        ]
        assert {row['operation_id'] for row in rows} == {'op-123'}
        assert rows[1]['command'] == 'play'
        assert rows[2]['command'] == 'pause'
        assert all(secret not in stream.getvalue() for secret in [
            'private-password', 'private-body', 'private-uri',
        ])
    finally:
        logging.getLogger('server.app').removeHandler(handler)
        handler.close()


def test_console_does_not_forward_raw_legacy_exception_to_parent_handlers():
    from server.app.logging_config import configure_logging

    safe_stream, parent_stream = io.StringIO(), io.StringIO()
    handler = configure_logging(stream=safe_stream)
    parent_handler = logging.StreamHandler(parent_stream)
    logging.getLogger().addHandler(parent_handler)
    try:
        try:
            raise RuntimeError('private-password')
        except RuntimeError:
            logging.getLogger('server.app.repositories.database').exception('legacy %s', 'private-body')
        assert 'private-password' not in safe_stream.getvalue()
        assert 'private-body' not in safe_stream.getvalue()
        assert parent_stream.getvalue() == ''
    finally:
        logging.getLogger().removeHandler(parent_handler)
        logging.getLogger('server.app').removeHandler(handler)
        handler.close()


def test_sync_shutdown_logs_terminal_phase_without_changing_business_result(tmp_path, media_fixture_dir):
    from server.app.logging_config import configure_logging

    stream = io.StringIO()
    handler = configure_logging(stream=stream)
    async def run():
        path = str(tmp_path / 'cancel.db')
        await initialize_database(path)
        entered = asyncio.Event()
        class Player(MockMPD):
            async def update_database(self):
                entered.set()
                await asyncio.Event().wait()
        service = LibrarySyncService(LibraryScanner(LibraryRepository(path)), Player(), media_fixture_dir)
        await service.request_scan((media_fixture_dir / 'metadata.flac',), 'manual')
        task = asyncio.create_task(service.run())
        await asyncio.wait_for(entered.wait(), 1)
        await service.close()
        await task
        assert service.get_state().error_code == 'LIBRARY_SYNC_CANCELLED'
    try:
        asyncio.run(run())
        phases = [json.loads(line) for line in stream.getvalue().splitlines()
                  if json.loads(line)['event'] == 'library_sync_phase']
        assert [row['status'] for row in phases] == ['SYNCING', 'FAILED']
        assert phases[-1]['error_code'] == 'LIBRARY_SYNC_CANCELLED'
        assert {row['generation'] for row in phases} == {1}
    finally:
        logging.getLogger('server.app').removeHandler(handler)
        handler.close()


def test_independent_failed_controls_are_not_deduplicated():
    from server.app.logging_config import configure_logging, log_context
    from server.app.player.mpd_adapter import MPDAdapter
    from server.app.player.ports import PlayerCommandError
    from server.tests.player.test_mpd_adapter_errors import FakeReader, FakeWriter

    stream = io.StringIO()
    handler = configure_logging(stream=stream)
    async def run():
        reader = FakeReader([b'OK MPD 0.23.5\n'] + [b'ACK [50@0] {play} private\n'] * 2)
        async def connect(host, port):
            return reader, FakeWriter()
        adapter = MPDAdapter('test-host', connection_factory=connect)
        try:
            for operation in ('op-one', 'op-two'):
                with log_context(operation_id=operation), pytest.raises(PlayerCommandError):
                    await adapter.play()
        finally:
            await adapter.close()
    try:
        asyncio.run(run())
        rows = [json.loads(line) for line in stream.getvalue().splitlines()]
        failures = [row for row in rows if row['event'] == 'mpd_command_failed']
        assert [row['operation_id'] for row in failures] == ['op-one', 'op-two']
    finally:
        logging.getLogger('server.app').removeHandler(handler)
        handler.close()
