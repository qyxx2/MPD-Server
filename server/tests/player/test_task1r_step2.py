import asyncio

from server.app.player.capabilities import CapabilityProbe


def test_probe_verifies_task1r_runtime_behavior_and_restores_queue():
    async def run():
        queue = [("song-a.flac", 10), ("song-b.flac", 11)]
        next_id = 20
        output_enabled = False
        updating_db = None
        seen = []

        async def handle(reader, writer):
            nonlocal next_id, output_enabled, updating_db
            writer.write(b"OK MPD 0.23.5\n")
            await writer.drain()
            try:
                while True:
                    raw = await reader.readline()
                    if not raw:
                        return
                    command = raw.decode().rstrip("\r\n")
                    seen.append(command)
                    parts = command.split(" ", 1)
                    verb = parts[0]
                    if verb == "commands":
                        for value in ("addid", "clear", "deleteid", "disableoutput", "enableoutput", "moveid", "outputs", "playid", "playlistinfo", "stats", "status", "update", "repeat", "random", "pause", "stop", "seekcur", "currentsong"):
                            writer.write(f"command: {value}\n".encode())
                        writer.write(b"OK\n")
                    elif verb == "notcommands":
                        writer.write(b"OK\n")
                    elif verb == "playlistinfo":
                        for pos, (uri, mpd_id) in enumerate(queue):
                            writer.write(f"file: {uri}\nPos: {pos}\nId: {mpd_id}\n".encode())
                        writer.write(b"OK\n")
                    elif verb == "addid":
                        next_id += 1
                        queue.append((parts[1].strip().strip('"'), next_id))
                        writer.write(f"Id: {next_id}\nOK\n".encode())
                    elif verb == "deleteid":
                        queue[:] = [item for item in queue if item[1] != int(parts[1])]
                        writer.write(b"OK\n")
                    elif verb == "moveid":
                        source_id, dest = (int(v) for v in parts[1].split())
                        source = next(i for i, item in enumerate(queue) if item[1] == source_id)
                        item = queue.pop(source)
                        queue.insert(dest, item)
                        writer.write(b"OK\n")
                    elif verb == "playid":
                        if any(item[1] == int(parts[1]) for item in queue):
                            writer.write(b"OK\n")
                        else:
                            writer.write(b"ACK [50@0] {playid} No such song\n")
                    elif verb == "clear":
                        queue.clear(); writer.write(b"OK\n")
                    elif verb == "outputs":
                        writer.write(f"outputid: 1\noutputname: HTTP Stream\nplugin: httpd\noutputenabled: {1 if output_enabled else 0}\nOK\n".encode())
                    elif verb == "enableoutput":
                        output_enabled = True; writer.write(b"OK\n")
                    elif verb == "disableoutput":
                        output_enabled = False; writer.write(b"OK\n")
                    elif verb == "stats":
                        writer.write(b"songs: 403\nalbums: 344\nartists: 264\ndb_playtime: 103730\ndb_update: 1786802874\nplaytime: 0\nuptime: 59917\nOK\n")
                    elif verb == "update":
                        updating_db = "9"; writer.write(b"updating_db: 9\nOK\n")
                    elif verb == "status":
                        writer.write(b"state: stop\nrepeat: 0\nrandom: 0\n")
                        if updating_db is not None: writer.write(f"updating_db: {updating_db}\n".encode())
                        writer.write(b"OK\n")
                    else:
                        writer.write(b"OK\n")
                    await writer.drain()
            finally:
                writer.close(); await writer.wait_closed()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        probe = CapabilityProbe("127.0.0.1", port=port, update_probe_path="__missing_mpd_server_probe__", probe_transport=True)
        try:
            result = await probe.run()
            assert {"queue_entries", "queue_clear", "queue_add", "queue_delete", "queue_move", "queue_play", "set_output_enabled", "stats", "database_update_status"}.issubset(result.verified_operations)
            assert result.stats_fields == {"songs", "albums", "artists", "db_playtime", "db_update", "playtime", "uptime"}
            assert result.update_status_fields == {"updating_db"}
            assert [uri for uri, _ in queue] == ["song-a.flac", "song-b.flac"]
            assert output_enabled is False
            assert any(c.startswith("addid ") for c in seen)
            assert any(c.startswith("moveid ") for c in seen)
            assert "enableoutput 1" in seen and "disableoutput 1" in seen
        finally:
            server.close(); await server.wait_closed()

    asyncio.run(run())


