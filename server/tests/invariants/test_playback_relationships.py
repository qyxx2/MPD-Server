from __future__ import annotations

import pytest

from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.tests.invariants.assertions import (
    assert_execution_relationship,
    server_snapshot,
)
from server.tests.support.playback import mutate, run, start


@pytest.mark.parametrize("operation", ["reorder", "delete"])
def test_same_uri_pending_mutation_preserves_occurrence_identity(real_client, operation):
    """PB-REORDER-001/PB-DELETE-PENDING-001: URI equality is not identity."""
    client, _, player, service = real_client
    start(client)
    assert mutate(client, "POST", "/api/playback/songs/b/queue").status_code == 200
    items = run(service.queue_manager.list_items())
    duplicates = [i for i in items if i.position > 0 and i.song_id == "b"]
    assert len(duplicates) >= 2
    selected = duplicates[0]
    current = next(i for i in items if i.position == 0)
    before = assert_execution_relationship(service, player)
    state = run(service.queue_manager.get_playback_state())
    history = server_snapshot(service)[2:]
    path = f"/api/playback/queue/items/{selected.queue_item_id}"
    method = "PUT" if operation == "reorder" else "DELETE"
    body = {} if operation == "reorder" else None
    response = mutate(client, method, path, body)
    assert response.status_code == (200 if operation == "reorder" else 204)
    after = assert_execution_relationship(service, player, current_id=current.queue_item_id)
    retained = set(before) - ({selected.queue_item_id} if operation == "delete" else set())
    assert set(after) == retained
    assert {i: after[i].mpd_song_id for i in retained} == {
        i: before[i].mpd_song_id for i in retained
    }
    if operation == "delete":
        assert before[selected.queue_item_id].mpd_song_id not in {
            entry.mpd_song_id for entry in run(player.queue_entries())
        }
    else:
        assert after[selected.queue_item_id].position == len(after) - 1
    assert run(service.queue_manager.get_playback_state()) == state
    assert server_snapshot(service)[2:] == history
    final = server_snapshot(service)
    entries = run(player.queue_entries())
    assert mutate(client, method, path, body).status_code == response.status_code
    assert server_snapshot(service) == final
    assert run(player.queue_entries()) == entries


@pytest.mark.parametrize("operation", ["reorder", "delete", "clear"])
def test_duplicate_execution_occurrences_survive_mutation(real_client, operation):
    client, _, player, service = real_client
    start(client)
    first = next(i for i in run(service.queue_manager.list_items()) if i.position == 0)
    duplicate = run(service.play_next("a"))
    assert duplicate.queue_item_id != first.queue_item_id
    bindings = assert_execution_relationship(
        service, player, current_id=first.queue_item_id
    )
    assert (
        bindings[first.queue_item_id].mpd_song_id
        != bindings[duplicate.queue_item_id].mpd_song_id
    )
    # Switch to the duplicate occurrence: same Song/URI, different Queue identity.
    response = mutate(client, "POST", "/api/playback/next", key="duplicate-next")
    assert response.status_code == 200, response.text
    assert_execution_relationship(service, player, current_id=duplicate.queue_item_id)
    assert (
        next(
            i
            for i in run(service.queue_manager.list_items())
            if i.queue_item_id == first.queue_item_id
        ).position
        < 0
    )
    active = service.history_service.active_event
    events = run(service.history_service.list_history())
    pending = next(
        i
        for i in run(service.queue_manager.list_items())
        if i.position > 0 and i.song_id == "c"
    )
    if operation == "reorder":
        response = mutate(
            client, "PUT", f"/api/playback/queue/items/{pending.queue_item_id}", {}
        )
    elif operation == "delete":
        response = mutate(
            client, "DELETE", f"/api/playback/queue/items/{pending.queue_item_id}"
        )
    else:
        response = mutate(client, "DELETE", "/api/playback/queue")
    assert response.status_code in (200, 204), response.text
    assert_execution_relationship(service, player, current_id=duplicate.queue_item_id)
    assert service.history_service.active_event == active
    assert run(service.history_service.list_history()) == events
    assert mutate(client, "POST", "/api/playback/pause").status_code == 200
    assert_execution_relationship(service, player, current_id=duplicate.queue_item_id)
    assert mutate(client, "POST", "/api/playback/stop").status_code == 200
    assert_execution_relationship(service, player, current_id=duplicate.queue_item_id)


