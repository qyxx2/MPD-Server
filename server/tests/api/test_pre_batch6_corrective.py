from __future__ import annotations

import asyncio

import pytest

from server.app.models.library import Song
from server.tests.support.playback import mutate, real_client, run, start

__all__ = ["real_client"]


def assert_synced(client, player):
    items = client.get("/api/playback/queue").json()["items"]
    desired = [
        f"{item['song_id']}.flac"
        for item in sorted(
            items,
            key=lambda item: item["position"],
        )
        if item["position"] >= 0
    ]
    assert [entry.song_uri for entry in run(player.queue_entries())] == desired


@pytest.mark.parametrize(
    "operation", ["reorder", "delete_pending", "delete_current", "clear"]
)
def test_queue_mutations_sync_real_player_and_history(real_client, operation):
    client, _, player, service = real_client
    items = start(client)
    ids = {
        item["song_id"]: item["queue_item_id"]
        for item in items
        if item["source"] == "MANUAL"
    }
    active = service.history_service.active_event
    if operation == "reorder":
        response = mutate(
            client,
            "PUT",
            f"/api/playback/queue/items/{ids['c']}",
            {
                "before_queue_item_id": ids["b"],
            },
        )
    elif operation == "delete_pending":
        response = mutate(client, "DELETE", f"/api/playback/queue/items/{ids['b']}")
    elif operation == "delete_current":
        response = mutate(client, "DELETE", f"/api/playback/queue/items/{ids['a']}")
    else:
        response = mutate(client, "DELETE", "/api/playback/queue")
    assert response.status_code in (200, 204), response.text
    assert_synced(client, player)
    state = run(service.queue_manager.get_playback_state())
    assert state.song_id == ("b" if operation == "delete_current" else "a")
    assert run(player.status()).song_uri == f"{state.song_id}.flac"
    assert service.history_service.active_event.song_id == state.song_id
    history = run(service.history_service.list_history())
    if operation == "delete_current":
        assert [(event.song_id, event.reason) for event in history] == [
            ("a", "SWITCH_AWAY")
        ]
        assert service.history_service.active_event.started_at != active.started_at
    else:
        assert service.history_service.active_event == active
        assert history == []
    # Replay must neither re-execute the mutation nor append another History event.
    revision = run(service.queue_manager.queue_repository.get_snapshot()).revision
    if operation == "reorder":
        replay = mutate(
            client,
            "PUT",
            f"/api/playback/queue/items/{ids['c']}",
            {
                "before_queue_item_id": ids["b"],
            },
        )
    else:
        path = (
            "/api/playback/queue"
            if operation == "clear"
            else (
                f"/api/playback/queue/items/{ids['a' if operation == 'delete_current' else 'b']}"
            )
        )
        replay = mutate(client, "DELETE", path)
    assert replay.status_code == response.status_code
    assert (
        run(service.queue_manager.queue_repository.get_snapshot()).revision == revision
    )
    assert run(service.history_service.list_history()) == history


@pytest.mark.parametrize("read", ["detail", "songs"])
def test_playlist_persisted_members_are_resource_members(real_client, read):
    client, library, _, _ = real_client
    for song_id, availability in [
        ("a", "AVAILABLE"),
        ("b", "MISSING"),
        ("c", "UNREADABLE"),
    ]:
        song = run(library.get_song(song_id))
        run(
            library.upsert_song(
                song.model_copy(update={"availability_status": availability})
            )
        )
    response = mutate(client, "POST", "/api/playlists", {"name": "Persistent"})
    assert response.status_code == 201
    playlist_id = response.json()["playlist_id"]
    base = f"/api/playlists/{playlist_id}"
    assert response.json()["song_ids"] == []
    for index, song_id in enumerate("abc", start=1):
        added = mutate(client, "POST", base + "/songs", {"song_id": song_id})
        assert added.status_code == 200, added.text
        assert added.json()["song_ids"] == list("abc")[:index]
    updated = mutate(client, "PATCH", base, {"name": "Renamed"})
    assert updated.json()["song_ids"] == list("abc")
    reordered = mutate(
        client,
        "PUT",
        base + "/songs/order",
        {
            "ordered_song_ids": ["c", "a", "b"],
        },
    )
    assert reordered.json()["song_ids"] == ["c", "a", "b"]
    listed = next(
        item
        for item in client.get("/api/playlists").json()["items"]
        if item["playlist_id"] == playlist_id
    )
    assert listed["song_ids"] == ["c", "a", "b"]
    if read == "detail":
        assert client.get(base).json() == listed
    else:
        songs = client.get(base + "/songs").json()
        assert songs["count"] == 3
        assert [
            (song["song_id"], song["availability_status"]) for song in songs["items"]
        ] == [
            ("c", "UNREADABLE"),
            ("a", "AVAILABLE"),
            ("b", "MISSING"),
        ]
    collection = client.post(
        "/api/library/collections",
        json={
            "source_type": "PLAYLIST",
            "source_id": playlist_id,
        },
    ).json()
    assert collection["song_ids"] == ["a"]
    assert collection["unavailable_song_ids"] == ["c", "b"]


