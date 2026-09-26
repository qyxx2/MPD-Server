from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from server.app.player.models import (
    DatabaseUpdateStatus,
    MPDStats,
    OutputInfo,
    PlayerQueueEntry,
    PlayerState,
    PlayerStatus,
)
from server.app.player.mpd_protocol import (
    MPDAckError,
    MPDProtocolError,
    MPDResponse,
    parse_response,
    quote_argument,
)
from server.app.player.ports import PlayerCommandError, PlayerPort, PlayerUnavailable

ConnectionFactory = Callable[
    [str, int], Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]]
]


class MPDAdapter(PlayerPort):
    """Async adapter for the line-oriented MPD TCP protocol."""

    def __init__(
        self,
        host: str,
        port: int = 6600,
        password: str | None = None,
        *,
        connection_timeout: float = 3.0,
        command_timeout: float = 5.0,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.connection_timeout = connection_timeout
        self.command_timeout = command_timeout
        self._connection_factory = connection_factory or asyncio.open_connection
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        writer = self._writer
        self._reader = None
        self._writer = None
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass

    async def status(self) -> PlayerStatus:
        async with self._lock:
            response = await self._command_unlocked("status")
            current = None
            song_position = _parse_int(_scalar(response.as_dict().get("song")))
            if song_position is not None and song_position >= 0:
                current = await self._command_unlocked("currentsong")
            return _status_from_response(response, current)

    async def play(self, song_uri: str | None = None) -> None:
        if song_uri is None:
            await self._command("play")
            return
        async with self._lock:
            playlist = await self._command_unlocked("playlistinfo")
            song_id = _find_song_id(playlist, song_uri)
            if song_id is None:
                raise PlayerCommandError("play", f"song URI not in MPD queue: {song_uri}")
            await self._command_unlocked("playid", str(song_id))

    async def pause(self) -> None:
        await self._command("pause", "1")

    async def stop(self) -> None:
        await self._command("stop")

    async def next(self) -> None:
        await self._command("next")

    async def previous(self) -> None:
        await self._command("previous")

    async def seek(self, seconds: float) -> None:
        if seconds < 0:
            raise PlayerCommandError("seek", "seek position must not be negative")
        await self._command("seekcur", _format_number(seconds))

    async def set_repeat(self, enabled: bool) -> None:
        await self._command("repeat", "1" if enabled else "0")

    async def set_random(self, enabled: bool) -> None:
        await self._command("random", "1" if enabled else "0")

    async def set_volume(self, volume: int) -> None:
        if not 0 <= volume <= 100:
            raise PlayerCommandError("set_volume", "volume must be between 0 and 100")
        await self._command("setvol", str(volume))

    async def update_database(self) -> None:
        await self._command("update")

    async def outputs(self) -> list[OutputInfo]:
        response = await self._command("outputs")
        return _outputs_from_response(response)

    async def queue_entries(self) -> list[PlayerQueueEntry]:
        response = await self._command("playlistinfo")
        return _queue_entries_from_response(response)

    async def queue_clear(self) -> None:
        await self._command("clear")

    async def queue_add(self, song_uri: str) -> int:
        response = await self._command("addid", song_uri)
        song_id = _parse_int(_scalar(response.as_dict().get("Id")))
        if song_id is None or song_id < 0:
            raise PlayerCommandError("addid", "MPD did not return a valid song id")
        return song_id

    async def queue_delete(self, mpd_song_id: int) -> None:
        await self._command("deleteid", str(mpd_song_id))

    async def queue_move(self, mpd_song_id: int, before_mpd_song_id: int | None) -> None:
        async with self._lock:
            response = await self._command_unlocked("playlistinfo")
            queue = _queue_entries_from_response(response)
            source_index = _queue_index(queue, mpd_song_id)
            if before_mpd_song_id is None:
                destination = len(queue) - 1
            else:
                target_index = _queue_index(queue, before_mpd_song_id)
                if target_index == source_index:
                    return
                destination = target_index - 1 if source_index < target_index else target_index
            await self._command_unlocked("moveid", str(mpd_song_id), str(max(destination, 0)))

    async def queue_play(self, mpd_song_id: int) -> None:
        await self._command("playid", str(mpd_song_id))

    async def set_output_enabled(self, output_id: int, enabled: bool) -> None:
        await self._command("enableoutput" if enabled else "disableoutput", str(output_id))

    async def stats(self) -> MPDStats:
        response = await self._command("stats")
        data = response.as_dict()
        return MPDStats(
            songs=_nonnegative_int(_scalar(data.get("songs"))),
            albums=_nonnegative_int(_scalar(data.get("albums"))),
            artists=_nonnegative_int(_scalar(data.get("artists"))),
            db_playtime=_nonnegative_int(_scalar(data.get("db_playtime"))),
            db_update=_nonnegative_int(_scalar(data.get("db_update"))),
            playtime=_nonnegative_int(_scalar(data.get("playtime"))),
            uptime=_nonnegative_int(_scalar(data.get("uptime"))),
        )

    async def database_update_status(self) -> DatabaseUpdateStatus:
        response = await self._command("status")
        job_id = _nonnegative_int(_scalar(response.as_dict().get("updating_db")))
        return DatabaseUpdateStatus(updating=job_id is not None, job_id=job_id)

    async def _command(self, command: str, *args: str) -> MPDResponse:
        async with self._lock:
            return await self._command_unlocked(command, *args)

    async def _command_unlocked(self, command: str, *args: str) -> MPDResponse:
        try:
            await self._ensure_connected()
            return await asyncio.wait_for(
                self._execute(command, *args),
                timeout=self.command_timeout,
            )
        except MPDAckError as exc:
            raise PlayerCommandError(
                command,
                exc.message,
                error_code=exc.error_code,
                command_list_index=exc.command_list_index,
            ) from exc
        except PlayerCommandError:
            raise
        except (asyncio.TimeoutError, TimeoutError) as exc:
            await self.close()
            raise PlayerUnavailable(f"MPD command timed out: {command}") from exc
        except (ConnectionError, OSError, EOFError, UnicodeError, MPDProtocolError) as exc:
            await self.close()
            raise PlayerUnavailable(f"MPD communication failed: {exc}") from exc

    async def _ensure_connected(self) -> None:
        if self._reader is not None and self._writer is not None:
            return
        try:
            reader, writer = await asyncio.wait_for(
                self._connection_factory(self.host, self.port),
                timeout=self.connection_timeout,
            )
            self._reader = reader
            self._writer = writer
            greeting = await asyncio.wait_for(
                reader.readline(), timeout=self.connection_timeout
            )
            _parse_greeting(greeting)
            if self.password is not None:
                try:
                    await asyncio.wait_for(
                        self._execute("password", self.password),
                        timeout=self.command_timeout,
                    )
                except MPDAckError as exc:
                    raise PlayerCommandError(
                        "password",
                        exc.message,
                        error_code=exc.error_code,
                        command_list_index=exc.command_list_index,
                    ) from exc
        except PlayerCommandError:
            await self.close()
            raise
        except (asyncio.TimeoutError, TimeoutError) as exc:
            await self.close()
            raise PlayerUnavailable("MPD connection timed out") from exc
        except (ConnectionError, OSError, EOFError, UnicodeError, MPDProtocolError) as exc:
            await self.close()
            raise PlayerUnavailable(f"MPD connection failed: {exc}") from exc

    async def _execute(self, command: str, *args: str) -> MPDResponse:
        if self._reader is None or self._writer is None:
            raise PlayerUnavailable("MPD is not connected")
        request = " ".join([command, *[quote_argument(arg) for arg in args]]) + "\n"
        self._writer.write(request.encode("utf-8"))
        await self._writer.drain()

        lines: list[str] = []
        while True:
            raw_line = await self._reader.readline()
            if raw_line == b"":
                raise EOFError("MPD closed the connection")
            line = raw_line.decode("utf-8")
            lines.append(line)
            if line.rstrip("\r\n") == "OK" or line.startswith("ACK "):
                return parse_response(lines)


def _parse_greeting(raw_line: bytes) -> str:
    if not raw_line:
        raise EOFError("MPD closed the connection before greeting")
    line = raw_line.decode("utf-8").rstrip("\r\n")
    if not line.startswith("OK MPD "):
        raise MPDProtocolError(f"invalid MPD greeting: {line}")
    return line.removeprefix("OK MPD ")


def _status_from_response(
    response: MPDResponse,
    current_song: MPDResponse | None,
) -> PlayerStatus:
    data = response.as_dict()
    state_raw = _scalar(data.get("state"))
    states = {
        "play": PlayerState.PLAYING,
        "pause": PlayerState.PAUSED,
        "stop": PlayerState.STOPPED,
    }
    try:
        state = states[state_raw or ""]
    except KeyError as exc:
        raise MPDProtocolError(f"unknown MPD player state: {state_raw!r}") from exc

    elapsed = _parse_float(_scalar(data.get("elapsed")))
    duration = _parse_float(_scalar(data.get("duration")))
    if elapsed is None and duration is None:
        time_value = _scalar(data.get("time"))
        if time_value and ":" in time_value:
            elapsed_text, duration_text = time_value.split(":", 1)
            elapsed = _parse_float(elapsed_text)
            duration = _parse_float(duration_text)

    song_position = _parse_int(_scalar(data.get("song")))
    song_id = _parse_int(_scalar(data.get("songid")))
    volume_raw = _parse_int(_scalar(data.get("volume")))
    volume = None if volume_raw is None or volume_raw < 0 else volume_raw

    song_uri = None
    if current_song is not None:
        song_uri = _scalar(current_song.as_dict().get("file"))

    return PlayerStatus(
        state=state,
        song_uri=song_uri,
        song_position=None if song_position is None or song_position < 0 else song_position,
        song_id=None if song_id is None or song_id < 0 else song_id,
        elapsed_seconds=elapsed,
        duration_seconds=duration,
        volume=volume,
        repeat=_parse_bool(_scalar(data.get("repeat"))),
        random=_parse_bool(_scalar(data.get("random"))),
    )


def _outputs_from_response(response: MPDResponse) -> list[OutputInfo]:
    outputs: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for key, value in response.pairs:
        if key == "outputid":
            if current is not None:
                outputs.append(current)
            current = {"id": int(value), "attributes": {}}
        elif current is not None:
            if key == "outputname":
                current["name"] = value
            elif key == "plugin":
                current["plugin"] = value
            elif key == "outputenabled":
                current["enabled"] = value == "1"
            elif key == "attribute" and "=" in value:
                name, attr_value = value.split("=", 1)
                current["attributes"][name] = attr_value
    if current is not None:
        outputs.append(current)
    try:
        return [OutputInfo(**output) for output in outputs]
    except (TypeError, ValueError) as exc:
        raise MPDProtocolError(f"invalid outputs response: {exc}") from exc


def _queue_entries_from_response(response: MPDResponse) -> list[PlayerQueueEntry]:
    entries: list[PlayerQueueEntry] = []
    current: dict[str, Any] = {}
    for key, value in response.pairs:
        if key == "file":
            if current:
                entries.append(PlayerQueueEntry(**current))
            current = {"song_uri": value}
        elif key == "Pos":
            current["position"] = int(value)
        elif key == "Id":
            current["mpd_song_id"] = int(value)
    if current:
        entries.append(PlayerQueueEntry(**current))
    return entries


def _queue_index(entries: list[PlayerQueueEntry], song_id: int) -> int:
    for index, entry in enumerate(entries):
        if entry.mpd_song_id == song_id:
            return index
    raise PlayerCommandError("queue_move", f"MPD song id {song_id} not found")


def _find_song_id(response: MPDResponse, song_uri: str) -> int | None:
    current_uri: str | None = None
    current_id: int | None = None
    for key, value in response.pairs:
        if key == "file":
            if current_uri == song_uri and current_id is not None:
                return current_id
            current_uri = value
            current_id = None
        elif key == "Id":
            current_id = _parse_int(value)
    if current_uri == song_uri:
        return current_id
    return None


def _scalar(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
        return value[0]
    return None


def _nonnegative_int(value: str | None) -> int | None:
    parsed = _parse_int(value)
    return parsed if parsed is not None and parsed >= 0 else None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_bool(value: str | None) -> bool:
    return value == "1"


def _format_number(value: float) -> str:
    return format(value, ".12g")
