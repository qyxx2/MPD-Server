from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from server.app.logging_config import log_event
from server.app.player.models import (
    DatabaseUpdateStatus,
    ExecutionSample,
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
from server.app.player.music_uri import MusicUriMapper
from server.app.player.ports import PlayerCommandError, PlayerPort, PlayerUnavailable

logger = logging.getLogger(__name__)
_CONTROL_COMMANDS = frozenset({
    'play', 'playid', 'pause', 'stop', 'next', 'previous', 'seekcur', 'repeat',
    'random', 'setvol', 'update', 'clear', 'addid', 'deleteid', 'moveid',
    'enableoutput', 'disableoutput',
})

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
        uri_mapper: MusicUriMapper | None = None,
        omit_song_tags: bool = False,
    ) -> None:
        self.uri_mapper = uri_mapper
        self.host = host
        self.port = port
        self.password = password
        self.connection_timeout = connection_timeout
        self.command_timeout = command_timeout
        self._connection_factory = connection_factory or asyncio.open_connection
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connection_epoch: str | None = None
        # Opt in only where consumers use file/Id/Pos and status duration.
        # Capability probes and other general-purpose clients keep full tags.
        self._omit_song_tags = omit_song_tags
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        writer = self._writer
        self._reader = None
        self._writer = None
        self._connection_epoch = None
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
            return _status_from_response(
                response, self._local_response(current, "status") if current else None,
            )

    async def read_execution_sample(self) -> ExecutionSample:
        async with self._lock:
            for _ in range(2):
                before = await self._command_unlocked("status")
                connection_epoch = self._connection_epoch
                playlist = await self._command_unlocked("playlistinfo")
                after = await self._command_unlocked("status")
                if connection_epoch != self._connection_epoch:
                    continue
                sample = _execution_sample_from_responses(
                    connection_epoch,
                    before,
                    self._local_response(playlist, "read_execution_sample"),
                    after,
                )
                if sample is not None:
                    return sample
        raise PlayerCommandError(
            "read_execution_sample",
            "inconsistent execution sample",
        )

    async def play(self, song_uri: str | None = None) -> None:
        if song_uri is None:
            await self._command("play")
            return
        raw_uri = self._mpd_uri(song_uri, "play")
        async with self._lock:
            playlist = await self._command_unlocked("playlistinfo")
            self._local_response(playlist, "play")
            song_id = _find_song_id(playlist, raw_uri)
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

    async def has_library_uri(self, song_uri: str) -> bool:
        raw = self._mpd_uri(song_uri, "has_library_uri")
        response = await self._command("find", "file", raw)
        return any(key == "file" and value == raw for key, value in response.pairs)

    async def update_database(self) -> None:
        await self._command("update")

    async def outputs(self) -> list[OutputInfo]:
        response = await self._command("outputs")
        return _outputs_from_response(response)

    async def queue_entries(self) -> list[PlayerQueueEntry]:
        response = await self._command("playlistinfo")
        return _queue_entries_from_response(self._local_response(response, "queue_entries"))

    async def queue_clear(self) -> None:
        await self._command("clear")

    async def queue_add(self, song_uri: str) -> int:
        response = await self._command("addid", self._mpd_uri(song_uri, "queue_add"))
        song_id = _parse_int(_scalar(response.as_dict().get("Id")))
        if song_id is None or song_id < 0:
            raise PlayerCommandError("addid", "MPD did not return a valid song id")
        return song_id

    async def queue_delete(self, mpd_song_id: int) -> None:
        await self._command("deleteid", str(mpd_song_id))

    async def queue_move(self, mpd_song_id: int, before_mpd_song_id: int | None) -> None:
        async with self._lock:
            response = await self._command_unlocked("playlistinfo")
            queue = _queue_entries_from_response(self._local_response(response, "queue_move"))
            source_index = _queue_index(queue, mpd_song_id)
            if before_mpd_song_id is None:
                destination = len(queue) - 1
            else:
                target_index = _queue_index(queue, before_mpd_song_id)
                if target_index == source_index:
                    return
                destination = target_index - 1 if source_index < target_index else target_index
            await self._command_unlocked("moveid", str(mpd_song_id), str(max(destination, 0)))

    async def queue_play(
        self, mpd_song_id: int, *, expected_connection_epoch: str | None = None,
    ) -> None:
        async with self._lock:
            await self._command_unlocked(
                "playid", str(mpd_song_id), expected_connection_epoch=expected_connection_epoch,
            )

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

    def _mpd_uri(self, local_uri: str, command: str) -> str:
        if self.uri_mapper is None:
            return local_uri
        try:
            return self.uri_mapper.to_mpd(local_uri)
        except ValueError as exc:
            logger.warning("MPD URI mapping rejected direction=local_to_mpd command=%s", command)
            raise PlayerCommandError(command, "invalid local music URI mapping") from exc

    def _local_response(self, response: MPDResponse, command: str) -> MPDResponse:
        if self.uri_mapper is None:
            return response
        try:
            return MPDResponse(tuple(
                (key, self.uri_mapper.to_local(value) if key == "file" else value)
                for key, value in response.pairs
            ))
        except ValueError as exc:
            logger.warning("MPD URI mapping rejected direction=mpd_to_local command=%s", command)
            raise PlayerCommandError(command, "invalid raw MPD URI mapping") from exc

    async def _command(self, command: str, *args: str) -> MPDResponse:
        async with self._lock:
            return await self._command_unlocked(command, *args)

    def _log_failure(self, command: str, code: str) -> None:
        signature = (command, code)
        # Only repetitive read observations are noise; each control attempt matters.
        if command in _CONTROL_COMMANDS or signature != getattr(self, '_last_log_failure', None):
            log_event('mpd_command_failed', level=30, command=command, error_code=code)
            self._last_log_failure = signature

    async def _command_unlocked(
        self, command: str, *args: str, expected_connection_epoch: str | None = None,
    ) -> MPDResponse:
        try:
            await self._ensure_connected()
            result = await asyncio.wait_for(
                (self._execute(command, *args) if expected_connection_epoch is None else
                 self._execute(command, *args, expected_connection_epoch=expected_connection_epoch)),
                timeout=self.command_timeout,
            )
            self._last_log_failure = None
            if command in _CONTROL_COMMANDS:
                log_event('mpd_control_accepted', command=command)
            return result
        except MPDAckError as exc:
            self._log_failure(command, 'PLAYER_COMMAND_ERROR')
            raise PlayerCommandError(
                command,
                exc.message,
                error_code=exc.error_code,
                command_list_index=exc.command_list_index,
            ) from exc
        except PlayerUnavailable:
            self._log_failure(command, 'PLAYER_UNAVAILABLE')
            raise
        except PlayerCommandError:
            self._log_failure(command, 'PLAYER_COMMAND_ERROR')
            raise
        except asyncio.CancelledError:
            # An interrupted response cannot be used by the next command.
            # Abandon transport only; cancellation never sends player Stop.
            await self.close()
            raise
        except (asyncio.TimeoutError, TimeoutError) as exc:
            self._log_failure(command, 'PLAYER_TIMEOUT')
            await self.close()
            raise PlayerUnavailable(f"MPD command timed out: {command}") from exc
        except (ConnectionError, OSError, EOFError, UnicodeError, MPDProtocolError) as exc:
            self._log_failure(command, 'PLAYER_UNAVAILABLE')
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
            if self._omit_song_tags:
                try:
                    await asyncio.wait_for(
                        self._execute("tagtypes", "clear"), timeout=self.command_timeout,
                    )
                    tags = await asyncio.wait_for(
                        self._execute("tagtypes"), timeout=self.command_timeout,
                    )
                    if tags.pairs:
                        raise MPDProtocolError("MPD song tag filter was not applied")
                except (TimeoutError, ConnectionError, OSError, EOFError,
                        UnicodeError, MPDProtocolError):
                    # No application command has been sent on this connection.
                    # Discard even a partially configured mask and reconnect with
                    # the default full response. Do not repeatedly probe a server
                    # that rejects, ignores or cannot verify this optional setting.
                    self._omit_song_tags = False
                    await self.close()
                    log_event('mpd_song_tag_filter_fallback', level=30)
                    await self._ensure_connected()
                    return
            self._connection_epoch = uuid4().hex
            log_event('mpd_connected')
        except PlayerCommandError:
            await self.close()
            raise
        except (asyncio.TimeoutError, TimeoutError) as exc:
            await self.close()
            raise PlayerUnavailable("MPD connection timed out") from exc
        except (ConnectionError, OSError, EOFError, UnicodeError, MPDProtocolError) as exc:
            await self.close()
            raise PlayerUnavailable(f"MPD connection failed: {exc}") from exc

    async def _execute(
        self, command: str, *args: str, expected_connection_epoch: str | None = None,
    ) -> MPDResponse:
        # Check in the actual send task, after any reconnect and before write.
        # There is no await between this fence and writing the command bytes.
        if expected_connection_epoch is not None and expected_connection_epoch != self._connection_epoch:
            raise PlayerUnavailable("MPD connection changed before playid")
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


