from __future__ import annotations

from dataclasses import replace

import pytest

from server.app.models.recovery import RecoveryResult
from server.app.player.ports import PlayerUnavailable
from server.app.repositories.database import run_transaction
from server.app.services.playback_service import PlaybackReconciliationError
from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_d6_recovery import capture_controls
from server.tests.support.playback import real_client, run, start

__all__ = ["real_client"]


def execution_case(real_client, command):
    from server.app.models import recovery
    from server.app.services.playback_execution import ExecutionSynchronizer

    client, library, player, service = real_client
    start(client)
    journal = service._recovery
    binding = run(service.get_execution_binding())
    sample = run(player.read_execution_sample())
    items = tuple((item_id, uri) for item_id, _, uri in binding.entries)
    target = items[0][0]
    if command == "add":
        items += (("planned-occurrence", "a.flac"),)
        commands = (recovery.ExecutionCommand("add", "planned-occurrence", uri="a.flac"),)
    elif command == "delete":
        commands = (recovery.ExecutionCommand("delete", mpd_song_id=binding.entries[-1][1]),)
        items = items[:-1]
    elif command == "move":
        commands = (recovery.ExecutionCommand("move", items[2][0], before_item_id=items[1][0]),)
        items = (items[0], items[2], items[1], *items[3:])
    else:
        target = items[1][0]
        commands = (recovery.ExecutionCommand("play", target),)
    intent = recovery.ExecutionIntent(
        service_epoch=journal.service_epoch, binding_generation=binding.binding_generation,
        operation_id=f"proof-{command}", queue_revision=binding.queue_revision,
        baseline=sample, entries=binding.entries, items=items, commands=commands,
        target_item_id=target, target_state="PLAYING", allow_start=True,
    )
    return library.path, player, service, journal, ExecutionSynchronizer(player, journal), intent


@pytest.mark.parametrize("command", ["add", "delete", "move", "play"])
@pytest.mark.parametrize("failure", ["before-send", "after-ack", "after-confirm"])
def test_each_command_prefix_is_retried_only_when_owned(real_client, monkeypatch, command, failure):
    path, player, service, journal, executor, intent = execution_case(real_client, command)
    controls = capture_controls(monkeypatch, player)
    record = journal.record_command
    failed = False

    def fault(operation_id, index, receipt):
        nonlocal failed
        phase = {"before-send": "sent", "after-ack": "ack", "after-confirm": "confirmed"}[failure]
        if receipt.phase == phase and not failed:
            failed = True
            if failure != "before-send":
                record(operation_id, index, receipt)
            raise RuntimeError(failure)
        record(operation_id, index, receipt)

    monkeypatch.setattr(journal, "record_command", fault)

    async def attempt(_):
        await executor.execute(intent)

    with pytest.raises(RuntimeError, match=failure):
        run(run_transaction(path, attempt))
    intent_before = journal.execution_intents[intent.operation_id]
    assert journal.get_execution_receipt(intent.operation_id) is None
    monkeypatch.setattr(journal, "record_command", record)

    async def retry(_):
        sample = await executor.execute(intent)
        journal.commit_execution(intent.operation_id, RecoveryResult("APPLIED", await service.queue_manager.get_playback_state()))
        assert journal.get_execution_receipt(intent.operation_id) is None
        return sample

    sample = run(run_transaction(path, retry))
    assert journal.execution_intents[intent.operation_id] == intent_before == intent
    assert tuple(item_id for item_id, _ in intent.items) == tuple(item_id for item_id, _, _ in executor.mapping(intent))
    assert tuple(entry.song_uri for entry in sample.entries) == tuple(uri for _, uri in intent.items)
    assert sum(name == "queue_add" for name, _, _ in controls) == (1 if command == "add" else 0)
    assert sum(name == f"queue_{command}" for name, _, _ in controls) <= 1
    revision = run(service.queue_manager.get_snapshot()).revision
    controls.clear()
    assert run(run_transaction(path, attempt)) is None
    assert journal.get_execution_receipt(intent.operation_id).outcome == "REPLAYED"
    assert controls == []
    assert run(service.queue_manager.get_snapshot()).revision == revision
    with pytest.raises(PlaybackReconciliationError, match="conflict"):
        journal.prepare_execution(replace(intent, items=intent.items[:-1]))


