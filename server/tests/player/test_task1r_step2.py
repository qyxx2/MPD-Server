import asyncio

from server.app.player.capabilities import CapabilityProbe


def test_probe_verifies_queue_output_stats_and_update_status_runtime_behavior():
    async def run():
        queue = [
            ("song-a.flac", 10),
            ("song-b.flac", 11),
        ]
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
                        for value in (
                            "addid", "clear", "deleteid", "disableoutput",
                            "enableoutput", "moveid", "outputs", "playid",
                            "playlistinfo", "stats", "status", "update",
                            "listallinfo", "repeat", "random", "pause",
                            "stop", "seekcur",
                        ):
                            writer.write(f"command: {value}\n".encode())
                        writer.write(b"OK\n")
                    elif verb == "notcommands":
                        writer.write(b"OK\n")
                    elif verb == "playlistinfo":
                        for position, (uri, mpd_id) in enumerate(queue):
                            writer.write(
                                f"file: {uri}\nPos: {position}\nId: {mpd_id}\n".encode()
                            )
                        writer.write(b"OK\n")
                    elif verb == "addid":
                        next_id += 1
                        uri = parts[1].strip().strip('"')
                        queue.append((uri, next_id))
                        writer.write(f"Id: {next_id}\nOK\n".encode())
                    elif verb == "deleteid":
                        mpd_id = int(parts[1])
                        queue[:] = [item for item in queue if item[1] != mpd_id]
                        writer.write(b"OK\n")
                    elif verb == "moveid":
                        source_id, destination = (
                            int(value) for value in parts[1].split()
                        )
                        source_index = next(
                            i for i, item in enumerate(queue) if item[1] == source_id
                        )
                        item = queue.pop(source_index)
                        queue.insert(destination, item)
                        writer.write(b"OK\n")
                    elif verb == "playid":
                        writer.write(b"OK\n")
                    elif verb == "clear":
                        queue.clear()
                        writer.write(b"OK\n")
                    elif verb == "outputs":
                        writer.write(
                            f"outputid: 1\noutputname: HTTP Stream\nplugin: httpd\n"
                            f"outputenabled: {1 if output_enabled else 0}\nOK\n".encode()
                        )
                    elif verb == "enableoutput":
                        output_enabled = True
                        writer.write(b"OK\n")
                    elif verb == "disableoutput":
                        output_enabled = False
                        writer.write(b"OK\n")
                    elif verb == "stats":
                        writer.write(
                            b"songs: 403\nalbums: 344\nartists: 264\n"
                            b"db_playtime: 103730\ndb_update: 1786802874\n"
                            b"playtime: 0\nuptime: 59917\nOK\n"
                        )
                    elif verb == "update":
                        updating_db = "9"
                        writer.write(b"updating_db: 9\nOK\n")
                    elif verb == "status":
                        writer.write(b"state: stop\nrepeat: 0\nrandom: 0\n")
                        if updating_db is not None:
                            writer.write(f"updating_db: {updating_db}\n".encode())
                        writer.write(b"OK\n")
                    else:
                        writer.write(b"OK\n")
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        probe = CapabilityProbe(
            "127.0.0.1",
            port=port,
            update_probe_path="__missing_mpd_server_probe__",
        )
        try:
            result = await probe.run()
            assert {
                "queue_entries",
                "queue_clear",
                "queue_add",
                "queue_delete",
                "queue_move",
                "queue_play",
                "set_output_enabled",
                "stats",
                "database_update_status",
            }.issubset(result.verified_operations)
            assert result.stats_fields == {
                "songs",
                "albums",
                "artists",
                "db_playtime",
                "db_update",
                "playtime",
                "uptime",
            }
            assert result.update_status_fields == {"updating_db"}
            assert "addid" in result.commands
            assert "moveid" in result.commands
            assert "enableoutput" in result.commands
            assert "disableoutput" in result.commands
            assert "stats" in result.commands
            assert "update" in result.commands
            assert any(command.startswith("addid ") for command in seen)
            assert any(command.startswith("moveid ") for command in seen)
            assert any(command.startswith("enableoutput ") for command in seen)
            assert any(command.startswith("disableoutput ") for command in seen)
            assert queue == [("song-a.flac", 10), ("song-b.flac", 11)]
            assert output_enabled is False
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())
