from __future__ import annotations

import asyncio
from pathlib import Path

from server.app.models.library import ScanResult


def _run(coro):
    return asyncio.run(coro)


def test_step8_default_debounce_is_500ms():
    from server.app.services.library_watch import LibraryWatch

    watch = LibraryWatch(lambda _paths: asyncio.sleep(0))
    assert watch.debounce_seconds == 0.5


def test_step8_debounces_events_and_scans_one_deduplicated_batch():
    from server.app.services.library_watch import LibraryWatch

    calls: list[list[Path]] = []

    async def scan_paths(paths: list[Path]) -> ScanResult:
        calls.append(paths)
        return ScanResult()

    async def scenario():
        watch = LibraryWatch(scan_paths, debounce_seconds=0.02)
        await watch.notify(Path("/music/a.mp3"))
        await watch.notify(Path("/music/a.mp3"))
        await watch.notify(Path("/music/b.mp3"))
        await asyncio.sleep(0.05)
        await watch.close()

    _run(scenario())
    assert calls == [[Path("/music/a.mp3"), Path("/music/b.mp3")]]


def test_batch2_watch_lrc_event_rescans_associated_audio(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    from server.app.services.library_watch import LibraryWatch

    db_path = tmp_path / "library.db"
    _run(initialize_database(str(db_path)))
    root = tmp_path / "library"
    root.mkdir()
    target = root / "track.mp3"
    copy2(media_fixture_dir / "no_lyrics.mp3", target)

    scanner = _scanner(db_path)
    first = _run(scanner.scan_full(root))
    assert len(first.added_song_ids) == 1

    lrc = root / "track.lrc"
    lrc.write_text("[00:00.00] watched lyrics\\n", encoding="utf-8")

    async def scenario():
        watch = LibraryWatch(scanner.scan_paths, debounce_seconds=0)
        await watch.notify(lrc)
        result = await watch.flush()
        await watch.close()
        return result

    result = _run(scenario())
    song = _run(LibraryRepository(str(db_path)).get_song(first.added_song_ids[0]))

    assert result is not None
    assert result.updated_song_ids == first.added_song_ids
    assert song is not None
    assert song.lyrics == "[00:00.00] watched lyrics\\n"
    assert song.lyrics_source == "sidecar"
    assert song.lyrics_status == "available"
