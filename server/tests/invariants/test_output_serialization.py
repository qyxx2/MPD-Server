"""O-PRESERVE-001 foundation: real transaction/playback/output coordination."""
from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from server.app.models.queue import PlaybackContext
from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.models import OutputInfo
from server.app.player.ports import PlayerUnavailable
from server.app.repositories.database import run_transaction
from server.app.services.output_manager import OutputError, OutputManager
from server.tests.invariants.assertions import assert_execution_relationship
from server.tests.support.playback import start


async def authority_snapshot(service):
    return (
        await service.queue_manager.queue_repository.get_snapshot(),
        await service.queue_manager.get_playback_state(),
        await service.history_service.list_history(),
        service.history_service.active_event,
        service.history_service.session_id,
    )


def test_output_runner_joins_outer_transaction_and_restores_history(real_client):
    client, _, _, service = real_client
    start(client)

    async def scenario():
        before = await authority_snapshot(service)
        path = service.queue_manager.queue_repository.path
        assert hasattr(service, "run_output_operation"), "B3 shared output runner is missing"

        async def operation():
            await service.queue_manager.play_next("b")
            await service.history_service.stop()
            return 17

        async def outer(_connection):
            assert await service.run_output_operation(operation) == 17
            assert await authority_snapshot(service) != before
            raise RuntimeError("outer witness failure")

        with pytest.raises(RuntimeError, match="outer witness failure"):
            await run_transaction(path, outer)
        assert await authority_snapshot(service) == before

        async def read_only():
            return await authority_snapshot(service)

        assert await service.run_output_operation(read_only) == before

    asyncio.run(scenario())


MUTATIONS = [
    "start_track", "play_context", "play_now", "play_next", "add_to_queue",
    "reorder", "clear", "delete_pending", "delete_current", "next", "previous",
    "pause", "seek", "stop", "reconcile_external_status",
]


async def playback_mutation(service, name, items):
    if name == "play_context":
        return await service.play_context(PlaybackContext(
            context_id="replacement", source_type="SONGS", ordered_song_ids=("b", "a"),
        ))
    if name == "play_now":
        return await service.play_now(items[1]["queue_item_id"])
    if name in {"start_track", "play_next", "add_to_queue"}:
        return await getattr(service, name)("b")
    if name == "reorder":
        return await service.reorder(items[2]["queue_item_id"], items[1]["queue_item_id"])
    if name.startswith("delete_"):
        return await service.delete(items[0 if name == "delete_current" else 1]["queue_item_id"])
    if name == "seek":
        return await service.seek(19)
    return await getattr(service, name)()


@pytest.mark.parametrize("name", MUTATIONS)
@pytest.mark.parametrize("first", ["output", "playback"])
def test_output_operation_serializes_with_playback_mutations(real_client, monkeypatch, name, first):
    client, _, player, service = real_client
    items = start(client)
    if name == "previous":
        asyncio.run(service.next())
    outputs_before = asyncio.run(player.outputs())

    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()
        attempted = asyncio.Event()
        output_entered = asyncio.Event()
        order = []
        blocked_once = False

        async def output():
            output_entered.set()
            order.append("output")
            if first == "output":
                entered.set()
                await release.wait()
            return "coordination witness"

        # Suspend an actual playback operation at its external read, after any
        # Queue write. A missing whole-operation transaction then leaks the lock.
        for method in ("queue_entries", "status"):
            original = getattr(player, method)

            async def blocked_read(original=original):
                nonlocal blocked_once
                if first == "playback" and not blocked_once:
                    blocked_once = True
                    order.append("playback")
                    entered.set()
                    await release.wait()
                return await original()

            monkeypatch.setattr(player, method, blocked_read)

        async def mutate():
            result = await playback_mutation(service, name, items)
            if first == "output":
                order.append("playback")
            return result

        async def contender(operation):
            attempted.set()
            return await operation()

        manager = output_manager(service, player, monotonic_clock=lambda: 0.0)

        async def output_call():
            return await manager._run_preserved_operation(output)
        leader = asyncio.create_task(output_call() if first == "output" else mutate())
        follower = None
        try:
            await asyncio.wait_for(entered.wait(), 3)
            follower = asyncio.create_task(contender(mutate if first == "output" else output_call))
            await asyncio.wait_for(attempted.wait(), 3)
            # attempted is set immediately before awaiting the operation. The
            # task yields only once blocked or finished, no timing-based sleep.
            assert not follower.done(), f"{name} escaped the shared transaction"
            if first == "playback":
                assert not output_entered.is_set(), f"output interleaved with {name}"
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(leader, *([follower] if follower else [])), 3)
        assert order == (["output", "playback"] if first == "output" else ["playback", "output"])
        assert await player.outputs() == outputs_before

    asyncio.run(scenario())
    assert_execution_relationship(service, player)


