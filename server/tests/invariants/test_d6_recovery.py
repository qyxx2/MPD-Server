from __future__ import annotations

import sqlite3
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from server.app.models.recovery import CompletionEvidence
from server.app.player.models import PlayerState
from server.app.player.ports import PlayerCommandError, PlayerUnavailable
from server.tests.invariants.assertions import server_snapshot
from server.tests.support.playback import run, start


def test_unclassified_external_stop_does_not_fabricate_history(real_client):
    """P §8.8 / PB-HISTORY-001: status alone cannot prove user Stop intent."""
    client, _, player, service = real_client
    start(client)
    queue = run(service.queue_manager.get_snapshot())
    state = run(service.queue_manager.get_playback_state())
    history = run(service.history_service.get_availability())
    assert state is not None and state.autoplay_enabled
    assert history.active_event is not None and history.session_id is not None
    assert run(service.history_service.list_history()) == []

    # External control: no PlaybackService.stop or user Stop request exists.
    # The service receives only transport status, with no causal evidence.
    run(player.stop())
    assert run(player.status()).state == PlayerState.STOPPED
    run(service.reconcile_external_status())

    after = run(service.queue_manager.get_playback_state())
    assert after is not None
    actual = {
        "events": run(service.history_service.list_history()),
        "history": run(service.history_service.get_availability()),
        "autoplay_enabled": after.autoplay_enabled,
        "context_id": after.playback_context_id,
        "queue": run(service.queue_manager.get_snapshot()),
    }
    assert actual == {
        "events": [],
        "history": history,
        "autoplay_enabled": True,
        "context_id": state.playback_context_id,
        "queue": queue,
    }


def authorities(service):
    """All durable tables plus rollback-sensitive History and binding."""
    with sqlite3.connect(service.queue_manager.queue_repository.path) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        durable = tuple(
            (name, connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall())
            for (name,) in tables
        )
    return durable, server_snapshot(service), service._observations.binding


def capture_controls(monkeypatch, player):
    controls = []
    for name in ("play", "pause", "stop", "next", "previous", "seek",
                 "queue_add", "queue_move", "queue_delete", "queue_clear", "queue_play"):
        original = getattr(player, name)

        async def record(*args, _name=name, _original=original, **kwargs):
            controls.append((_name, args, kwargs))
            return await _original(*args, **kwargs)

        monkeypatch.setattr(player, name, record)
    return controls


@pytest.mark.parametrize("drift", [
    "stop", "foreign", "duplicate", "missing-id", "queue-mismatch",
    "unbound", "elapsed-at-end", "pending-duplicate",
])
def test_unknown_recovery_preserves_all_authorities(real_client, monkeypatch, drift):
    """Rejecting only STOPPED would still accept foreign/ambiguous occurrences."""
    client, _, player, service = real_client
    start(client)
    if drift in {"stop", "elapsed-at-end"}:
        run(player.stop())
    elif drift == "foreign":
        run(player.play("b.flac"))
    elif drift == "duplicate":
        run(player.queue_delete(run(player.queue_entries())[0].mpd_song_id))
        new_id = run(player.queue_add("a.flac"))
        run(player.queue_move(new_id, run(player.queue_entries())[0].mpd_song_id))
        run(player.play("a.flac"))
    elif drift == "queue-mismatch":
        run(player.queue_add("d.flac"))
    elif drift == "unbound":
        service._observations.binding = None
    elif drift == "pending-duplicate":
        entries = run(player.queue_entries())
        run(player.queue_delete(entries[1].mpd_song_id))
        new_id = run(player.queue_add("b.flac"))
        run(player.queue_move(new_id, run(player.queue_entries())[1].mpd_song_id))
    if drift in {"missing-id", "elapsed-at-end"}:
        original = player.status

        async def status():
            actual = await original()
            return actual.model_copy(update=(
                {"song_id": None} if drift == "missing-id" else
                {"elapsed_seconds": actual.duration_seconds}
            ))

        monkeypatch.setattr(player, "status", status)
    before = authorities(service)
    controls = capture_controls(monkeypatch, player)
    for _ in range(2):
        result = run(service.reconcile_external_status())
        assert result.outcome == "UNKNOWN"
        assert result.reconciliation_required is True
        assert result.playback == before[1][1]
        assert result.transition_id is None
        assert authorities(service) == before
        assert controls == []


@pytest.mark.parametrize("failure", ["unavailable", "status", "queue_entries", "validator-unavailable", "validator-command"])
def test_recovery_source_failure_preserves_authorities(real_client, monkeypatch, failure):
    """Read errors must propagate rather than publishing fabricated success."""
    client, _, player, service = real_client
    start(client)
    before = authorities(service)
    evidence = None
    if failure.startswith("validator-"):
        evidence = evidence_for(service, player)
        expected = PlayerUnavailable if failure == "validator-unavailable" else PlayerCommandError

        class FailingSource:
            async def validate(self, evidence, baseline):
                if failure == "validator-unavailable":
                    raise PlayerUnavailable("source unavailable")
                raise PlayerCommandError("completion", "source command failed")

        service._completion_validator = FailingSource()
    elif failure == "unavailable":
        player.disconnect()
        expected = PlayerUnavailable
    else:
        player.fail_next(failure, "source failure")
        expected = PlayerCommandError
    controls = capture_controls(monkeypatch, player)
    with pytest.raises(expected):
        run(service.reconcile_external_status(evidence=evidence))
    assert authorities(service) == before
    assert controls == []