@pytest.mark.parametrize("transition", ["switch", "skip", "stop"])
def test_transition_history_matches_confirmed_current(real_client, transition):
    client, library, player, service = real_client
    start(client)
    if transition == "skip":
        song = run(library.get_song("b"))
        run(
            library.upsert_song(
                song.model_copy(update={"availability_status": "MISSING"})
            )
        )
    endpoint = "/api/playback/stop" if transition == "stop" else "/api/playback/next"
    response = mutate(client, "POST", endpoint, key="transition")
    assert response.status_code == 200, response.text
    assert_execution_relationship(service, player)
    assert [
        (e.song_id, e.reason) for e in run(service.history_service.list_history())
    ] == [("a", "STOP" if transition == "stop" else "SWITCH_AWAY")]
    if transition != "stop":
        assert service.history_service.active_event.song_id == (
            "c" if transition == "skip" else "b"
        )
    before = server_snapshot(service)
    assert mutate(client, "POST", endpoint, key="transition").json() == response.json()
    assert server_snapshot(service) == before


@pytest.mark.parametrize("reported_position", [0, 1])
def test_wrong_duplicate_current_is_reconciliation_failure(
    real_client, monkeypatch, reported_position
):
    client, _, player, service = real_client
    start(client)
    duplicate = run(service.play_next("a"))
    entries = run(player.queue_entries())
    assert entries[0].song_uri == entries[1].song_uri
    before = server_snapshot(service)
    actual_status = player.status

    async def wrong_occurrence():
        status = await actual_status()
        return status.model_copy(
            update={
                "song_id": entries[1].mpd_song_id,
                "song_position": reported_position,
            }
        )

    monkeypatch.setattr(player, "status", wrong_occurrence)
    response = mutate(
        client, "PUT", f"/api/playback/queue/items/{duplicate.queue_item_id}", {}
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "PLAYBACK_RECONCILIATION_FAILED"
    assert server_snapshot(service) == before
    monkeypatch.setattr(player, "status", actual_status)


@pytest.mark.parametrize("operation", ["reorder", "delete"])
def test_pending_duplicate_mutation_preserves_retained_occurrence_ids(
    real_client, operation
):
    client, _, player, service = real_client
    start(client)
    items = run(service.queue_manager.list_items())
    current = next(i for i in items if i.position == 0)
    duplicate = next(
        i for i in items if i.position > 0 and i.song_id == current.song_id
    )
    successor = next(i for i in items if i.position == 1)
    before = assert_execution_relationship(
        service, player, current_id=current.queue_item_id
    )
    if operation == "reorder":
        response = mutate(
            client,
            "PUT",
            f"/api/playback/queue/items/{duplicate.queue_item_id}",
            {"before_queue_item_id": successor.queue_item_id},
        )
    else:
        response = mutate(
            client, "DELETE", f"/api/playback/queue/items/{duplicate.queue_item_id}"
        )
    assert response.status_code in (200, 204), response.text
    after = assert_execution_relationship(
        service, player, current_id=current.queue_item_id
    )
    # Across pending-only mutation, retained execution occurrences keep engine
    # identity. This deliberately does not require ID continuity across a switch.
    expected_ids = set(before) - (
        {duplicate.queue_item_id} if operation == "delete" else set()
    )
    assert set(after) == expected_ids
    assert {i: e.mpd_song_id for i, e in after.items()} == {
        i: before[i].mpd_song_id for i in expected_ids
    }
    if operation == "delete":
        assert before[duplicate.queue_item_id].mpd_song_id not in {
            e.mpd_song_id for e in after.values()
        }
    else:
        assert after[duplicate.queue_item_id].position == 1


@pytest.mark.parametrize("action", ["queue", "play-next"])
def test_insertion_rejects_actual_playback_divergence_and_can_retry(
    real_client, monkeypatch, action
):
    client, _, player, service = real_client
    start(client)
    before = server_snapshot(service)
    actual_add = player.queue_add

    async def add_then_pause(uri):
        result = await actual_add(uri)
        await player.pause()
        return result

    monkeypatch.setattr(player, "queue_add", add_then_pause)
    endpoint = f"/api/playback/songs/a/{action}"
    response = mutate(client, "POST", endpoint, key="divergent-insert")
    assert response.status_code == 502, response.text
    assert response.json()["error"]["code"] == "PLAYBACK_RECONCILIATION_FAILED"
    assert server_snapshot(service) == before
    records = IdempotencyRepository(service.queue_manager.queue_repository.path)
    assert run(records.get_by_key("divergent-insert")) is None
    monkeypatch.setattr(player, "queue_add", actual_add)
    # Recover the external player separately: SQLite cannot undo its side effects.
    run(player.queue_play(run(player.queue_entries())[0].mpd_song_id))
    retry = mutate(client, "POST", endpoint, key="divergent-insert")
    assert retry.status_code == 200, retry.text
    assert_execution_relationship(service, player)
    final = server_snapshot(service)
    assert (
        mutate(client, "POST", endpoint, key="divergent-insert").json() == retry.json()
    )
    assert server_snapshot(service) == final
