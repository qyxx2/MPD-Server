import asyncio
import pytest

from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.models import DatabaseUpdateStatus, MPDStats, OutputInfo, PlayerState, PlayerStatus
from server.app.player.ports import PlayerCommandError


class SpyPlayer:
    def __init__(self): self.calls=[]
    async def queue_entries(self): self.calls.append("queue_entries"); return []
    async def queue_clear(self): self.calls.append("queue_clear")
    async def queue_add(self, uri): self.calls.append("queue_add"); return 1
    async def queue_delete(self, song_id): self.calls.append("queue_delete")
    async def queue_move(self, song_id, before): self.calls.append("queue_move")
    async def queue_play(self, song_id): self.calls.append("queue_play")
    async def set_output_enabled(self, output_id, enabled): self.calls.append("set_output_enabled")
    async def stats(self): self.calls.append("stats"); return MPDStats()
    async def database_update_status(self): self.calls.append("database_update_status"); return DatabaseUpdateStatus()
    async def status(self): return PlayerStatus(state=PlayerState.STOPPED)
    async def play(self, song_uri=None): pass
    async def pause(self): pass
    async def stop(self): pass
    async def next(self): pass
    async def previous(self): pass
    async def seek(self, seconds): pass
    async def set_repeat(self, enabled): pass
    async def set_random(self, enabled): pass
    async def set_volume(self, volume): pass
    async def update_database(self): pass
    async def outputs(self): return [OutputInfo(id=0,name="x",plugin="mock",enabled=True)]


def test_all_task1r_operations_are_blocked_until_runtime_verified():
    async def run():
        commands=frozenset({"playlistinfo","clear","addid","deleteid","moveid","playid","outputs","enableoutput","disableoutput","stats","status","update"})
        player=SpyPlayer(); verified=VerifiedPlayerPort(player,MPDCapabilities.from_commands(commands))
        for invoke in [verified.queue_entries, verified.queue_clear, lambda:verified.queue_add("a"), lambda:verified.queue_delete(1), lambda:verified.queue_move(1,None), lambda:verified.queue_play(1), lambda:verified.set_output_enabled(1,True), verified.stats, verified.database_update_status]:
            with pytest.raises(PlayerCommandError, match="runtime behavior not verified"): await invoke()
        assert player.calls==[]
    asyncio.run(run())


def test_verified_task1r_operations_delegate_after_probe():
    async def run():
        commands=frozenset({"playlistinfo","clear","addid","deleteid","moveid","playid","outputs","enableoutput","disableoutput","stats","status","update"})
        runtime=frozenset({"queue_entries","queue_clear","queue_add","queue_delete","queue_move","queue_play","set_output_enabled","stats","database_update_status"})
        cap=MPDCapabilities(version="0.23.5",commands=commands,not_commands=frozenset(),status_fields=frozenset(),stats={},stats_fields=frozenset(),outputs=(),update_supported=True,update_response={},update_status_fields=frozenset({"updating_db"}),verified_operations=runtime)
        player=SpyPlayer(); verified=VerifiedPlayerPort(player,cap)
        await verified.queue_entries(); await verified.queue_clear(); await verified.queue_add("a"); await verified.queue_delete(1); await verified.queue_move(1,None); await verified.queue_play(1); await verified.set_output_enabled(1,True); await verified.stats(); await verified.database_update_status()
        assert player.calls==["queue_entries","queue_clear","queue_add","queue_delete","queue_move","queue_play","set_output_enabled","stats","database_update_status"]
    asyncio.run(run())