class TestCompletionValidator:
    """Deterministic test source only; cannot vouch for production MPD causes."""

    async def validate(self, evidence, baseline):
        return (
            evidence.source_id == "test-only" and evidence.source_epoch == "test-source-1"
            and evidence.continuity_token == "continuous"
        )


@pytest.mark.parametrize("pending", ["available", "missing", "unreadable", "absent", "already-playing", "confirmation-fails"])
def test_natural_completion_promotes_confirmed_successor(real_client, monkeypatch, pending):
    from server.app.services.playback_service import PlaybackReconciliationError

    client, library, player, service = real_client
    start(client)
    service._completion_validator = TestCompletionValidator()
    if pending in {"missing", "unreadable", "absent"}:
        song = run(library.get_song("b"))
        # Absent lookup is injected at the Library boundary, not in the consumer.
        if pending == "absent":
            original = library.get_song

            async def lookup(song_id):
                return None if song_id == "b" else await original(song_id)

            monkeypatch.setattr(service.library_repository, "get_song", lookup)
        else:
            run(library.upsert_song(song.model_copy(update={"availability_status": pending.upper()})))
    evidence = evidence_for(service, player)
    before = server_snapshot(service)
    target = "c" if pending in {"missing", "unreadable", "absent"} else "b"
    target_item = next(i for i in before[0].items if i.song_id == target)
    if pending == "already-playing":
        run(player.queue_play(run(player.queue_entries())[1].mpd_song_id))
    else:
        run(player.stop())
    controls = capture_controls(monkeypatch, player)
    if pending == "confirmation-fails":
        original = player.status

        async def wrong():
            actual = await original()
            return actual.model_copy(update={"song_id": 999}) if actual.state == PlayerState.PLAYING else actual

        monkeypatch.setattr(player, "status", wrong)
        with pytest.raises(PlaybackReconciliationError):
            run(service.reconcile_external_status(evidence=evidence))
        assert server_snapshot(service) == before
        return
    result = run(service.reconcile_external_status(evidence=evidence))
    assert result.outcome == "APPLIED"
    after = server_snapshot(service)
    assert [(e.song_id, e.reason) for e in after[2]] == [("a", "NATURAL_COMPLETION")]
    assert after[3].song_id == target and after[4] == before[4]
    assert after[3].started_at >= evidence.ended_at
    assert after[1].playback_context_id == before[1].playback_context_id
    assert after[1].autoplay_enabled is True
    assert after[0].revision == before[0].revision + 1
    assert next(i for i in after[0].items if i.queue_item_id == evidence.queue_item_id).position == -1
    current = next(i for i in after[0].items if i.position == 0)
    assert current.queue_item_id == target_item.queue_item_id
    assert current.source == target_item.source and current.playback_context_id == target_item.playback_context_id
    assert not any(name in {"stop", "next", "play"} for name, _, _ in controls)
    if pending == "already-playing":
        assert not any(name == "queue_play" for name, _, _ in controls)


@pytest.mark.parametrize("candidate", ["autoplay", "one-song"])
def test_natural_completion_refills_once(real_client, monkeypatch, candidate):
    client, library, player, service = real_client
    start(client)
    run(service.clear())
    # clear refills by its own frozen contract; remove pending via the Queue facade
    # then establish an actual committed execution binding before completion.
    run(service.queue_manager.clear())
    if candidate == "one-song":
        for song_id in "bc":
            song = run(library.get_song(song_id))
            run(library.upsert_song(song.model_copy(update={"availability_status": "MISSING"})))
    async def confirm(_):
        await service._sync_player_queue()
        await service._confirm_preserved_state()
    from server.app.repositories.database import run_transaction
    run(run_transaction(library.path, confirm))
    service._completion_validator = TestCompletionValidator()
    evidence = evidence_for(service, player)
    before = server_snapshot(service)
    run(player.stop())
    controls = capture_controls(monkeypatch, player)
    result = run(service.reconcile_external_status(evidence=evidence))
    assert result.outcome == "APPLIED"
    after = server_snapshot(service)
    current = next(i for i in after[0].items if i.position == 0)
    assert current.song_id == ("a" if candidate == "one-song" else "b")
    assert current.source == "AUTOPLAY" and current.queue_item_id != evidence.queue_item_id
    assert [(e.song_id, e.reason) for e in after[2]] == [("a", "NATURAL_COMPLETION")]
    assert after[4] == before[4] and after[1].autoplay_enabled is True
    controls.clear()
    replay = run(service.reconcile_external_status(evidence=evidence))
    assert replay.outcome == "REPLAYED" and replay.playback == result.playback
    assert server_snapshot(service) == after and controls == []


