from __future__ import annotations

import pytest

from server.app.models.library import Song
from server.app.models.queue import PlaybackContext
from server.app.repositories.database import run_transaction
from server.app.repositories.queue_repository import QueueRevisionConflictError
from server.app.services.playback_service import PlaybackReconciliationError
from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_d6_recovery import capture_controls
from server.tests.support.playback import run


def prepare(real_client, *, played=False, duplicate=False):
    _, library, player, service = real_client
    run(library.upsert_song(Song(song_id="d", title="d", file_uri="d.flac")))
    if played:
        run(service.start_track("d"))
    run(service.play_context(PlaybackContext(
        context_id="s6", source_type="SONGS", ordered_song_ids=("a", "b", "c", "d"),
    )))
    if duplicate:
        response = run(service.add_to_queue("a"))
        assert response is not None
    queue = run(service.queue_manager.get_snapshot())
    execution = sorted((i for i in queue.items if i.position >= 0), key=lambda i: i.position)
    binding = run(service.get_execution_binding())
    return player, service, queue, execution, binding


def assert_adopted(service, player, before, execution, binding, target):
    queue, state, history, active, session = server_snapshot(service)
    old_queue, old_state, old_history, _, old_session = before
    expected = [execution[target], *[i for i in execution[1:] if i != execution[target]]]
    positions = {i.queue_item_id: i.position for i in queue.items}
    assert positions[execution[0].queue_item_id] == -1
    assert [i.queue_item_id for i in sorted((i for i in queue.items if i.position >= 0), key=lambda i: i.position)] == [i.queue_item_id for i in expected]
    for index, item in enumerate(expected):
        assert positions[item.queue_item_id] == index
    old_played = {i.queue_item_id: i for i in old_queue.items if i.position < 0}
    new_played = {i.queue_item_id: i for i in queue.items if i.position < -1}
    assert new_played.keys() == old_played.keys()
    for item_id, item in old_played.items():
        assert new_played[item_id].position == item.position - 1
    assert queue.revision == old_queue.revision + 1
    assert {(i.queue_item_id, i.song_id, i.source, i.playback_context_id) for i in queue.items} == {(i.queue_item_id, i.song_id, i.source, i.playback_context_id) for i in old_queue.items}
    assert history == old_history and active is None and session == old_session
    assert state.song_id == execution[target].song_id
    assert state.autoplay_enabled == old_state.autoplay_enabled
    assert state.playback_context_id == old_state.playback_context_id
    new_binding = run(service.get_execution_binding())
    old_ids = {item_id: mpd_id for item_id, mpd_id, _ in binding.entries}
    assert new_binding.entries == tuple((i.queue_item_id, old_ids[i.queue_item_id], run(service.library_repository.get_song(i.song_id)).file_uri) for i in expected)
    assert new_binding.queue_revision == queue.revision
    sample = run(player.read_execution_sample())
    assert sample.status.song_id == old_ids[execution[target].queue_item_id]
    assert sample.status.song_position == 0
    assert state.state == sample.status.state.value.upper()
    assert tuple(e.mpd_song_id for e in sample.entries) == tuple(e[1] for e in new_binding.entries)


@pytest.mark.parametrize("target", [1, 2], ids=["b", "c"])
@pytest.mark.parametrize("played", [False, True], ids=["no-played", "existing-played"])
@pytest.mark.parametrize("paused", [False, True], ids=["playing", "paused"])
@pytest.mark.parametrize("duplicate", [False, True], ids=["distinct", "duplicate-uri"])
def test_current_adoption_preserves_unobserved_manual_occurrences(real_client, monkeypatch, target, played, paused, duplicate):
    player, service, _, execution, binding = prepare(real_client, played=played, duplicate=duplicate)
    run(player.queue_play(binding.entries[target][1]))
    if paused:
        run(player.pause())
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    result = run(service.reconcile_external_status())
    assert result.outcome == "APPLIED" and not result.reconciliation_required
    assert_adopted(service, player, before, execution, binding, target)
    assert all(name in {"queue_delete", "queue_move"} for name, _, _ in controls)
    controls.clear()
    committed = server_snapshot(service)
    assert run(service.reconcile_external_status()).outcome == "UNCHANGED"
    assert server_snapshot(service) == committed and controls == []


