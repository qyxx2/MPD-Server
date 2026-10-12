"""LIB-SEARCH-VIEW-001: category identities/order and their contents stay server-owned."""
from server.app.models.library import Song
from server.tests.support.playback import real_client, run  # noqa: F401


def test_categories_keep_catalog_order_and_collection_member_order(real_client):  # noqa: F811
    client, repository, _, _ = real_client
    for sid, title, track in (("a", "Z song", 1), ("b", "A song", 2), ("c", "Missing", 3)):
        run(repository.upsert_song(Song(
            song_id=sid, title=title, file_uri=f"{sid}.flac", album="Shared album",
            artists=("Shared singer",), album_artists=("Shared album artist",),
            genres=("Shared genre",), tag_names=("Shared tag",), year=2024,
            track_number=track, availability_status="MISSING" if sid == "c" else "AVAILABLE",
        )))
    run(repository.upsert_song(Song(song_id="d", title="Direct Shared", file_uri="d.flac")))
    before = client.get("/api/state").json()
    response = client.get("/api/library/search/results", params={"q": "Shared"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert [(g["kind"], g["name"]) for g in data["groups"]] == [
        ("albums", "Shared album"), ("artists", "Shared album artist"),
        ("artists", "Shared singer"), ("genres", "Shared genre"), ("tags", "Shared tag"),
    ]
    assert data["groups"][0]["song_ids"] == ["a", "b"]
    for group in data["groups"]:
        catalog = client.get(f'/api/library/{group["kind"]}').json()["items"]
        id_field = {"albums": "album_id", "artists": "artist_id", "genres": "genre_id", "tags": "tag_id"}[group["kind"]]
        assert any(item[id_field] == group["source_id"] for item in catalog)
        contents = client.get(f'/api/library/{group["kind"]}/{group["source_id"]}/songs').json()
        assert group["song_ids"] == [song["song_id"] for song in contents["items"]]
        assert "c" not in group["song_ids"]
    assert data["song_ids"] == ["d"]
    assert client.get("/api/library/search", params={"q": "Shared"}).json()["song_ids"] == ["b", "a", "d"]
    years = client.get("/api/library/search/results", params={"q": "2024"}).json()
    assert [(g["kind"], g["name"], g["song_ids"]) for g in years["groups"]] == [("years", "2024", ["b", "a"])]
    assert years["song_ids"] == []
    after = client.get("/api/state").json()
    for domain in ("epoch", "sequence", "revisions", "queue", "playback", "history"):
        assert after[domain] == before[domain]


def test_object_search_query_validation_and_empty_results(real_client):  # noqa: F811
    client, _, _, _ = real_client
    assert client.get("/api/library/search/results").status_code == 422
    for query in ("   ", "not present"):
        response = client.get("/api/library/search/results", params={"q": query})
        assert response.status_code == 200, response.text
        assert response.json() == {"groups": [], "song_ids": []}