def test_natural_completion_without_candidates_retains_session(real_client, monkeypatch):
    client, library, player, service = real_client
    start(client)
    for song_id in "abc":
        song = run(library.get_song(song_id))
        run(library.upsert_song(song.model_copy(update={"availability_status": "MISSING"})))
    service._completion_validator = TestCompletionValidator()
    evidence = evidence_for(service, player)
    before = server_snapshot(service)
    run(player.stop())
    controls = capture_controls(monkeypatch, player)
    result = run(service.reconcile_external_status(evidence=evidence))
    assert result.outcome == "APPLIED"
    after = server_snapshot(service)
    assert (after[1].state, after[1].song_id, after[1].position_seconds, after[1].autoplay_enabled) == ("STOPPED", None, None, True)
    assert after[3] is None and after[4] == before[4]
    assert after[1].playback_context_id == before[1].playback_context_id
    assert not any(i.position >= 0 for i in after[0].items)
    assert next(i for i in after[0].items if i.queue_item_id == evidence.queue_item_id).position == -1
    assert [(e.song_id, e.reason) for e in after[2]] == [("a", "NATURAL_COMPLETION")]
    assert run(player.status()).state == PlayerState.STOPPED and run(player.queue_entries()) == []
    assert not any(name in {"stop", "play", "queue_play", "next"} for name, _, _ in controls)
    from server.tests.invariants.assertions import assert_execution_relationship
    assert_execution_relationship(service, player)
    controls.clear()
    assert run(service.reconcile_external_status(evidence=evidence)).outcome == "REPLAYED"
    assert server_snapshot(service) == after and controls == []
    run(service.stop())
    assert service.history_service.session_id is None
    assert run(service.queue_manager.get_playback_state()).autoplay_enabled is False
    assert run(service.history_service.list_history()) == list(after[2])


@pytest.mark.parametrize("correct", [True, False])
def test_duplicate_song_completion_uses_occurrence_identity(real_client, monkeypatch, correct):
    from server.app.models.queue import PlaybackContext

    _, _, player, service = real_client
    run(service.play_context(PlaybackContext(context_id="duplicates", source_type="SONGS", ordered_song_ids=("a", "a", "b"))))
    service._completion_validator = TestCompletionValidator()
    evidence = evidence_for(service, player)
    before = server_snapshot(service)
    if not correct:
        evidence = replace(evidence, queue_item_id=next(i.queue_item_id for i in before[0].items if i.position == 1))
    run(player.stop())
    controls = capture_controls(monkeypatch, player)
    result = run(service.reconcile_external_status(evidence=evidence))
    assert result.outcome == ("APPLIED" if correct else "UNKNOWN")
    if correct:
        after = server_snapshot(service)
        assert next(i for i in after[0].items if i.position == 0).queue_item_id == next(i for i in before[0].items if i.position == 1).queue_item_id
        assert [(e.song_id, e.reason) for e in after[2]] == [("a", "NATURAL_COMPLETION")]
        assert after[3].song_id == "a" and after[4] == before[4]
    else:
        assert server_snapshot(service) == before and controls == []


def evidence_for(service, player, **updates):
    queue = run(service.queue_manager.get_snapshot())
    current = next(item for item in queue.items if item.position == 0)
    journal = getattr(service, "_recovery", None)
    evidence = CompletionEvidence(
        service_epoch=journal.service_epoch if journal else "not-created",
        source_id="test-only", source_epoch="test-source-1", continuity_token="continuous",
        business_generation=journal.business_generation if journal else 0,
        queue_revision=queue.revision, queue_item_id=current.queue_item_id,
        mpd_song_id=run(player.queue_entries())[0].mpd_song_id,
        transition_id="completion-1",
        ended_at=service.history_service.active_event.started_at + timedelta(seconds=1),
    )
    return replace(evidence, **updates)


@pytest.mark.parametrize("invalid", [
    "epoch", "generation", "occurrence", "source-continuity", "restart",
    "missing-active", "invalid-time", "default-validator",
])
def test_recovery_rejects_stale_evidence(real_client, monkeypatch, invalid):
    """Evidence cannot bypass generation/binding checks via an ordinary pause."""
    client, _, player, service = real_client
    start(client)
    if invalid != "default-validator":
        service._completion_validator = TestCompletionValidator()
    evidence = evidence_for(service, player)
    updates = {
        "epoch": {"service_epoch": "old-process"},
        "generation": {"business_generation": -1},
        "occurrence": {"queue_item_id": "other-occurrence"},
        "source-continuity": {"continuity_token": "disconnected"},
        "invalid-time": {"ended_at": service.history_service.active_event.started_at - timedelta(seconds=1)},
    }
    evidence = replace(evidence, **updates.get(invalid, {}))
    if invalid == "missing-active":
        service.history_service._active = None
    elif invalid == "restart":
        from server.app.services.playback_service import PlaybackService

        service = PlaybackService(
            queue_manager=service.queue_manager, history_service=service.history_service,
            autoplay=service.autoplay, player=player, library_repository=service.library_repository,
        )
    run(player.stop())
    before = authorities(service)
    controls = capture_controls(monkeypatch, player)
    result = run(service.reconcile_external_status(evidence=evidence))
    assert result.outcome == "UNKNOWN" and result.reconciliation_required is True
    assert authorities(service) == before
    assert controls == []


