from __future__ import annotations

import inspect
import random
from collections.abc import Awaitable, Callable, Sequence

from server.app.player.models import OutputInfo, PlayerEvent, PlayerState, PlayerStatus
from server.app.player.ports import PlayerCommandError, PlayerPort, PlayerUnavailable

EventListener = Callable[[PlayerEvent], object | Awaitable[object]]


class MockMPD(PlayerPort):
    """Deterministic in-memory playback engine for development and tests."""

    def __init__(
        self,
        songs: Sequence[str] = (),
        *,
        durations: dict[str, float] | None = None,
        outputs: Sequence[OutputInfo] | None = None,
        random_seed: int = 0,
    ) -> None:
        self._songs = list(songs)
        self._durations = {song: 300.0 for song in self._songs}
        if durations:
            self._durations.update(durations)
        self._outputs = list(outputs or [
            OutputInfo(id=0, name="Mock Output", plugin="mock", enabled=True)
        ])
        self._random = random.Random(random_seed)
        self._connected = True
        self._state = PlayerState.STOPPED
        self._current_index: int | None = None
        self._elapsed = 0.0
        self._volume = 50
        self._repeat = False
        self._random_enabled = False
        self._fail_next: dict[str, str] = {}
        self._listeners: list[EventListener] = []

    def disconnect(self) -> None:
        self._connected = False

    def reconnect(self) -> None:
        self._connected = True

    def fail_next(self, command: str, message: str = "injected command failure") -> None:
        self._fail_next[command] = message

    def subscribe(self, listener: EventListener) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    async def status(self) -> PlayerStatus:
        self._check("status")
        return self._status()

    async def play(self, song_uri: str | None = None) -> None:
        self._check("play")
        if song_uri is not None:
            try:
                self._current_index = self._songs.index(song_uri)
            except ValueError as exc:
                raise PlayerCommandError("play", f"unknown song URI: {song_uri}") from exc
            self._elapsed = 0.0
        elif self._current_index is None:
            if not self._songs:
                raise PlayerCommandError("play", "no songs available")
            self._current_index = 0
            self._elapsed = 0.0
        self._state = PlayerState.PLAYING
        await self._emit("play")

    async def pause(self) -> None:
        self._check("pause")
        self._state = PlayerState.PAUSED
        await self._emit("pause")

    async def stop(self) -> None:
        self._check("stop")
        self._state = PlayerState.STOPPED
        self._elapsed = 0.0
        await self._emit("stop")

    async def next(self) -> None:
        self._check("next")
        if not self._songs:
            raise PlayerCommandError("next", "no songs available")
        if self._current_index is None:
            next_index = 0
        elif self._random_enabled and len(self._songs) > 1:
            choices = [i for i in range(len(self._songs)) if i != self._current_index]
            next_index = self._random.choice(choices)
        else:
            next_index = self._current_index + 1
            if next_index >= len(self._songs):
                if self._repeat:
                    next_index = 0
                else:
                    self._state = PlayerState.STOPPED
                    await self._emit("next")
                    return
        self._current_index = next_index
        self._elapsed = 0.0
        self._state = PlayerState.PLAYING
        await self._emit("next")

    async def previous(self) -> None:
        self._check("previous")
        if not self._songs:
            raise PlayerCommandError("previous", "no songs available")
        if self._current_index is None:
            self._current_index = 0
        else:
            self._current_index = max(0, self._current_index - 1)
        self._elapsed = 0.0
        self._state = PlayerState.PLAYING
        await self._emit("previous")

    async def seek(self, seconds: float) -> None:
        self._check("seek")
        if self._current_index is None:
            raise PlayerCommandError("seek", "no current song")
        if seconds < 0:
            raise PlayerCommandError("seek", "seek position must not be negative")
        duration = self._durations[self._songs[self._current_index]]
        self._elapsed = min(seconds, duration)
        await self._emit("seek")

    async def set_repeat(self, enabled: bool) -> None:
        self._check("set_repeat")
        self._repeat = enabled
        await self._emit("set_repeat")

    async def set_random(self, enabled: bool) -> None:
        self._check("set_random")
        self._random_enabled = enabled
        await self._emit("set_random")

    async def set_volume(self, volume: int) -> None:
        self._check("set_volume")
        if not 0 <= volume <= 100:
            raise PlayerCommandError("set_volume", "volume must be between 0 and 100")
        self._volume = volume
        await self._emit("set_volume")

    async def update_database(self) -> None:
        self._check("update_database")
        await self._emit("update_database")

    async def outputs(self) -> list[OutputInfo]:
        self._check("outputs")
        return [output.model_copy(deep=True) for output in self._outputs]

    def _check(self, command: str) -> None:
        if not self._connected:
            raise PlayerUnavailable("MPD is unavailable")
        if command in self._fail_next:
            raise PlayerCommandError(command, self._fail_next.pop(command))

    def _status(self) -> PlayerStatus:
        uri = None if self._current_index is None else self._songs[self._current_index]
        duration = None if uri is None else self._durations[uri]
        return PlayerStatus(
            state=self._state,
            song_uri=uri,
            song_position=self._current_index,
            song_id=None if self._current_index is None else self._current_index + 1,
            elapsed_seconds=self._elapsed if uri is not None else None,
            duration_seconds=duration,
            volume=self._volume,
            repeat=self._repeat,
            random=self._random_enabled,
        )

    async def _emit(self, kind: str) -> None:
        event = PlayerEvent(kind=kind, status=self._status())
        for listener in tuple(self._listeners):
            result = listener(event)
            if inspect.isawaitable(result):
                await result
