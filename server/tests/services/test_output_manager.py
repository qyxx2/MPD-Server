import asyncio

import pytest

from server.app.models.output import OutputMode
from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.mock_mpd import MockMPD
from server.app.player.models import OutputInfo
from server.app.services.output_manager import OutputManager
from server.tests.invariants.test_output_enable import enable_manager
from server.tests.support.playback import real_client

__all__ = ["real_client"]


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


def test_nas_disable_confirms_inactive_and_request_is_disabled(real_client):
    _, _, player, service = real_client

    async def run():
        player._outputs = [OutputInfo(id=37, name="DAC", plugin="alsa", enabled=True)]
        manager = enable_manager(service, player, monotonic_clock=lambda: 0.0)
        result = await manager.set_enabled(OutputMode.NAS_DAC, False)
        assert result.states[0].status == "INACTIVE"
        assert result.states[0].stale is False
        assert result.last_request.enabled is False
        assert result.last_request.status == "SUCCEEDED"
        assert (await player.outputs())[0].enabled is False

    asyncio.run(run())