def test_lost_add_response_never_guesses_or_resends(real_client, monkeypatch):
    path, player, service, journal, executor, intent = execution_case(real_client, "add")
    before = server_snapshot(service)
    add = player.queue_add
    calls = []

    async def lost(uri):
        calls.append(uri)
        await add(uri)
        raise PlayerUnavailable("response EOF")

    monkeypatch.setattr(player, "queue_add", lost)

    async def attempt(_):
        await executor.execute(intent)

    with pytest.raises(PlayerUnavailable):
        run(run_transaction(path, attempt))
    with pytest.raises(PlaybackReconciliationError, match="UNKNOWN"):
        run(run_transaction(path, attempt))
    assert calls == ["a.flac"]
    assert server_snapshot(service) == before
    assert journal.get_execution_receipt(intent.operation_id) is None


@pytest.mark.parametrize("command", ["delete", "move", "play"])
@pytest.mark.parametrize("drift", ["none", "version", "connection", "ambiguous"])
def test_lost_response_requires_unique_owned_result(real_client, monkeypatch, command, drift):
    import asyncio

    path, player, service, journal, executor, intent = execution_case(real_client, command)
    before = server_snapshot(service)
    if drift == "ambiguous":
        intent = replace(intent, commands=(replace(intent.commands[0], kind="move", item_id=intent.items[0][0],
                                                   before_item_id=intent.items[1][0], mpd_song_id=None),),
                         items=tuple((key, uri) for key, _, uri in intent.entries),
                         target_item_id=intent.entries[0][0])
    send = executor._send
    controls = capture_controls(monkeypatch, player)

    async def lost(*args):
        await send(*args)
        raise asyncio.CancelledError()

    monkeypatch.setattr(executor, "_send", lost)

    async def attempt(_):
        return await executor.execute(intent)

    with pytest.raises(asyncio.CancelledError):
        run(run_transaction(path, attempt))
    prefix_controls = list(controls)
    monkeypatch.setattr(executor, "_send", send)
    if drift == "version":
        player._playlist_version += 1
    elif drift == "connection":
        player.reconnect()
    controls.clear()
    if drift == "none" and command != "play":
        run(run_transaction(path, attempt))
        assert journal.command_receipts[intent.operation_id][0].phase == "confirmed"
    else:
        from server.app.services.playback_service import PlaybackReconciliationError
        with pytest.raises(PlaybackReconciliationError, match="UNKNOWN"):
            run(run_transaction(path, attempt))
    assert len(prefix_controls) == 1
    assert controls == []
    assert server_snapshot(service) == before
    assert journal.get_execution_receipt(intent.operation_id) is None


@pytest.mark.parametrize("drift", ["version", "queue", "connection", "generation"])
def test_acknowledged_prefix_never_claims_external_drift(real_client, monkeypatch, drift):
    from server.app.services.playback_service import PlaybackReconciliationError

    _, player, service, journal, executor, intent = execution_case(real_client, "add")
    record = journal.record_command

    def ack_then_fail(operation_id, index, receipt):
        record(operation_id, index, receipt)
        if receipt.phase == "ack":
            raise RuntimeError("after-ack")

    monkeypatch.setattr(journal, "record_command", ack_then_fail)
    with pytest.raises(RuntimeError, match="after-ack"):
        run(executor.execute(intent))
    monkeypatch.setattr(journal, "record_command", record)
    if drift == "version":
        player._playlist_version += 1
    elif drift == "queue":
        player._queue[-1] = ("a.flac", 999)
    elif drift == "connection":
        player.reconnect()
    else:
        journal.business_generation += 1
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    for _ in range(2):
        with pytest.raises(PlaybackReconciliationError, match="UNKNOWN"):
            run(executor.execute(intent))
    assert controls == []
    assert server_snapshot(service) == before
    assert journal.get_execution_receipt(intent.operation_id) is None


def test_current_departure_cannot_be_hidden_by_returning_to_old_entry(real_client, monkeypatch):
    from server.app.services.playback_service import PlaybackReconciliationError

    _, player, _, journal, executor, intent = execution_case(real_client, "add")
    add = player.queue_add

    async def advance(uri):
        result = await add(uri)
        await player.queue_play(intent.entries[1][1])
        return result

    monkeypatch.setattr(player, "queue_add", advance)
    with pytest.raises(PlaybackReconciliationError, match="UNKNOWN"):
        run(executor.execute(intent))
    run(player.queue_play(intent.entries[0][1]))
    controls = capture_controls(monkeypatch, player)
    with pytest.raises(PlaybackReconciliationError, match="UNKNOWN"):
        run(executor.execute(intent))
    assert controls == []
    assert journal.get_execution_receipt(intent.operation_id) is None


