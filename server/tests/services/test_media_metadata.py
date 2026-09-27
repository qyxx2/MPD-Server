from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


def test_step1_media_fixtures_cover_flac_mp3_lrc_and_parse_failure(
    media_fixture_dir: Path,
) -> None:
    assert (media_fixture_dir / "metadata.flac").read_bytes().startswith(
        b"fLaC"
    )
    assert (media_fixture_dir / "sidecar.mp3").read_bytes().startswith(
        b"ID3"
    )
    assert (media_fixture_dir / "no_lyrics.mp3").read_bytes().startswith(
        b"ID3"
    )
    assert (
        media_fixture_dir / "sidecar.lrc"
    ).read_text(encoding="utf-8") == (
        "[00:00.00] LRC line 1\n[00:01.50] LRC line 2\n"
    )
    assert (media_fixture_dir / "broken.mp3").read_bytes() == (
        b"not a media file"
    )


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
    assert (
        sidecar.lyrics
        == "[00:00.00] LRC line 1\n[00:01.50] LRC line 2\n"
    )
    assert sidecar.lyrics_format == "lrc"
    assert sidecar.lyrics_source == "sidecar"
    assert sidecar.lyrics_status == "available"

    embedded = parse_media_file(media_fixture_dir / "metadata.flac")
    assert embedded.lyrics == "Plain embedded lyric line 1\nline 2"
    assert embedded.lyrics_format == "text"
    assert embedded.lyrics_source == "embedded"
    assert embedded.lyrics_status == "available"

    missing = parse_media_file(media_fixture_dir / "no_lyrics.mp3")
    assert missing.title is None
    assert missing.lyrics is None
    assert missing.lyrics_format is None
    assert missing.lyrics_source is None
    assert missing.lyrics_status == "missing"


def test_step3_sidecar_read_failure_is_observable_and_embedded_lyrics_fallback_is_used(
    media_fixture_dir: Path,
) -> None:
    from server.app.services.media_metadata import parse_media_file

    lrc = media_fixture_dir / "sidecar.lrc"
    lrc.write_text("not valid lrc", encoding="utf-8")
    fallback = parse_media_file(media_fixture_dir / "sidecar.mp3")

    assert fallback.lyrics == "Embedded MP3 lyrics"
    assert fallback.lyrics_format == "text"
    assert fallback.lyrics_source == "embedded"
    assert fallback.lyrics_status == "read_error"


def test_step4_parse_failure_is_typed_and_does_not_modify_source_files(
    media_fixture_dir: Path,
) -> None:
    from server.app.services.media_metadata import (
        MediaMetadataError,
        parse_media_file,
    )

    target = media_fixture_dir / "metadata.flac"
    before = hashlib.sha256(target.read_bytes()).hexdigest()
    parse_media_file(target)
    after = hashlib.sha256(target.read_bytes()).hexdigest()
    assert before == after

    with pytest.raises(MediaMetadataError):
        parse_media_file(media_fixture_dir / "broken.mp3")


def test_step6_embedded_artwork_is_returned_as_reference_without_writing_artwork_file(
    media_fixture_dir: Path,
) -> None:
    from mutagen.flac import FLAC, Picture

    from server.app.services.media_metadata import parse_media_file

    target = media_fixture_dir / "artwork.flac"
    target.write_bytes((media_fixture_dir / "metadata.flac").read_bytes())

    image_data = b"test-image-bytes"
    audio = FLAC(target)
    picture = Picture()
    picture.type = 3
    picture.mime = "image/png"
    picture.width = 1
    picture.height = 1
    picture.depth = 8
    picture.data = image_data
    audio.add_picture(picture)
    audio.save()

    before = hashlib.sha256(target.read_bytes()).hexdigest()
    parsed = parse_media_file(target)
    after = hashlib.sha256(target.read_bytes()).hexdigest()

    assert before == after
    assert parsed.artwork is not None
    assert parsed.artwork.source == "EMBEDDED"
    assert parsed.artwork.picture_index == 0
    assert parsed.artwork.mime_type == "image/png"
    assert parsed.artwork.width == 1
    assert parsed.artwork.height == 1
    assert (
        parsed.artwork.content_sha256
        == hashlib.sha256(image_data).hexdigest()
    )
