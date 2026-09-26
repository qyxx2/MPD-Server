from __future__ import annotations

import asyncio
import base64
import gzip
from pathlib import Path

import pytest


FLAC_FIXTURE_GZIP_B64 = (
    "H4sIANqAt2oC/+3Ov0oDMRwH8LR0sSgqOBQcDG4OLXen+GcI9BS3okVdHNNLWkJzObhLCw4dXB0cXMUncPQd3HwCX8LBwU2TOyuCbyDfDwnJ75u/wx4/IoRs1rv1LiHLrtXe628u6Tden9Pb48vp/dPN3Us2e2iQ2uqiW+jx6XA37Ox1wmDb12uuS5NkQubs95q7i1hltWQXsrD0PDMjH/HcqsKyuBxo/Dc6XPGRHkzS6mDsp615Nt/r57Q6seQfynkyNpN04D4R+V8JVSTfdejfENxKFgXRTjvYbwcHTReNpMklO8uS8cJPFWu75Qp9laukYH3NlaHS3SKEFLRMqVZG0rBZDtE12VgnAAAAAAAAAAAAAAAAAAAA/9vnh2iR08eqmJ18ARPRGgRtIAAA"
)

MP3_WITH_LYRICS_GZIP_B64 = (
    "H4sIANqAt2oC//N0MWZhAAJOgxDPECMgg4uBgdk3wFghOD8vnSEkwNUQKMYDFXMsKsksLmEICXL2BoqyAUWN9Q2NGEIcfZyAfG6Yqpyk0lygVv9goCArUNBIH6jGJcgZapKRgZGxrqGhroE5Q0hwsCtQlA8o6pNYlmZmqGeuZ2hgzBAa7BMCFJcEiqcCneGam5SakpKaogAyPqeyKDO5mGEUjIJRMILB/8cemIKeeWn5QIofiJkZGFgaGBoIgQOEwH9CAGQvsPRKBpZehpbIjlFhngBhsDQ8C7ktT//wSQFSjEsgXGZwaPk4+roaA4tYg9DQUGT2CASj4TMaPpQAANx8HAI6CQAA"
)

MP3_NO_LYRICS_GZIP_B64 = (
    "H4sIANqAt2oC//N0MWZhAAGlkOBgVyDNx8DA7JNYlmZmqGeuZ2hgzIAA/x97MGAAz7y0fCDFD8TMDAwsDQwNhMABQuA/IQCyF+jGZKAbDS2RHaPCPAHCYGl4FnJbnoG+ABg+KUCKcQmEywwOLR9HX1djYEAahIaGIrNHIBgNn9HwoQQAAASEy0ysBAAA"
)

SIDECAR_LRC = "[00:00.00] LRC line 1\n[00:01.50] LRC line 2\n"


def _inflate_fixture(encoded: str) -> bytes:
    return gzip.decompress(base64.b64decode(encoded))


@pytest.fixture
def media_fixture_dir(tmp_path: Path) -> Path:
    (tmp_path / "metadata.flac").write_bytes(_inflate_fixture(FLAC_FIXTURE_GZIP_B64))
    (tmp_path / "sidecar.mp3").write_bytes(
        _inflate_fixture(MP3_WITH_LYRICS_GZIP_B64)
    )
    (tmp_path / "sidecar.lrc").write_text(SIDECAR_LRC, encoding="utf-8")
    (tmp_path / "no_lyrics.mp3").write_bytes(
        _inflate_fixture(MP3_NO_LYRICS_GZIP_B64)
    )
    (tmp_path / "broken.mp3").write_bytes(b"not a media file")
    return tmp_path


def test_step1_media_fixtures_cover_flac_mp3_lrc_and_parse_failure(
    media_fixture_dir: Path,
) -> None:
    assert (media_fixture_dir / "metadata.flac").read_bytes().startswith(b"fLaC")
    assert (media_fixture_dir / "sidecar.mp3").read_bytes().startswith(b"ID3")
    assert (media_fixture_dir / "no_lyrics.mp3").read_bytes().startswith(b"ID3")
    assert (media_fixture_dir / "sidecar.lrc").read_text(encoding="utf-8") == SIDECAR_LRC
    assert (media_fixture_dir / "broken.mp3").read_bytes() == b"not a media file"


