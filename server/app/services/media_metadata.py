from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Literal

from mutagen import MutagenError
from mutagen.flac import FLAC
from mutagen.id3 import APIC, USLT
from mutagen.mp3 import MP3
from pydantic import BaseModel

from server.app.models.library import ArtworkRef


LyricsFormat = Literal["lrc", "text"] | None
LyricsSource = Literal["sidecar", "embedded"] | None
LyricsStatus = Literal["available", "missing", "read_error"]


class MediaMetadataError(Exception):
    """Raised when a supported media file cannot be parsed safely."""


class ParsedSongMetadata(BaseModel):
    title: str | None
    artists: tuple[str, ...] = ()
    album: str | None = None
    album_artists: tuple[str, ...] = ()
    track_number: int | None = None
    disc_number: int | None = None
    year: int | None = None
    date: str | None = None
    genres: tuple[str, ...] = ()
    duration: float | None = None
    codec: str | None = None
    bit_depth: int | None = None
    sample_rate_hz: int | None = None
    channel_count: int | None = None
    lyrics: str | None = None
    lyrics_format: LyricsFormat = None
    lyrics_source: LyricsSource = None
    lyrics_status: LyricsStatus = "missing"
    artwork: ArtworkRef | None = None
    metadata_status: str = "OK"


_LRC_TIMESTAMP = re.compile(r"\[(\d+):([0-5]\d)(?:[.:](\d{1,3}))?\]")