def output_manager(service, player, **kwargs):
    caps = MPDCapabilities.from_commands({"outputs", "status", "currentsong", "playlistinfo"})
    caps = replace(caps, verified_operations=frozenset({"queue_entries"}))
    return OutputManager(
        player=VerifiedPlayerPort(player, caps), capabilities=caps,
        operation_runner=service.run_output_operation, **kwargs,
    )


def test_output_guard_rejects_playback_state_drift(real_client):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        before = await authority_snapshot(service)
        manager = output_manager(service, player)
        assert hasattr(manager, "_run_preserved_operation"), "B3 preservation guard is missing"

        async def external_drift():
            await player.pause()
            return "must not report success"

        with pytest.raises(OutputError) as error:
            await manager._run_preserved_operation(external_drift)
        assert error.value.code == "OUTPUT_RECONCILIATION_FAILED"
        assert await authority_snapshot(service) == before
        assert (await player.status()).state.value == "paused"
        # OutputManager reports actual divergence; it never auto-replays/seeks.

    asyncio.run(scenario())


@pytest.mark.parametrize("state", ["paused", "stopped", "unknown"])
def test_output_guard_rejects_nonplaying_or_unknown_position_change(real_client, monkeypatch, state):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        if state == "paused":
            await service.pause()
            await service.seek(17)
        elif state == "stopped":
            await service.stop()
        original = player.status
        unknown = state == "unknown"

        async def status():
            result = await original()
            return result.model_copy(update={"elapsed_seconds": None}) if unknown else result

        monkeypatch.setattr(player, "status", status)
        before = await authority_snapshot(service)
        manager = output_manager(service, player)

        async def external_position_drift():
            nonlocal unknown
            unknown = False
            await player.seek(23)

        with pytest.raises(OutputError) as error:
            await manager._run_preserved_operation(external_position_drift)
        assert error.value.code == "OUTPUT_RECONCILIATION_FAILED"
        assert await authority_snapshot(service) == before
        assert (await original()).elapsed_seconds == 23

    asyncio.run(scenario())


@pytest.mark.parametrize("elapsed_after, wall_seconds", [(0, 2), (16, 2), (30, 2), (17, 8)])
def test_output_guard_rejects_unnatural_playing_position(real_client, elapsed_after, wall_seconds):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        await service.seek(17)
        now = 100.0
        manager = output_manager(service, player, monotonic_clock=lambda: now)
        before = await authority_snapshot(service)

        async def drift():
            nonlocal now
            now += wall_seconds
            await player.seek(elapsed_after)

        with pytest.raises(OutputError) as error:
            await manager._run_preserved_operation(drift)
        assert error.value.code == "OUTPUT_RECONCILIATION_FAILED"
        assert await authority_snapshot(service) == before
        assert (await player.status()).elapsed_seconds == elapsed_after

    asyncio.run(scenario())