@pytest.mark.parametrize(
    "operation,command",
    [
        ("reorder", "queue_move"),
        ("delete_pending", "queue_delete"),
        ("delete_current", "play"),
        ("clear", "queue_delete"),
    ],
)
def test_queue_player_failure_rolls_back_and_key_can_retry(
    real_client, operation, command
):
    client, _, player, service = real_client
    items = start(client)
    ids = {
        item["song_id"]: item["queue_item_id"]
        for item in items
        if item["source"] == "MANUAL"
    }
    before = run(service.queue_manager.queue_repository.get_snapshot())
    state = run(service.queue_manager.get_playback_state())
    active = service.history_service.active_event
    method, path, body = "DELETE", "/api/playback/queue", None
    if operation == "reorder":
        method, path, body = (
            "PUT",
            f"/api/playback/queue/items/{ids['c']}",
            {
                "before_queue_item_id": ids["b"],
            },
        )
    elif operation != "clear":
        path = f"/api/playback/queue/items/{ids['a' if operation == 'delete_current' else 'b']}"
    player.fail_next(command)
    response = mutate(client, method, path, body, key="retry-failure")
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "PLAYER_COMMAND_FAILED"
    assert run(service.queue_manager.queue_repository.get_snapshot()) == before
    assert run(service.queue_manager.get_playback_state()) == state
    assert service.history_service.active_event == active
    assert run(service.history_service.list_history()) == []
    retry = mutate(client, method, path, body, key="retry-failure")
    assert retry.status_code in (200, 204), retry.text
    assert_synced(client, player)


@pytest.mark.parametrize("operation", ["reorder", "delete", "clear"])
def test_queue_revision_conflict_precedes_player_side_effects(real_client, operation):
    from server.app.services.queue_manager import QueueRevisionConflictError

    client, _, player, service = real_client
    items = start(client)
    pending = next(item for item in items if item["song_id"] == "b")
    before = run(service.queue_manager.queue_repository.get_snapshot())
    entries = run(player.queue_entries())
    # Disconnected player proves a stale revision must be rejected before transport.
    player.disconnect()
    with pytest.raises(QueueRevisionConflictError):
        if operation == "clear":
            run(service.clear(expected_revision=before.revision - 1))
        elif operation == "reorder":
            run(
                service.reorder(
                    pending["queue_item_id"], expected_revision=before.revision - 1
                )
            )
        else:
            run(
                service.delete(
                    pending["queue_item_id"], expected_revision=before.revision - 1
                )
            )
    player.reconnect()
    assert run(player.queue_entries()) == entries
    assert run(service.queue_manager.queue_repository.get_snapshot()) == before


@pytest.mark.parametrize("available", [True, False])
def test_delete_current_without_pending_uses_autoplay_or_confirmed_stop(
    real_client, available
):
    client, library, player, service = real_client
    items = start(client)
    current = next(item for item in items if item["position"] == 0)
    # Arrange exhaustion at the Queue business layer; no live engine involved.
    run(service.queue_manager.clear())
    if not available:
        for song_id in "abc":
            song = run(library.get_song(song_id))
            run(
                library.upsert_song(
                    song.model_copy(update={"availability_status": "MISSING"})
                )
            )
    response = mutate(
        client, "DELETE", f"/api/playback/queue/items/{current['queue_item_id']}"
    )
    assert response.status_code == 204, response.text
    assert_synced(client, player)
    state = run(service.queue_manager.get_playback_state())
    if available:
        assert state.state == "PLAYING"
        assert state.song_id == "b"
        assert service.history_service.active_event.song_id == "b"
        assert run(service.history_service.list_history())[0].reason == "SWITCH_AWAY"
    else:
        assert state.state == "STOPPED"
        assert not state.autoplay_enabled
        assert run(player.status()).state.value == "stopped"
        assert service.history_service.active_event is None
        assert run(service.history_service.list_history())[0].reason == "STOP"


