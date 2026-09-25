from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable

from server.app.player.models import OutputInfo, PlayerStatus
from server.app.player.mpd_protocol import (
    MPDAckError,
    MPDProtocolError,
    MPDResponse,
    parse_response,
    quote_argument,
)
from server.app.player.ports import PlayerCommandError, PlayerPort

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
}


@dataclass(frozen=True)
class ProbeError:
    command: str
    error_code: int | None
    command_list_index: int | None
    message: str


@dataclass(frozen=True)
class MPDCapabilities:
    version: str | None
    commands: frozenset[str]
    status_fields: frozenset[str]
    stats: dict[str, str]
    outputs: tuple[OutputInfo, ...]
    update_supported: bool
    update_response: dict[str, str]
    errors: tuple[ProbeError, ...] = ()

    @classmethod
    def from_commands(
        cls, commands: set[str] | frozenset[str]
    ) -> MPDCapabilities:
        return cls(
            version=None,
            commands=frozenset(commands),
            status_fields=frozenset(),
            stats={},
            outputs=(),
            update_supported="update" in commands,
            update_response={},
        )

    def missing_commands(self, operation: str) -> frozenset[str]:
        required = OPERATION_COMMANDS[operation]
        return required.difference(self.commands)

    def supports_operation(self, operation: str) -> bool:
        return not self.missing_commands(operation)


class VerifiedPlayerPort(PlayerPort):
    """PlayerPort wrapper that blocks operations not verified on the target MPD."""

    def __init__(self, delegate: PlayerPort, capabilities: MPDCapabilities) -> None:
        self._delegate = delegate
        self.capabilities = capabilities

    def _require(self, operation: str) -> None:
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
    ) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.connection_timeout = connection_timeout
        self.command_timeout = command_timeout
        self.update_probe_path = update_probe_path
        self._connection_factory = connection_factory or asyncio.open_connection
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self.__version = ""

    async def run(self) -> MPDCapabilities:
        await self._connect()
        try:
            commands_response = await self._execute("commands")
            commands = frozenset(
                value
                for key, value in commands_response.pairs
                if key == "command"
            )

            status = await self._safe_execute("status", commands, "status")
            outputs_response = await self._safe_execute(
                "outputs", commands, "outputs"
            )
            stats_response = await self._safe_execute("stats", commands, "stats")

            errors: list[ProbeError] = []
            update_supported = "update" in commands
            update_response: dict[str, str] = {}
            if update_supported:
                response, error = await self._probe_command(
                    "update", self.update_probe_path
                )
                if response is not None:
                    update_response = _scalar_map(response.as_dict())
                if error is not None:
                    errors.append(error)

            _, error = await self._probe_command(
                "__mpd_server_unsupported_probe__"
            )
            if error is not None:
                errors.append(error)

            return MPDCapabilities(
                version=self.__version,
                commands=commands,
                status_fields=frozenset(key for key, _ in status.pairs),
                stats=_scalar_map(stats_response.as_dict()),
                outputs=tuple(_parse_outputs(outputs_response)),
                update_supported=update_supported,
                update_response=update_response,
                errors=tuple(errors),
            )
        finally:
            await self.close()

    async def _safe_execute(
        self,
        command: str,
        commands: frozenset[str],
        required_command: str,
    ) -> MPDResponse:
        if required_command not in commands:
            return MPDResponse(())
        response, error = await self._probe_command(command)
        if error is not None:
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
                error_code=exc.error_code,
                command_list_index=exc.command_list_index,
                message=exc.message,
            )

    async def _connect(self) -> None:
        reader, writer = await asyncio.wait_for(
            self._connection_factory(self.host, self.port),
            timeout=self.connection_timeout,
        )
        self._reader, self._writer = reader, writer
        greeting = await asyncio.wait_for(
            reader.readline(), timeout=self.connection_timeout
        )
        line = greeting.decode("utf-8").rstrip("
")
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
        ) + "
"
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
            if line.rstrip("
") == "OK" or line.startswith("ACK "):
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


def _scalar_map(data: dict[str, str | list[str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = value
        elif isinstance(value, list):
            result[key] = "
".join(value)
    return result


def _parse_outputs(response: MPDResponse) -> list[OutputInfo]:
    outputs: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for key, value in response.pairs:
        if key == "outputid":
            if current is not None:
                outputs.append(current)
            current = {
                "id": int(value),
                "name": "",
                "plugin": "",
                "enabled": False,
                "attributes": {},
            }
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


def _json_result(result: MPDCapabilities) -> dict[str, Any]:
    data = asdict(result)
    data["commands"] = sorted(result.commands)
    data["status_fields"] = sorted(result.status_fields)
    data["outputs"] = [output.model_dump() for output in result.outputs]
    data["errors"] = [asdict(error) for error in result.errors]
    return data


async def _probe_from_args(args: argparse.Namespace) -> int:
    probe = CapabilityProbe(
        args.host,
        port=args.port,
        password=args.password,
        connection_timeout=args.connection_timeout,
        command_timeout=args.command_timeout,
        update_probe_path=args.update_probe_path,
    )
    result = await probe.run()
    print(
        json.dumps(
            _json_result(result),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe an MPD endpoint and record verified capabilities."
    )
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=6600)
    parser.add_argument("--password")
    parser.add_argument("--connection-timeout", type=float, default=3.0)
    parser.add_argument("--command-timeout", type=float, default=5.0)
    parser.add_argument(
        "--update-probe-path",
        default="__mpd_server_capability_probe__",
    )
    args = parser.parse_args()
    return asyncio.run(_probe_from_args(args))


if __name__ == "__main__":
    raise SystemExit(main())
