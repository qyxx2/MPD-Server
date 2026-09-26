from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
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
from server.app.player.ports import PlayerCommandError, PlayerPort

NEGATIVE_COMMAND_PROBE = "__mpd_server_unsupported_probe__"
ACK_ERROR_PROBE_COMMAND = "playid"
ACK_ERROR_PROBE_ARG = "2147483647"

ConnectionFactory = Callable[
    [str, int], Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]]
]

OPERATION_COMMANDS: dict[str, frozenset[str]] = {
    "status": frozenset({"status", "currentsong"}),
    "play": frozenset({"play"}),
    "play_song": frozenset({"playlistinfo", "playid"}),
    "pause": frozenset({"pause"}),
    "stop": frozenset({"stop"}),
    "next": frozenset({"next"}),
    "previous": frozenset({"previous"}),
    "seek": frozenset({"seekcur"}),
    "set_repeat": frozenset({"repeat"}),
    "set_random": frozenset({"random"}),
    "set_volume": frozenset({"setvol"}),
    "update_database": frozenset({"update"}),
    "outputs": frozenset({"outputs"}),
    "queue_entries": frozenset({"playlistinfo"}),
    "queue_clear": frozenset({"clear"}),
    "queue_add": frozenset({"addid", "deleteid"}),
    "queue_delete": frozenset({"addid", "deleteid"}),
    "queue_move": frozenset({"moveid"}),
    "queue_play": frozenset({"playid"}),
    "set_output_enabled": frozenset({"outputs", "enableoutput", "disableoutput"}),
    "stats": frozenset({"stats"}),
    "database_update_status": frozenset({"status", "update"}),
}


RUNTIME_VERIFIED_OPERATIONS = frozenset(
    {
        "queue_entries",
        "queue_clear",
        "queue_add",
        "queue_delete",
        "queue_move",
        "queue_play",
        "set_output_enabled",
        "stats",
        "database_update_status",
    }
)


@dataclass(frozen=True)
class ProbeError:
    command: str
    outcome: str
    error_code: int | None
    command_list_index: int | None
    message: str


@dataclass(frozen=True)
class MPDCapabilities:
    version: str | None
    commands: frozenset[str]
    not_commands: frozenset[str]
    status_fields: frozenset[str]
    stats: dict[str, str]
    stats_fields: frozenset[str]
    outputs: tuple[OutputInfo, ...]
    update_supported: bool
    update_response: dict[str, str]
    update_status_fields: frozenset[str]
    verified_operations: frozenset[str]
    errors: tuple[ProbeError, ...] = ()

    @classmethod
    def from_commands(
        cls, commands: set[str] | frozenset[str]
    ) -> MPDCapabilities:
        return cls(
            version=None,
            commands=frozenset(commands),
            not_commands=frozenset(),
            status_fields=frozenset(),
            stats={},
            stats_fields=frozenset(),
            outputs=(),
            update_supported="update" in commands,
            update_response={},
            update_status_fields=frozenset(),
            verified_operations=frozenset(),
        )

    def missing_commands(self, operation: str) -> frozenset[str]:
        required = OPERATION_COMMANDS[operation]
        return required.difference(self.commands)

    def supports_operation(self, operation: str) -> bool:
        if self.missing_commands(operation):
            return False
        if operation in RUNTIME_VERIFIED_OPERATIONS:
            return operation in self.verified_operations
        return True


