"""Queue shortcuts inherit occurrence reorder, never song insertion."""
from server.tests.support.playback import mutate, run, start


def test_duplicate_occurrence_moves_to_head_and_tail_preserving_membership_and_replay(real_client):
    client, _, _, service = real_client
    start(client)
    duplicate = run(service.add_to_queue("b"))
    manager = service.queue_manager
    before = run(manager.get_snapshot())
    before_state = client.get("/api/state").json()
    pending = sorted((i for i in before.items if i.position > 0), key=lambda i: i.position)
    assert sum(i.song_id == "b" for i in pending) == 2
    path = f"/api/playback/queue/items/{duplicate.queue_item_id}"
    first = mutate(client, "PUT", path, {"before_queue_item_id": pending[0].queue_item_id}, key="move-head")
    assert first.status_code == 200, first.text
    middle = run(manager.get_snapshot())
    assert next(i for i in middle.items if i.queue_item_id == duplicate.queue_item_id).position == 1
    tail = mutate(client, "PUT", path, {"before_queue_item_id": None}, key="move-tail")
    assert tail.status_code == 200, tail.text
    after = run(manager.get_snapshot())
    assert next(i for i in after.items if i.queue_item_id == duplicate.queue_item_id).position == len(pending)
    for snapshot in (middle, after):
        assert {(i.queue_item_id, i.song_id, i.source, i.playback_context_id) for i in snapshot.items} == {
            (i.queue_item_id, i.song_id, i.source, i.playback_context_id) for i in before.items
        }
        assert [i for i in snapshot.items if i.position <= 0] == [i for i in before.items if i.position <= 0]
    replay = mutate(client, "PUT", path, {"before_queue_item_id": pending[0].queue_item_id}, key="move-head")
    assert replay.json() == first.json()
    assert run(manager.get_snapshot()) == after
    after_state = client.get("/api/state").json()
    for field in ("playback", "history", "explicit_stop_generation"):
        assert after_state[field] == before_state[field]
