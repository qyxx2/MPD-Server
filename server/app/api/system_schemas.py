from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool
from pydantic.alias_generators import to_camel

from server.app.models.hardware_volume import (
    HardwareVolumeControlSource,
    HardwareVolumeRequestStatus,
    HardwareVolumeStatus,
)
from server.app.models.output import OutputMode


class OutputSetRequest(BaseModel):
    mode: OutputMode
    enabled: StrictBool


class HardwareVolumeSetRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    volume_percent: int = Field(strict=True, ge=0, le=100)


class HardwareVolumeStateResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    status: HardwareVolumeStatus
    volume_percent: int | None = Field(default=None, strict=True, ge=0, le=100)
    output_name: str | None
    output_plugin: str | None
    output_enabled: bool | None
    control_source: HardwareVolumeControlSource | None
    error_code: str | None
    error_message: str | None
    updated_at: datetime
    stale: bool


class HardwareVolumeRequestResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    requested_percent: int = Field(strict=True, ge=0, le=100)
    status: HardwareVolumeRequestStatus
    error_code: str | None
    error_message: str | None
    updated_at: datetime


class HardwareVolumeObservationResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    observed_at: datetime | None
    freshness: Literal["fresh", "stale", "unknown"]
    error_code: str | None
    error_message: str | None


class HardwareVolumeSnapshotResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    state: HardwareVolumeStateResponse
    observation: HardwareVolumeObservationResponse
    last_request: HardwareVolumeRequestResponse | None


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
