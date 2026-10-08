from __future__ import annotations

from server.app.models.recovery import CommandReceipt, ExecutionCommand, ExecutionIntent
from server.app.player.models import (
    ExecutionSample,
    PlayerQueueEntry,
    PlayerState,
    PlayerStatus,
)
from server.app.player.ports import PlayerCommandError, PlayerPort, PlayerUnavailable
from server.app.services.playback_recovery import RecoveryJournal


class ExecutionSynchronizer:
    """Execute only the unsent suffix of a fixed, process-owned command plan."""

    def __init__(self, player: PlayerPort, journal: RecoveryJournal) -> None:
        self.player, self.journal = player, journal

    @staticmethod
    def adoption_commands(entries, target_id):
        """Retain all pending IDs, deleting only the previously confirmed current."""
        commands = [ExecutionCommand("delete", mpd_song_id=entries[0][1])]
        remaining = entries[1:]
        target = next(index for index, row in enumerate(remaining) if row[0] == target_id)
        if target:
            commands.append(ExecutionCommand("move", target_id, before_item_id=remaining[0][0]))
        return tuple(commands)

    @staticmethod
    def append_commands(items):
        return tuple(ExecutionCommand("add", item_id, uri=uri) for item_id, uri in items)

    def _verify_fence(self, intent):
        if (self.journal.execution_fences[intent.operation_id]
                != (self.journal._invalidation, self.journal.business_generation)
                or (self.journal.binding is not None
                    and intent.binding_generation != self.journal.binding.binding_generation)):
            self.journal.unknown_executions.add(intent.operation_id)
            self.journal.invalidate_binding()
            raise self.journal.conflict("UNKNOWN stale execution generation")

    def mapping(self, intent: ExecutionIntent) -> tuple[tuple[str, int, str], ...]:
        ids = {item_id: mpd_id for item_id, mpd_id, _ in intent.entries}
        for index, command in enumerate(intent.commands):
            receipt = self.journal.command_receipts[intent.operation_id].get(index)
            if command.kind == "add" and receipt is not None and receipt.returned_id is not None:
                ids[command.item_id] = receipt.returned_id
        return tuple((item_id, ids[item_id], uri) for item_id, uri in intent.items)

    def _id(self, intent: ExecutionIntent, item_id: str | None) -> int | None:
        if item_id is None:
            return None
        ids = {key: value for key, value, _ in intent.entries}
        for index, command in enumerate(intent.commands):
            receipt = self.journal.command_receipts[intent.operation_id].get(index)
            if command.kind == "add" and receipt and receipt.returned_id is not None:
                ids[command.item_id] = receipt.returned_id
        return ids[item_id]

    def _expected(self, intent, command, before, receipt):
        entries = [(e.mpd_song_id, e.song_uri) for e in before.entries]
        status = before.status.model_dump()
        version = before.playlist_version
        mpd_id = command.mpd_song_id if command.kind == "delete" else self._id(intent, command.item_id)
        if command.kind == "add":
            if receipt.returned_id is None or any(e[0] == receipt.returned_id for e in entries):
                raise self.journal.conflict("UNKNOWN add response identity")
            entries.append((receipt.returned_id, command.uri))
            version += 1
        elif command.kind == "delete":
            entries = [entry for entry in entries if entry[0] != mpd_id]
            version += 1
            if status["song_id"] == mpd_id:
                status.update(state=PlayerState.STOPPED, song_id=None, song_uri=None, song_position=None)
        elif command.kind == "move":
            entry = next(entry for entry in entries if entry[0] == mpd_id)
            entries.remove(entry)
            before_id = (command.before_mpd_song_id if command.before_item_id is None else self._id(intent, command.before_item_id))
            position = next((i for i, e in enumerate(entries) if e[0] == before_id), len(entries))
            entries.insert(position, entry)
            version += int(tuple(e.mpd_song_id for e in before.entries) != tuple(e[0] for e in entries))
        elif command.kind == "play":
            status.update(state=PlayerState.PLAYING, song_id=mpd_id,
                          song_uri=next(uri for key, uri in entries if key == mpd_id))
        else:
            status["state"] = PlayerState.PAUSED
        status["song_position"] = next((i for i, e in enumerate(entries) if e[0] == status["song_id"]), None)
        return ExecutionSample(**(before.model_dump() | {
            "entries": tuple(PlayerQueueEntry(mpd_song_id=key, song_uri=uri, position=i)
                             for i, (key, uri) in enumerate(entries)),
            "playlist_version": version, "status": PlayerStatus(**status),
        }))

    def _verify(self, intent, actual, expected, *, append_only=False):
        if append_only and actual.error:
            raise self.journal.conflict("UNKNOWN player error pauses append execution")
        if (actual.connection_epoch != expected.connection_epoch
                or actual.partition != expected.partition
                or actual.playlist_version != expected.playlist_version
                or actual.entries != expected.entries
                or (actual.single, actual.consume, actual.status.random, actual.status.repeat)
                != (expected.single, expected.consume, expected.status.random, expected.status.repeat)):
            self.journal.unknown_executions.add(intent.operation_id)
            self.journal.invalidate_binding()
            raise self.journal.conflict("UNKNOWN command ownership")
        if (append_only and actual.status.state == expected.status.state
                and actual.status.state in {PlayerState.PLAYING, PlayerState.PAUSED}
                and any((entry.mpd_song_id, entry.song_uri, entry.position)
                        == (actual.status.song_id, actual.status.song_uri, actual.status.song_position)
                        for entry in actual.entries)):
            # Owned add-only prefixes can outlive their original current fact.
            # Re-sample the mapped current; Service performs a separate adoption.
            return
        if (actual.status.state, actual.status.song_id, actual.status.song_position) != (
                expected.status.state, expected.status.song_id, expected.status.song_position):
            if (actual.status.song_id, actual.status.song_position) != (
                    expected.status.song_id, expected.status.song_position):
                self.journal.unknown_executions.add(intent.operation_id)
                self.journal.invalidate_binding()
            raise self.journal.conflict("UNKNOWN current changed during execution")

    async def _send(self, intent, command):
        if command.kind == "add":
            return await self.player.queue_add(command.uri)
        if command.kind == "delete":
            await self.player.queue_delete(command.mpd_song_id)
        elif command.kind == "move":
            await self.player.queue_move(self._id(intent, command.item_id), (command.before_mpd_song_id if command.before_item_id is None else self._id(intent, command.before_item_id)))
        elif command.kind == "play":
            if command.uri is not None:
                await self.player.play(command.uri)
            else:
                await self.player.queue_play(self._id(intent, command.item_id))
        else:
            await self.player.pause()
        return None

    async def execute_append(self, intent: ExecutionIntent) -> ExecutionSample:
        if not intent.commands or any(command.kind != "add" for command in intent.commands):
            raise self.journal.conflict("Append execution requires only add commands")
        return await self.execute(intent, append_only=True)

    async def execute(self, intent: ExecutionIntent, *, append_only=False) -> ExecutionSample:
        intent = self.journal.prepare_execution(intent)
        if self.journal.get_execution_receipt(intent.operation_id) is not None:
            return self.journal.execution_samples[intent.operation_id]
        if self.journal.quarantined or intent.operation_id in self.journal.unknown_executions:
            raise self.journal.conflict("UNKNOWN execution requires explicit handling")
        if (self.journal.execution_fences[intent.operation_id] != (self.journal._invalidation, self.journal.business_generation)
                or (self.journal.binding is not None
                    and intent.binding_generation != self.journal.binding.binding_generation)):
            raise self.journal.conflict("UNKNOWN stale execution generation")
        receipts = self.journal.command_receipts[intent.operation_id]
        expected = intent.baseline
        confirmed = 0
        for index in range(len(intent.commands)):
            receipt = receipts.get(index)
            if receipt is None or receipt.phase != "confirmed":
                break
            expected = receipt.sample
            confirmed += 1
        try:
            actual = await self.player.read_execution_sample()
            self._verify_fence(intent)
            for index in range(confirmed, len(intent.commands)):
                command = intent.commands[index]
                receipt = receipts.get(index)
                if receipt and receipt.phase in {"sent", "ack"}:
                    if receipt.phase == "sent" and command.kind in {"add", "play", "pause"}:
                        self.journal.unknown_executions.add(intent.operation_id)
                        # A current fact cannot distinguish an unacknowledged
                        # play from natural advance or another transport owner.
                        raise self.journal.conflict("UNKNOWN lost response; never resend")
                    after = self._expected(intent, command, expected, receipt)
                    # A lost response is claimable only as a distinct, unique result.
                    if receipt.phase == "sent" and after == expected:
                        raise self.journal.conflict("UNKNOWN ambiguous command result")
                    self._verify(intent, actual, after, append_only=append_only)
                else:
                    self._verify(intent, actual, expected, append_only=append_only)
                    if command.kind == "play" and not intent.allow_start:
                        raise self.journal.conflict("UNKNOWN stopped execution cannot restart")
                    self.journal.record_command(intent.operation_id, index, CommandReceipt("sent"))
                    try:
                        returned_id = await self._send(intent, command)
                    except PlayerCommandError as error:
                        # The port's rejection is an ACK, not a successful response.
                        if error.command not in {"addid", "read_execution_sample", "status", "queue_entries"}:
                            self.journal.record_command(intent.operation_id, index, CommandReceipt("rejected"))
                        raise
                    self.journal.record_command(intent.operation_id, index, CommandReceipt("ack", returned_id))
                    receipt = receipts[index]
                    after = self._expected(intent, command, expected, receipt)
                    actual = await self.player.read_execution_sample()
                    self._verify_fence(intent)
                    self._verify(intent, actual, after, append_only=append_only)
                self.journal.record_command(intent.operation_id, index, CommandReceipt(
                    "confirmed", receipt.returned_id, actual,
                ))
                expected = actual
            self._verify_fence(intent)
            self._verify(intent, actual, expected, append_only=append_only)
            mapping = self.mapping(intent)
            if tuple((e.mpd_song_id, e.song_uri) for e in actual.entries) != tuple((key, uri) for _, key, uri in mapping):
                raise self.journal.conflict("UNKNOWN incomplete execution target")
            if intent.target_item_id is not None and not append_only:
                target_id = self._id(intent, intent.target_item_id)
                if actual.status.song_id != target_id or actual.status.state.value.upper() != intent.target_state:
                    raise self.journal.conflict("UNKNOWN unconfirmed execution target")
            self.journal.execution_samples[intent.operation_id] = actual
            return actual
        except (PlayerUnavailable, TimeoutError):
            self.journal.unknown_executions.add(intent.operation_id)
            self.journal.invalidate_binding()
            raise
        except PlayerCommandError as error:
            if error.command in {"read_execution_sample", "status", "queue_entries", "playlistinfo", "currentsong"}:
                self.journal.unknown_executions.add(intent.operation_id)
                self.journal.invalidate_binding()
            raise