def test_current_delete_skips_unavailable_successor(real_client):
    client, library, player, service = real_client
    items = start(client)
    current = next(item for item in items if item["position"] == 0)
    song = run(library.get_song("b"))
    run(
        library.upsert_song(
            song.model_copy(update={"availability_status": "UNREADABLE"})
        )
    )
    response = mutate(
        client, "DELETE", f"/api/playback/queue/items/{current['queue_item_id']}"
    )
    assert response.status_code == 204, response.text
    assert run(service.queue_manager.get_playback_state()).song_id == "c"
    assert service.history_service.active_event.song_id == "c"
    assert_synced(client, player)


@pytest.mark.parametrize(
    "operation", ["reorder", "delete_pending", "delete_current", "clear"]
)
def test_mutation_rejects_player_unavailable(real_client, operation):
    client, _, player, service = real_client
    items = start(client)
    ids = {
        item["song_id"]: item["queue_item_id"]
        for item in items
        if item["source"] == "MANUAL"
    }
    before = run(service.queue_manager.queue_repository.get_snapshot())
    state = run(service.queue_manager.get_playback_state())
    active = service.history_service.active_event
    player.disconnect()
    if operation == "reorder":
        response = mutate(
            client,
            "PUT",
            f"/api/playback/queue/items/{ids['c']}",
            {
                "before_queue_item_id": ids["b"],
            },
        )
    else:
        path = (
            "/api/playback/queue"
            if operation == "clear"
            else (
                f"/api/playback/queue/items/{ids['a' if operation == 'delete_current' else 'b']}"
            )
        )
        response = mutate(client, "DELETE", path)
    assert response.status_code == 503, response.text
    assert run(service.queue_manager.queue_repository.get_snapshot()) == before
    assert run(service.queue_manager.get_playback_state()) == state
    assert service.history_service.active_event == active
    player.reconnect()


@pytest.mark.parametrize(
    "operation", ["reorder", "delete_pending", "delete_current", "clear"]
)
def test_mutation_requires_final_player_confirmation(
    real_client, monkeypatch, operation
):
    client, _, player, service = real_client
    items = start(client)
    ids = {
        item["song_id"]: item["queue_item_id"]
        for item in items
        if item["source"] == "MANUAL"
    }
    before = run(service.queue_manager.queue_repository.get_snapshot())
    state = run(service.queue_manager.get_playback_state())
    active = service.history_service.active_event
    actual_status = player.status
    actual_move = player.queue_move
    actual_delete = player.queue_delete
    changed = False

    async def wrong_status_after_sync():
        status = await actual_status()
        return (
            status.model_copy(update={"song_uri": "wrong.flac"}) if changed else status
        )

    async def move(*args):
        nonlocal changed
        await actual_move(*args)
        changed = True

    async def delete(*args):
        nonlocal changed
        await actual_delete(*args)
        changed = True

    monkeypatch.setattr(player, "status", wrong_status_after_sync)
    monkeypatch.setattr(player, "queue_move", move)
    monkeypatch.setattr(player, "queue_delete", delete)
    if operation == "reorder":
        response = mutate(
            client,
            "PUT",
            f"/api/playback/queue/items/{ids['c']}",
            {
                "before_queue_item_id": ids["b"],
            },
        )
    else:
        path = (
            "/api/playback/queue"
            if operation == "clear"
            else (
                f"/api/playback/queue/items/{ids['a' if operation == 'delete_current' else 'b']}"
            )
        )
        response = mutate(client, "DELETE", path)
    assert changed
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "PLAYBACK_RECONCILIATION_FAILED"
    assert run(service.queue_manager.queue_repository.get_snapshot()) == before
    assert run(service.queue_manager.get_playback_state()) == state
    assert service.history_service.active_event == active
    assert run(service.history_service.list_history()) == []