@pytest.mark.parametrize("cause", ["natural-like", "seek-end", "seek-remainder", "external-next", "playid", "seekid", "decoder-error", "input-error", "output-error", "same-entry-replay"])
def test_current_fact_never_claims_cause(real_client, monkeypatch, cause):
    player, service, _, execution, binding = prepare(real_client)
    # These inputs deliberately have the same observable facts; no fake causal proof.
    target = 0 if cause == "same-entry-replay" else 1
    run(player.queue_play(binding.entries[target][1]))
    if cause.startswith("seek"):
        run(player.seek(180 if cause == "seek-end" else 20))
    if cause.endswith("error"):
        read = player.read_execution_sample

        async def error_sample():
            return (await read()).model_copy(update={"error": cause})

        monkeypatch.setattr(player, "read_execution_sample", error_sample)
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    result = run(service.reconcile_external_status())
    assert result.outcome == ("UNCHANGED" if target == 0 else "APPLIED")
    assert run(service.history_service.list_history()) == before[2]
    claimed_reason = getattr(result, "reason", None)
    assert claimed_reason is None
    if target == 0:
        assert server_snapshot(service) == before
    else:
        assert_adopted(service, player, before, execution, binding, target)
    assert not any(name in {"play", "queue_play", "seek", "next"} for name, _, _ in controls)


@pytest.mark.parametrize("drift", ["stop", "foreign", "queue-edit", "id-reuse", "late-sample", "queue-cas", "new-current-during-cleanup"])
def test_stop_foreign_drift_and_concurrent_mutation_fail_closed(real_client, monkeypatch, drift):
    player, service, _, _, binding = prepare(real_client)
    run(player.queue_play(binding.entries[2][1]))
    if drift == "stop":
        run(player.stop())
    elif drift == "foreign":
        player._songs.append("outside.flac")
        player._durations["outside.flac"] = 180
        run(player.play("outside.flac"))
    elif drift == "queue-edit":
        run(player.queue_add("a.flac"))
    elif drift == "id-reuse":
        player._queue[2] = ("d.flac", binding.entries[2][1])
    elif drift == "late-sample":
        read = player.read_execution_sample

        async def late():
            sample = await read()
            service._recovery.advance()
            return sample

        monkeypatch.setattr(player, "read_execution_sample", late)
    elif drift == "queue-cas":
        adopt = service.queue_manager.queue_repository

        async def stale(*args, **kwargs):
            raise QueueRevisionConflictError(kwargs["expected_revision"], kwargs["expected_revision"] + 1)

        monkeypatch.setattr(adopt, "adopt_current", stale, raising=False)
    else:
        delete = player.queue_delete

        async def progressed(mpd_id):
            await delete(mpd_id)
            await player.queue_play(binding.entries[3][1])

        monkeypatch.setattr(player, "queue_delete", progressed)
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    try:
        result = run(service.reconcile_external_status())
    except (PlaybackReconciliationError, QueueRevisionConflictError):
        result = None
    else:
        assert result.outcome == "UNKNOWN" and result.reconciliation_required
    assert server_snapshot(service) == before
    if drift not in {"queue-cas", "new-current-during-cleanup"}:
        assert controls == []
    else:
        assert not any(name in {"play", "seek", "next"} for name, _, _ in controls)
    controls.clear()
    retry = run(service.reconcile_external_status())
    assert retry.outcome == "UNKNOWN" and retry.reconciliation_required
    assert server_snapshot(service) == before and controls == []


def test_adoption_outer_rollback_retries_fixed_target_without_replay(real_client, monkeypatch):
    player, service, _, execution, binding = prepare(real_client)
    run(player.queue_play(binding.entries[2][1]))
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)

    async def failed(_):
        result = await service.reconcile_external_status()
        assert result.outcome == "APPLIED"
        assert service._recovery.get_execution_receipt(result.transition_id) is None
        raise RuntimeError("outer")

    with pytest.raises(RuntimeError, match="outer"):
        run(run_transaction(service.queue_manager.queue_repository.path, failed))
    assert server_snapshot(service) == before
    prefix = list(controls)
    result = run(service.reconcile_external_status())
    assert result.outcome == "APPLIED" and controls == prefix
    assert_adopted(service, player, before, execution, binding, 2)
    assert service._recovery.get_execution_receipt(result.transition_id).outcome == "REPLAYED"


