"""Real main.lifespan, real HTTP/WS routes, and committed SQLite facts."""
from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.app.api.library import router as library_router
from server.app.api.realtime import router as realtime_router
from server.app.main import lifespan
from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository
from server.app.services import library_scan_prepare as media
from server.app.services.library_scanner import LibraryScanner
from server.tests.invariants.test_startup_library_reconciliation import (
    IndexedPlayer,
    music_fixture,
)


def test_http_ws_and_library_read_during_startup_prepare(tmp_path, media_fixture_dir, monkeypatch, barrier_stage="prepare"):
    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / "http.db")

    async def seed():
        await initialize_database(db)
        await LibraryScanner(LibraryRepository(db)).scan_full(root)
        return {song.song_id for song in await LibraryRepository(db).list_songs()}

    old_ids = asyncio.run(seed())
    for name, value in {"APP_ENV": "development", "MPD_MODE": "mock", "DATABASE_PATH": db, "CONFIG_DIR": str(tmp_path / "config"), "MUSIC_ROOT": str(root)}.items():
        monkeypatch.setenv(name, value)
    entered, release = threading.Event(), threading.Event()
    original = media.prepare_scan

    def barrier(*args, **kwargs):
        entered.set()
        assert release.wait(10), "test watchdog failed to release prepare"
        return original(*args, **kwargs)

    if barrier_stage == "prepare":
        monkeypatch.setattr(media, "prepare_scan", barrier)
    else:
        from pathlib import Path
        stat = Path.stat

        def root_barrier(path, *args, **kwargs):
            if path == root:
                entered.set()
                assert release.wait(10), "test watchdog failed to release root stat"
            return stat(path, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", root_barrier)
    # A new app bypasses conftest's legacy global-app owner cancellation.
    app = FastAPI(lifespan=lifespan)
    app.include_router(library_router)
    app.include_router(realtime_router)
    app.state.player = IndexedPlayer(root)
    client = TestClient(app)
    guard = threading.Timer(9, release.set)
    guard.start()
    futures, timely, results = {}, {}, {}

    def snapshot():
        with client.websocket_connect("/api/realtime") as socket:
            return socket.receive_json()

    with ThreadPoolExecutor(max_workers=4) as pool:
        startup = pool.submit(client.__enter__)
        try:
            try:
                startup.result(timeout=1)
                timely["lifespan"] = True
            except TimeoutError:
                timely["lifespan"] = False
            assert entered.wait(2), "startup owner did not reach prepare barrier"
            if not timely["lifespan"]:
                # Release a failed constructor barrier so HTTP assertions use a
                # fully assembled real app; the readiness budget still fails.
                release.set()
                startup.result(timeout=5)
            futures = {
                "state": pool.submit(client.get, "/api/state"),
                "library": pool.submit(client.get, "/api/library/songs"),
                "ws": pool.submit(snapshot),
            }
            # One common budget, not three sequential seconds.
            from concurrent.futures import wait
            done, _ = wait(futures.values(), timeout=1)
            timely.update({name: future in done for name, future in futures.items()})
            for name, future in futures.items():
                if future in done:
                    results[name] = future.result()
        finally:
            release.set()
            startup.result(timeout=5)
            for future in futures.values():
                future.result(timeout=5)
            client.__exit__(None, None, None)
            guard.cancel()
    assert all(timely.values()), f"1s readiness budget failed while prepare held: {timely}"
    assert results["state"].status_code == 200
    assert results["library"].status_code == 200
    assert {song["song_id"] for song in results["library"].json()["items"]} == old_ids
    assert results["ws"]["type"] == "snapshot"
    assert results["ws"]["state"]["revisions"] == results["state"].json()["revisions"]


def test_startup_failure_keeps_http_ready_and_old_library_readable(tmp_path, media_fixture_dir, monkeypatch):
    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'failed-http.db')

    async def seed():
        await initialize_database(db)
        await LibraryScanner(LibraryRepository(db)).scan_full(root)
        return {s.song_id for s in await LibraryRepository(db).list_songs()}

    old_ids = asyncio.run(seed())
    # Missing music root is config syntax/type valid; owner must fail in background.
    absent = tmp_path / 'absent'
    for name, value in {'APP_ENV': 'development', 'MPD_MODE': 'mock', 'DATABASE_PATH': db, 'CONFIG_DIR': str(tmp_path / 'config'), 'MUSIC_ROOT': str(absent)}.items():
        monkeypatch.setenv(name, value)
    app = FastAPI(lifespan=lifespan)
    app.include_router(library_router)
    app.include_router(realtime_router)
    player = IndexedPlayer(root)
    app.state.player = player
    client = TestClient(app)
    error = None
    try:
        with client:
            async def failed():
                async with asyncio.timeout(1):
                    while app.state.library_sync_service.get_state().status != 'FAILED':
                        await asyncio.sleep(0.001)
            client.portal.call(failed)
            with ThreadPoolExecutor(max_workers=3) as pool:
                from concurrent.futures import wait

                def snapshot():
                    with client.websocket_connect('/api/realtime') as socket:
                        return socket.receive_json()
                requests = [pool.submit(client.get, '/api/state'), pool.submit(client.get, '/api/library/songs'), pool.submit(snapshot)]
                done, _ = wait(requests, timeout=1)
                assert len(done) == 3
                state, songs, ws = [f.result() for f in requests]
            assert state.json()['library_sync']['status'] == 'FAILED'
            assert {s['song_id'] for s in songs.json()['items']} == old_ids
            assert ws['state']['revisions'] == state.json()['revisions']
            assert player.calls == []
    except ValueError as exc:
        error = exc
    assert error is None, f'valid path configuration blocked lifespan instead of background failure: {error}'


def test_http_ws_and_library_read_during_startup_root_validation(tmp_path, media_fixture_dir, monkeypatch):
    test_http_ws_and_library_read_during_startup_prepare(tmp_path, media_fixture_dir, monkeypatch, barrier_stage="root")