def _clean_values(
    values: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    if not values:
        return ()
    return tuple(value.strip() for value in values if value.strip())


def _split_number(value: str | None) -> int | None:
    if not value:
        return None
    first = value.split("/", 1)[0].strip()
    try:
        return int(first)
    except ValueError:
        return None


def _parse_year(date: str | None) -> int | None:
    if not date:
        return None
    match = re.match(r"^(\d{4})", date.strip())
    return int(match.group(1)) if match else None


def _flac_values(audio: FLAC, *keys: str) -> list[str]:
    if audio.tags is None:
        return []
    for key in keys:
        values = audio.tags.get(key)
        if values:
            return [str(value) for value in values]
    return []


def _id3_values(audio: MP3, frame_id: str) -> list[str]:
    if audio.tags is None:
        return []
    return [
        str(value)
        for frame in audio.tags.getall(frame_id)
        for value in frame.text
    ]


def _extract_embedded_lyrics(audio: FLAC | MP3) -> str | None:
    if isinstance(audio, FLAC):
        values = _flac_values(
            audio,
            "lyrics",
            "LYRICS",
            "unsyncedlyrics",
        )
        return values[0] if values else None

    if audio.tags is None:
        return None
    frames = [
        frame
        for frame in audio.tags.values()
        if isinstance(frame, USLT)
    ]
    return frames[0].text if frames else None


def _extract_artwork(
    path: Path,
    audio: FLAC | MP3,
) -> ArtworkRef | None:
    pictures = list(audio.pictures) if isinstance(audio, FLAC) else []
    if isinstance(audio, MP3) and audio.tags is not None:
        pictures = [
            frame
            for frame in audio.tags.values()
            if isinstance(frame, APIC)
        ]

    if not pictures:
        return None

    picture = pictures[0]
    data = bytes(picture.data)
    digest = hashlib.sha256(data).hexdigest()
    artwork_id = hashlib.sha256(
        f"{path.resolve()}:{0}:{digest}".encode("utf-8")
    ).hexdigest()

    return ArtworkRef(
        artwork_id=artwork_id,
        source="EMBEDDED",
        picture_index=0,
        mime_type=getattr(picture, "mime", None),
        width=getattr(picture, "width", None) or None,
        height=getattr(picture, "height", None) or None,
        content_sha256=digest,
    )


def _read_sidecar(
    path: Path,
) -> tuple[str | None, str | None, str | None, str | None]:
    sidecar = path.with_suffix(".lrc")
    try:
        text = sidecar.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, None, None, None
    except (OSError, UnicodeError) as exc:
        return None, None, None, str(exc)

    if not _LRC_TIMESTAMP.search(text):
        return None, None, None, "invalid LRC timestamp"

    return text, "lrc", "sidecar", None


def parse_media_file(path: Path) -> ParsedSongMetadata:
    path = Path(path)
    suffix = path.suffix.casefold()
    if suffix not in {".flac", ".mp3"}:
        raise MediaMetadataError(
            f"unsupported media format: {path.suffix or '<none>'}"
        )

    try:
        audio: FLAC | MP3
        if suffix == ".flac":
            audio = FLAC(path)
            artists = _flac_values(audio, "artist", "ARTIST")
            album_artists = _flac_values(
                audio,
                "albumartist",
                "ALBUMARTIST",
            )
            genres = _flac_values(audio, "genre", "GENRE")
            title_values = _flac_values(audio, "title", "TITLE")
            album_values = _flac_values(audio, "album", "ALBUM")
            track_values = _flac_values(
                audio,
                "tracknumber",
                "TRACKNUMBER",
            )
            disc_values = _flac_values(audio, "discnumber", "DISCNUMBER")
            date_values = _flac_values(audio, "date", "DATE")
            bit_depth = getattr(
                audio.info,
                "bits_per_sample",
                None,
            )
        else:
            audio = MP3(path)
            artists = _id3_values(audio, "TPE1")
            album_artists = _id3_values(audio, "TPE2")
            genres = _id3_values(audio, "TCON")
            title_values = _id3_values(audio, "TIT2")
            album_values = _id3_values(audio, "TALB")
            track_values = _id3_values(audio, "TRCK")
            disc_values = _id3_values(audio, "TPOS")
            date_values = _id3_values(audio, "TDRC")
            bit_depth = None

        title = title_values[0].strip() if title_values else None
        date = date_values[0].strip() if date_values else None

        (
            sidecar_lyrics,
            lyrics_format,
            lyrics_source,
            sidecar_error,
        ) = _read_sidecar(path)
        embedded_lyrics = _extract_embedded_lyrics(audio)

        if sidecar_lyrics is not None:
            lyrics = sidecar_lyrics
            lyrics_status: LyricsStatus = "available"
        elif sidecar_error is not None:
            lyrics = embedded_lyrics
            lyrics_status = "read_error"
            lyrics_format = "text" if embedded_lyrics else None
            lyrics_source = "embedded" if embedded_lyrics else None
        elif embedded_lyrics is not None:
            lyrics = embedded_lyrics
            lyrics_format = "text"
            lyrics_source = "embedded"
            lyrics_status = "available"
        else:
            lyrics = None
            lyrics_format = None
            lyrics_source = None
            lyrics_status = "missing"

        return ParsedSongMetadata(
            title=title,
            artists=_clean_values(artists),
            album=(
                album_values[0].strip()
                if album_values
                else None
            ),
            album_artists=_clean_values(album_artists),
            track_number=(
                _split_number(track_values[0])
                if track_values
                else None
            ),
            disc_number=(
                _split_number(disc_values[0])
                if disc_values
                else None
            ),
            year=_parse_year(date),
            date=date,
            genres=_clean_values(genres),
            duration=(
                float(audio.info.length)
                if audio.info.length is not None
                else None
            ),
            codec="FLAC" if suffix == ".flac" else "MP3",
            bit_depth=bit_depth,
            sample_rate_hz=getattr(audio.info, "sample_rate", None),
            channel_count=getattr(audio.info, "channels", None),
            lyrics=lyrics,
            lyrics_format=lyrics_format,
            lyrics_source=lyrics_source,
            lyrics_status=lyrics_status,
            artwork=_extract_artwork(path, audio),
            metadata_status="OK",
        )
    except MediaMetadataError:
        raise
    except (
        MutagenError,
        OSError,
        ValueError,
        TypeError,
        RuntimeError,
        EOFError,
    ) as exc:
        raise MediaMetadataError(
            f"failed to parse media file {path}: {exc}"
        ) from exc
