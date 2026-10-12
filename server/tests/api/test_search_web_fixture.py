"""B06 public Search Collection -> Song wire proof using SQLite and real services."""
from __future__ import annotations

import json
from pathlib import Path

from server.app.models.library import Song
from server.tests.support.playback import real_client, run  # noqa: F401

FIXTURE = Path(__file__).resolve().parents[3] / "web/tests/fixtures/search.json"


def test_search_web_fixture_from_real_resources(real_client, monkeypatch):  # noqa: F811
    client, repository, _, _ = real_client
    monkeypatch.setattr("server.app.repositories.library_repository._now", lambda: "2026-10-11T00:00:00+00:00")
    monkeypatch.setattr("server.app.repositories.library_repository.uuid.uuid4", lambda: "album-wire")
    for song_id in "abc":
        run(repository.upsert_song(Song(
            song_id=song_id, title="长标题 / " + song_id, file_uri=f"{song_id}.flac",
            artists=("艺术家 / 长名",), album_id="album-wire", album="长专辑",
            album_artists=("专辑艺术家",), genres=("Rock",), year=2024,
            track_number={"a": 2, "b": 1, "c": 3}[song_id], tag_names=("Live",),
            availability_status="MISSING" if song_id == "c" else "AVAILABLE",
        )))
    before = client.get("/api/state").json()
    queries = ("长标题", "长名", "长专辑", "专辑艺术家", "Rock", "2024", "Live", "不存在", "   ")
    actual = {"queries": {}, "results": {}}
    for query in queries:
        response = client.get("/api/library/search", params={"q": query})
        assert response.status_code == 200, response.text
        actual["queries"][query] = response.json()
        assert response.json()["song_ids"] == (["a", "b"] if query not in ("不存在", "   ") else [])
        assert response.json()["unavailable_song_ids"] == []
        result = client.get("/api/library/search/results", params={"q": query})
        assert result.status_code == 200, result.text
        actual["results"][query] = result.json()
    actual["songs"] = {}
    for song_id in "ab":
        response = client.get(f"/api/library/songs/{song_id}")
        assert response.status_code == 200, response.text
        actual["songs"][song_id] = response.json()
    after = client.get("/api/state").json()
    for domain in ("epoch", "sequence", "revisions", "queue", "playback", "history"):
        assert after[domain] == before[domain]
    assert json.loads(FIXTURE.read_text()) == actual