class VerifiedPlayerPort(PlayerPort):
    """PlayerPort wrapper that blocks operations not verified on the target MPD."""

    def __init__(self, delegate: PlayerPort, capabilities: MPDCapabilities) -> None:
        self._delegate = delegate
        self.capabilities = capabilities

    def _require(self, operation: str) -> None:
        if (
            operation in RUNTIME_VERIFIED_OPERATIONS
            and operation not in self.capabilities.verified_operations
        ):
            raise PlayerCommandError(
                operation,
                f"runtime behavior not verified for {operation}",
            )
        missing = self.capabilities.missing_commands(operation)
        if missing:
            commands = ", ".join(sorted(missing))
            raise PlayerCommandError(
                operation,
                f"MPD capability not verified for {operation}: missing {commands}",
            )

    async def status(self) -> PlayerStatus:
        self._require("status")
        return await self._delegate.status()

    async def play(self, song_uri: str | None = None) -> None:
        self._require("play_song" if song_uri is not None else "play")
        await self._delegate.play(song_uri)

    async def pause(self) -> None:
        self._require("pause")
        await self._delegate.pause()

    async def stop(self) -> None:
        self._require("stop")
        await self._delegate.stop()

    async def next(self) -> None:
        self._require("next")
        await self._delegate.next()

    async def previous(self) -> None:
        self._require("previous")
        await self._delegate.previous()

    async def seek(self, seconds: float) -> None:
        self._require("seek")
        await self._delegate.seek(seconds)

    async def set_repeat(self, enabled: bool) -> None:
        self._require("set_repeat")
        await self._delegate.set_repeat(enabled)

    async def set_random(self, enabled: bool) -> None:
        self._require("set_random")
        await self._delegate.set_random(enabled)

    async def set_volume(self, volume: int) -> None:
        self._require("set_volume")
        await self._delegate.set_volume(volume)

    async def update_database(self) -> None:
        self._require("update_database")
        await self._delegate.update_database()

    async def outputs(self) -> list[OutputInfo]:
        self._require("outputs")
        return await self._delegate.outputs()

    async def queue_entries(self) -> list[PlayerQueueEntry]:
        self._require("queue_entries")
        return await self._delegate.queue_entries()

    async def queue_clear(self) -> None:
        self._require("queue_clear")
        await self._delegate.queue_clear()

    async def queue_add(self, song_uri: str) -> int:
        self._require("queue_add")
        return await self._delegate.queue_add(song_uri)

    async def queue_delete(self, mpd_song_id: int) -> None:
        self._require("queue_delete")
        await self._delegate.queue_delete(mpd_song_id)

    async def queue_move(self, mpd_song_id: int, before_mpd_song_id: int | None) -> None:
        self._require("queue_move")
        await self._delegate.queue_move(mpd_song_id, before_mpd_song_id)

    async def queue_play(self, mpd_song_id: int) -> None:
        self._require("queue_play")
        await self._delegate.queue_play(mpd_song_id)

    async def set_output_enabled(self, output_id: int, enabled: bool) -> None:
        self._require("set_output_enabled")
        await self._delegate.set_output_enabled(output_id, enabled)

    async def stats(self) -> MPDStats:
        self._require("stats")
        return await self._delegate.stats()

    async def database_update_status(self) -> DatabaseUpdateStatus:
        self._require("database_update_status")
        return await self._delegate.database_update_status()


