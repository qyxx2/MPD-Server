"""Persist the next-start MPD endpoint without replacing the running PlayerPort."""

import ipaddress
import json
import os
import re
import tempfile
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class MPDConnectionAddress(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    host: str
    port: StrictInt = Field(ge=1, le=65535)

    @field_validator("host")
    @classmethod
    def valid_host(cls, host: str) -> str:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if (
                len(host) > 253
                or not re.fullmatch(
                    r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?",
                    host,
                )
                or any(
                    not label
                    or len(label) > 63
                    or label.startswith("-")
                    or label.endswith("-")
                    for label in host.split(".")
                )
            ):
                raise ValueError("MPD host must be an IP address or hostname") from None
        return host


class MPDConnectionSnapshot(BaseModel):
    active: MPDConnectionAddress
    saved: MPDConnectionAddress | None
    restart_required: bool


class MPDConnectionService:
    def __init__(self, path: Path, default: Callable[[], MPDConnectionAddress]):
        self.path = path
        try:
            self.active = self._saved() or default()
        except (OSError, ValueError) as exc:
            raise ValueError("Invalid saved MPD connection") from exc

    def _saved(self) -> MPDConnectionAddress | None:
        try:
            content = self.path.read_text()
        except FileNotFoundError:
            return None
        return MPDConnectionAddress.model_validate(json.loads(content))

    def get(self) -> MPDConnectionSnapshot:
        saved = self._saved()
        return MPDConnectionSnapshot(
            active=self.active,
            saved=saved,
            restart_required=saved is not None and saved != self.active,
        )

    def save(self, address: MPDConnectionAddress) -> MPDConnectionSnapshot:
        # The parent belongs to deployment, never create/replace directories here.
        fd, name = tempfile.mkstemp(prefix=".mpd-connection-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as file:
                file.write(address.model_dump_json())
                file.flush()
                os.fsync(file.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return self.get()