def test_multi_command_retry_keeps_the_owned_prefix(real_client, monkeypatch):
    from server.app.models.recovery import ExecutionCommand

    path, player, _, journal, executor, intent = execution_case(real_client, "add")
    old = intent.items[:-1]
    intent = replace(intent, items=(intent.items[-1], old[0], *old[2:]),
                     target_item_id="planned-occurrence", commands=(
                         intent.commands[0], ExecutionCommand("move", "planned-occurrence", before_item_id=old[0][0]),
                         ExecutionCommand("delete", mpd_song_id=intent.entries[1][1]),
                         ExecutionCommand("play", "planned-occurrence"),
                     ))
    controls = capture_controls(monkeypatch, player)
    record = journal.record_command

    def partial(operation_id, index, receipt):
        record(operation_id, index, receipt)
        if index == 2 and receipt.phase == "ack":
            raise RuntimeError("partial-prefix")

    monkeypatch.setattr(journal, "record_command", partial)
    with pytest.raises(RuntimeError, match="partial-prefix"):
        run(executor.execute(intent))
    assert [receipt.phase for receipt in journal.command_receipts[intent.operation_id].values()] == ["confirmed", "confirmed", "ack"]
    assert [name for name, _, _ in controls] == ["queue_add", "queue_move", "queue_delete"]
    monkeypatch.setattr(journal, "record_command", record)
    controls.clear()

    async def retry(_):
        result = await executor.execute(intent)
        journal.commit_execution(intent.operation_id, RecoveryResult("APPLIED", None))
        return result

    result = run(run_transaction(path, retry))
    assert [name for name, _, _ in controls] == ["queue_play"]
    assert result.status.song_position == 0
    controls.clear()
    run(executor.execute(intent))
    assert controls == []


@pytest.mark.parametrize("operation", ["start", "context", "play-now", "next", "previous", "delete"])
def test_explicit_service_retry_preserves_ids_and_does_not_replay(real_client, monkeypatch, operation):
    from server.app.models.queue import PlaybackContext

    client, library, player, service = real_client
    start(client)
    if operation == "previous":
        run(service.next())
    before = server_snapshot(service)
    planned = []

    async def change():
        if operation == "start":
            await service.start_track("b")
        elif operation == "context":
            await service.play_context(PlaybackContext(context_id="fixed-context", source_type="SONGS",
                                                      ordered_song_ids=("b", "a")))
        elif operation == "play-now":
            await service.play_now(next(item.queue_item_id for item in before[0].items if item.position == 1))
        elif operation == "delete":
            await service.delete(next(item.queue_item_id for item in before[0].items if item.position == 0))
        else:
            await getattr(service, operation)()

    async def failing(_):
        await change()
        planned.append(await service.queue_manager.get_snapshot())
        raise RuntimeError("outer-failure")

    with pytest.raises(RuntimeError, match="outer-failure"):
        run(run_transaction(library.path, failing))
    assert server_snapshot(service) == before
    controls = capture_controls(monkeypatch, player)
    run(change())
    assert run(service.queue_manager.get_snapshot()) == planned[0]
    assert controls == []


def test_collection_request_retry_preserves_context_and_random_plan(real_client, monkeypatch):
    import sqlite3

    from server.tests.support.playback import mutate

    client, library, player, service = real_client
    snapshots = []
    original = service._sync_player_queue

    async def capture(**kwargs):
        snapshots.append(await service.queue_manager.get_snapshot())
        return await original(**kwargs)

    monkeypatch.setattr(service, "_sync_player_queue", capture)
    run(run_transaction(library.path, lambda c: c.execute("""
        CREATE TRIGGER fail_s4_context BEFORE INSERT ON idempotency_records
        WHEN NEW.idempotency_key = 's4-context'
        BEGIN SELECT RAISE(ABORT, 'context terminal'); END
    """)))
    before = server_snapshot(service)
    body = {"source_type": "SONGS", "song_ids": ["a", "b", "c"], "randomize": True}
    with pytest.raises(sqlite3.IntegrityError, match="context terminal"):
        mutate(client, "POST", "/api/playback/collections/play", body, key="s4-context")
    assert server_snapshot(service) == before
    run(run_transaction(library.path, lambda c: c.execute("DROP TRIGGER fail_s4_context")))
    controls = capture_controls(monkeypatch, player)
    response = mutate(client, "POST", "/api/playback/collections/play", body, key="s4-context")
    assert response.status_code == 200, response.text
    assert snapshots[1] == snapshots[0]
    assert controls == []
    replay = mutate(client, "POST", "/api/playback/collections/play", body, key="s4-context")
    assert replay.json() == response.json()
    assert len(snapshots) == 2
    assert controls == []


