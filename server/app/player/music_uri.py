"""Exact local/MPD path representation at the player boundary."""
from pathlib import Path, PurePosixPath


class MusicUriMapper:
    def __init__(self, local_root: Path, mpd_prefix: str = '') -> None:
        self.local_root = local_root.resolve()
        self.mpd_prefix = mpd_prefix
        if mpd_prefix:
            self._relative_parts(mpd_prefix)

    @staticmethod
    def _relative_parts(uri: str) -> tuple[str, ...]:
        parts = tuple(uri.split('/'))
        if (PurePosixPath(uri).is_absolute() or
                any(part in {'', '.', '..'} for part in parts) or
                any(char in uri for char in ('\\', '\n', '\r', '\0'))):
            raise ValueError('Expected a nonempty relative music path without traversal')
        return parts

    def _check_local(self, path: Path) -> None:
        try:
            path.resolve().relative_to(self.local_root)
        except (ValueError, OSError, RuntimeError) as exc:
            raise ValueError('Music path escapes the local root or cannot be resolved') from exc

    def to_mpd(self, local_uri: str) -> str:
        if not local_uri.startswith('/'):
            raise ValueError('Expected an absolute local music path')
        self._relative_parts(local_uri[1:])
        path = Path(local_uri)
        try:
            relative = path.relative_to(self.local_root).as_posix()
        except ValueError as exc:
            raise ValueError('Local music path is outside the music root') from exc
        self._relative_parts(relative)
        self._check_local(path)
        return f'{self.mpd_prefix}/{relative}' if self.mpd_prefix else relative

    def to_local(self, mpd_uri: str) -> str:
        self._relative_parts(mpd_uri)
        relative = mpd_uri
        if self.mpd_prefix:
            prefix = self.mpd_prefix + '/'
            if not relative.startswith(prefix):
                raise ValueError('MPD music path is outside the configured prefix')
            relative = relative[len(prefix):]
        self._relative_parts(relative)
        path = self.local_root / relative
        self._check_local(path)
        return str(path)
