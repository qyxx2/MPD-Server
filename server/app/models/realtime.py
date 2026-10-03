from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StateMarker(BaseModel):
    model_config = ConfigDict(frozen=True)

    epoch: str
    sequence: int = Field(default=0, ge=0)
    library_revision: int = Field(default=0, ge=0)
    playlist_revision: int = Field(default=0, ge=0)


class Invalidation(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["invalidate"] = "invalidate"
    protocol_version: Literal[1] = 1
    epoch: str
    sequence: int = Field(ge=0)
    domains: frozenset[str]
    revisions: dict[str, int]