@pytest.mark.parametrize("operation", ["start", "context", "play-now", "next", "previous", "delete", "stop"])
def test_recovery_business_generation_follows_committed_current(real_client, operation):
    """Late completion identities must be invalidated by every legal current change."""
    from server.app.models.queue import PlaybackContext
    from server.app.repositories.database import run_transaction

    client, _, _, service = real_client
    start(client)
    if operation == "previous":
        run(service.next())
    journal = getattr(service, "_recovery", None)
    assert journal is not None, "current changes need a rollback-sensitive recovery identity"
    old = journal.business_generation
    epoch = journal.service_epoch
    run(service.observe())
    run(service.pause())
    run(service.seek(1))
    assert journal.business_generation == old
    items = run(service.queue_manager.list_items())

    async def change():
        if operation == "start":
            await service.start_track("b")
        elif operation == "context":
            await service.play_context(PlaybackContext(context_id="new", source_type="SONGS", ordered_song_ids=("b", "c")))
        elif operation == "play-now":
            await service.play_now(next(i.queue_item_id for i in items if i.position > 0))
        elif operation == "delete":
            await service.delete(next(i.queue_item_id for i in items if i.position == 0))
        else:
            await getattr(service, operation)()

    async def fail(_):
        await change()
        assert journal.business_generation == old + 1
        raise RuntimeError("outer failed")

    with pytest.raises(RuntimeError, match="outer failed"):
        run(run_transaction(service.queue_manager.queue_repository.path, fail))
    assert journal.business_generation == old and journal.service_epoch == epoch
    run(change())
    assert journal.business_generation == old + 1


@pytest.mark.parametrize("transport", ["pause", "resume", "no-op", "confirmation-conflict"])
def test_bound_external_pause_resume_preserves_history(real_client, monkeypatch, transport):
    from server.app.services.playback_service import PlaybackReconciliationError

    client, _, player, service = real_client
    start(client)
    if transport == "resume":
        run(service.pause())
        run(player.play())
    elif transport != "no-op":
        run(player.pause())
    before = server_snapshot(service)
    generation = service._recovery.business_generation
    controls = capture_controls(monkeypatch, player)
    if transport == "confirmation-conflict":
        original = player.status
        reads = 0

        async def inconsistent():
            nonlocal reads
            reads += 1
            actual = await original()
            return actual if reads == 1 else actual.model_copy(update={"song_id": 999})

        monkeypatch.setattr(player, "status", inconsistent)
        with pytest.raises(PlaybackReconciliationError):
            run(service.reconcile_external_status())
        assert server_snapshot(service) == before
    else:
        result = run(service.reconcile_external_status())
        assert result.outcome == ("UNCHANGED" if transport == "no-op" else "APPLIED")
        after = server_snapshot(service)
        assert after[0] == before[0] and after[2:] == before[2:]
        assert result.playback.state == ("PAUSED" if transport == "pause" else "PLAYING")
        assert result.playback.playback_context_id == before[1].playback_context_id
        assert result.playback.autoplay_enabled is True
        if transport == "no-op":
            assert after == before
        repeated = run(service.reconcile_external_status())
        assert repeated.outcome == "UNCHANGED"
        assert server_snapshot(service) == after
    assert controls == [] and service._recovery.business_generation == generation


@pytest.mark.parametrize("failure", ["outer", "precommit-cancel"])
def test_transport_recovery_rollback_and_retry(real_client, monkeypatch, failure):
    import asyncio

    from server.app.repositories.database import run_transaction
    from server.app.services.realtime_coordinator import RealtimeCoordinator

    client, library, player, service = real_client
    start(client)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service._coordinator = coordinator
    service._event_publisher = Publisher()
    run(player.pause())
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)

    async def fail(_):
        result = await service.reconcile_external_status()
        assert result.outcome == "APPLIED"
        assert coordinator.marker().sequence == 0 and events == []
        assert subscriber.pending is None
        if failure == "precommit-cancel":
            raise asyncio.CancelledError()
        raise RuntimeError("outer failed")

    with pytest.raises(asyncio.CancelledError if failure == "precommit-cancel" else RuntimeError):
        run(run_transaction(library.path, fail))
    assert server_snapshot(service) == before
    assert events == [] and subscriber.pending is None
    assert run(service.reconcile_external_status()).outcome == "APPLIED"
    after = server_snapshot(service)
    assert after[0] == before[0] and after[2:] == before[2:]
    assert coordinator.marker().sequence == 1
    assert [event.domains for event in events] == [frozenset({"playback"})]
    assert run(service.reconcile_external_status()).outcome == "UNCHANGED"
    assert server_snapshot(service) == after and coordinator.marker().sequence == 1
    assert controls == []


