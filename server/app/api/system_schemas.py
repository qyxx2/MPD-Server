from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from server.app.models.output import OutputMode


class OutputStateResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    mode: OutputMode
    status: Literal["UNAVAILABLE", "INACTIVE", "ACTIVE"]
    target_client_id: str | None
    stream_url: str | None
    format: str | None
    sample_rate: int | None
    bit_depth: int | None
    channels: int | None
    error_code: str | None
    error_message: str | None
    updated_at: datetime
    stale: bool


class OutputRequestResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    mode: OutputMode
    enabled: bool
    status: Literal["PREPARING", "SUCCEEDED", "SWITCH_FAILED"]
    error_code: str | None
    error_message: str | None
    updated_at: datetime


class OutputSnapshotResponse(BaseModel):
    states: tuple[OutputStateResponse, ...]
    last_request: OutputRequestResponse | None


class MPDStatsResponse(BaseModel):
    artists: int | None
    albums: int | None
    songs: int | None
    uptime: int | None
    db_playtime: int | None
    db_update: int | None
    playtime: int | None


class DatabaseUpdateResponse(BaseModel):
    updating: bool | None
    job_id: int | None


class MPDInfoErrorResponse(BaseModel):
    code: Literal["CAPABILITY_UNVERIFIED", "PLAYER_UNAVAILABLE", "PLAYER_COMMAND_ERROR"]
    message: str


class MPDInfoResponse(BaseModel):
    version: str | None
    version_source: Literal["verified_capability"] | None
    stats: MPDStatsResponse
    database_update_status: DatabaseUpdateResponse
    connected: bool | None
    errors: dict[str, MPDInfoErrorResponse]
    observed_at: datetime