class CapabilityProbe:
    """Probe MPD commands and runtime fields, with a bounded update-path check."""

    def __init__(
        self,
        host: str,
        port: int = 6600,
        password: str | None = None,
        *,
        connection_timeout: float = 3.0,
        command_timeout: float = 5.0,
        update_probe_path: str = "__mpd_server_capability_probe__",
        connection_factory: ConnectionFactory | None = None,
        probe_transport: bool = False,
        probe_song_uri: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.connection_timeout = connection_timeout
        self.command_timeout = command_timeout
        self.update_probe_path = update_probe_path
        self.probe_transport = probe_transport
        self.probe_song_uri = probe_song_uri
        self._connection_factory = connection_factory or asyncio.open_connection
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self.__version = ""

    async def run(self) -> MPDCapabilities:
        await self._connect()
        try:
            commands_response = await self._execute("commands")
            commands = frozenset(
                value for key, value in commands_response.pairs if key == "command"
            )
            errors: list[ProbeError] = []

            not_commands_response, error = await self._probe_command("notcommands")
            if error is not None:
                errors.append(error)
            not_commands = _command_names(not_commands_response)

            status_response = await self._safe_execute("status", commands, "status", errors)
            outputs_response = await self._safe_execute("outputs", commands, "outputs", errors)
            stats_response = await self._safe_execute("stats", commands, "stats", errors)
            stats = _scalar_map(stats_response.as_dict())
            verified_operations: set[str] = set()

            if "playlistinfo" in commands:
                _, probe_error = await self._probe_command("playlistinfo")
                if probe_error is None:
                    verified_operations.add("queue_entries")
                else:
                    errors.append(probe_error)
            if "stats" in commands and stats_response.pairs:
                verified_operations.add("stats")

            update_supported = "update" in commands
            update_response: dict[str, str] = {}
            update_status_fields: frozenset[str] = frozenset()
            if update_supported:
                response, error = await self._probe_command(
                    "update", self.update_probe_path
                )
                if response is not None:
                    update_response = _scalar_map(response.as_dict())
                if error is not None:
                    errors.append(error)
            if self.probe_transport:
                verified_operations.update(
                    await self._probe_transport_runtime(commands, errors)
                )

            _, error = await self._probe_fresh_command(NEGATIVE_COMMAND_PROBE)
            if error is not None:
                errors.append(error)
            _, error = await self._probe_fresh_command(
                ACK_ERROR_PROBE_COMMAND, ACK_ERROR_PROBE_ARG
            )
            if error is not None:
                errors.append(error)

            return MPDCapabilities(
                version=self.__version,
                commands=commands,
                not_commands=not_commands,
                status_fields=frozenset(key for key, _ in status_response.pairs),
                stats=stats,
                stats_fields=frozenset(stats),
                outputs=tuple(_parse_outputs(outputs_response)),
                update_supported=update_supported,
                update_response=update_response,
                update_status_fields=update_status_fields,
                verified_operations=frozenset(verified_operations),
                errors=tuple(errors),
            )
        finally:
            await self.close()

    async def _probe_transport_runtime(
        self,
        commands: frozenset[str],
        errors: list[ProbeError],
    ) -> set[str]:
        verified: set[str] = set()
        snapshot_queue: list[PlayerQueueEntry] = []
        snapshot_status: PlayerStatus | None = None
        snapshot_outputs: list[OutputInfo] = []
        queue_cleared = False
        mutated_output_ids: set[int] = set()

        try:
            if "playlistinfo" in commands:
                snapshot_queue = _queue_entries_from_response(await self._execute("playlistinfo"))
                verified.add("queue_entries")
            if "status" in commands:
                status_response = await self._execute("status")
                current = None
                song_position = _parse_int(_scalar(status_response.as_dict().get("song")))
                if song_position is not None and song_position >= 0 and "currentsong" in commands:
                    current = await self._execute("currentsong")
                snapshot_status = _status_from_responses(status_response, current)
            if "stats" in commands:
                stats = _stats_from_response(await self._execute("stats"))
                if stats is not None:
                    verified.add("stats")

            probe_uri = self.probe_song_uri or (snapshot_queue[0].song_uri if snapshot_queue else None)
            if probe_uri is not None and {"addid", "deleteid"}.issubset(commands):
                added = await self._execute("addid", probe_uri)
                added_id = _required_int(_scalar(added.as_dict().get("Id")), "addid.Id")
                await self._execute("deleteid", str(added_id))
                verified.update({"queue_add", "queue_delete"})

            if len(snapshot_queue) >= 2 and "moveid" in commands:
                last = snapshot_queue[-1].mpd_song_id
                await self._execute("moveid", str(last), "0")
                await self._execute("moveid", str(last), str(len(snapshot_queue) - 1))
                verified.add("queue_move")

            if snapshot_queue and "playid" in commands:
                await self._execute("playid", str(snapshot_queue[0].mpd_song_id))
                verified.add("queue_play")

            if "clear" in commands and (not snapshot_queue or "addid" in commands):
                await self._execute("clear")
                queue_cleared = True
                verified.add("queue_clear")

            if "outputs" in commands and {"enableoutput", "disableoutput"}.issubset(commands):
                snapshot_outputs = _parse_outputs(await self._execute("outputs"))
                target = next(
                    (output for output in snapshot_outputs if output.plugin == "httpd" and not output.enabled),
                    None,
                )
                if target is not None:
                    await self._execute("enableoutput", str(target.id))
                    mutated_output_ids.add(target.id)
                    enabled = next(
                        output for output in _parse_outputs(await self._execute("outputs"))
                        if output.id == target.id
                    )
                    await self._execute("disableoutput", str(target.id))
                    disabled = next(
                        output for output in _parse_outputs(await self._execute("outputs"))
                        if output.id == target.id
                    )
                    if enabled.enabled and not disabled.enabled:
                        verified.add("set_output_enabled")

            if "update" in commands and "status" in commands:
                post_update = await self._execute("status")
                if "updating_db" in post_update.as_dict():
                    verified.add("database_update_status")
        except (MPDAckError, MPDProtocolError, EOFError, ConnectionError, OSError, UnicodeError) as exc:
            errors.append(_probe_error_from_exception(exc, "transport_probe"))
        finally:
            try:
                if queue_cleared:
                    await self._execute("clear")
                    for entry in snapshot_queue:
                        await self._execute("addid", entry.song_uri)
                if snapshot_status is not None:
                    if "repeat" in commands:
                        await self._execute("repeat", "1" if snapshot_status.repeat else "0")
                    if "random" in commands:
                        await self._execute("random", "1" if snapshot_status.random else "0")
                    if snapshot_queue:
                        if snapshot_status.state in {PlayerState.PLAYING, PlayerState.PAUSED} and "playid" in commands:
                            restored_queue = _queue_entries_from_response(
                                await self._execute("playlistinfo")
                            )
                            if snapshot_status.song_position is not None and snapshot_status.song_position < len(restored_queue):
                                target = restored_queue[snapshot_status.song_position]
                                await self._execute("playid", str(target.mpd_song_id))
                                if snapshot_status.state is PlayerState.PAUSED and "pause" in commands:
                                    await self._execute("pause", "1")
                                if snapshot_status.elapsed_seconds is not None and "seekcur" in commands:
                                    await self._execute("seekcur", _format_number(snapshot_status.elapsed_seconds))
                            else:
                                if "stop" in commands:
                                    await self._execute("stop")
                        elif "stop" in commands:
                            await self._execute("stop")
                    elif "stop" in commands:
                        await self._execute("stop")
                if snapshot_outputs:
                    for output in snapshot_outputs:
                        if output.id in mutated_output_ids:
                            command = "enableoutput" if output.enabled else "disableoutput"
                            await self._execute(command, str(output.id))
            except (MPDAckError, MPDProtocolError, EOFError, ConnectionError, OSError, UnicodeError) as exc:
                errors.append(_probe_error_from_exception(exc, "transport_restore"))
        return verified

    async def _safe_execute(
        self,
        command: str,
        commands: frozenset[str],
        required_command: str,
        errors: list[ProbeError],
    ) -> MPDResponse:
        if required_command not in commands:
            return MPDResponse(())
        response, error = await self._probe_command(command)
        if error is not None:
            errors.append(error)
            return MPDResponse(())
        return response or MPDResponse(())

    async def _probe_command(
        self, command: str, *args: str
    ) -> tuple[MPDResponse | None, ProbeError | None]:
        try:
            return await self._execute(command, *args), None
        except MPDAckError as exc:
            return None, ProbeError(
                command=exc.command,
                outcome="ack",
                error_code=exc.error_code,
                command_list_index=exc.command_list_index,
                message=exc.message,
            )
        except EOFError as exc:
            await self.close()
            return None, ProbeError(
                command=command,
                outcome="connection_closed",
                error_code=None,
                command_list_index=None,
                message=str(exc),
            )
        except (asyncio.TimeoutError, TimeoutError) as exc:
            await self.close()
            return None, ProbeError(
                command=command,
                outcome="timeout",
                error_code=None,
                command_list_index=None,
                message=str(exc),
            )
        except (ConnectionError, OSError, UnicodeError, MPDProtocolError) as exc:
            await self.close()
            return None, ProbeError(
                command=command,
                outcome="communication_error",
                error_code=None,
                command_list_index=None,
                message=str(exc),
            )

    async def _probe_fresh_command(
        self, command: str, *args: str
    ) -> tuple[MPDResponse | None, ProbeError | None]:
        await self.close()
        try:
            await self._connect()
            return await self._probe_command(command, *args)
        except (asyncio.TimeoutError, TimeoutError) as exc:
            return None, ProbeError(
                command=command,
                outcome="timeout",
                error_code=None,
                command_list_index=None,
                message=str(exc),
            )
        except (EOFError, ConnectionError, OSError, UnicodeError, MPDProtocolError, MPDAckError) as exc:
            return None, ProbeError(
                command=command,
                outcome="connection_error",
                error_code=getattr(exc, "error_code", None),
                command_list_index=getattr(exc, "command_list_index", None),
                message=str(exc),
            )
        finally:
            await self.close()

    async def _connect(self) -> None:
        reader, writer = await asyncio.wait_for(
            self._connection_factory(self.host, self.port),
            timeout=self.connection_timeout,
        )
        self._reader, self._writer = reader, writer
        greeting = await asyncio.wait_for(
            reader.readline(), timeout=self.connection_timeout
        )
        line = greeting.decode("utf-8").rstrip("\r\n")
        if not line.startswith("OK MPD "):
            await self.close()
            raise MPDProtocolError(f"invalid MPD greeting: {line}")
        self.__version = line.removeprefix("OK MPD ")
        if self.password is not None:
            await self._execute("password", self.password)

    async def _execute(self, command: str, *args: str) -> MPDResponse:
        if self._reader is None or self._writer is None:
            raise MPDProtocolError("probe is not connected")
        request = " ".join(
            [command, *[quote_argument(arg) for arg in args]]
        ) + "\n"
        self._writer.write(request.encode("utf-8"))
        await self._writer.drain()
        lines: list[str] = []
        while True:
            raw = await asyncio.wait_for(
                self._reader.readline(), timeout=self.command_timeout
            )
            if raw == b"":
                raise EOFError("MPD closed the connection")
            line = raw.decode("utf-8")
            lines.append(line)
            if line.rstrip("\r\n") == "OK" or line.startswith("ACK "):
                return parse_response(lines)

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


def _command_names(response: MPDResponse | None) -> frozenset[str]:
    if response is None:
        return frozenset()
    return frozenset(
        value
        for key, value in response.pairs
        if key in {"command", "notcommand"}
    )


def _scalar_map(data: dict[str, str | list[str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in data.items():
        result[key] = value if isinstance(value, str) else "\\n".join(value)
    return result


def _parse_outputs(response: MPDResponse) -> list[OutputInfo]:
    outputs: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for key, value in response.pairs:
        if key == "outputid":
            if current is not None:
                outputs.append(current)
            current = {"id": int(value), "name": "", "plugin": "", "enabled": False, "attributes": {}}
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
    return [OutputInfo(**output) for output in outputs]


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


def _stats_from_response(response: MPDResponse) -> MPDStats | None:
    data = response.as_dict()
    if not data:
        return None
    return MPDStats(
        songs=_parse_int(_scalar(data.get("songs"))),
        albums=_parse_int(_scalar(data.get("albums"))),
        artists=_parse_int(_scalar(data.get("artists"))),
        db_playtime=_parse_int(_scalar(data.get("db_playtime"))),
        db_update=_parse_int(_scalar(data.get("db_update"))),
        playtime=_parse_int(_scalar(data.get("playtime"))),
        uptime=_parse_int(_scalar(data.get("uptime"))),
    )


def _status_from_responses(response: MPDResponse, current_song: MPDResponse | None) -> PlayerStatus:
    data = response.as_dict()
    state_raw = _scalar(data.get("state"))
    states = {"play": PlayerState.PLAYING, "pause": PlayerState.PAUSED, "stop": PlayerState.STOPPED}
    if state_raw not in states:
        raise MPDProtocolError(f"unknown MPD player state: {state_raw!r}")
    elapsed = _parse_float(_scalar(data.get("elapsed")))
    duration = _parse_float(_scalar(data.get("duration")))
    if elapsed is None or duration is None:
        time_value = _scalar(data.get("time"))
        if time_value and ":" in time_value:
            elapsed_text, duration_text = time_value.split(":", 1)
            elapsed = elapsed if elapsed is not None else _parse_float(elapsed_text)
            duration = duration if duration is not None else _parse_float(duration_text)
    song_position = _parse_int(_scalar(data.get("song")))
    song_id = _parse_int(_scalar(data.get("songid")))
    volume_raw = _parse_int(_scalar(data.get("volume")))
    return PlayerStatus(
        state=states[state_raw],
        song_uri=_scalar(current_song.as_dict().get("file")) if current_song else None,
        song_position=None if song_position is None or song_position < 0 else song_position,
        song_id=None if song_id is None or song_id < 0 else song_id,
        elapsed_seconds=elapsed,
        duration_seconds=duration,
        volume=None if volume_raw is None or volume_raw < 0 else volume_raw,
        repeat=_parse_bool(_scalar(data.get("repeat"))),
        random=_parse_bool(_scalar(data.get("random"))),
    )


def _scalar(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
        return value[0]
    return None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _required_int(value: str | None, field: str) -> int:
    parsed = _parse_int(value)
    if parsed is None:
        raise MPDProtocolError(f"missing integer field: {field}")
    return parsed


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


def _probe_error_from_exception(exc: BaseException, command: str) -> ProbeError:
    return ProbeError(
        command=getattr(exc, "command", command),
        outcome="ack" if isinstance(exc, MPDAckError) else "communication_error",
        error_code=getattr(exc, "error_code", None),
        command_list_index=getattr(exc, "command_list_index", None),
        message=str(exc),
    )


def _json_result(result: MPDCapabilities) -> dict[str, Any]:
    data = asdict(result)
    data["commands"] = sorted(result.commands)
    data["not_commands"] = sorted(result.not_commands)
    data["status_fields"] = sorted(result.status_fields)
    data["stats_fields"] = sorted(result.stats_fields)
    data["update_status_fields"] = sorted(result.update_status_fields)
    data["verified_operations"] = sorted(result.verified_operations)
    data["outputs"] = [output.model_dump() for output in result.outputs]
    data["errors"] = [asdict(error) for error in result.errors]
    return data


async def _probe_from_args(args: argparse.Namespace) -> int:
    result = await CapabilityProbe(
        args.host,
        port=args.port,
        password=args.password,
        connection_timeout=args.connection_timeout,
        command_timeout=args.command_timeout,
        update_probe_path=args.update_probe_path,
        probe_transport=args.probe_transport,
        probe_song_uri=args.probe_song_uri,
    ).run()
    print(json.dumps(_json_result(result), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe an MPD endpoint and record verified capabilities.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=6600)
    parser.add_argument("--password")
    parser.add_argument("--connection-timeout", type=float, default=3.0)
    parser.add_argument("--command-timeout", type=float, default=5.0)
    parser.add_argument("--update-probe-path", default="__mpd_server_capability_probe__")
    parser.add_argument("--probe-transport", action="store_true")
    parser.add_argument("--probe-song-uri")
    args = parser.parse_args()
    return asyncio.run(_probe_from_args(args))


if __name__ == "__main__":
    raise SystemExit(main())