def prepare_completion(real_client, target):
    client, library, player, service = real_client
    start(client)
    if target == "autoplay":
        run(service.queue_manager.clear())
        from server.app.repositories.database import run_transaction

        async def confirm(_):
            await service._sync_player_queue()
            await service._confirm_preserved_state()
        run(run_transaction(library.path, confirm))
    elif target == "empty":
        for song_id in "abc":
            song = run(library.get_song(song_id))
            run(library.upsert_song(song.model_copy(update={"availability_status": "MISSING"})))
    service._completion_validator = TestCompletionValidator()
    evidence = evidence_for(service, player)
    run(player.stop())
    return library, player, service, evidence


@pytest.mark.parametrize("target", ["successor", "autoplay", "empty"])
@pytest.mark.parametrize("failure", [
    "confirmation", "history-write", "queue-write", "state-write",
    "outer", "materialization", "terminal", "precommit-cancel",
])
def test_recovery_rollback_retry_keeps_identity(real_client, monkeypatch, target, failure):
    import asyncio
    import json

    from starlette.requests import Request
    from starlette.responses import StreamingResponse

    from server.app.models.recovery import RecoveryResult
    from server.app.repositories.database import run_transaction
    from server.app.repositories.idempotency_repository import IdempotencyRepository
    from server.app.services import playback_recovery
    from server.app.services.idempotency_service import IdempotencyService
    from server.app.services.playback_service import PlaybackReconciliationError
    from server.app.services.realtime_coordinator import RealtimeCoordinator

    library, player, service, evidence = prepare_completion(real_client, target)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service._coordinator = coordinator
    service._event_publisher = Publisher()
    before = authorities(service)
    generation = service._recovery.business_generation
    controls = capture_controls(monkeypatch, player)
    identity = service._recovery.identity(evidence)
    terminal = IdempotencyRepository(library.path)
    request = Request({"type": "http", "method": "POST", "path": "/test-only-recovery",
                       "headers": [(b"idempotency-key", b"d6-terminal")], "query_string": b""})
    request._body = b"{}"

    async def response(_):
        result = await service.reconcile_external_status(evidence=evidence)
        return StreamingResponse(iter([json.dumps(result.playback.model_dump(mode="json")).encode()]), media_type="application/json")

    async def explode(*args, **kwargs):
        raise RuntimeError("injected failure")

    with monkeypatch.context() as fault:
        if failure == "confirmation":
            original = player.status
            reads = 0

            async def wrong():
                nonlocal reads
                reads += 1
                actual = await original()
                return actual if reads == 1 else actual.model_copy(update={"state": PlayerState.PAUSED})
            fault.setattr(player, "status", wrong)
        elif failure == "history-write":
            fault.setattr(service.history_service.history_repository, "record_history", explode)
        elif failure == "queue-write":
            fault.setattr(service.queue_manager.queue_repository, "complete_current", explode)
        elif failure == "state-write":
            fault.setattr(service.queue_manager.playback_state_repository, "save", explode)
        elif failure == "materialization":
            original_copy = playback_recovery.deepcopy

            def copy_result(value):
                if isinstance(value, RecoveryResult):
                    raise TypeError("injected failure")
                return original_copy(value)
            fault.setattr(playback_recovery, "deepcopy", copy_result)
        elif failure == "terminal":
            fault.setattr(terminal, "create", explode)

        async def attempt(_):
            result = await service.reconcile_external_status(evidence=evidence)
            assert result.outcome == "APPLIED"
            assert service._recovery.get_receipt(identity, evidence) is None
            assert subscriber.pending is None and events == []
            if failure == "outer":
                raise RuntimeError("injected failure")
            if failure == "precommit-cancel":
                raise asyncio.CancelledError()
            return result

        expected = (asyncio.CancelledError if failure == "precommit-cancel"
                    else PlaybackReconciliationError if failure == "confirmation"
                    else TypeError if failure == "materialization" else RuntimeError)
        with pytest.raises(expected):
            if failure == "terminal":
                run(IdempotencyService(terminal).execute(request, response))
            else:
                run(run_transaction(library.path, attempt))
    assert authorities(service) == before
    assert service._recovery.business_generation == generation
    assert service._recovery.get_receipt(identity, evidence) is None
    assert events == [] and subscriber.pending is None and coordinator.marker().sequence == 0
    plan = service._recovery.pending[identity]
    planned_ids = tuple(i.queue_item_id for i in plan.pending)
    actual_after_failure = run(player.queue_entries())
    if failure == "terminal":
        assert run(terminal.get_by_key("d6-terminal")) is None
        assert run(IdempotencyService(terminal).execute(request, response)).status_code == 200
    else:
        assert run(service.reconcile_external_status(evidence=evidence)).outcome == "APPLIED"
    after = server_snapshot(service)
    assert tuple(i.queue_item_id for i in after[0].items if i.position >= 0) == planned_ids
    assert service._recovery.pending[identity] == plan
    assert [(e.song_id, e.reason) for e in after[2]] == [("a", "NATURAL_COMPLETION")]
    assert after[4] == before[1][4]
    assert len([c for c in controls if c[0] == "queue_play"]) == (0 if target == "empty" else 1)
    assert not any(c[0] in {"next", "play", "stop"} for c in controls)
    assert len(events) == 1 and coordinator.marker().sequence == 1
    assert service._recovery.get_receipt(identity, evidence).outcome == "REPLAYED"
    if target != "empty":
        assert run(player.queue_entries()) == actual_after_failure


