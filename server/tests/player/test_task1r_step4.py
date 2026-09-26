import asyncio
import pytest

from server.app.player.models import MPDStats, OutputInfo, PlayerState
from server.app.player.mock_mpd import MockMPD
from server.app.player.ports import PlayerCommandError


def test_mock_task1r_queue_output_stats_and_update_status():
    async def run():
        player = MockMPD(["a.flac", "b.flac"], outputs=[OutputInfo(id=0, name="USB DAC", plugin="alsa", enabled=True), OutputInfo(id=1, name="HTTP Stream", plugin="httpd", enabled=False)], stats=MPDStats(songs=2, albums=1, artists=1, uptime=99))
        first = await player.queue_add("a.flac"); second = await player.queue_add("b.flac")
        await player.queue_move(second, first)
        assert [e.mpd_song_id for e in await player.queue_entries()] == [second, first]
        await player.queue_play(second)
        assert (await player.status()).song_uri == "b.flac"
        await player.queue_delete(first); await player.queue_clear()
        assert await player.queue_entries() == []
        await player.set_output_enabled(1, True); assert (await player.outputs())[1].enabled is True
        await player.set_output_enabled(1, False); assert (await player.outputs())[1].enabled is False
        assert (await player.stats()).uptime == 99
        assert (await player.database_update_status()).updating is False
        await player.update_database()
        status = await player.database_update_status()
        assert status.updating is True and status.job_id == 1
    asyncio.run(run())


def test_mock_task1r_failures_are_typed_and_one_shot():
    async def run():
        player = MockMPD(["a.flac"]); await player.queue_add("a.flac")
        player.fail_next("queue_delete", "Injected queue delete failure")
        with pytest.raises(PlayerCommandError, match="Injected queue delete failure"): await player.queue_delete(1)
        await player.queue_delete(1)
        player.fail_next("stats", "Injected stats failure")
        with pytest.raises(PlayerCommandError, match="Injected stats failure"): await player.stats()
    asyncio.run(run())