def _execution_sample_from_responses(
    connection_epoch: str | None,
    before: MPDResponse,
    playlist: MPDResponse,
    after: MPDResponse,
) -> ExecutionSample | None:
    if connection_epoch is None:
        return None
    before_data = before.as_dict()
    after_data = after.as_dict()
    stable_fields = ("partition", "playlist", "playlistlength", "song", "songid", "state")
    if any(_scalar(before_data.get(key)) != _scalar(after_data.get(key)) for key in stable_fields):
        return None

    partition = _scalar(after_data.get("partition"))
    playlist_version = _nonnegative_int(_scalar(after_data.get("playlist")))
    playlist_length = _nonnegative_int(_scalar(after_data.get("playlistlength")))
    single = _scalar(after_data.get("single"))
    consume_raw = _scalar(after_data.get("consume"))
    if (
        not partition
        or playlist_version is None
        or playlist_length is None
        or single is None
        or consume_raw not in {"0", "1"}
    ):
        return None

    try:
        entries = tuple(_queue_entries_from_response(playlist))
    except (TypeError, ValueError):
        return None
    if playlist_length != len(entries):
        return None
    if [entry.position for entry in entries] != list(range(len(entries))):
        return None
    if len({entry.mpd_song_id for entry in entries}) != len(entries):
        return None

    status = _status_from_response(after, None)
    if (status.song_position is None) != (status.song_id is None):
        return None
    if status.song_position is not None:
        if status.song_position >= len(entries):
            return None
        current_entry = entries[status.song_position]
        if status.song_id != current_entry.mpd_song_id:
            return None
        status = status.model_copy(update={"song_uri": current_entry.song_uri})

    error = _scalar(after_data.get("error")) or None
    return ExecutionSample(
        connection_epoch=connection_epoch,
        partition=partition,
        playlist_version=playlist_version,
        status=status,
        entries=entries,
        single=single,
        consume=consume_raw == "1",
        error=error,
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
