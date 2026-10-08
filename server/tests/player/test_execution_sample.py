import asyncio
from collections.abc import Callable

import pytest
from pydantic import ValidationError

from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.mock_mpd import MockMPD
from server.app.player.mpd_adapter import MPDAdapter
from server.app.player.ports import PlayerCommandError, PlayerUnavailable


class SampleMPDServer:
    def __init__(
        self,
        *,
        conflict: str | None = None,
        state: str = "play",
        selected: bool = True,
        entry_count: int = 2,
        error: str | None = None,
        disconnect_on: str | None = None,
    ) -> None:
        self.conflict = conflict
        self.state = state
        self.selected = selected
        self.entry_count = entry_count
        self.error = error
        self.disconnect_on = disconnect_on
        self.received: list[str] = []
        self.connections = 0
        self._server: asyncio.Server | None = None

    async def start(self) -> int:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        return self._server.sockets[0].getsockname()[1]

    async def close(self) -> None:
        assert self._server is not None
        self._server.close()
        await self._server.wait_closed()

    async def _handle(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self.connections += 1
        status_reads = 0
        writer.write(b"OK MPD 0.23.5\n")
        await writer.drain()
        try:
            while raw := await reader.readline():
                command = raw.decode().rstrip("\r\n")
                self.received.append(command)
                if command == self.disconnect_on:
                    return
                if command == "status":
                    status_reads += 1
                    lines = self._status_lines(status_reads)
                elif command == "playlistinfo":
                    lines = self._playlist_lines()
                else:
                    lines = ["OK\n"]
                writer.writelines(line.encode() for line in lines)
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    def _status_lines(self, read_number: int) -> list[str]:
        second_read = read_number % 2 == 0
        playlist_version = 101 if self.conflict == "version" and second_read else 100
        song_position = 1 if self.conflict == "current" and second_read else 0
        song_id = 11 if self.conflict == "current" and second_read else 10
        playlist_length = 3 if self.conflict == "length" else self.entry_count
        sampled_state = "pause" if self.conflict == "state" and second_read else self.state
        lines = [
            "partition: default\n",
            f"playlist: {playlist_version}\n",
            f"playlistlength: {playlist_length}\n",
            f"state: {sampled_state}\n",
            "single: 0\n",
            "consume: 0\n",
            "repeat: 1\n",
            "random: 0\n",
            "elapsed: 12.5\n",
            "duration: 180.0\n",
            "volume: 40\n",
        ]
        if self.selected:
            lines.extend([f"song: {song_position}\n", f"songid: {song_id}\n"])
        if self.error is not None:
            lines.append(f"error: {self.error}\n")
        lines.append("OK\n")
        return lines

    def _playlist_lines(self) -> list[str]:
        if self.entry_count == 0:
            return ["OK\n"]
        second_position = 2 if self.conflict == "position" else 1
        second_id = 10 if self.conflict == "duplicate-id" else 11
        return [
            "file: music/one.flac\n",
            "Pos: 0\n",
            "Id: 10\n",
            "file: music/two.flac\n",
            f"Pos: {second_position}\n",
            f"Id: {second_id}\n",
            "OK\n",
        ]


async def with_adapter(
    server: SampleMPDServer,
    check: Callable[[MPDAdapter], object],
) -> None:
    port = await server.start()
    adapter = MPDAdapter("127.0.0.1", port=port)
    try:
        result = check(adapter)
        if asyncio.iscoroutine(result):
            await result
    finally:
        await adapter.close()
        await server.close()


@pytest.mark.parametrize(
    "conflict",
    ["current", "state", "version", "length", "duplicate-id", "position"],
)
def test_sample_rejects_torn_current_and_queue(conflict: str) -> None:
    async def run() -> None:
        server = SampleMPDServer(conflict=conflict)

        async def check(adapter: MPDAdapter) -> None:
            with pytest.raises(PlayerCommandError) as exc_info:
                await adapter.read_execution_sample()

            assert exc_info.value.command == "read_execution_sample"
            assert str(exc_info.value) == "inconsistent execution sample"
            assert server.received.count("playlistinfo") == 2
            controls = [
                command
                for command in server.received
                if command not in {"status", "playlistinfo", "currentsong"}
            ]
            assert controls == []

        await with_adapter(server, check)

    asyncio.run(run())


def test_sample_epoch_and_modes_are_not_completion_evidence() -> None:
    async def run() -> None:
        server = SampleMPDServer(error="decoder error")
        port = await server.start()
        adapter = MPDAdapter("127.0.0.1", port=port)
        try:
            old = await adapter.read_execution_sample()
            await adapter.close()
            new = await adapter.read_execution_sample()
            assert new.connection_epoch != old.connection_epoch
            assert new.partition == "default"
            assert new.playlist_version == 100
            assert new.single == "0"
            assert new.consume is False
            assert new.error == "decoder error"
            assert "reason" not in new.model_dump()
            assert new.status.song_id == new.entries[new.status.song_position].mpd_song_id
        finally:
            await adapter.close()
            await server.close()

        no_error = SampleMPDServer(error=None)

        async def check_no_error(current: MPDAdapter) -> None:
            sample = await current.read_execution_sample()
            assert sample.error is None
            assert "reason" not in sample.model_dump()

        await with_adapter(no_error, check_no_error)

        empty = SampleMPDServer(state="stop", selected=False, entry_count=0)

        async def check_empty(current: MPDAdapter) -> None:
            sample = await current.read_execution_sample()
            assert sample.entries == ()
            assert sample.status.song_id is None
            assert sample.status.song_position is None

        await with_adapter(empty, check_empty)

        stopped_selected = SampleMPDServer(state="stop", selected=True)

        async def check_stopped_selected(current: MPDAdapter) -> None:
            sample = await current.read_execution_sample()
            assert sample.status.state.value == "stopped"
            assert sample.status.song_id == 10
            assert sample.status.song_position == 0
            assert "reason" not in sample.model_dump()

        await with_adapter(stopped_selected, check_stopped_selected)

        disconnected = SampleMPDServer(disconnect_on="playlistinfo")

        async def check_disconnect(current: MPDAdapter) -> None:
            with pytest.raises(PlayerUnavailable):
                await current.read_execution_sample()

        await with_adapter(disconnected, check_disconnect)

        reconnected = SampleMPDServer()
        port = await reconnected.start()
        reconnecting_adapter = MPDAdapter("127.0.0.1", port=port)
        original_command = reconnecting_adapter._command_unlocked
        closed_once = False

        async def close_after_first_status(command: str, *args: str):
            nonlocal closed_once
            response = await original_command(command, *args)
            if command == "status" and not closed_once:
                closed_once = True
                await reconnecting_adapter.close()
            return response

        reconnecting_adapter._command_unlocked = close_after_first_status
        try:
            await reconnecting_adapter.read_execution_sample()
            assert reconnected.received.count("playlistinfo") == 2
        finally:
            await reconnecting_adapter.close()
            await reconnected.close()

        mock = MockMPD(["music/one.flac"])
        await mock.queue_add("music/one.flac")
        await mock.queue_play(1)
        mock_sample = await mock.read_execution_sample()
        assert mock_sample.status.song_id == 1
        assert mock_sample.entries[0].song_uri == "music/one.flac"
        with pytest.raises(ValidationError):
            mock_sample.status.song_id = 999
        with pytest.raises(ValidationError):
            mock_sample.entries[0].position = 99

        verified = VerifiedPlayerPort(
            mock,
            MPDCapabilities.from_commands({"status", "playlistinfo"}),
        )
        verified_sample = await verified.read_execution_sample()
        assert verified_sample.status.song_id == 1

        blocked = VerifiedPlayerPort(
            mock,
            MPDCapabilities.from_commands({"status"}),
        )
        with pytest.raises(PlayerCommandError) as exc_info:
            await blocked.read_execution_sample()
        assert exc_info.value.command == "read_execution_sample"

    asyncio.run(run())