@pytest.mark.parametrize("control", ["pause", "stop"])
def test_clear_preserves_session_control_and_history(real_client, control):
    client, _, player, service = real_client
    start(client)
    run(getattr(service, control)())
    active = service.history_service.active_event
    history = run(service.history_service.list_history())
    response = mutate(client, "DELETE", "/api/playback/queue")
    assert response.status_code == 204, response.text
    state = run(service.queue_manager.get_playback_state())
    assert state.state == ("PAUSED" if control == "pause" else "STOPPED")
    pending = [
        item for item in run(service.queue_manager.list_items()) if item.position > 0
    ]
    assert bool(pending) == (control == "pause")
    assert service.history_service.active_event == active
    assert run(service.history_service.list_history()) == history
    assert_synced(client, player)


def test_current_deletion_after_explicit_stop_does_not_restart(real_client):
    client, _, player, service = real_client
    items = start(client)
    current = next(item for item in items if item["position"] == 0)
    run(service.stop())
    history = run(service.history_service.list_history())
    response = mutate(
        client, "DELETE", f"/api/playback/queue/items/{current['queue_item_id']}"
    )
    assert response.status_code == 204, response.text
    assert run(player.status()).state.value == "stopped"
    state = run(service.queue_manager.get_playback_state())
    assert state.state == "STOPPED"
    assert not state.autoplay_enabled
    assert service.history_service.active_event is None
    assert run(service.history_service.list_history()) == history
    assert_synced(client, player)


@pytest.mark.parametrize("successor", [True, False])
def test_current_delete_terminal_record_failure_restores_history(
    real_client, successor
):
    from server.app.repositories.database import run_transaction

    client, library, player, service = real_client
    items = start(client)
    current = next(item for item in items if item["position"] == 0)
    if not successor:
        run(service.queue_manager.clear())
        for song_id in "abc":
            song = run(library.get_song(song_id))
            run(
                library.upsert_song(
                    song.model_copy(update={"availability_status": "MISSING"})
                )
            )
    before = run(service.queue_manager.queue_repository.get_snapshot())
    state = run(service.queue_manager.get_playback_state())
    active = service.history_service.active_event
    session = service.history_service.session_id
    path = service.queue_manager.queue_repository.path
    run(
        run_transaction(
            path,
            lambda connection: connection.execute("""
        CREATE TRIGGER fail_delete_record BEFORE INSERT ON idempotency_records
        WHEN NEW.idempotency_key = 'terminal-delete'
        BEGIN SELECT RAISE(ABORT, 'terminal record failure'); END
    """),
        )
    )
    # TestClient propagates the SQLite failure; a real HTTP client receives 500.
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError, match="terminal record failure"):
        mutate(
            client,
            "DELETE",
            f"/api/playback/queue/items/{current['queue_item_id']}",
            key="terminal-delete",
        )
    assert run(service.queue_manager.queue_repository.get_snapshot()) == before
    assert run(service.queue_manager.get_playback_state()) == state
    assert run(service.history_service.list_history()) == []
    assert service.history_service.active_event == active
    assert service.history_service.session_id == session
    run(
        run_transaction(
            path,
            lambda connection: connection.execute("DROP TRIGGER fail_delete_record"),
        )
    )
    response = mutate(
        client,
        "DELETE",
        f"/api/playback/queue/items/{current['queue_item_id']}",
        key="terminal-delete",
    )
    assert response.status_code == 204
    history = run(service.history_service.list_history())
    assert [(event.song_id, event.reason) for event in history] == [
        ("a", "SWITCH_AWAY" if successor else "STOP"),
    ]
    assert_synced(client, player)


def test_mock_reports_execution_occurrence_for_duplicate_uri(real_client):
    client, _, player, _ = real_client
    start(client)
    entries = run(player.queue_entries())
    repeated = entries[-1]
    assert repeated.song_uri == "a.flac"
    run(player.queue_play(repeated.mpd_song_id))
    status = run(player.status())
    assert status.song_id == repeated.mpd_song_id
    assert status.song_position == repeated.position


def test_reorder_rejects_wrong_current_occurrence(real_client, monkeypatch):
    client, _, player, service = real_client
    items = start(client)
    before = run(service.queue_manager.queue_repository.get_snapshot())
    entries = run(player.queue_entries())
    actual_status = player.status

    async def wrong_occurrence():
        status = await actual_status()
        return status.model_copy(
            update={
                "song_position": 3,
                "song_id": entries[-1].mpd_song_id,
            }
        )

    monkeypatch.setattr(player, "status", wrong_occurrence)
    pending = next(item for item in items if item["song_id"] == "c")
    response = mutate(
        client, "PUT", f"/api/playback/queue/items/{pending['queue_item_id']}", {}
    )
    assert response.status_code == 502, response.text
    assert run(service.queue_manager.queue_repository.get_snapshot()) == before


