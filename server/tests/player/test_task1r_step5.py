import asyncio

from server.app.player.mpd_adapter import MPDAdapter


def test_adapter_task1r_transport_operations():
    async def run():
        received=[]
        async def handle(reader, writer):
            writer.write(b"OK MPD 0.23.5\n"); await writer.drain()
            try:
                while True:
                    raw=await reader.readline()
                    if not raw:return
                    command=raw.decode().rstrip("\r\n"); received.append(command); verb=command.split(" ",1)[0]
                    if verb=="playlistinfo": writer.write(b"file: a.flac\nPos: 0\nId: 10\nfile: b.flac\nPos: 1\nId: 11\nfile: c.flac\nPos: 2\nId: 12\nOK\n")
                    elif verb=="addid": writer.write(b"Id: 20\nOK\n")
                    elif verb=="stats": writer.write(b"songs: 403\nalbums: 344\nartists: 264\ndb_playtime: 103730\ndb_update: 1786802874\nplaytime: 0\nuptime: 59917\nOK\n")
                    elif verb=="status": writer.write(b"state: pause\nsong: 1\nsongid: 11\nelapsed: 4.5\nduration: 90\nvolume: 45\nrepeat: 1\nrandom: 0\nupdating_db: 9\nOK\n")
                    elif verb=="outputs": writer.write(b"outputid: 0\noutputname: USB DAC\nplugin: alsa\noutputenabled: 1\nattribute: device=hw:1,0\noutputid: 1\noutputname: HTTP Stream\nplugin: httpd\noutputenabled: 0\nOK\n")
                    else: writer.write(b"OK\n")
                    await writer.drain()
            finally: writer.close(); await writer.wait_closed()
        server=await asyncio.start_server(handle,"127.0.0.1",0); adapter=MPDAdapter("127.0.0.1",port=server.sockets[0].getsockname()[1])
        try:
            assert len(await adapter.queue_entries())==3
            assert await adapter.queue_add("a.flac")==20
            await adapter.queue_delete(20); await adapter.queue_move(10,11); await adapter.queue_move(11,None); await adapter.queue_play(11); await adapter.queue_clear()
            await adapter.set_output_enabled(1,True); await adapter.set_output_enabled(1,False)
            assert (await adapter.stats()).songs==403
            status=await adapter.database_update_status(); assert status.updating is True and status.job_id==9
            assert "moveid 10 0" in received and "moveid 11 2" in received
        finally: await adapter.close(); server.close(); await server.wait_closed()
    asyncio.run(run())
