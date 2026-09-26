from __future__ import annotations

import base64
import gzip
from pathlib import Path

import pytest


_FLAC_GZIP_B64 = (
    "H4sIANqAt2oC/+3Ov0oDMRwH8LR0sSgqOBQcDG4OLXen+GcI9BS3okVdHNNLWkJzObhLCw4dXB0cXMUncPQd3HwCX8LBwU2TOyuCbyDfDwnJ75u/wx4/IoRs1rv1LiHLrtXe628u6Tden9Pb48vp/dPN3Us2e2iQ2uqiW+jx6XA37Ox1wmDb12uuS5NkQubs95q7i1hltWQXsrD0PDMjH/HcqsKyuBxo/Dc6XPGRHkzS6mDsp615Nt/r57Q6seQfynkyNpN04D4R+V8JVSTfdejfENxKFgXRTjvYbwcHTReNpMklO8uS8cJPFWu75Qp9laukYH3NlaHS3SKEFLRMqVZG0rBZDtE12VgnAAAAAAAAAAAAAAAAAAAA/9vnh2iR08eqmJ18ARPRGgRtIAAA"
)
_MP3_WITH_LYRICS_GZIP_B64 = (
    "H4sIANqAt2oC//N0MWZhAAJOgxDPECMgg4uBgdk3wFghOD8vnSEkwNUQKMYDFXMsKsksLmEICXL2BoqyAUWN9Q2NGEIcfZyAfG6Yqpyk0lygVv9goCArUNBIH6jGJcgZapKRgZGxrqGhroE5Q0hwsCtQlA8o6pNYlmZmqGeuZ2hgzBAa7BMCFJcEiqcCneGam5SakpKaogAyPqeyKDO5mGEUjIJRMILB/8cemIKeeWn5QIofiJkZGFgaGBoIgQOEwH9CAGQvsPRKBpZehpbIjlFhngBhsDQ8C7ktT//wSQFSjEsgXGZwaPk4+roaA4tYg9DQUGT2CASj4TMaPpQAANx8HAI6CQAA"
)
_MP3_NO_LYRICS_GZIP_B64 = (
    "H4sIANqAt2oC//N0MWZhAAGlkOBgVyDNx8DA7JNYlmZmqGeuZ2hgzIAA/x97MGAAz7y0fCDFD8TMDAwsDQwNhMABQuA/IQCyF+jGZKAbDS2RHaPCPAHCYGl4FnJbnoG+ABg+KUCKcQmEywwOLR9HX1djYEAahIaGIrNHIBgNn9HwoQQAAASEy0ysBAAA"
)
SIDECAR_LRC = "[00:00.00] LRC line 1\n[00:01.50] LRC line 2\n"


def _inflate(encoded: str) -> bytes:
    return gzip.decompress(base64.b64decode(encoded))


@pytest.fixture
def media_fixture_dir(tmp_path: Path) -> Path:
    (tmp_path / "metadata.flac").write_bytes(_inflate(_FLAC_GZIP_B64))
    (tmp_path / "sidecar.mp3").write_bytes(_inflate(_MP3_WITH_LYRICS_GZIP_B64))
    (tmp_path / "sidecar.lrc").write_text(SIDECAR_LRC, encoding="utf-8")
    (tmp_path / "no_lyrics.mp3").write_bytes(_inflate(_MP3_NO_LYRICS_GZIP_B64))
    (tmp_path / "broken.mp3").write_bytes(b"not a media file")
    return tmp_path
