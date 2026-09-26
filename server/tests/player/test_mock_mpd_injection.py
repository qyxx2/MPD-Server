import asyncio

import pytest

from server.app.player.mock_mpd import MockMPD
from server.app.player.ports import PlayerCommandError, PlayerUnavailable


def test_disconnect_and_reconnect_are_injectable():
    async def run():
        player = MockMPD(["a.flac"])

        player.disconnect()
        with pytest.raises(PlayerUnavailable):
            await player.status()

        player.reconnect()
        assert (await player.status()).state.value == "stopped"

    asyncio.run(run())


def test_fail_next_injection_is_one_shot():
    async def run():
        player = MockMPD(["a.flac"])
        player.fail_next("pause", "Injected pause failure")

        with pytest.raises(PlayerCommandError) as exc:
            await player.pause()
        assert exc.value.command == "pause"
        assert str(exc.value) == "Injected pause failure"

        await player.pause()
        assert (await player.status()).state.value == "paused"

    asyncio.run(run())
