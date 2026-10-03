"""F5 transport proof: real adapter over a deterministic localhost MPD server."""

from __future__ import annotations

import asyncio

import pytest

from server.app.models.output import OutputMode
from server.app.player.mpd_adapter import MPDAdapter
from server.app.player.ports import PlayerCommandError, PlayerUnavailable
from server.app.services.output_manager import OutputError
from server.tests.invariants.test_output_enable import enable_manager
from server.tests.invariants.test_output_serialization import authority_snapshot
from server.tests.support.playback import start


@pytest.mark.parametrize("outcome", ["success", "ack-no-effect", "ack-error", "timeout-after-effect"])
def test_output_confirmation_through_mpd_adapter(real_client, outcome):
    client, _, mock, service = real_client
    start(client)

    async def scenario():
        await service.add_to_queue("a")
        await service.pause()
        await service.seek(17)
        before = await authority_snapshot(service)
        status = await mock.status()
        entries = await mock.queue_entries()
        received, events = [], []
        handlers = set()
        enabled = False
        fault = outcome
        queue_wire = "".join(
            f"file: {entry.song_uri}\nPos: {entry.position}\nId: {entry.mpd_song_id}\n"
            for entry in entries
        )
        status_wire = (
            f"state: pause\nsong: 0\nsongid: {entries[0].mpd_song_id}\n"
            "elapsed: 17.000\nduration: 300\nvolume: 50\nrepeat: 0\nrandom: 0\n"
        )

        async def handle(reader, writer):
            nonlocal enabled
            task = asyncio.current_task()
            handlers.add(task)
            writer.write(b"OK MPD 0.23.5\n")
            await writer.drain()
            try:
                while raw := await reader.readline():
                    command = raw.decode().rstrip("\r\n")
                    received.append(command)
                    if command == "status":
                        response = status_wire + "OK\n"
                    elif command == "currentsong":
                        response = f"file: a.flac\nPos: 0\nId: {entries[0].mpd_song_id}\nOK\n"
                    elif command == "playlistinfo":
                        response = queue_wire + "OK\n"
                    elif command == "outputs":
                        response = (
                            f"outputid: 91\noutputname: USB DAC\nplugin: alsa\noutputenabled: {int(enabled)}\n"
                            "outputid: 0\noutputname: Stream\nplugin: httpd\noutputenabled: 1\nOK\n"
                        )
                    elif command == "enableoutput 91":
                        if fault == "ack-error":
                            response = "ACK [50@0] {enableoutput} unavailable\n"
                        else:
                            if fault != "ack-no-effect":
                                enabled = True
                            if fault == "timeout-after-effect":
                                # No ACK; wait for the adapter's timeout/close, then permit reconnect.
                                continue
                            response = "OK\n"
                    else:
                        response = "ACK [5@0] {} unexpected command\n"
                    writer.write(response.encode())
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
                handlers.discard(task)

        class Publisher:
            async def publish(self, event):
                assert received[-2:] == ["currentsong", "playlistinfo"]
                assert await asyncio.wait_for(
                    asyncio.create_task(authority_snapshot(service)), 3,
                ) == before
                events.append(event)

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        adapter = MPDAdapter(
            "127.0.0.1", port=server.sockets[0].getsockname()[1], command_timeout=0.1,
        )
        service.player = adapter
        manager = enable_manager(service, adapter, event_publisher=Publisher())
        try:
            if outcome == "success":
                receipt = await manager.set_enabled(OutputMode.NAS_DAC, True)
                assert receipt.last_request.status == "SUCCEEDED"
                assert len(events) == 1
            else:
                error = {
                    "ack-no-effect": OutputError, "ack-error": PlayerCommandError,
                    "timeout-after-effect": PlayerUnavailable,
                }[outcome]
                with pytest.raises(error):
                    await manager.set_enabled(OutputMode.NAS_DAC, True)
                assert events == []
            assert received.count("enableoutput 91") == 1
            assert not set(received) - {"status", "currentsong", "playlistinfo", "outputs", "enableoutput 91"}
            observation = await manager.get_state()
            assert observation.states[0].status == (
                "ACTIVE" if outcome in {"success", "timeout-after-effect"} else "INACTIVE"
            )
            assert observation.last_request.status == ("SUCCEEDED" if outcome == "success" else "SWITCH_FAILED")
            assert await adapter.status() == status
            assert await adapter.queue_entries() == entries
            assert (await adapter.outputs())[1].enabled is True
            assert await authority_snapshot(service) == before
            fault = "success"
            assert (await manager.set_enabled(OutputMode.NAS_DAC, True)).states[0].status == "ACTIVE"
            needs_write = outcome in {"ack-no-effect", "ack-error"}
            assert received.count("enableoutput 91") == 1 + int(needs_write)
            assert len(events) == (1 if outcome == "success" else int(needs_write))
            assert await authority_snapshot(service) == before
        finally:
            await adapter.close()
            server.close()
            await server.wait_closed()
            if handlers:
                await asyncio.wait_for(asyncio.gather(*handlers), 3)
            service.player = mock

    asyncio.run(scenario())