def test_cleanup_barrier_rejects_a_new_mpd_current(real_client, monkeypatch):
    import asyncio

    player, service, _, _, binding = prepare(real_client)
    run(player.queue_play(binding.entries[2][1]))
    before = server_snapshot(service)
    delete = player.queue_delete
    controls = capture_controls(monkeypatch, player)

    async def scenario():
        deleted, advanced = asyncio.Event(), asyncio.Event()

        async def blocked_delete(mpd_id):
            await delete(mpd_id)
            deleted.set()
            await advanced.wait()

        async def external():
            await deleted.wait()
            await player.queue_play(binding.entries[3][1])
            advanced.set()

        monkeypatch.setattr(player, "queue_delete", blocked_delete)
        progression = asyncio.create_task(external())
        result = await service.reconcile_external_status()
        await progression
        return result

    result = run(scenario())
    assert result.outcome == "UNKNOWN" and result.reconciliation_required
    assert server_snapshot(service) == before
    assert run(player.read_execution_sample()).status.song_id == binding.entries[3][1]
    assert not any(name == "queue_move" for name, _, _ in controls)
    assert not any(key.endswith("/adopt") for key in service._recovery.execution_receipts)


def test_late_sample_after_a_committed_writer_keeps_new_business(real_client, monkeypatch):
    import asyncio

    player, service, _, execution, binding = prepare(real_client)
    run(player.queue_play(binding.entries[2][1]))
    old_sample = run(player.read_execution_sample())
    controls = capture_controls(monkeypatch, player)

    async def business():
        return (await service.queue_manager.get_snapshot(), await service.queue_manager.get_playback_state(),
                await service.history_service.list_history(), service.history_service.active_event,
                service.history_service.session_id)

    async def scenario():
        committed, queued, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        baseline = None
        cutoff = None

        async def writer(_):
            nonlocal baseline, cutoff
            await service.play_now(execution[3].queue_item_id)
            baseline = await business()
            cutoff = len(controls)
            committed.set()
            await release.wait()

        async def late_sample():
            return old_sample

        async def recovery():
            await committed.wait()
            monkeypatch.setattr(player, "read_execution_sample", late_sample)
            queued.set()
            return await service.reconcile_external_status()

        first = asyncio.create_task(run_transaction(service.queue_manager.queue_repository.path, writer))
        second = asyncio.create_task(recovery())
        await queued.wait()
        assert not second.done()
        release.set()
        await first
        result = await second
        assert await business() == baseline
        assert len(controls) == cutoff
        return result, baseline

    result, baseline = run(scenario())
    assert result.outcome == "UNKNOWN" and result.reconciliation_required
    assert server_snapshot(service) == baseline
    assert baseline[1].song_id == "d"


def test_queue_adoption_cas_and_invalid_targets_are_atomic(real_client):
    _, service, queue, execution, _ = prepare(real_client, played=True)
    repository = service.queue_manager.queue_repository
    with pytest.raises(QueueRevisionConflictError):
        run(repository.adopt_current(execution[0].queue_item_id, execution[2].queue_item_id,
                                     expected_revision=queue.revision - 1))
    assert run(repository.get_snapshot()) == queue
    played = next(i for i in queue.items if i.position < 0)
    for previous, target in [(execution[1].queue_item_id, execution[2].queue_item_id),
                             (execution[0].queue_item_id, played.queue_item_id),
                             (execution[0].queue_item_id, execution[0].queue_item_id),
                             (execution[0].queue_item_id, "foreign")]:
        with pytest.raises(ValueError):
            run(repository.adopt_current(previous, target, expected_revision=queue.revision))
        assert run(repository.get_snapshot()) == queue