@pytest.mark.parametrize("wrong", ["duplicate", "unknown-current", "wrong-id"])
def test_output_guard_rejects_unconfirmed_current_before_callback(real_client, monkeypatch, wrong):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        await service.add_to_queue("a")
        entries = await player.queue_entries()
        original = player.status

        async def status():
            current = await original()
            changes = (
                {"song_id": entries[-1].mpd_song_id, "song_position": len(entries) - 1}
                if wrong == "duplicate" else
                {"song_id": None, "song_position": None} if wrong == "unknown-current" else
                {"song_id": entries[-1].mpd_song_id}
            )
            return current.model_copy(update=changes)

        monkeypatch.setattr(player, "status", status)
        manager = output_manager(service, player, monotonic_clock=lambda: 0.0)
        called = []

        async def callback():
            called.append("must not execute with invalid baseline")

        before = await authority_snapshot(service)
        with pytest.raises(OutputError) as error:
            await manager._run_preserved_operation(callback)
        assert error.value.code == "OUTPUT_RECONCILIATION_FAILED"
        assert called == []
        assert await authority_snapshot(service) == before

    asyncio.run(scenario())


@pytest.mark.parametrize("state", ["playing", "paused", "stopped", "empty", "unknown", "natural"])
def test_output_guard_preserves_occurrence_context_and_history(real_client, monkeypatch, state):
    client, _, player, service = real_client
    if state != "empty":
        start(client)

    async def scenario():
        if state != "empty":
            await service.add_to_queue("a")  # same URI, distinct occurrence
            await service.seek(17)
        if state == "paused":
            await service.pause()
        elif state == "stopped":
            await service.stop()
        await player.set_repeat(True)
        await player.set_random(True)
        await player.set_volume(23)
        player._outputs = [OutputInfo(id=37, name="USB DAC", plugin="alsa", enabled=True)]
        original_status = player.status
        if state == "unknown":
            async def unknown_status():
                return (await original_status()).model_copy(update={"elapsed_seconds": None})
            monkeypatch.setattr(player, "status", unknown_status)
        before = await authority_snapshot(service)
        before_status = await player.status()
        entries = await player.queue_entries()
        outputs = await player.outputs()
        calls = []
        check = player._check

        def record(command):
            calls.append(command)
            check(command)

        monkeypatch.setattr(player, "_check", record)
        now = 100.0
        manager = output_manager(service, player, monotonic_clock=lambda: now)

        async def observe_only():
            nonlocal now
            if state == "natural":
                # Model external natural time, not an output seek/play command.
                player._elapsed += 2
                now += 2
            return await manager.get_state()

        result = await manager._run_preserved_operation(observe_only)
        assert result.states[0].status == "ACTIVE"
        assert result.last_request is None
        assert calls == ["status", "queue_entries", "outputs", "status", "queue_entries"]
        assert await authority_snapshot(service) == before
        assert await player.queue_entries() == entries
        assert await player.outputs() == outputs
        after = await player.status()
        assert after.model_dump(exclude={"elapsed_seconds"}) == before_status.model_dump(
            exclude={"elapsed_seconds"},
        )
        assert after.elapsed_seconds == (
            19 if state == "natural" else before_status.elapsed_seconds
        )
        if state != "empty":
            assert entries[0].song_uri == entries[-1].song_uri == "a.flac"
            assert entries[0].mpd_song_id != entries[-1].mpd_song_id

    asyncio.run(scenario())