@pytest.mark.parametrize("change", ["foreign", "new-current", "continuity"])
def test_recovery_retry_does_not_overwrite_drift(real_client, monkeypatch, change):
    from server.app.repositories.database import run_transaction

    library, player, service, evidence = prepare_completion(real_client, "autoplay")

    async def failed(_):
        assert (await service.reconcile_external_status(evidence=evidence)).outcome == "APPLIED"
        raise RuntimeError("outer failed")
    with pytest.raises(RuntimeError, match="outer failed"):
        run(run_transaction(library.path, failed))
    plan = service._recovery.pending[service._recovery.identity(evidence)]
    if change == "foreign":
        run(player.play("d.flac"))
    elif change == "new-current":
        run(service.start_track("c"))
    else:
        class Discontinuous:
            async def validate(self, evidence, baseline):
                return False
        service._completion_validator = Discontinuous()
    before = authorities(service)
    controls = capture_controls(monkeypatch, player)
    result = run(service.reconcile_external_status(evidence=evidence))
    assert result.outcome == "UNKNOWN" and result.reconciliation_required
    assert authorities(service) == before and controls == []
    assert service._recovery.pending[plan.identity] == plan
    assert service._recovery.get_receipt(plan.identity, evidence) is None


@pytest.mark.parametrize("later", ["unavailable", "new-current", "same-state"])
def test_recovery_replay_and_conflict(real_client, monkeypatch, later):
    from server.app.services.playback_service import PlaybackReconciliationError

    _, player, service, evidence = prepare_completion(real_client, "successor")
    result = run(service.reconcile_external_status(evidence=evidence))
    assert result.outcome == "APPLIED"
    original_playback = result.playback.model_copy(deep=True)
    # The caller cannot mutate a committed receipt via its returned object.
    result.playback.song_id = "tampered"
    if later == "new-current":
        run(service.start_track("c"))
    elif later == "unavailable":
        player.disconnect()
    before = authorities(service)
    controls = capture_controls(monkeypatch, player)
    replay = run(service.reconcile_external_status(evidence=evidence))
    assert replay.outcome == "REPLAYED" and replay.playback == original_playback
    assert authorities(service) == before and controls == []

    conflict = replace(evidence, ended_at=evidence.ended_at + timedelta(seconds=1))
    with pytest.raises(PlaybackReconciliationError, match="conflict"):
        run(service.reconcile_external_status(evidence=conflict))
    assert authorities(service) == before and controls == []


def test_recovery_commit_failure_restores_runtime_and_intent(real_client, monkeypatch):
    from server.app.repositories import database

    _, player, service, evidence = prepare_completion(real_client, "autoplay")
    before = authorities(service)
    generation = service._recovery.business_generation
    connect = database._connect

    class CommitFailure:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def commit(self):
            raise RuntimeError("commit failed")

    with monkeypatch.context() as fault:
        fault.setattr(database, "_connect", lambda path: CommitFailure(connect(path)))
        with pytest.raises(RuntimeError, match="commit failed"):
            run(service.reconcile_external_status(evidence=evidence))
    assert authorities(service) == before and service._recovery.business_generation == generation
    identity = service._recovery.identity(evidence)
    assert service._recovery.get_receipt(identity, evidence) is None
    intent = service._recovery.pending[identity]
    controls = capture_controls(monkeypatch, player)
    assert run(service.reconcile_external_status(evidence=evidence)).outcome == "APPLIED"
    assert service._recovery.pending[identity] == intent and controls == []