@pytest.mark.parametrize("failure", ["queue-write", "state-write", "materialization", "outer", "precommit-cancel"])
def test_adoption_business_failure_restores_runtime_and_owned_retry(real_client, monkeypatch, failure):
    import asyncio

    from server.app.models.recovery import RecoveryResult
    from server.app.services import playback_recovery
    from server.app.services.realtime_coordinator import RealtimeCoordinator

    player, service, _, execution, binding = prepare(real_client)
    run(player.queue_play(binding.entries[2][1]))
    before = server_snapshot(service)
    generation = service._recovery.business_generation
    service._coordinator = RealtimeCoordinator(service.queue_manager.queue_repository.path)
    subscriber = service._coordinator.subscribe()
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service._event_publisher = Publisher()
    controls = capture_controls(monkeypatch, player)

    async def explode(*args, **kwargs):
        raise RuntimeError("injected failure")

    with monkeypatch.context() as fault:
        if failure == "queue-write":
            fault.setattr(service.queue_manager, "adopt_current", explode)
        elif failure == "state-write":
            fault.setattr(service.queue_manager.playback_state_repository, "save", explode)
        elif failure == "materialization":
            copy = playback_recovery.deepcopy

            def fail_copy(value):
                if isinstance(value, RecoveryResult):
                    raise TypeError("injected failure")
                return copy(value)

            fault.setattr(playback_recovery, "deepcopy", fail_copy)

        async def attempt(_):
            await service.reconcile_external_status()
            if failure == "outer":
                raise RuntimeError("injected failure")
            if failure == "precommit-cancel":
                raise asyncio.CancelledError()

        expected = (asyncio.CancelledError if failure == "precommit-cancel"
                    else TypeError if failure == "materialization" else RuntimeError)
        with pytest.raises(expected):
            run(run_transaction(service.queue_manager.queue_repository.path, attempt))
    assert server_snapshot(service) == before
    assert service._recovery.business_generation == generation
    assert service._recovery.binding == binding
    assert subscriber.pending is None and events == []
    assert not any(key.endswith("/adopt") for key in service._recovery.execution_receipts)
    prefix = list(controls)
    result = run(service.reconcile_external_status())
    assert result.outcome == "APPLIED" and controls == prefix
    assert_adopted(service, player, before, execution, binding, 2)
    assert service._recovery.business_generation == generation + 1
    assert subscriber.pending is not None
    assert len(events) == 1


@pytest.mark.parametrize("command", ["delete", "move"])
@pytest.mark.parametrize("failure", ["after-ack", "after-confirm", "lost-response"])
def test_adoption_retries_only_the_owned_cleanup_suffix(real_client, monkeypatch, command, failure):
    import asyncio

    player, service, _, execution, binding = prepare(real_client)
    run(player.queue_play(binding.entries[2][1]))
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    journal = service._recovery
    with monkeypatch.context() as fault:
        if failure == "lost-response":
            method = getattr(player, f"queue_{command}")

            async def lost(*args):
                await method(*args)
                raise asyncio.CancelledError()

            fault.setattr(player, f"queue_{command}", lost)
        else:
            record = journal.record_command

            def interrupted(operation_id, index, receipt):
                record(operation_id, index, receipt)
                if (journal.execution_intents[operation_id].commands[index].kind == command
                        and receipt.phase == failure.removeprefix("after-").replace("confirm", "confirmed")):
                    raise asyncio.CancelledError()

            fault.setattr(journal, "record_command", interrupted)
        with pytest.raises(asyncio.CancelledError):
            run(service.reconcile_external_status())
    assert server_snapshot(service) == before
    intent = next(intent for key, intent in journal.execution_intents.items() if key.endswith("/adopt"))
    assert journal.get_execution_receipt(intent.operation_id) is None
    result = run(service.reconcile_external_status())
    assert result.outcome == "APPLIED"
    assert journal.execution_intents[intent.operation_id] == intent
    assert [name for name, _, _ in controls] == ["queue_delete", "queue_move"]
    assert_adopted(service, player, before, execution, binding, 2)


@pytest.mark.parametrize("mode", ["random", "repeat", "single", "consume"])
def test_adoption_in_unsupported_modes_sends_no_controls(real_client, monkeypatch, mode):
    player, service, _, _, binding = prepare(real_client)
    run(player.queue_play(binding.entries[2][1]))
    if mode in {"random", "repeat"}:
        run(getattr(player, f"set_{mode}")(True))
    else:
        read = player.read_execution_sample

        async def unsupported():
            return (await read()).model_copy(update={mode: "1" if mode == "single" else True})

        monkeypatch.setattr(player, "read_execution_sample", unsupported)
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    result = run(service.reconcile_external_status())
    assert result.outcome == "UNKNOWN" and result.reconciliation_required
    assert controls == [] and server_snapshot(service) == before


def test_transport_confirmation_rejects_a_changed_business_generation(real_client, monkeypatch):
    player, service, _, _, _ = prepare(real_client)
    run(player.pause())
    before = server_snapshot(service)
    sample = player.read_execution_sample
    reads = 0

    async def late_confirmation():
        nonlocal reads
        reads += 1
        actual = await sample()
        if reads == 2:
            service._recovery.advance()
        return actual

    monkeypatch.setattr(player, "read_execution_sample", late_confirmation)
    controls = capture_controls(monkeypatch, player)
    with pytest.raises(PlaybackReconciliationError, match="confirmation"):
        run(service.reconcile_external_status())
    assert server_snapshot(service) == before and controls == []


