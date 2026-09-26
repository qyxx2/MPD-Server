from __future__ import annotations

from typing import Protocol

from server.app.player.models import OutputInfo, PlayerStatus


class PlayerUnavailable(RuntimeError):
    """The playback engine cannot currently be reached."""


class PlayerCommandError(RuntimeError):
    """The playback engine rejected a command."""

    def __init__(
        self,
        command: str,
        message: str,
        *,
        error_code: int | None = None,
        command_list_index: int | None = None,
    ) -> None:
        super().__init__(message)
        self.command = command
        self.error_code = error_code
        self.command_list_index = command_list_index


class PlayerPort(Protocol):
    async def status(self) -> PlayerStatus: ...
    async def play(self, song_uri: str | None = None) -> None: ...
    async def pause(self) -> None: ...
    async def stop(self) -> None: ...
    async def next(self) -> None: ...
    async def previous(self) -> None: ...
    async def seek(self, seconds: float) -> None: ...
    async def set_repeat(self, enabled: bool) -> None: ...
    async def set_random(self, enabled: bool) -> None: ...
    async def set_volume(self, volume: int) -> None: ...
    async def update_database(self) -> None: ...
    async def outputs(self) -> list[OutputInfo]: ...