@pytest.mark.parametrize("failure", ["cancel", "publisher", "visibility-registration", "receipt-registration"])
def test_recovery_post_commit_failure_preserves_receipt(real_client, monkeypatch, failure):
    import asyncio

    from server.app.repositories.database import on_transaction_visible, run_transaction
    from server.app.services.realtime_coordinator import RealtimeCoordinator

    library, player, service, evidence = prepare_completion(real_client, "successor")
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    service._coordinator = coordinator

    class Publisher:
        async def publish(self, event):
            if failure == "cancel":
                raise asyncio.CancelledError()
            if failure == "publisher":
                raise RuntimeError("publisher failure")

    service._event_publisher = Publisher()
    identity = service._recovery.identity(evidence)
    if failure == "receipt-registration":
        class BrokenReceipts(dict):
            def __setitem__(self, key, value):
                if value is not None:
                    raise RuntimeError("receipt registration failed")
                super().__setitem__(key, value)
        service._recovery.receipts = BrokenReceipts()

    async def commit(_):
        result = await service.reconcile_external_status(evidence=evidence)
        assert service._recovery.get_receipt(identity, evidence) is None
        assert subscriber.pending is None
        if failure == "visibility-registration":
            def broken():
                raise RuntimeError("visibility registration failed")
            on_transaction_visible(library.path, broken)
        return result

    if failure == "cancel":
        with pytest.raises(asyncio.CancelledError):
            run(run_transaction(library.path, commit))
    else:
        assert run(run_transaction(library.path, commit)).outcome == "APPLIED"
    committed = server_snapshot(service)
    assert committed[1].song_id == "b" and committed[3].song_id == "b"
    assert [(e.song_id, e.reason) for e in committed[2]] == [("a", "NATURAL_COMPLETION")]
    service._event_publisher = None
    controls = capture_controls(monkeypatch, player)
    if failure == "receipt-registration":
        # An unreliable journal is isolated even for newly presented valid IDs.
        service._recovery.receipts = {}
        newer = evidence_for(service, player, transition_id="new-completion")
        run(player.stop())
        controls.clear()
        result = run(service.reconcile_external_status(evidence=newer))
        assert result.outcome == "UNKNOWN" and result.reconciliation_required
    else:
        replay = run(service.reconcile_external_status(evidence=evidence))
        assert replay.outcome == "REPLAYED" and replay.playback == committed[1]
    assert server_snapshot(service) == committed and controls == []
    if failure in {"visibility-registration", "receipt-registration"}:
        assert subscriber.valid is False
        with pytest.raises(RuntimeError, match="unavailable"):
            coordinator.marker()
    else:
        assert coordinator.marker().sequence == 1


@pytest.mark.parametrize("kind", ["unknown", "transport", "natural", "empty", "replay", "rollback"])
def test_recovery_preserves_independent_domains_and_old_terminals(real_client, kind):
    from server.app.main import app
    from server.app.repositories.database import run_transaction
    from server.app.services.realtime_coordinator import RealtimeCoordinator

    library, player, service, evidence = prepare_completion(real_client, "empty" if kind == "empty" else "successor")
    playlists = app.state.playlist_service
    playlist = run(playlists.create_playlist("preserved"))
    run(playlists.add_song(playlist.playlist_id, "a"))
    run(playlists.add_song(playlist.playlist_id, "b"))
    run(playlists.set_favorite("a", True))
    coordinator = RealtimeCoordinator(library.path)
    service._coordinator = coordinator
    if kind == "replay":
        run(service.reconcile_external_status(evidence=evidence))
    elif kind == "transport":
        run(player.queue_play(evidence.mpd_song_id))
        run(player.pause())
    before = authorities(service)
    membership = run(playlists.revision_content())
    output = app.state.output_manager
    output_runtime = deepcopy((output._nas_observation, output._last_request, output._observed_at, output._generation))
    outputs = run(player.outputs())
    marker = coordinator.marker()
    if kind == "rollback":
        async def fail(_):
            await service.reconcile_external_status(evidence=evidence)
            raise RuntimeError("outer failed")
        with pytest.raises(RuntimeError, match="outer failed"):
            run(run_transaction(library.path, fail))
        assert authorities(service) == before
    else:
        result = run(service.reconcile_external_status(evidence=None if kind in {"unknown", "transport"} else evidence))
        assert result.outcome == {"unknown": "UNKNOWN", "transport": "APPLIED", "natural": "APPLIED", "empty": "APPLIED", "replay": "REPLAYED"}[kind]
    changed_tables = {"queue_items", "queue_state", "playback_state", "history", "sqlite_sequence"}
    assert [(name, rows) for name, rows in authorities(service)[0] if name not in changed_tables] == [
        (name, rows) for name, rows in before[0] if name not in changed_tables
    ]
    assert run(playlists.revision_content()) == membership
    assert (output._nas_observation, output._last_request, output._observed_at, output._generation) == output_runtime
    assert run(player.outputs()) == outputs
    after_marker = coordinator.marker()
    assert (after_marker.library_revision, after_marker.playlist_revision) == (marker.library_revision, marker.playlist_revision)