def test_same_uri_target_is_adopted_by_distinct_occurrence_id(real_client, monkeypatch):
    player, service, _, execution, binding = prepare(real_client, duplicate=True)
    target = len(execution) - 1
    assert execution[target].song_id == execution[0].song_id == "a"
    assert binding.entries[target][2] == binding.entries[0][2]
    assert binding.entries[target][1] != binding.entries[0][1]
    run(player.queue_play(binding.entries[target][1]))
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    result = run(service.reconcile_external_status())
    assert result.outcome == "APPLIED"
    assert_adopted(service, player, before, execution, binding, target)
    assert [name for name, _, _ in controls] == ["queue_delete", "queue_move"]


@pytest.mark.parametrize("failure", ["discard", "publisher"])
def test_adoption_history_discard_and_publisher_boundaries(real_client, monkeypatch, failure):
    player, service, _, execution, binding = prepare(real_client)
    run(player.queue_play(binding.entries[2][1]))
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)

    async def explode(*args, **kwargs):
        raise RuntimeError("boundary failure")

    if failure == "discard":
        with monkeypatch.context() as fault:
            fault.setattr(service.history_service, "discard_unconfirmed_active", explode)
            with pytest.raises(RuntimeError, match="boundary failure"):
                run(service.reconcile_external_status())
        assert server_snapshot(service) == before
        assert service._recovery.binding == binding
        assert not any(key.endswith("/adopt") for key in service._recovery.execution_receipts)
        controls.clear()
    else:
        class Publisher:
            publish = staticmethod(explode)

        service._event_publisher = Publisher()
    result = run(service.reconcile_external_status())
    assert result.outcome == "APPLIED"
    if failure == "discard":
        assert controls == []
    assert_adopted(service, player, before, execution, binding, 2)
    receipt = service._recovery.get_execution_receipt(result.transition_id)
    assert receipt.outcome == "REPLAYED"
    controls.clear()
    assert run(service.reconcile_external_status()).outcome == "UNCHANGED"
    assert controls == []


@pytest.mark.parametrize("outer_failure", [False, True], ids=["commit", "rollback-retry"])
def test_paused_current_delete_confirms_explicit_successor(real_client, monkeypatch, outer_failure):
    player, service, _, execution, binding = prepare(real_client)
    run(service.pause())
    before = server_snapshot(service)
    assert before[1].state == "PAUSED"
    generation = service._recovery.business_generation
    controls = capture_controls(monkeypatch, player)

    if outer_failure:
        async def fail(_):
            await service.delete(execution[0].queue_item_id)
            assert (await service.queue_manager.get_playback_state()).state == "PLAYING"
            raise RuntimeError("outer delete failure")

        with pytest.raises(RuntimeError, match="outer delete failure"):
            run(run_transaction(service.queue_manager.queue_repository.path, fail))
        assert server_snapshot(service) == before
        assert service._recovery.business_generation == generation
        assert service._recovery.binding == binding
        prefix = list(controls)
    else:
        prefix = None

    promoted = run(service.delete(execution[0].queue_item_id))
    assert promoted.queue_item_id == execution[1].queue_item_id
    if outer_failure:
        assert controls == prefix
    queue, state, history, active, session = server_snapshot(service)
    assert state.state == "PLAYING" and state.song_id == "b"
    assert state.autoplay_enabled == before[1].autoplay_enabled
    assert state.playback_context_id == before[1].playback_context_id
    assert queue.revision == before[0].revision + 1
    assert next(i for i in queue.items if i.queue_item_id == execution[0].queue_item_id).position == -1
    assert [i.queue_item_id for i in sorted((i for i in queue.items if i.position >= 0), key=lambda i: i.position)] == [i.queue_item_id for i in execution[1:]]
    assert [(event.song_id, event.reason) for event in history] == [("a", "SWITCH_AWAY")]
    assert active.song_id == "b" and session == before[4]
    assert service._recovery.business_generation == generation + 1
    sample = run(player.read_execution_sample())
    assert sample.status.state.value == "playing" and sample.status.song_position == 0
    assert sample.status.song_id == binding.entries[1][1]
    assert sum(name in {"play", "queue_play"} for name, _, _ in controls) == 1
    assert not any(name in {"pause", "seek", "next"} for name, _, _ in controls)