def test_protocol_read_failure_seals_the_acknowledged_prefix(real_client, monkeypatch):
    from server.app.player.ports import PlayerCommandError
    from server.app.services.playback_service import PlaybackReconciliationError

    _, player, service, journal, executor, intent = execution_case(real_client, "add")
    original = player.read_execution_sample
    reads = 0

    async def protocol_failure():
        nonlocal reads
        reads += 1
        if reads == 2:
            raise PlayerCommandError("read_execution_sample", "invalid sample")
        return await original()

    monkeypatch.setattr(player, "read_execution_sample", protocol_failure)
    with pytest.raises(PlayerCommandError):
        run(executor.execute(intent))
    monkeypatch.setattr(player, "read_execution_sample", original)
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    with pytest.raises(PlaybackReconciliationError, match="UNKNOWN"):
        run(executor.execute(intent))
    assert controls == []
    assert server_snapshot(service) == before
    assert journal.binding is None


def test_fixed_allocation_rejects_inherited_child_writers(real_client):
    import asyncio
    from uuid import uuid4

    _, _, _, service = real_client
    repo = service.queue_manager.queue_repository
    before = run(repo.get_snapshot())

    async def scenario(_):
        with repo.fixed_allocation(str(uuid4())), pytest.raises(RuntimeError, match="allocation owner"):
            await asyncio.create_task(repo.add_to_queue("a"))
        raise RuntimeError("outer cleanup")

    with pytest.raises(RuntimeError, match="outer cleanup"):
        run(run_transaction(repo.path, scenario))
    assert run(repo.get_snapshot()) == before


def test_service_retry_read_failure_cannot_bypass_unknown_by_reconnect(real_client, monkeypatch):
    from server.app.player.ports import PlayerCommandError

    client, library, player, service = real_client
    start(client)
    before = server_snapshot(service)

    async def failing(_):
        await service.start_track("b")
        raise RuntimeError("outer-failure")

    with pytest.raises(RuntimeError, match="outer-failure"):
        run(run_transaction(library.path, failing))
    sample = player.read_execution_sample

    async def protocol():
        raise PlayerCommandError("read_execution_sample", "protocol failure on retry")

    monkeypatch.setattr(player, "read_execution_sample", protocol)
    with pytest.raises(PlayerCommandError):
        run(service.start_track("b"))
    player.reconnect()
    monkeypatch.setattr(player, "read_execution_sample", sample)
    controls = capture_controls(monkeypatch, player)
    with pytest.raises(PlaybackReconciliationError, match="UNKNOWN"):
        run(service.start_track("b"))
    assert controls == []
    assert server_snapshot(service) == before


@pytest.mark.parametrize("operation", ["append", "start"])
def test_read_only_observation_preserves_owned_rollback_prefix(real_client, monkeypatch, operation):
    client, library, player, service = real_client
    start(client)
    before = server_snapshot(service)

    async def change():
        if operation == "append":
            await service.add_to_queue("b")
        else:
            await service.start_track("b")

    async def failing(_):
        await change()
        raise RuntimeError("outer-failure")

    with pytest.raises(RuntimeError, match="outer-failure"):
        run(run_transaction(library.path, failing))
    controls = capture_controls(monkeypatch, player)
    observation = run(service.observe())
    assert observation.reconciliation_required
    assert server_snapshot(service) == before
    assert controls == []
    run(change())
    assert controls == []
    assert run(service.observe()).matches_current is True


def test_committed_execution_receipt_precedes_new_generation_and_source_reads(real_client, monkeypatch):
    path, player, _, journal, executor, intent = execution_case(real_client, "move")

    async def commit(_):
        sample = await executor.execute(intent)
        journal.commit_execution(intent.operation_id, RecoveryResult("APPLIED", None))
        return sample

    sample = run(run_transaction(path, commit))
    journal.business_generation += 1
    journal.invalidate_binding()
    player.reconnect()
    controls = capture_controls(monkeypatch, player)

    async def unreadable():
        raise AssertionError("receipt replay must precede source reads")

    monkeypatch.setattr(player, "read_execution_sample", unreadable)
    assert run(executor.execute(intent)) == sample
    assert journal.get_execution_receipt(intent.operation_id).outcome == "REPLAYED"
    assert controls == []