@pytest.mark.parametrize("first", ["recovery", "mutation"])
def test_recovery_serializes_with_new_current_and_commit_visibility(real_client, first):
    import asyncio

    from server.app.repositories.database import run_transaction

    library, _, service, evidence = prepare_completion(real_client, "successor")
    identity = service._recovery.identity(evidence)

    async def scenario():
        entered, release, second_started = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def owner(_):
            if first == "recovery":
                result = await service.reconcile_external_status(evidence=evidence)
                assert result.outcome == "APPLIED"
                assert service._recovery.get_receipt(identity, evidence) is None
            else:
                await service.start_track("c")
            entered.set()
            await release.wait()

        async def second():
            await entered.wait()
            second_started.set()
            if first == "recovery":
                await service.start_track("c")
                return None
            return await service.reconcile_external_status(evidence=evidence)

        first_task = asyncio.create_task(run_transaction(library.path, owner))
        second_task = asyncio.create_task(second())
        await second_started.wait()
        assert not second_task.done()
        assert service._recovery.get_receipt(identity, evidence) is None
        release.set()
        await first_task
        return await second_task

    result = run(scenario())
    final = server_snapshot(service)
    assert final[1].song_id == "c" and final[3].song_id == "c"
    if first == "mutation":
        assert result.outcome == "UNKNOWN"
        assert [(e.song_id, e.reason) for e in final[2]] == [("a", "SWITCH_AWAY")]
    else:
        receipt = service._recovery.get_receipt(identity, evidence)
        assert receipt.playback.song_id == "b"
        assert [(e.song_id, e.reason) for e in final[2]] == [("b", "SWITCH_AWAY"), ("a", "NATURAL_COMPLETION")]


def test_natural_completion_rejects_unbound_local_pending(real_client, monkeypatch):
    _, player, service, _ = prepare_completion(real_client, "successor")
    run(service.queue_manager.add_to_queue("b"))
    evidence = evidence_for(service, player)
    before = authorities(service)
    controls = capture_controls(monkeypatch, player)
    result = run(service.reconcile_external_status(evidence=evidence))
    assert result.outcome == "UNKNOWN" and result.reconciliation_required
    assert authorities(service) == before and controls == []


@pytest.mark.parametrize("invalid", ["stale", "duplicate", "new-manual", "overwrite", "reverse", "wrong-successor"])
def test_completion_queue_cas_rejects_noncompletion_plans(real_client, invalid):
    from server.app.models.queue import QueueItem
    from server.app.repositories.queue_repository import QueueRevisionConflictError

    client, _, _, service = real_client
    start(client)
    queue = run(service.queue_manager.get_snapshot())
    current = next(i for i in queue.items if i.position == 0)
    pending = tuple(i for i in queue.items if i.position > 0)
    revision = queue.revision
    target = pending[0].queue_item_id
    if invalid == "stale":
        revision -= 1
    elif invalid == "duplicate":
        pending = (pending[0], pending[0])
    elif invalid == "new-manual":
        pending += (QueueItem(queue_item_id="new", song_id="b", position=9, source="MANUAL"),)
    elif invalid == "overwrite":
        pending = (pending[0].model_copy(update={"song_id": "c"}), *pending[1:])
    elif invalid == "reverse":
        pending = tuple(reversed(pending))
        target = pending[0].queue_item_id
    else:
        target = current.queue_item_id
    with pytest.raises(QueueRevisionConflictError if invalid == "stale" else ValueError):
        run(service.queue_manager.complete_current(current.queue_item_id, pending=pending, successor_id=target, expected_revision=revision))
    assert run(service.queue_manager.get_snapshot()) == queue


def test_completion_retains_existing_played_occurrences(real_client):
    from server.tests.invariants.assertions import assert_execution_relationship

    client, _, player, service = real_client
    start(client)
    run(service.next())
    before = server_snapshot(service)
    service._completion_validator = TestCompletionValidator()
    evidence = evidence_for(service, player)
    run(player.stop())
    assert run(service.reconcile_external_status(evidence=evidence)).outcome == "APPLIED"
    after = server_snapshot(service)
    played = [i for i in after[0].items if i.position < 0]
    assert [i.queue_item_id for i in played] == [evidence.queue_item_id, *[i.queue_item_id for i in before[0].items if i.position < 0]]
    assert [i.position for i in played] == [-1, -2]
    assert [(e.song_id, e.reason) for e in after[2]] == [("b", "NATURAL_COMPLETION"), ("a", "SWITCH_AWAY")]
    assert after[2][1:] == before[2]
    assert_execution_relationship(service, player)


def test_recovery_binding_uses_the_confirmed_execution_sample(real_client, monkeypatch):
    """A late same-URI replacement must not silently establish a new binding."""
    _, player, service, evidence = prepare_completion(real_client, "successor")
    original = player.queue_entries
    reads = 0

    async def replace_last():
        entries = await original()
        last = entries[-1]
        await player.queue_delete(last.mpd_song_id)
        await player.queue_add(last.song_uri)

    async def late_read():
        nonlocal reads
        reads += 1
        if reads == 3:
            await replace_last()
        return await original()

    monkeypatch.setattr(player, "queue_entries", late_read)
    result = run(service.reconcile_external_status(evidence=evidence))
    assert result.outcome == "APPLIED"
    identity = service._recovery.identity(evidence)
    assert service._observations.binding[6] == service._recovery.execution[identity]
    monkeypatch.setattr(player, "queue_entries", original)
    run(replace_last())
    before = authorities(service)
    assert run(service.reconcile_external_status()).outcome == "UNKNOWN"
    assert authorities(service) == before
