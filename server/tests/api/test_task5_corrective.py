from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.models.library import Song
from server.app.repositories.library_repository import LibraryRepository


@pytest.fixture
def real_client(tmp_path, monkeypatch):
    path = str(tmp_path / "corrective.db")
    monkeypatch.setenv("DATABASE_PATH", path)
    with TestClient(app) as client:
        yield client, LibraryRepository(path)


@pytest.mark.parametrize(
    "source_type", ["ALBUM", "ARTIST", "GENRE", "YEAR", "TAG", "PLAYLIST"]
)
@pytest.mark.parametrize("action", ["read", "play"])
def test_absent_source_is_404_without_mutation(real_client, source_type, action):
    client, _ = real_client
    endpoint = (
        "/api/library/collections"
        if action == "read"
        else "/api/playback/collections/play"
    )
    before_queue = client.get("/api/playback/queue").json()
    before_history = client.get("/api/history").json()
    headers = {"Idempotency-Key": "absent-source"}
    response = client.post(
        endpoint,
        json={"source_type": source_type, "source_id": "absent"},
        headers=headers,
    )
    assert response.status_code == 404, response.text
    error = response.json()["error"]
    assert error["code"] == (
        "PLAYLIST_NOT_FOUND"
        if source_type == "PLAYLIST"
        else "COLLECTION_SOURCE_NOT_FOUND"
    )
    assert set(error) == {"code", "message", "details"}
    if source_type != "PLAYLIST":
        assert error["details"] == {"source_type": source_type, "source_id": "absent"}
    assert client.get("/api/playback/queue").json() == before_queue
    assert client.get("/api/history").json() == before_history
    # A failed request must not consume its key: changing the request is no conflict.
    retry = client.post(endpoint, json={"source_type": "SONGS"}, headers=headers)
    assert retry.status_code == 200, retry.text


@pytest.mark.parametrize("kind", ["albums", "artists", "genres", "years", "tags"])
def test_absent_category_song_route_is_404(real_client, kind):
    client, _ = real_client
    response = client.get(f"/api/library/{kind}/absent/songs")
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "COLLECTION_SOURCE_NOT_FOUND"