@pytest.mark.parametrize("failure", [
    "queue", "state", "history-runtime", "terminal", "materialization", "outer-commit",
    "precommit-cancel", "postcommit-cancel", "publisher", "visibility",
])
def test_execution_outer_failures_and_post_commit_receipt(real_client, monkeypatch, failure):
    import asyncio
    import sqlite3

    from server.app.repositories import database
    from server.app.repositories.idempotency_repository import IdempotencyRepository
    from server.app.services import playback_recovery

    path, player, service, journal, executor, intent = execution_case(real_client, "move")
    before = server_snapshot(service)
    events = []
    controls = capture_controls(monkeypatch, player)
    connect = database._connect
    committed = failure in {"postcommit-cancel", "publisher", "visibility"}
    terminal = IdempotencyRepository(path)
    if failure == "terminal":
        run(run_transaction(path, lambda c: c.execute("""
            CREATE TRIGGER fail_s4_terminal BEFORE INSERT ON idempotency_records
            BEGIN SELECT RAISE(ABORT, 'terminal'); END
        """)))
    if failure == "materialization":
        original_copy = playback_recovery.deepcopy

        def copy_result(value):
            if isinstance(value, RecoveryResult):
                raise TypeError("materialization")
            return original_copy(value)

        monkeypatch.setattr(playback_recovery, "deepcopy", copy_result)

    class FailingCommit(sqlite3.Connection):
        def commit(self):
            raise sqlite3.OperationalError("outer-commit")

    async def attempt(connection):
        service.history_service.preserve_active_on_rollback()
        ids = [item_id for item_id, _ in intent.items]
        await service.queue_manager.reorder(ids[1], ids[2])
        if failure == "queue":
            raise RuntimeError(failure)
        await service.queue_manager.set_playback_state(before[1].model_copy(update={"position_seconds": 9}))
        if failure == "state":
            raise RuntimeError(failure)
        service.history_service._active = None
        if failure == "history-runtime":
            raise RuntimeError(failure)
        await executor.execute(intent)
        journal.commit_execution(intent.operation_id, RecoveryResult("APPLIED", await service.queue_manager.get_playback_state()))
        assert journal.get_execution_receipt(intent.operation_id) is None
        if failure == "terminal":
            await terminal.create(operation_scope="s4", idempotency_key="s4-terminal", payload_hash="fixed",
                                  response_status=200, response_body="{}")
        if failure == "precommit-cancel":
            raise asyncio.CancelledError()
        if failure == "visibility":
            def fail_visible():
                raise RuntimeError(failure)
            database.on_transaction_visible(path, fail_visible)
            service._coordinator.stage_change(frozenset({"queue"}), before[0], await service.queue_manager.get_snapshot())
        def publish():
            if failure == "postcommit-cancel":
                raise asyncio.CancelledError()
            if failure == "publisher":
                raise RuntimeError(failure)
            events.append("success")
        database.on_transaction_commit(path, publish)

    if failure == "outer-commit":
        monkeypatch.setattr(database, "_connect", lambda p: sqlite3.connect(p, factory=FailingCommit))
    if failure in {"publisher", "visibility"}:
        run(run_transaction(path, attempt))
    else:
        with pytest.raises((RuntimeError, TypeError, sqlite3.Error, asyncio.CancelledError)):
            run(run_transaction(path, attempt))
    monkeypatch.setattr(database, "_connect", connect)
    after = server_snapshot(service)
    if not committed:
        assert after == before
        assert events == []
        assert journal.get_execution_receipt(intent.operation_id) is None
        assert run(terminal.get_by_key("s4-terminal")) is None
    else:
        assert after[0].revision == before[0].revision + 1
        assert after[1].position_seconds == 9
        assert journal.get_execution_receipt(intent.operation_id).outcome == "REPLAYED"
        assert service.history_service.active_event is None
        if failure == "visibility":
            assert real_client[0].get("/api/state").status_code == 503
        controls.clear()
        run(executor.execute(intent))
        assert controls == []
        assert server_snapshot(service) == after