def test_step2_parses_flac_and_mp3_metadata_and_technical_audio_properties(
    media_fixture_dir: Path,
) -> None:
    from server.app.services.media_metadata import parse_media_file

    flac = parse_media_file(media_fixture_dir / "metadata.flac")
    assert flac.title == "Test Song"
    assert flac.artists == ("Artist A", "Artist B")
    assert flac.album == "Test Album"
    assert flac.album_artists == ("Album Artist",)
    assert flac.track_number == 2
    assert flac.disc_number == 1
    assert flac.year == 2024
    assert flac.date == "2024-08-09"
    assert flac.genres == ("Rock", "Alt")
    assert flac.duration == pytest.approx(0.01, abs=0.02)
    assert flac.codec == "FLAC"
    assert flac.bit_depth == 16
    assert flac.sample_rate_hz == 8000
    assert flac.channel_count == 2

    mp3 = parse_media_file(media_fixture_dir / "sidecar.mp3")
    assert mp3.title == "MP3 Song"
    assert mp3.artists == ("MP3 Artist",)
    assert mp3.album == "MP3 Album"
    assert mp3.album_artists == ()
    assert mp3.track_number == 3
    assert mp3.disc_number == 2
    assert mp3.year == 2023
    assert mp3.duration is not None and mp3.duration > 0
    assert mp3.codec == "MP3"
    assert mp3.sample_rate_hz == 8000
    assert mp3.channel_count == 2


def test_step3_prefers_sidecar_lrc_and_preserves_embedded_ordinary_lyrics(
    media_fixture_dir: Path,
) -> None:
    from server.app.services.media_metadata import parse_media_file

    sidecar = parse_media_file(media_fixture_dir / "sidecar.mp3")
    assert sidecar.lyrics == SIDECAR_LRC
    assert sidecar.lyrics_format == "lrc"

    embedded = parse_media_file(media_fixture_dir / "metadata.flac")
    assert embedded.lyrics == "Plain embedded lyric line 1\nline 2"
    assert embedded.lyrics_format == "text"

    missing = parse_media_file(media_fixture_dir / "no_lyrics.mp3")
    assert missing.lyrics is None
    assert missing.lyrics_format is None

    with pytest.raises(Exception):
        parse_media_file(media_fixture_dir / "broken.mp3")


def test_step4_unknown_values_remain_null_and_parse_failure_is_not_silent(
    media_fixture_dir: Path,
) -> None:
    from server.app.services.media_metadata import parse_media_file

    missing = parse_media_file(media_fixture_dir / "no_lyrics.mp3")
    assert missing.album is None
    assert missing.album_artists == ()
    assert missing.track_number is None
    assert missing.disc_number is None
    assert missing.year is None
    assert missing.date is None
    assert missing.genres == ()
    assert missing.lyrics is None
    assert missing.lyrics_format is None
    assert missing.bit_depth is None

    with pytest.raises(Exception):
        parse_media_file(media_fixture_dir / "broken.mp3")


def test_step4_failed_scan_does_not_replace_known_good_song_metadata(
    media_fixture_dir: Path,
) -> None:
    from server.app.services.library_scanner import scan_paths

    existing = {
        media_fixture_dir / "metadata.flac": {
            "title": "Known Good Title",
            "lyrics": "known-good",
            "sample_rate_hz": 96000,
        }
    }

    result = asyncio.run(
        scan_paths([media_fixture_dir / "metadata.flac"], existing_metadata=existing)
    )

    assert result.failed == []
    assert result.changed[0].metadata_status != "parse_failed"

    broken_result = asyncio.run(
        scan_paths([media_fixture_dir / "broken.mp3"], existing_metadata=existing)
    )
    assert broken_result.failed == [media_fixture_dir / "broken.mp3"]
    assert existing[media_fixture_dir / "metadata.flac"]["title"] == "Known Good Title"
