import asyncio
import pytest

from server.app.player.mpd_adapter import MPDAdapter
from server.app.player.ports import PlayerCommandError, PlayerUnavailable


def test_task1r_adapter_ack_and_connection_failures_are_typed():
    async def run():
        connections=0
        async def handle(reader,writer):
            nonlocal connections
            connections+=1; writer.write(b"OK MPD 0.23.5\n"); await writer.drain()
            command=(await reader.readline()).decode().rstrip("\r\n")
            if command=="stats": writer.write(b"ACK [50@0] {stats} injected failure\n")
            elif command=="playlistinfo": writer.close(); await writer.wait_closed(); return
            else: writer.write(b"state: stop\nOK\n")
            await writer.drain(); writer.close(); await writer.wait_closed()
        server=await asyncio.start_server(handle,"127.0.0.1",0); adapter=MPDAdapter("127.0.0.1",port=server.sockets[0].getsockname()[1])
        try:
            with pytest.raises(PlayerCommandError) as exc: await adapter.stats()
            assert exc.value.error_code==50
            with pytest.raises(PlayerUnavailable): await adapter.queue_entries()
            assert (await adapter.status()).state.value=="stopped"
            assert connections==2
        finally: await adapter.close(); server.close(); await server.wait_closed()
    asyncio.run(run())