def test_mock_transport_controls_keep_queue_current_identity(real_client):
    client, _, player, _ = real_client
    start(client)
    run(player.next())
    entries = run(player.queue_entries())
    status = run(player.status())
    assert status.song_uri == "b.flac"
    assert status.song_id == entries[1].mpd_song_id
    assert status.song_position == 1
    run(player.previous())
    status = run(player.status())
    assert status.song_uri == "a.flac"
    assert status.song_id == entries[0].mpd_song_id
    assert status.song_position == 0


@pytest.mark.parametrize(
    "operation", ["next", "play_now", "start_track", "context", "previous", "stop"]
)
def test_playback_terminal_failure_restores_history_and_retry(real_client, operation):
    import sqlite3

    from server.app.repositories.database import run_transaction

    client, _, player, service = real_client
    items = start(client)
    if operation == "previous":
        assert (
            mutate(
                client, "POST", "/api/playback/next", key="prepare-previous"
            ).status_code
            == 200
        )
    pending = next(item for item in items if item["song_id"] == "b")
    endpoint = {
        "next": "/api/playback/next",
        "play_now": f"/api/playback/queue/items/{pending['queue_item_id']}/play",
        "start_track": "/api/playback/tracks/b/play",
        "context": "/api/playback/collections/play",
        "previous": "/api/playback/previous",
        "stop": "/api/playback/stop",
    }[operation]
    body = (
        {"source_type": "SONGS", "song_ids": ["b", "c"]}
        if operation == "context"
        else None
    )
    before = run(service.queue_manager.queue_repository.get_snapshot())
    state = run(service.queue_manager.get_playback_state())
    active = service.history_service.active_event
    session = service.history_service.session_id
    before_history = run(service.history_service.list_history())
    path = service.queue_manager.queue_repository.path
    run(
        run_transaction(
            path,
            lambda connection: connection.execute("""
        CREATE TRIGGER fail_playback_record BEFORE INSERT ON idempotency_records
        WHEN NEW.idempotency_key = 'terminal-playback'
        BEGIN SELECT RAISE(ABORT, 'terminal playback failure'); END
    """),
        )
    )
    with pytest.raises(sqlite3.IntegrityError, match="terminal playback failure"):
        mutate(client, "POST", endpoint, body, key="terminal-playback")
    assert run(service.queue_manager.queue_repository.get_snapshot()) == before
    assert run(service.queue_manager.get_playback_state()) == state
    assert run(service.history_service.list_history()) == before_history
    assert service.history_service.active_event == active
    assert service.history_service.session_id == session
    run(
        run_transaction(
            path,
            lambda connection: connection.execute("DROP TRIGGER fail_playback_record"),
        )
    )
    retry = mutate(client, "POST", endpoint, body, key="terminal-playback")
    assert retry.status_code == 200, retry.text
    history = run(service.history_service.list_history())
    expected_history = (
        [("b", "SWITCH_AWAY"), ("a", "SWITCH_AWAY")]
        if operation == "previous"
        else [("a", "STOP" if operation == "stop" else "SWITCH_AWAY")]
    )
    assert [(event.song_id, event.reason) for event in history] == expected_history
    if operation == "stop":
        assert service.history_service.active_event is None
        assert service.history_service.session_id is None
    else:
        assert service.history_service.active_event.song_id == (
            "a" if operation == "previous" else "b"
        )
    assert_synced(client, player)
    snapshot = run(service.queue_manager.queue_repository.get_snapshot())
    replay = mutate(client, "POST", endpoint, body, key="terminal-playback")
    assert replay.json() == retry.json()
    assert run(service.queue_manager.queue_repository.get_snapshot()) == snapshot
    assert run(service.history_service.list_history()) == history


