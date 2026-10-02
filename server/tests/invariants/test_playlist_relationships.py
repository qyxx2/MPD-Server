from server.app.repositories.playlist_repository import PlaylistRepository
from server.tests.support.playback import mutate, run


def test_persisted_membership_matches_every_representation_and_collection_split(
    real_client,
):
    client, library, _, service = real_client
    availability = {"a": "AVAILABLE", "b": "MISSING", "c": "UNREADABLE"}
    for song_id, status in availability.items():
        song = run(library.get_song(song_id))
        run(
            library.upsert_song(song.model_copy(update={"availability_status": status}))
        )
    created = mutate(client, "POST", "/api/playlists", {"name": "Membership"})
    assert created.status_code == 201
    playlist_id = created.json()["playlist_id"]
    base = f"/api/playlists/{playlist_id}"
    repository = PlaylistRepository(service.queue_manager.queue_repository.path)

    def assert_representations(response):
        assert response.status_code in (200, 201), response.text
        persisted = run(repository.list_song_ids(playlist_id))
        listed = next(
            p
            for p in client.get("/api/playlists").json()["items"]
            if p["playlist_id"] == playlist_id
        )
        assert (
            response.json()["song_ids"]
            == listed["song_ids"]
            == client.get(base).json()["song_ids"]
            == persisted
        )
        songs = client.get(base + "/songs").json()
        assert songs["count"] == len(persisted)
        assert [(s["song_id"], s["availability_status"]) for s in songs["items"]] == [
            (i, availability[i]) for i in persisted
        ]
        collection = client.post(
            "/api/library/collections",
            json={"source_type": "PLAYLIST", "source_id": playlist_id},
        )
        assert collection.status_code == 200, collection.text
        assert collection.json()["song_ids"] == [
            i for i in persisted if availability[i] == "AVAILABLE"
        ]
        assert collection.json()["unavailable_song_ids"] == [
            i for i in persisted if availability[i] != "AVAILABLE"
        ]
        assert run(repository.list_song_ids(playlist_id)) == persisted

    assert_representations(created)
    for song_id in "abc":
        assert_representations(
            mutate(client, "POST", base + "/songs", {"song_id": song_id})
        )
    assert_representations(
        mutate(
            client, "PUT", base + "/songs/order", {"ordered_song_ids": ["c", "a", "b"]}
        )
    )
    assert run(repository.list_song_ids(playlist_id)) == ["c", "a", "b"]
    assert_representations(mutate(client, "PATCH", base, {"name": "Renamed"}))
