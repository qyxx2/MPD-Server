from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

_ACK_RE = re.compile(
    r"^ACK \[(?P<error>\d+)@(?P<index>\d+)\] "
    r"\{(?P<command>[^}]*)\}(?: (?P<message>.*))?$"
)


class MPDProtocolError(ValueError):
    """An MPD response could not be parsed."""


class MPDAckError(MPDProtocolError):
    """MPD returned a command error."""

    def __init__(self, error_code: int, command_list_index: int, command: str, message: str):
        self.error_code = error_code
        self.command_list_index = command_list_index
        self.command = command
        self.message = message
        super().__init__(message or f"MPD command failed: {command}")


@dataclass(frozen=True)
class MPDResponse:
    pairs: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, str | list[str]]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for key, value in self.pairs:
            grouped[key].append(value)
        return {key: values[0] if len(values) == 1 else values for key, values in grouped.items()}


def parse_response(lines: Iterable[str]) -> MPDResponse:
    pairs: list[tuple[str, str]] = []
    saw_completion = False

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if line == "OK":
            saw_completion = True
            break
        if line == "list_OK":
            continue
        if line.startswith("ACK "):
            match = _ACK_RE.fullmatch(line)
            if match is None:
                raise MPDProtocolError(f"malformed ACK response: {line}")
            raise MPDAckError(
                int(match.group("error")),
                int(match.group("index")),
                match.group("command"),
                match.group("message") or "",
            )
        if ":" not in line:
            raise MPDProtocolError(f"malformed response line: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        if not key:
            raise MPDProtocolError(f"malformed response line: {line}")
        pairs.append((key, decode_value(value.removeprefix(" "))))

    if not saw_completion:
        raise MPDProtocolError("missing completion code")
    return MPDResponse(tuple(pairs))


def decode_value(value: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(value):
        if value[i] != "\\":
            out.append(value[i])
            i += 1
            continue
        i += 1
        if i == len(value):
            out.append("\\")
            break
        escaped = value[i]
        out.append({"\\": "\\", "n": "\n", "r": "\r", "t": "\t"}.get(escaped, escaped))
        i += 1
    return "".join(out)


def quote_argument(value: str) -> str:
    if value and not any(char in value for char in ' \t\r\n\\\"'):
        return value
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'