@pytest.mark.parametrize("availability", ["MISSING", "UNREADABLE"])
def test_next_skips_unavailable_pending(real_client, availability, caplog):
    client, library, player, service = real_client
    start(client)
    song = run(library.get_song("b"))
    run(
        library.upsert_song(
            song.model_copy(update={"availability_status": availability})
        )
    )
    response = mutate(client, "POST", "/api/playback/next", key="skip-invalid")
    assert response.status_code == 200, response.text
    assert response.json()["song_id"] == "c"
    assert f"(song b): {availability}" in caplog.text
    assert service.history_service.active_event.song_id == "c"
    assert [
        (event.song_id, event.reason)
        for event in run(service.history_service.list_history())
    ] == [("a", "SWITCH_AWAY")]
    assert not any(
        item.song_id == "b" and item.position > 0
        for item in run(service.queue_manager.list_items())
    )
    assert_synced(client, player)


@pytest.mark.parametrize(
    "operation", ["start_track", "play_context", "play_now", "next", "previous"]
)
def test_direct_playback_sync_failure_restores_transaction(
    real_client, monkeypatch, operation
):
    from server.app.models.queue import PlaybackContext
    from server.app.player.ports import PlayerCommandError

    client, _, _, service = real_client
    items = start(client)
    if operation == "previous":
        run(service.next())
    before = run(service.queue_manager.queue_repository.get_snapshot())
    state = run(service.queue_manager.get_playback_state())
    active = service.history_service.active_event
    session = service.history_service.session_id
    history = run(service.history_service.list_history())

    async def fail_sync():
        raise PlayerCommandError("queue_move", "forced post-History sync failure")

    monkeypatch.setattr(service, "_sync_player_queue", fail_sync)
    pending = next(item for item in items if item["song_id"] == "b")
    with pytest.raises(PlayerCommandError, match="forced post-History sync failure"):
        if operation == "play_now":
            run(service.play_now(pending["queue_item_id"]))
        elif operation == "start_track":
            run(service.start_track("b"))
        elif operation == "play_context":
            run(
                service.play_context(
                    PlaybackContext(
                        context_id="new",
                        source_type="SONGS",
                        ordered_song_ids=("b", "c"),
                    )
                )
            )
        else:
            run(getattr(service, operation)())
    assert run(service.queue_manager.queue_repository.get_snapshot()) == before
    assert run(service.queue_manager.get_playback_state()) == state
    assert run(service.history_service.list_history()) == history
    assert service.history_service.active_event == active
    assert service.history_service.session_id == session


@pytest.mark.parametrize("drift", ["stop", "foreign", "pause"])
def test_reconciliation_outer_rollback_restores_history(real_client, monkeypatch, drift):
    from server.app.repositories.database import run_transaction

    client, _, player, service = real_client
    start(client)
    state = run(service.queue_manager.get_playback_state())
    active = service.history_service.active_event
    session = service.history_service.session_id
    queue = run(service.queue_manager.get_snapshot())
    if drift == "stop":
        run(player.stop())
    elif drift == "foreign":
        run(player.play("b.flac"))
    else:
        run(player.pause())

    async def fail_after_reconcile(_connection):
        await service.reconcile_external_status()
        raise RuntimeError("outer transaction failure")

    with pytest.raises(RuntimeError, match="outer transaction failure"):
        run(
            run_transaction(
                service.queue_manager.queue_repository.path, fail_after_reconcile
            )
        )
    assert run(service.queue_manager.get_playback_state()) == state
    assert run(service.history_service.list_history()) == []
    assert service.history_service.active_event == active
    assert service.history_service.session_id == session
    assert run(service.queue_manager.get_snapshot()) == queue
    from server.tests.invariants.test_d6_recovery import capture_controls

    controls = capture_controls(monkeypatch, player)
    result = run(service.reconcile_external_status())
    assert result.outcome == ("APPLIED" if drift in {"pause", "foreign"} else "UNKNOWN")
    assert run(service.history_service.list_history()) == []
    assert service.history_service.session_id == session
    assert controls == []  # retry only verifies the already executed fixed prefix
    if drift == "foreign":
        assert service.history_service.active_event is None
        adopted = run(service.queue_manager.get_snapshot())
        assert adopted.revision == queue.revision + 1
        assert result.playback.song_id == "b"
        assert next(i for i in adopted.items if i.position == -1).queue_item_id == next(i for i in queue.items if i.position == 0).queue_item_id
    else:
        assert service.history_service.active_event == active
        assert run(service.queue_manager.get_snapshot()) == queue
        if drift == "pause":
            assert result.playback.state == "PAUSED"
        else:
            assert run(service.queue_manager.get_playback_state()) == state


