import asyncio

import pytest

from server.app.models.output import OutputMode
from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.mock_mpd import MockMPD
from server.app.player.models import OutputInfo
from server.app.services.output_manager import OutputError, OutputManager


class ObservedMPD(MockMPD):
    """Keep MockMPD behavior, recording every read and mutation boundary."""

    def __init__(self, outputs):
        super().__init__(songs=["a.flac"], outputs=outputs)
        self.calls = []

    def _check(self, command):
        self.calls.append(command)
        super()._check(command)

    def replace_outputs(self, outputs):
        self._outputs = list(outputs)


async def direct_runner(operation):
    return await operation()


async def player_facts(player):
    return (await player.outputs(), await player.queue_entries(), await player.status())


def alsa(output_id=37, enabled=True):
    return OutputInfo(id=output_id, name="USB DAC", plugin="alsa", enabled=enabled)


def invalid_selector(candidates):
    return candidates[0].model_copy(deep=True)


def throwing_selector(candidates):
    raise ValueError("selector cannot identify this device")


@pytest.mark.parametrize("case, expected", [
    ("none", "UNAVAILABLE"),
    ("single", "ACTIVE"),
    ("multiple", "UNAVAILABLE"),
    ("selected", "INACTIVE"),
    ("no-match", "UNAVAILABLE"),
    ("foreign", "UNAVAILABLE"),
    ("exception", "UNAVAILABLE"),
    ("duplicate-id", "UNAVAILABLE"),
])
def test_output_identity_and_observation_follow_current_port(case, expected):
    async def run():
        outputs = [alsa(), alsa(72, False)]
        if case == "none":
            outputs = []
        elif case == "single":
            outputs = [alsa()]
        elif case == "duplicate-id":
            outputs = [alsa(), alsa(37, False)]
        selectors = {
            "selected": lambda candidates: candidates[1],
            "no-match": lambda candidates: None,
            "foreign": invalid_selector,
            "exception": throwing_selector,
            "duplicate-id": lambda candidates: candidates[0],
        }
        seen = []
        selector = selectors.get(case)

        def select(candidates):
            seen.append(candidates)
            return selector(candidates)

        player = ObservedMPD(outputs + [
            OutputInfo(id=0, name="HTTP", plugin="httpd", enabled=True),
        ])
        await player.queue_add("a.flac")
        await player.play("a.flac")
        await player.seek(19)
        await player.pause()
        await player.set_repeat(True)
        await player.set_random(True)
        await player.set_volume(23)
        before = await player_facts(player)
        player.calls.clear()
        cap = MPDCapabilities.from_commands({"outputs"})
        manager = OutputManager(
            player=VerifiedPlayerPort(player, cap), capabilities=cap,
            operation_runner=direct_runner, selector=select if selector else None,
        )
        result = await manager.get_state()
        assert player.calls == ["outputs"]
        nas, stream = result.states
        assert nas.status == expected
        assert nas.stale is False
        assert (nas.error_code is not None) == (expected == "UNAVAILABLE")
        assert stream.status == "UNAVAILABLE"
        assert result.last_request is None
        if selector:
            assert all(candidate.plugin == "alsa" for candidate in seen[0])
        assert await player_facts(player) == before

        if case == "single":
            # The same device's current ID/fact replaces the previous observation.
            player.replace_outputs([alsa(91, False)])
            player.calls.clear()
            refreshed = await manager.get_state()
            assert refreshed.states[0].status == "INACTIVE"
            assert refreshed.states[0].stale is False
            assert player.calls == ["outputs"]
            assert result.states[0].status == "ACTIVE"

    asyncio.run(run())


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("connected", [False, True])
def test_reserved_mode_has_no_external_side_effect(enabled, connected):
    async def run():
        player = ObservedMPD([
            alsa(), OutputInfo(id=0, name="Enabled HTTPD", plugin="httpd", enabled=True),
        ])
        await player.queue_add("a.flac")
        await player.play("a.flac")
        await player.seek(17)
        before = await player_facts(player)
        cap = MPDCapabilities.from_commands({"outputs"})
        events = []

        class Publisher:
            async def publish(self, event):
                events.append(event)

        runner_calls = []

        async def runner(operation):
            runner_calls.append("entered")
            return await operation()

        manager = OutputManager(
            player=VerifiedPlayerPort(player, cap), capabilities=cap,
            operation_runner=runner, event_publisher=Publisher(),
        )
        observed = await manager.get_state()
        player.calls.clear()
        runner_calls.clear()
        if not connected:
            player.disconnect()
        for _ in range(2):
            with pytest.raises(OutputError) as error:
                await manager.set_enabled(OutputMode.CLIENT_STREAM, enabled)
            assert error.value.code == "OUTPUT_MODE_UNSUPPORTED"
        assert player.calls == []
        assert runner_calls == []
        assert events == []
        player.reconnect()
        assert await player_facts(player) == before
        refreshed = await manager.get_state()
        assert refreshed.states[0].status == observed.states[0].status == "ACTIVE"
        assert refreshed.states[1].status == "UNAVAILABLE"
        assert refreshed.last_request is None

    asyncio.run(run())


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("failure", ["disconnected", "command", "capability", "wrapper"])
def test_output_read_failure_marks_last_confirmed_fact_stale_and_retry_refreshes(cached, failure):
    async def run():
        player = ObservedMPD([alsa()])
        cap = MPDCapabilities.from_commands({"outputs"})
        manager = OutputManager(
            player=VerifiedPlayerPort(player, cap), capabilities=cap,
            operation_runner=direct_runner,
        )
        previous = await manager.get_state() if cached else None
        player.calls.clear()
        if failure == "disconnected":
            player.disconnect()
        elif failure == "command":
            player.fail_next("outputs", "outputs rejected")
        elif failure == "capability":
            manager.capabilities = MPDCapabilities.from_commands(set())
        else:
            manager.player = VerifiedPlayerPort(player, MPDCapabilities.from_commands(set()))
        failed = await manager.get_state()
        nas = failed.states[0]
        assert nas.status == ("ACTIVE" if cached else "UNAVAILABLE")
        assert nas.stale is True
        assert nas.error_code is not None
        assert nas.error_message
        assert player.calls == ([] if failure in {"capability", "wrapper"} else ["outputs"])
        assert failed.last_request is None
        if cached:
            assert nas.updated_at == previous.states[0].updated_at
            assert previous.states[0].stale is False
            assert previous.states[0].error_code is None
        player.reconnect()
        manager.capabilities = cap
        manager.player = VerifiedPlayerPort(player, cap)
        player.replace_outputs([alsa(91, False)])
        player.calls.clear()
        retried = await manager.get_state()
        assert retried.states[0].status == "INACTIVE"
        assert retried.states[0].stale is False
        assert retried.states[0].error_code is None
        assert player.calls == ["outputs"]

    asyncio.run(run())