@pytest.mark.parametrize("drift", ["occurrence", "queue-order", "queue-id", "repeat", "random", "volume"])
def test_output_guard_rejects_external_drift_without_repair(real_client, drift):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        await service.add_to_queue("a")
        before = await authority_snapshot(service)
        entries = await player.queue_entries()
        manager = output_manager(service, player, monotonic_clock=lambda: 0.0)

        async def external_drift():
            if drift == "occurrence":
                player._current_queue_id = entries[-1].mpd_song_id
            elif drift == "queue-order":
                await player.queue_move(entries[-1].mpd_song_id, entries[1].mpd_song_id)
            elif drift == "queue-id":
                player._queue[-1] = ("a.flac", 999)
            elif drift == "repeat":
                await player.set_repeat(True)
            elif drift == "random":
                await player.set_random(True)
            else:
                await player.set_volume(23)

        with pytest.raises(OutputError) as error:
            await manager._run_preserved_operation(external_drift)
        assert error.value.code == "OUTPUT_RECONCILIATION_FAILED"
        assert await authority_snapshot(service) == before
        # Retry observes a fresh baseline, not a replay of an old observation.
        # Occurrence/execution drift requires existing playback reconciliation.
        if drift in {"repeat", "random", "volume"}:
            facts = (await player.status(), await player.queue_entries())
            async def no_op():
                return 41
            assert await manager._run_preserved_operation(no_op) == 41
            assert (await player.status(), await player.queue_entries()) == facts
            assert await authority_snapshot(service) == before

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["before-read", "after-read", "callback", "cancel"])
def test_output_guard_failure_releases_transaction_and_retry_reobserves(real_client, failure):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        manager = output_manager(service, player, monotonic_clock=lambda: 0.0)
        before = await authority_snapshot(service)
        called = []
        if failure == "before-read":
            player.disconnect()

        async def callback():
            called.append("entered")
            if failure == "after-read":
                player.disconnect()
            elif failure == "callback":
                raise RuntimeError("callback witness failure")
            elif failure == "cancel":
                raise asyncio.CancelledError()

        error = (
            PlayerUnavailable if failure in {"before-read", "after-read"} else
            RuntimeError if failure == "callback" else asyncio.CancelledError
        )
        with pytest.raises(error):
            await manager._run_preserved_operation(callback)
        assert called == ([] if failure == "before-read" else ["entered"])
        player.reconnect()
        assert await authority_snapshot(service) == before

        async def retry():
            return await manager.get_state()

        # A new task proves the prior transaction context/lock was released.
        result = await asyncio.wait_for(asyncio.create_task(manager._run_preserved_operation(retry)), 3)
        assert result.last_request is None
        assert await authority_snapshot(service) == before

    asyncio.run(scenario())


def test_output_guard_brackets_status_latency_and_millisecond_precision(real_client, monkeypatch):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        await service.seek(17)
        before = await authority_snapshot(service)
        original_status = player.status
        times = iter([100.0, 101.0, 102.0, 103.0])
        status_reads = 0

        async def status():
            nonlocal status_reads
            status_reads += 1
            # Actual status sampling happened inside each measured read window.
            return (await original_status()).model_copy(update={
                "elapsed_seconds": 17.0 if status_reads == 1 else 18.001,
            })

        monkeypatch.setattr(player, "status", status)
        manager = output_manager(service, player, monotonic_clock=lambda: next(times))

        async def no_op():
            return "unchanged"

        assert await manager._run_preserved_operation(no_op) == "unchanged"
        assert status_reads == 2
        assert await authority_snapshot(service) == before

    asyncio.run(scenario())


@pytest.mark.parametrize("shared", ["status", "entries"])
def test_output_guard_keeps_independent_baseline_when_port_reuses_models(real_client, monkeypatch, shared):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        status = await player.status()
        entries = await player.queue_entries()
        before = await authority_snapshot(service)
        if shared == "status":
            async def shared_status():
                return status
            monkeypatch.setattr(player, "status", shared_status)
        else:
            async def shared_entries():
                return entries
            monkeypatch.setattr(player, "queue_entries", shared_entries)
        manager = output_manager(service, player, monotonic_clock=lambda: 0.0)

        async def external_change():
            if shared == "status":
                status.volume = 23
            else:
                entries[-1].mpd_song_id = 999

        with pytest.raises(OutputError) as error:
            await manager._run_preserved_operation(external_change)
        assert error.value.code == "OUTPUT_RECONCILIATION_FAILED"
        assert await authority_snapshot(service) == before

    asyncio.run(scenario())