@pytest.mark.parametrize("failure", ["play", "disconnected", "confirmation"])
def test_next_skip_failure_rolls_back_and_same_key_retries(
    real_client, monkeypatch, failure
):
    client, library, player, service = real_client
    start(client)
    song = run(library.get_song("b"))
    run(library.upsert_song(song.model_copy(update={"availability_status": "MISSING"})))
    before = run(service.queue_manager.queue_repository.get_snapshot())
    state = run(service.queue_manager.get_playback_state())
    active = service.history_service.active_event
    actual_status = player.status
    if failure == "play":
        player.fail_next("play")
    elif failure == "disconnected":
        player.disconnect()
    else:

        async def wrong_status():
            status = await actual_status()
            if status.song_uri == "c.flac":
                return status.model_copy(update={"song_uri": "wrong.flac"})
            return status

        monkeypatch.setattr(player, "status", wrong_status)
    response = mutate(client, "POST", "/api/playback/next", key="skip-retry")
    assert response.status_code == (503 if failure == "disconnected" else 502), (
        response.text
    )
    assert run(service.queue_manager.queue_repository.get_snapshot()) == before
    assert run(service.queue_manager.get_playback_state()) == state
    assert run(service.history_service.list_history()) == []
    assert service.history_service.active_event == active
    player.reconnect()
    monkeypatch.setattr(player, "status", actual_status)
    retry = mutate(client, "POST", "/api/playback/next", key="skip-retry")
    assert retry.status_code == 200, retry.text
    assert retry.json()["song_id"] == "c"
    assert_synced(client, player)
    snapshot = run(service.queue_manager.queue_repository.get_snapshot())
    history = run(service.history_service.list_history())
    replay = mutate(client, "POST", "/api/playback/next", key="skip-retry")
    assert replay.json() == retry.json()
    assert run(service.queue_manager.queue_repository.get_snapshot()) == snapshot
    assert run(service.history_service.list_history()) == history


def test_next_skips_unavailable_later_pending(real_client):
    client, library, player, service = real_client
    start(client)
    song = run(library.get_song("c"))
    run(library.upsert_song(song.model_copy(update={"availability_status": "MISSING"})))
    response = mutate(client, "POST", "/api/playback/next", key="later-invalid")
    assert response.status_code == 200, response.text
    assert response.json()["song_id"] == "b"
    assert not any(
        item.song_id == "c" and item.position > 0
        for item in run(service.queue_manager.list_items())
    )
    assert_synced(client, player)


@pytest.mark.parametrize("candidate", [True, False])
def test_next_unavailable_exhaustion_attempts_autoplay(
    real_client, candidate, monkeypatch
):
    client, library, player, service = real_client
    start(client)
    for song_id in "abc":
        song = run(library.get_song(song_id))
        run(
            library.upsert_song(
                song.model_copy(update={"availability_status": "MISSING"})
            )
        )
    if candidate:
        run(library.upsert_song(Song(song_id="d", title="d", file_uri="d.flac")))
    calls = []
    actual_refill = service.autoplay.refill

    async def refill(context):
        calls.append(context)
        return await actual_refill(context)

    monkeypatch.setattr(service.autoplay, "refill", refill)
    active = service.history_service.active_event
    response = mutate(client, "POST", "/api/playback/next", key="exhaustion")
    assert response.status_code == 200, response.text
    assert len(calls) == 1
    assert response.json()["song_id"] == ("d" if candidate else "a")
    assert run(player.status()).song_uri == ("d.flac" if candidate else "a.flac")
    if candidate:
        assert service.history_service.active_event.song_id == "d"
        assert [
            (event.song_id, event.reason)
            for event in run(service.history_service.list_history())
        ] == [("a", "SWITCH_AWAY")]
    else:
        assert service.history_service.active_event == active
        assert run(service.history_service.list_history()) == []
    assert_synced(client, player)


def test_next_skips_absent_pending_identity(real_client, monkeypatch, caplog):
    client, _, player, service = real_client
    start(client)
    actual_get = service.library_repository.get_song

    async def absent_b(song_id):
        return None if song_id == "b" else await actual_get(song_id)

    # Persisted Queue foreign keys prohibit deleting a referenced Song. Simulate
    # the repository's absent lookup boundary without disabling DB constraints.
    monkeypatch.setattr(service.library_repository, "get_song", absent_b)
    response = mutate(client, "POST", "/api/playback/next", key="absent-pending")
    assert response.status_code == 200, response.text
    assert response.json()["song_id"] == "c"
    assert "(song b): SONG_NOT_FOUND" in caplog.text
    assert_synced(client, player)


