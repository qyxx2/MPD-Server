import asyncio

import pytest

from server.app.models.output import OutputMode
from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.mock_mpd import MockMPD
from server.app.player.models import OutputInfo
from server.app.services.output_manager import OutputError, OutputManager


async def direct_runner(operation):
    return await operation(None)


@pytest.mark.parametrize("enabled, expected", [(True, "ACTIVE"), (False, "INACTIVE")])
def test_observation_uses_current_alsa_fact_without_control_capability(enabled, expected):
    async def run():
        cap = MPDCapabilities.from_commands({"outputs"})
        player = MockMPD(outputs=[
            OutputInfo(id=37, name="USB DAC", plugin="alsa", enabled=enabled),
            OutputInfo(id=0, name="Stream", plugin="httpd", enabled=True),
        ])
        calls = []

        async def runner(operation):
            calls.append("entered")
            return await operation(None)

        manager = OutputManager(
            player=VerifiedPlayerPort(player, cap), capabilities=cap, operation_runner=runner,
        )
        before = await player.outputs()
        snapshot = await manager.get_state()
        nas, stream = snapshot.states
        assert nas.mode == "NAS_DAC"
        assert nas.status == expected
        assert nas.stale is False
        assert nas.error_code is None
        assert nas.updated_at.tzinfo is not None
        assert stream.mode == "CLIENT_STREAM"
        assert stream.status == "UNAVAILABLE"
        assert stream.error_code == "OUTPUT_MODE_UNSUPPORTED"
        for state in snapshot.states:
            for field in ("target_client_id", "stream_url", "format", "sample_rate", "bit_depth", "channels"):
                assert getattr(state, field) is None
        assert snapshot.last_request is None
        assert await player.outputs() == before
        assert calls == ["entered"]

    asyncio.run(run())


@pytest.mark.parametrize("enabled", [False, True])
def test_nas_control_is_explicitly_unavailable_in_read_only_batch(enabled):
    async def run():
        class NoCallsPlayer:
            async def outputs(self):
                pytest.fail("B1 must refuse NAS control before external access")

        async def no_runner(operation):
            pytest.fail("B1 must refuse NAS control before entering an operation")

        manager = OutputManager(
            player=NoCallsPlayer(), capabilities=MPDCapabilities.from_commands(set()),
            operation_runner=no_runner,
        )
        with pytest.raises(OutputError) as error:
            await manager.set_enabled(OutputMode.NAS_DAC, enabled)
        assert error.value.code == "OUTPUT_CONTROL_UNAVAILABLE"

    asyncio.run(run())
