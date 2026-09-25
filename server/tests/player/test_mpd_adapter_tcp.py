import asyncio

from server.app.player.mpd_adapter import MPDAdapter


def test_adapter_controls_real_line_protocol_over_fake_tcp_server():
    async def run():
        received = []

        async def handle(reader, writer):
            writer.write(b"OK MPD 0.23.5\n")
            await writer.drain()
            try:
                while True:
                    raw = await reader.readline()
                    if not raw:
                        return
                    command = raw.decode().rstrip("\r\n")
                    received.append(command)
                    verb = command.split(" ", 1)[0]
                    responses = {
                        "status": [
                            "state: play\n",
                            "song: 0\n",
                            "songid: 10\n",
                            "elapsed: 12.5\n",
                            "duration: 180.0\n",
                            "volume: 40\n",
                            "repeat: 1\n",
                            "random: 0\n",
                            "OK\n",
                        ],
                        "currentsong": [
                            "file: music/one.flac\n",
                            "OK\n",
                        ],
                        "playlistinfo": [
                            "file: music/one.flac\n",
                            "Id: 10\n",
                            "file: music/two.flac\n",
                            "Id: 11\n",
                            "OK\n",
                        ],
                        "outputs": [
                            "outputid: 3\n",
                            "outputname: USB DAC\n",
                            "plugin: alsa\n",
                            "outputenabled: 1\n",
                            "attribute: device=hw:1,0\n",
                            "OK\n",
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
        adapter = MPDAdapter("127.0.0.1", port=port)
        try:
            status = await adapter.status()
            assert status.state.value == "playing"
            assert status.song_uri == "music/one.flac"
            assert status.song_id == 10
            assert status.elapsed_seconds == 12.5
            assert status.duration_seconds == 180.0
            assert status.volume == 40
            assert status.repeat is True
            assert status.random is False

            await adapter.play("music/two.flac")
            await adapter.pause()
            await adapter.stop()
            await adapter.next()
            await adapter.previous()
            await adapter.seek(33.25)
            await adapter.set_repeat(False)
            await adapter.set_random(True)
            await adapter.set_volume(75)
            await adapter.update_database()

            outputs = await adapter.outputs()
            assert len(outputs) == 1
            assert outputs[0].name == "USB DAC"
            assert outputs[0].plugin == "alsa"
            assert outputs[0].enabled is True
            assert outputs[0].attributes == {"device": "hw:1,0"}

            assert received == [
                "status",
                "currentsong",
                "playlistinfo",
                "playid 11",
                "pause 1",
                "stop",
                "next",
                "previous",
                "seekcur 33.25",
                "repeat 0",
                "random 1",
                "setvol 75",
                "update",
                "outputs",
            ]
        finally:
            await adapter.close()
            server.close()
            await server.wait_closed()

    asyncio.run(run())