@pytest.mark.parametrize("source_type", ["ALBUM", "ARTIST", "GENRE", "YEAR", "TAG"])
def test_known_all_unavailable_source_is_not_absent(real_client, source_type):
    client, repository = real_client
    asyncio.run(
        repository.upsert_song(
            Song(
                song_id="missing",
                title="Missing",
                file_uri="missing.flac",
                album_id="album",
                album="Album",
                artists=("Artist",),
                genres=("Genre",),
                tag_names=("Tag",),
                year=2024,
                availability_status="MISSING",
            )
        )
    )
    ids = {
        "ALBUM": asyncio.run(repository.get_song("missing")).album_id,
        "ARTIST": "Artist",
        "GENRE": "Genre",
        "YEAR": "2024",
        "TAG": "Tag",
    }
    response = client.post(
        "/api/library/collections",
        json={"source_type": source_type, "source_id": ids[source_type]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["song_ids"] == []
    assert response.json()["unavailable_song_ids"] == ["missing"]


@pytest.mark.parametrize(
    "source_type", ["LIBRARY", "FAVORITES", "SEARCH", "SONGS", "PLAYLIST"]
)
def test_legal_empty_collection_remains_success(real_client, source_type):
    client, _ = real_client
    body = {"source_type": source_type}
    if source_type == "SEARCH":
        body["query"] = "no match"
    if source_type == "PLAYLIST":
        created = client.post(
            "/api/playlists",
            json={"name": "Empty"},
            headers={"Idempotency-Key": "create-empty"},
        )
        body["source_id"] = created.json()["playlist_id"]
    response = client.post("/api/library/collections", json=body)
    assert response.status_code == 200
    assert response.json()["song_ids"] == []
    assert response.json()["unavailable_song_ids"] == []


def test_catalog_api_calls_summary_service_without_song_enumeration(real_client):
    from pydantic import BaseModel

    class Summary(BaseModel):
        artist_id: str = "stable"
        name: str = "Artist"
        song_count: int = 3

    class SummaryOnlyService:
        async def list_artists(self):
            return [Summary()]

    client, _ = real_client
    previous = app.state.library_service
    app.state.library_service = SummaryOnlyService()
    try:
        response = client.get("/api/library/artists")
    finally:
        app.state.library_service = previous
    assert response.status_code == 200, response.text
    assert response.json() == {
        "items": [{"artist_id": "stable", "name": "Artist", "song_count": 3}],
        "count": 1,
    }


@pytest.mark.parametrize(
    "kind,source_type,id_key",
    [
        ("albums", "ALBUM", "album_id"),
        ("artists", "ARTIST", "artist_id"),
        ("genres", "GENRE", "genre_id"),
        ("years", "YEAR", "source_id"),
        ("tags", "TAG", "tag_id"),
    ],
)
@pytest.mark.parametrize("blank", [False, True])
def test_unknown_category_round_trip_without_fabricated_metadata(
    real_client, kind, source_type, id_key, blank
):
    client, repository = real_client
    fields = (
        {
            "album": " ",
            "artists": ("", " "),
            "album_artists": (" ",),
            "genres": (" ",),
            "tag_names": ("",),
        }
        if blank
        else {}
    )
    for song_id, title, availability in [
        ("unknown-a", "Z", "AVAILABLE"),
        ("unknown-b", "A", "AVAILABLE"),
        ("unknown-missing", "M", "MISSING"),
    ]:
        asyncio.run(
            repository.upsert_song(
                Song(
                    song_id=song_id,
                    title=title,
                    file_uri=f"{song_id}.flac",
                    availability_status=availability,
                    **fields,
                )
            )
        )
    before = client.get("/api/library/songs/unknown-a").json()
    response = client.get(f"/api/library/{kind}")
    assert response.status_code == 200, response.text
    assert response.json()["count"] == 1
    summary = response.json()["items"][0]
    assert summary["song_count"] == 2
    if kind == "years":
        assert summary["value"] is None
        assert summary["source_id"] == "unknown"
    else:
        assert summary["title" if kind == "albums" else "name"] == "未知"
    source_id = summary[id_key]
    body = {"source_type": source_type, "source_id": source_id}
    collection = client.post("/api/library/collections", json=body)
    assert collection.status_code == 200, collection.text
    expected = (
        ["unknown-a", "unknown-b"] if kind == "albums" else ["unknown-b", "unknown-a"]
    )
    assert collection.json()["song_ids"] == expected
    assert collection.json()["unavailable_song_ids"] == ["unknown-missing"]
    songs = client.get(f"/api/library/{kind}/{source_id}/songs")
    assert songs.status_code == 200
    assert [item["song_id"] for item in songs.json()["items"]] == expected
    from server.app.player.mock_mpd import MockMPD

    previous = app.state.playback_service.player
    app.state.playback_service.player = MockMPD(["unknown-a.flac", "unknown-b.flac"])
    try:
        played = client.post(
            "/api/playback/collections/play",
            json=body,
            headers={"Idempotency-Key": "play-unknown"},
        )
    finally:
        app.state.playback_service.player = previous
    assert played.status_code == 200, played.text
    assert played.json()["song_id"] == expected[0]
    assert client.get("/api/library/songs/unknown-a").json() == before


@pytest.mark.parametrize(
    "kind,source_type,id_key,field",
    [
        ("artists", "ARTIST", "artist_id", "artists"),
        ("genres", "GENRE", "genre_id", "genres"),
        ("tags", "TAG", "tag_id", "tag_names"),
    ],
)
def test_unknown_does_not_collide_with_real_unknown_name(
    real_client, kind, source_type, id_key, field
):
    client, repository = real_client
    asyncio.run(
        repository.upsert_song(
            Song(song_id="unknown", title="Unknown", file_uri="u.flac")
        )
    )
    asyncio.run(
        repository.upsert_song(
            Song(
                song_id="named", title="Named", file_uri="n.flac", **{field: ("未知",)}
            )
        )
    )
    items = client.get(f"/api/library/{kind}").json()["items"]
    assert len(items) == 2
    assert len({item[id_key] for item in items}) == 2
    collections = [
        client.post(
            "/api/library/collections",
            json={"source_type": source_type, "source_id": item[id_key]},
        ).json()["song_ids"]
        for item in items
    ]
    assert sorted(collections) == [["named"], ["unknown"]]


def test_absent_queue_item_play_is_404(real_client):
    client, _ = real_client
    response = client.post(
        "/api/playback/queue/items/absent/play",
        headers={"Idempotency-Key": "queue-absent"},
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "QUEUE_ITEM_NOT_FOUND"


@pytest.mark.parametrize(
    "availability,error_type",
    [(None, "PlaybackSongNotFoundError"), ("MISSING", "PlaybackSongUnavailableError")],
)
def test_playback_song_lookup_errors_are_typed(real_client, availability, error_type):
    client, repository = real_client
    if availability:
        asyncio.run(
            repository.upsert_song(
                Song(
                    song_id="target",
                    title="Target",
                    file_uri="target.flac",
                    availability_status=availability,
                )
            )
        )
    with pytest.raises(ValueError) as caught:
        asyncio.run(app.state.playback_service._require_available_song("target"))
    assert type(caught.value).__name__ == error_type
    response = client.post(
        "/api/playback/tracks/target/play", headers={"Idempotency-Key": "lookup"}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PLAYBACK_REQUEST_INVALID"


def test_plain_domain_error_is_not_classified_by_message(real_client):
    class InvalidRequestService:
        async def start_track(self, song_id):
            raise ValueError("song not found: this is a request description")

    client, _ = real_client
    previous = app.state.playback_service
    app.state.playback_service = InvalidRequestService()
    try:
        response = client.post(
            "/api/playback/tracks/target/play",
            headers={"Idempotency-Key": "plain-domain-error"},
        )
    finally:
        app.state.playback_service = previous
    assert response.status_code == 400, response.text


@pytest.mark.parametrize("source_type", ["ALBUM", "ARTIST", "GENRE", "YEAR", "TAG"])
def test_unknown_all_unavailable_category_is_known(real_client, source_type):
    from server.app.services.library_service import unknown_category_id

    client, repository = real_client
    asyncio.run(
        repository.upsert_song(
            Song(
                song_id="unreadable",
                title="Unreadable",
                file_uri="u.flac",
                availability_status="UNREADABLE",
            )
        )
    )
    response = client.post(
        "/api/library/collections",
        json={
            "source_type": source_type,
            "source_id": unknown_category_id(source_type),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["song_ids"] == []
    assert response.json()["unavailable_song_ids"] == ["unreadable"]


def test_unparseable_year_enters_unknown_after_real_scan(
    real_client, media_fixture_dir
):
    from mutagen.flac import FLAC

    client, _ = real_client
    scan_root = media_fixture_dir / "year-only"
    scan_root.mkdir()
    path = scan_root / "metadata.flac"
    path.write_bytes((media_fixture_dir / "metadata.flac").read_bytes())
    # This is a generated test fixture; production scanner must only read it.
    audio = FLAC(path)
    audio["date"] = ["invalid-date"]
    audio.save()
    before = path.read_bytes()
    scanned = client.post(
        "/api/library/scan",
        json={"root": str(scan_root)},
        headers={"Idempotency-Key": "invalid-year-scan"},
    )
    assert scanned.status_code == 200, scanned.text
    songs = client.get("/api/library/songs").json()["items"]
    flac = next(item for item in songs if item["file_uri"] == str(path.resolve()))
    assert flac["year"] is None
    assert flac["date"] == "invalid-date"
    years = client.get("/api/library/years").json()["items"]
    assert years[-1]["source_id"] == "unknown"
    assert years[-1]["value"] is None
    collection = client.post(
        "/api/library/collections", json={"source_type": "YEAR", "source_id": "unknown"}
    )
    assert flac["song_id"] in collection.json()["song_ids"]
    assert path.read_bytes() == before
