from __future__ import annotations

import asyncio
import shlex
from dataclasses import dataclass


@dataclass(frozen=True)
class FakeMPDQueueEntry:
    mpd_song_id: int
    position: int
    song_uri: str


@dataclass(frozen=True)
class FakeMPDSnapshot:
    queue: tuple[FakeMPDQueueEntry, ...]
    current_song_uri: str | None
    player_state: str
    elapsed: float
    volume: int
    repeat: bool
    random: bool


class StatefulFakeMPD:
    """Stateful MPD 0.23.5-shaped TCP fake for service-to-adapter integration tests."""

    def __init__(self) -> None:
        self.host = "127.0.0.1"
        self._server: asyncio.AbstractServer | None = None
        self._writers: set[asyncio.StreamWriter] = set()

        self.queue: list[FakeMPDQueueEntry] = []
        self.current_song_id: int | None = None
        self.player_state = "stop"
        self.elapsed = 0.0
        self.volume = 50
        self.repeat = False
        self.random = False

        self._next_song_id = 1
        self._fail_next: dict[str, tuple[int, str]] = {}

    @property
    def port(self) -> int:
        if self._server is None or not self._server.sockets:
            raise RuntimeError("Fake MPD server is not started")
        return int(self._server.sockets[0].getsockname()[1])

    async def start(self) -> None:
        if self._server is not None:
            raise RuntimeError("Fake MPD server is already started")
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            0,
        )

    async def close(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.close()
            await server.wait_closed()

        writers = list(self._writers)
        self._writers.clear()
        for writer in writers:
            writer.close()
        for writer in writers:
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass

    def fail_next(
        self,
        command: str,
        message: str = "injected MPD command failure",
        *,
        error_code: int = 50,
    ) -> None:
        self._fail_next[command] = (error_code, message)

    async def queue_entries(self) -> list[FakeMPDQueueEntry]:
        return list(self.queue)

    async def snapshot(self) -> FakeMPDSnapshot:
        current_uri = None
        if self.current_song_id is not None:
            current = self._find_entry(self.current_song_id)
            if current is not None:
                current_uri = current.song_uri
        return FakeMPDSnapshot(
            queue=tuple(self.queue),
            current_song_uri=current_uri,
            player_state=self.player_state,
            elapsed=self.elapsed,
            volume=self.volume,
            repeat=self.repeat,
            random=self.random,
        )

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self._writers.add(writer)
        writer.write(b"OK MPD 0.23.5\n")
        await writer.drain()
        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    return

                request = raw.decode("utf-8").rstrip("\r\n")
                try:
                    response = self._dispatch(request)
                except ValueError as exc:
                    writer.write(
                        f"ACK [2@0] {{command}} {exc}\n".encode("utf-8")
                    )
                except Exception as exc:
                    writer.write(
                        f"ACK [50@0] {{command}} {exc}\n".encode("utf-8")
                    )
                else:
                    writer.write(response.encode("utf-8"))
                await writer.drain()
        finally:
            self._writers.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass

    def _dispatch(self, request: str) -> str:
        parts = shlex.split(request)
        if not parts:
            return "OK\n"

        command = parts[0]
        args = parts[1:]

        injected = self._fail_next.pop(command, None)
        if injected is not None:
            error_code, message = injected
            return f"ACK [{error_code}@0] {{{command}}} {message}\n"

        handlers = {
            "status": self._cmd_status,
            "currentsong": self._cmd_currentsong,
            "playlistinfo": self._cmd_playlistinfo,
            "addid": self._cmd_addid,
            "deleteid": self._cmd_deleteid,
            "moveid": self._cmd_moveid,
            "playid": self._cmd_playid,
            "pause": self._cmd_pause,
            "stop": self._cmd_stop,
            "next": self._cmd_next,
            "previous": self._cmd_previous,
            "play": self._cmd_play,
            "repeat": self._cmd_repeat,
            "random": self._cmd_random,
            "setvol": self._cmd_setvol,
        }
        handler = handlers.get(command)
        if handler is None:
            return f"ACK [5@0] {{{command}}} unsupported command\n"
        return handler(args)

    def _cmd_status(self, args: list[str]) -> str:
        del args
        position = -1
        song_id = -1
        if self.current_song_id is not None:
            current = self._find_entry(self.current_song_id)
            if current is not None:
                position = current.position
                song_id = current.mpd_song_id

        lines = [
            f"volume: {self.volume}",
            f"repeat: {1 if self.repeat else 0}",
            f"random: {1 if self.random else 0}",
            f"state: {self.player_state}",
            f"song: {position}",
            f"songid: {song_id}",
            f"elapsed: {self.elapsed:.3f}",
            "duration: 180.0",
            "OK\n",
        ]
        return "\n".join(lines)

    def _cmd_currentsong(self, args: list[str]) -> str:
        del args
        if self.current_song_id is None:
            return "OK\n"
        current = self._find_entry(self.current_song_id)
        if current is None:
            return "OK\n"
        return (
            f"file: {current.song_uri}\n"
            f"Pos: {current.position}\n"
            f"Id: {current.mpd_song_id}\n"
            "OK\n"
        )

    def _cmd_playlistinfo(self, args: list[str]) -> str:
        del args
        lines: list[str] = []
        for entry in self.queue:
            lines.extend(
                [
                    f"file: {entry.song_uri}",
                    f"Pos: {entry.position}",
                    f"Id: {entry.mpd_song_id}",
                ]
            )
        lines.append("OK")
        return "\n".join(lines) + "\n"

    def _cmd_addid(self, args: list[str]) -> str:
        if len(args) != 1:
            return "ACK [2@0] {addid} expected one song URI\n"
        song_id = self._next_song_id
        self._next_song_id += 1
        self.queue.append(
            FakeMPDQueueEntry(
                mpd_song_id=song_id,
                position=len(self.queue),
                song_uri=args[0],
            )
        )
        return f"Id: {song_id}\nOK\n"

    def _cmd_deleteid(self, args: list[str]) -> str:
        if len(args) != 1:
            return "ACK [2@0] {deleteid} expected one song id\n"
        target_id = int(args[0])
        index = self._index_of(target_id)
        if index is None:
            return f"ACK [50@0] {{deleteid}} No such song id {target_id}\n"

        del self.queue[index]
        self._renumber_positions()
        if self.current_song_id == target_id:
            self.current_song_id = None
            self.player_state = "stop"
            self.elapsed = 0.0
        return "OK\n"

    def _cmd_moveid(self, args: list[str]) -> str:
        if len(args) != 2:
            return "ACK [2@0] {moveid} expected song id and destination\n"
        target_id = int(args[0])
        destination = int(args[1])
        source_index = self._index_of(target_id)
        if source_index is None:
            return f"ACK [50@0] {{moveid}} No such song id {target_id}\n"

        entry = self.queue.pop(source_index)
        destination = max(0, min(destination, len(self.queue)))
        self.queue.insert(destination, entry)
        self._renumber_positions()
        return "OK\n"

    def _cmd_playid(self, args: list[str]) -> str:
        if len(args) != 1:
            return "ACK [2@0] {playid} expected one song id\n"
        target_id = int(args[0])
        if self._find_entry(target_id) is None:
            return f"ACK [50@0] {{playid}} No such song id {target_id}\n"

        self.current_song_id = target_id
        self.player_state = "play"
        self.elapsed = 0.0
        return "OK\n"

    def _cmd_pause(self, args: list[str]) -> str:
        if not self.queue:
            return "OK\n"
        enabled = True if not args else args[0] == "1"
        if enabled:
            self.player_state = "pause"
        else:
            self.player_state = "play"
        return "OK\n"

    def _cmd_stop(self, args: list[str]) -> str:
        del args
        self.player_state = "stop"
        return "OK\n"

    def _cmd_next(self, args: list[str]) -> str:
        del args
        if not self.queue:
            return "OK\n"
        current_index = self._current_index()
        if current_index is None:
            target_index = 0
        elif current_index + 1 < len(self.queue):
            target_index = current_index + 1
        elif self.repeat:
            target_index = 0
        else:
            self.player_state = "stop"
            return "OK\n"

        self.current_song_id = self.queue[target_index].mpd_song_id
        self.player_state = "play"
        self.elapsed = 0.0
        return "OK\n"

    def _cmd_previous(self, args: list[str]) -> str:
        del args
        if not self.queue:
            return "OK\n"
        current_index = self._current_index()
        if current_index is None:
            target_index = 0
        elif current_index > 0:
            target_index = current_index - 1
        elif self.repeat:
            target_index = len(self.queue) - 1
        else:
            self.player_state = "stop"
            return "OK\n"

        self.current_song_id = self.queue[target_index].mpd_song_id
        self.player_state = "play"
        self.elapsed = 0.0
        return "OK\n"

    def _cmd_play(self, args: list[str]) -> str:
        del args
        if not self.queue:
            return "OK\n"
        if self.current_song_id is None:
            self.current_song_id = self.queue[0].mpd_song_id
        self.player_state = "play"
        self.elapsed = 0.0
        return "OK\n"

    def _cmd_repeat(self, args: list[str]) -> str:
        if len(args) != 1:
            return "ACK [2@0] {repeat} expected 0 or 1\n"
        self.repeat = args[0] == "1"
        return "OK\n"

    def _cmd_random(self, args: list[str]) -> str:
        if len(args) != 1:
            return "ACK [2@0] {random} expected 0 or 1\n"
        self.random = args[0] == "1"
        return "OK\n"

    def _cmd_setvol(self, args: list[str]) -> str:
        if len(args) != 1:
            return "ACK [2@0] {setvol} expected one volume\n"
        volume = int(args[0])
        if not 0 <= volume <= 100:
            return "ACK [50@0] {setvol} invalid volume\n"
        self.volume = volume
        return "OK\n"

    def _find_entry(self, mpd_song_id: int) -> FakeMPDQueueEntry | None:
        for entry in self.queue:
            if entry.mpd_song_id == mpd_song_id:
                return entry
        return None

    def _index_of(self, mpd_song_id: int) -> int | None:
        for index, entry in enumerate(self.queue):
            if entry.mpd_song_id == mpd_song_id:
                return index
        return None

    def _current_index(self) -> int | None:
        if self.current_song_id is None:
            return None
        return self._index_of(self.current_song_id)

    def _renumber_positions(self) -> None:
        self.queue = [
            FakeMPDQueueEntry(
                mpd_song_id=entry.mpd_song_id,
                position=index,
                song_uri=entry.song_uri,
            )
            for index, entry in enumerate(self.queue)
        ]
