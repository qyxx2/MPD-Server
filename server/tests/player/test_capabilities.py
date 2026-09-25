import asyncio

import pytest

from server.app.player.capabilities import (
    CapabilityProbe,
    MPDCapabilities,
    VerifiedPlayerPort,
)
from server.app.player.models import OutputInfo, PlayerState, PlayerStatus
from server.app.player.ports import PlayerCommandError


class SpyPlayer:
    def __init__(self):
        self.calls = []

    async def status(self):
        self.calls.append(("status",))
        return PlayerStatus(state=PlayerState.STOPPED)

    async def play(self, song_uri=None):
        self.calls.append(("play", song_uri))

    async def pause(self):
        self.calls.append(("pause",))

    async def stop(self):
        self.calls.append(("stop",))

    async def next(self):
        self.calls.append(("next",))

    async def previous(self):
        self.calls.append(("previous",))

    async def seek(self, seconds):
        self.calls.append(("seek", seconds))

    async def set_repeat(self, enabled):
        self.calls.append(("set_repeat", enabled))

    async def set_random(self, enabled):
        self.calls.append(("set_random", enabled))

    async def set_volume(self, volume):
        self.calls.append(("set_volume", volume))

    async def update_database(self):
        self.calls.append(("update_database",))

    async def outputs(self):
        self.calls.append(("outputs",))
        return [OutputInfo(id=0, name="x", plugin="mock", enabled=True)]


def test_verified_port_rejects_unverified_operations_before_delegate():
    async def run():
        player = SpyPlayer()
        capabilities = MPDCapabilities.from_commands({"status", "currentsong", "play"})
        verified = VerifiedPlayerPort(player, capabilities)

        await verified.play()
        assert player.calls == [("play", None)]

        with pytest.raises(PlayerCommandError, match="not verified") as exc:
            await verified.pause()
        assert exc.value.command == "pause"
        assert player.calls == [("play", None)]

    asyncio.run(run())


def test_verified_port_requires_playlist_commands_for_play_by_uri():
    async def run():
        player = SpyPlayer()
        verified = VerifiedPlayerPort(
            player,
            MPDCapabilities.from_commands({"play"}),
        )
        with pytest.raises(PlayerCommandError, match="not verified"):
            await verified.play("music/a.flac")

    asyncio.run(run())


def test_probe_records_commands_status_outputs_and_update_result():
    async def run():
        seen = []

        async def handle(reader, writer):
            writer.write(b"OK MPD 0.23.5\n")
            await writer.drain()
            try:
                while True:
                    raw = await reader.readline()
                    if not raw:
                        return
                    command = raw.decode().rstrip("\r\n")
                    seen.append(command)
                    verb = command.split(" ", 1)[0]
                    responses = {
                        "commands": [
                            "command: status\n",
                            "command: outputs\n",
                            "command: update\n",
                            "command: stats\n",
                            "OK\n",
                        ],
                        "status": [
                            "state: stop\n",
                            "volume: -1\n",
                            "song: -1\n",
                            "OK\n",
                        ],
                        "outputs": [
                            "outputid: 3\n",
                            "outputname: USB DAC\n",
                            "plugin: alsa\n",
                            "outputenabled: 1\n",
                            "OK\n",
                        ],
                        "stats": [
                            "artists: 2\n",
                            "albums: 3\n",
                            "songs: 4\n",
                            "db_update: 123\n",
                            "db_playtime: 456.0\n",
                            "db_uptime: 789\n",
                            "OK\n",
                        ],
                        "update": ["updating_db: 9\n", "OK\n"],
                        "__mpd_server_unsupported_probe__": [
                            "ACK [5@0] {__mpd_server_unsupported_probe__} unknown command\n",
                        ],
                    }
                    for response_line in responses.get(verb, ["OK\n"]):
                        writer.write(response_line.encode())
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            probe = CapabilityProbe(
                "127.0.0.1",
                port=port,
                update_probe_path="__missing_mpd_server_probe__",
            )
            result = await probe.run()
            assert result.version == "0.23.5"
            assert "status" in result.commands
            assert "outputs" in result.commands
            assert result.status_fields == {"state", "volume", "song"}
            assert result.outputs[0].name == "USB DAC"
            assert result.update_supported is True
            assert result.update_response == {"updating_db": "9"}
            assert result.stats == {
                "artists": "2",
                "albums": "3",
                "songs": "4",
                "db_update": "123",
                "db_playtime": "456.0",
                "db_uptime": "789",
            }
            assert result.errors[0].error_code == 5
            assert seen == [
                "commands",
                "status",
                "outputs",
                "stats",
                "update __missing_mpd_server_probe__",
                "__mpd_server_unsupported_probe__",
            ]
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())