def test_next_transaction_serializes_stale_revision_mutation(real_client):
    from server.app.repositories.queue_repository import QueueRevisionConflictError

    client, _, player, service = real_client
    items = start(client)
    pending = next(item for item in items if item["song_id"] == "c")
    snapshot = run(service.queue_manager.queue_repository.get_snapshot())

    async def concurrent_mutations():
        return await asyncio.gather(
            service.next(),
            service.reorder(
                pending["queue_item_id"], expected_revision=snapshot.revision
            ),
            return_exceptions=True,
        )

    transition, stale = run(concurrent_mutations())
    assert transition.song_id == "b"
    assert isinstance(stale, QueueRevisionConflictError)
    assert service.history_service.active_event.song_id == "b"
    assert_synced(client, player)


@pytest.mark.parametrize("initial", [True, False])
def test_initial_or_skipping_next_terminal_failure_retries(real_client, initial):
    import sqlite3

    from server.app.repositories.database import run_transaction

    client, library, player, service = real_client
    endpoint = "/api/playback/tracks/a/play" if initial else "/api/playback/next"
    if not initial:
        start(client)
        song = run(library.get_song("b"))
        run(
            library.upsert_song(
                song.model_copy(update={"availability_status": "MISSING"})
            )
        )
    snapshot = run(service.queue_manager.queue_repository.get_snapshot())
    state = run(service.queue_manager.get_playback_state())
    active = service.history_service.active_event
    session = service.history_service.session_id
    path = service.queue_manager.queue_repository.path
    run(
        run_transaction(
            path,
            lambda connection: connection.execute("""
        CREATE TRIGGER fail_initial_or_skip BEFORE INSERT ON idempotency_records
        WHEN NEW.idempotency_key = 'initial-or-skip'
        BEGIN SELECT RAISE(ABORT, 'forced terminal failure'); END
    """),
        )
    )
    with pytest.raises(sqlite3.IntegrityError, match="forced terminal failure"):
        mutate(client, "POST", endpoint, key="initial-or-skip")
    assert run(service.queue_manager.queue_repository.get_snapshot()) == snapshot
    assert run(service.queue_manager.get_playback_state()) == state
    assert service.history_service.active_event == active
    assert service.history_service.session_id == session
    assert run(service.history_service.list_history()) == []
    run(
        run_transaction(
            path,
            lambda connection: connection.execute("DROP TRIGGER fail_initial_or_skip"),
        )
    )
    retry = mutate(client, "POST", endpoint, key="initial-or-skip")
    assert retry.status_code == 200, retry.text
    assert service.history_service.active_event.song_id == ("a" if initial else "c")
    history = run(service.history_service.list_history())
    assert [(event.song_id, event.reason) for event in history] == (
        [] if initial else [("a", "SWITCH_AWAY")]
    )
    assert_synced(client, player)


@pytest.mark.parametrize("outer", [True, False])
def test_cancelled_playback_restores_history_and_database(
    real_client, monkeypatch, outer
):
    from server.app.repositories.database import run_transaction

    client, _, _, service = real_client
    start(client)
    snapshot = run(service.queue_manager.queue_repository.get_snapshot())
    state = run(service.queue_manager.get_playback_state())
    active = service.history_service.active_event
    session = service.history_service.session_id

    async def cancel():
        asyncio.current_task().cancel()
        await asyncio.sleep(0)

    async def stop_then_cancel(_connection):
        await service.stop()
        await cancel()

    if outer:
        action = run_transaction(
            service.queue_manager.queue_repository.path, stop_then_cancel
        )
    else:
        monkeypatch.setattr(service, "_sync_player_queue", cancel)
        action = service.next()
    with pytest.raises(asyncio.CancelledError):
        run(action)
    assert run(service.queue_manager.queue_repository.get_snapshot()) == snapshot
    assert run(service.queue_manager.get_playback_state()) == state
    assert run(service.history_service.list_history()) == []
    assert service.history_service.active_event == active
    assert service.history_service.session_id == session
