import asyncio

import pytest

from server.app.player.mpd_adapter import MPDAdapter
from server.app.player.ports import PlayerCommandError, PlayerUnavailable


class FakeReader:
    def __init__(self, lines, *, delay=0):
        self.lines = iter(lines)
        self.delay = delay
        self.reads = 0

    async def readline(self):
        self.reads += 1
        if self.delay and self.reads > 1:
            await asyncio.sleep(self.delay)
        return next(self.lines, b"")


class FakeWriter:
    def __init__(self):
        self.closed = False
        self.data = b""

    def write(self, data):
        self.data += data

    async def drain(self):
        return None

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None


def test_adapter_maps_ack_to_typed_command_error():
    async def run():
        reader = FakeReader([
            b"OK MPD 0.23.5\n",
            b"ACK [50@0] {play} No such song\n",
        ])
        writer = FakeWriter()

        async def connect(host, port):
            return reader, writer

        adapter = MPDAdapter("127.0.0.1", connection_factory=connect)

        with pytest.raises(PlayerCommandError) as exc:
            await adapter.play()

        assert exc.value.error_code == 50
        assert exc.value.command == "play"
        assert str(exc.value) == "No such song"

    asyncio.run(run())


def test_adapter_connection_timeout_is_typed_unavailable():
    async def run():
        async def timeout_connection(host, port):
            await asyncio.sleep(0.05)
            raise AssertionError("must be cancelled")

        adapter = MPDAdapter(
            "127.0.0.1",
            connection_timeout=0.01,
            connection_factory=timeout_connection,
        )

        with pytest.raises(PlayerUnavailable, match="connection timed out"):
            await adapter.status()

    asyncio.run(run())


def test_adapter_command_timeout_closes_unusable_connection():
    async def run():
        reader = FakeReader(
            [b"OK MPD 0.23.5\n"],
            delay=0.05,
        )
        writer = FakeWriter()

        async def connect(host, port):
            return reader, writer

        adapter = MPDAdapter(
            "127.0.0.1",
            command_timeout=0.01,
            connection_factory=connect,
        )

        with pytest.raises(PlayerUnavailable, match="command timed out"):
            await adapter.status()
        assert writer.closed is True

    asyncio.run(run())