def test_transport_probe_never_toggles_usb_when_httpd_is_absent():
    async def run():
        seen = []

        async def handle(reader, writer):
            writer.write(b"OK MPD 0.23.5\n"); await writer.drain()
            try:
                while True:
                    raw = await reader.readline()
                    if not raw: return
                    command = raw.decode().rstrip("\r\n"); seen.append(command); verb = command.split(" ", 1)[0]
                    if verb == "commands":
                        for value in ("playlistinfo", "status", "currentsong", "stats", "outputs", "clear", "addid", "deleteid", "moveid", "playid", "enableoutput", "disableoutput", "update", "stop", "repeat", "random", "seekcur"):
                            writer.write(f"command: {value}\n".encode())
                        writer.write(b"OK\n")
                    elif verb == "playlistinfo": writer.write(b"file: usb.flac\nPos: 0\nId: 7\nOK\n")
                    elif verb == "status": writer.write(b"state: stop\nsong: -1\nrepeat: 0\nrandom: 0\nOK\n")
                    elif verb == "stats": writer.write(b"songs: 1\nOK\n")
                    elif verb == "outputs": writer.write(b"outputid: 0\noutputname: USB DAC\nplugin: alsa\noutputenabled: 1\nOK\n")
                    elif verb == "update": writer.write(b"updating_db: 1\nOK\n")
                    else: writer.write(b"OK\n")
                    await writer.drain()
            finally:
                writer.close(); await writer.wait_closed()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        probe = CapabilityProbe("127.0.0.1", port=server.sockets[0].getsockname()[1], probe_transport=True)
        try:
            result = await probe.run()
            assert "set_output_enabled" not in result.verified_operations
            assert not any(c.startswith("enableoutput ") or c.startswith("disableoutput ") for c in seen)
        finally:
            server.close(); await server.wait_closed()

    asyncio.run(run())


def test_transport_probe_never_toggles_an_active_httpd_output():
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
                    if verb == "commands":
                        for value in (
                            "playlistinfo", "status", "stats", "outputs",
                            "enableoutput", "disableoutput", "update",
                        ):
                            writer.write(f"command: {value}\n".encode())
                        writer.write(b"OK\n")
                    elif verb == "playlistinfo":
                        writer.write(b"file: x.flac\nPos: 0\nId: 7\nOK\n")
                    elif verb == "status":
                        writer.write(b"state: stop\nsong: -1\nrepeat: 0\nrandom: 0\nOK\n")
                    elif verb == "stats":
                        writer.write(b"songs: 1\nOK\n")
                    elif verb == "outputs":
                        writer.write(
                            b"outputid: 1\noutputname: HTTP Stream\nplugin: httpd\n"
                            b"outputenabled: 1\nOK\n"
                        )
                    elif verb == "update":
                        writer.write(b"updating_db: 1\nOK\n")
                    elif verb == "__mpd_server_unsupported_probe__":
                        writer.close()
                        await writer.wait_closed()
                        return
                    else:
                        writer.write(b"OK\n")
                    await writer.drain()
            finally:
                if not writer.is_closing():
                    writer.close()
                    await writer.wait_closed()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        probe = CapabilityProbe(
            "127.0.0.1",
            port=server.sockets[0].getsockname()[1],
            probe_transport=True,
        )
        try:
            result = await probe.run()
            assert "set_output_enabled" not in result.verified_operations
            assert not any(
                command.startswith("enableoutput ") or command.startswith("disableoutput ")
                for command in seen
            )
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())
