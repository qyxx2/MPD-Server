"""B04: save the authoritative pending queue, never a client projection."""
import pytest

from server.app.repositories.playlist_repository import PlaylistRepository
from server.tests.support.playback import mutate, run, start


def test_save_reads_latest_complete_up_next_and_replay_does_not_create_twice(real_client):
    client, _, player, service = real_client
    start(client)
    manager = service.queue_manager
    # Change current after any browser preview, leaving Played/current outside saving.
    pending = run(manager.queue_repository.list_up_next())
    run(service.play_now(pending[0].queue_item_id))
    run(service.add_to_queue("b"))
    before_queue = run(manager.get_snapshot())
    before_state = client.get("/api/state").json()
    pending_ids = [item.song_id for item in run(manager.queue_repository.list_up_next())]
    assert pending_ids == ["c", "a", "b"]
    assert any(item.source == "AUTOPLAY" for item in run(manager.queue_repository.list_up_next()))
    execution = run(player.status())
    execution_queue = run(player.queue_entries())
    response = mutate(client, "POST", "/api/playback/queue/save-as-playlist", {"name": "Complete pending"}, key="save-one")
    assert response.status_code == 200, response.text
    assert response.json()["song_ids"] == pending_ids
    assert run(manager.get_snapshot()) == before_queue
    after_state = client.get("/api/state").json()
    for domain in ("playback", "history", "explicit_stop_generation"):
        assert after_state[domain] == before_state[domain]
    assert run(player.status()) == execution
    assert run(player.queue_entries()) == execution_queue
    replay = mutate(client, "POST", "/api/playback/queue/save-as-playlist", {"name": "Complete pending"}, key="save-one")
    assert replay.json() == response.json()
    playlists = client.get("/api/playlists").json()["items"]
    assert [p["song_ids"] for p in playlists if p["name"] == "Complete pending"] == [pending_ids]


def test_duplicate_pending_rejection_leaves_no_playlist_or_revision(real_client):
    client, _, _, service = real_client
    start(client)
    run(service.add_to_queue("b"))
    before = client.get("/api/playlists").json()
    state = client.get("/api/state").json()
    response = mutate(client, "POST", "/api/playback/queue/save-as-playlist", {"name": "Rejected"})
    assert response.status_code == 400, response.text
    assert "duplicate" in response.text
    assert client.get("/api/playlists").json() == before
    assert client.get("/api/state").json()["revisions"] == state["revisions"]
    assert run(service.queue_manager.get_snapshot()).revision == state["queue"]["revision"]


def test_save_membership_failure_rolls_back_playlist_and_first_member(real_client, monkeypatch):
    client, _, _, service = real_client
    start(client)
    repository = service.queue_manager.playlist_repository
    before = run(repository.list_playlists())
    snapshot = client.get("/api/state").json()
    original = repository.add_song
    calls = 0

    async def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("membership write failed")
        return await original(*args, **kwargs)

    monkeypatch.setattr(repository, "add_song", fail_second)
    with pytest.raises(RuntimeError, match="membership write failed"):
        run(service.queue_manager.save_as_playlist("Atomic"))
    assert calls == 2
    assert run(PlaylistRepository(repository.path).list_playlists()) == before
    assert client.get("/api/state").json()["revisions"] == snapshot["revisions"]
    assert client.get("/api/state").json()["queue"] == snapshot["queue"]
