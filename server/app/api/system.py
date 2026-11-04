from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from server.app.models.hardware_volume import (
    HardwareVolumeObservation,
    HardwareVolumeSnapshot,
)
from server.app.player.ports import PlayerCommandError, PlayerUnavailable
from server.app.services.hardware_volume_manager import (
    HardwareVolumeError,
    HardwareVolumeManager,
)
from server.app.services.health_service import HealthResponse
from server.app.services.mpd_connection_service import (
    MPDConnectionAddress,
    MPDConnectionSnapshot,
)
from server.app.services.mpd_info_service import MPDInfoService
from server.app.services.output_manager import OutputError, OutputManager

from .dependencies import (
    get_hardware_volume_manager,
    get_mpd_info_service,
    get_output_manager,
)
from .schemas import ErrorResponse
from .system_schemas import (
    HardwareVolumeSetRequest,
    HardwareVolumeSnapshotResponse,
    MPDInfoResponse,
    OutputSetRequest,
    OutputSnapshotResponse,
)

health_router = APIRouter(tags=["system"])


@health_router.get("/api/health", response_model=HealthResponse)
async def health(request: Request, response: Response) -> HealthResponse:
    result = await request.app.state.health_service.read()
    response.status_code = 200 if result.status == "ok" else 503
    return result


router = APIRouter(prefix="/api/system", tags=["system"])


def _hardware_volume_response(
    snapshot: HardwareVolumeSnapshot,
    observation: HardwareVolumeObservation,
) -> HardwareVolumeSnapshotResponse:
    return HardwareVolumeSnapshotResponse.model_validate({
        "state": snapshot.state.model_dump(),
        "observation": observation.model_dump(),
        "last_request": (
            snapshot.last_request.model_dump() if snapshot.last_request is not None else None
        ),
    })


@router.get(
    "/hardware-volume",
    response_model=HardwareVolumeSnapshotResponse,
    responses={503: {"model": ErrorResponse, "description": "A complete hardware volume snapshot cannot be constructed"}},
)
async def get_hardware_volume(
    manager: Annotated[HardwareVolumeManager, Depends(get_hardware_volume_manager)],
) -> HardwareVolumeSnapshotResponse:
    await manager.get_state(read_timeout=5.0)
    observation = await manager.get_observation()
    # Read after the freshness check so the state and observation describe
    # the same accepted cache, including any stale transition.
    snapshot = manager.get_cached_state()
    return _hardware_volume_response(snapshot, observation)


@router.put(
    "/hardware-volume",
    response_model=HardwareVolumeSnapshotResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Hardware volume is not configured or the ALSA target is ambiguous"},
        422: {"model": ErrorResponse, "description": "The request value is not a strict integer from 0 to 100"},
        502: {"model": ErrorResponse, "description": "MPD rejected the write or readback could not confirm it"},
        503: {"model": ErrorResponse, "description": "MPD or the selected hardware volume target is unavailable"},
    },
)
async def set_hardware_volume(
    body: HardwareVolumeSetRequest,
    manager: Annotated[HardwareVolumeManager, Depends(get_hardware_volume_manager)],
) -> HardwareVolumeSnapshotResponse:
    try:
        snapshot = await manager.set_volume(body.volume_percent)
    except HardwareVolumeError as exc:
        error_code = (
            "HARDWARE_VOLUME_UNAVAILABLE"
            if exc.code in {"PLAYER_COMMAND_ERROR", "PLAYER_TIMEOUT", "PLAYER_OBSERVATION_FAILED"}
            else exc.code
        )
        status = {
            "HARDWARE_VOLUME_NOT_CONFIGURED": 400,
            "HARDWARE_VOLUME_OUTPUT_AMBIGUOUS": 400,
            "HARDWARE_VOLUME_WRITE_FAILED": 502,
            "HARDWARE_VOLUME_RECONCILIATION_FAILED": 502,
            "PLAYER_UNAVAILABLE": 503,
            "HARDWARE_VOLUME_UNAVAILABLE": 503,
        }.get(error_code, 502)
        raise HTTPException(status_code=status, detail={
            "code": error_code, "message": str(exc), "details": None,
        }) from exc
    except PlayerUnavailable as exc:
        raise HTTPException(status_code=503, detail={
            "code": "PLAYER_UNAVAILABLE", "message": str(exc), "details": None,
        }) from exc
    except PlayerCommandError as exc:
        code = (
            "HARDWARE_VOLUME_WRITE_FAILED"
            if exc.command == "set_volume"
            else "HARDWARE_VOLUME_UNAVAILABLE"
        )
        status = 502 if code == "HARDWARE_VOLUME_WRITE_FAILED" else 503
        raise HTTPException(status_code=status, detail={
            "code": code, "message": str(exc), "details": None,
        }) from exc

    observation = await manager.get_observation()
    return _hardware_volume_response(snapshot, observation)


@router.put("/output", response_model=OutputSnapshotResponse)
async def set_output(
    request: OutputSetRequest,
    manager: Annotated[OutputManager, Depends(get_output_manager)],
) -> OutputSnapshotResponse:
    try:
        snapshot = await manager.set_enabled(request.mode, request.enabled)
    except OutputError as exc:
        status = 502
        if exc.code in {"OUTPUT_MODE_UNSUPPORTED", "OUTPUT_AMBIGUOUS", "OUTPUT_SELECTION_FAILED"}:
            status = 400
        elif exc.code in {"OUTPUT_UNAVAILABLE", "OUTPUT_CAPABILITY_UNVERIFIED"}:
            status = 503
        raise HTTPException(status_code=status, detail={
            "code": exc.code, "message": str(exc), "details": None,
        }) from exc
    except PlayerUnavailable as exc:
        raise HTTPException(status_code=503, detail={
            "code": "PLAYER_UNAVAILABLE", "message": str(exc), "details": None,
        }) from exc
    except PlayerCommandError as exc:
        raise HTTPException(status_code=502, detail={
            "code": "PLAYER_COMMAND_FAILED", "message": str(exc),
            "details": {"command": exc.command, "error_code": exc.error_code,
                        "command_list_index": exc.command_list_index},
        }) from exc
    return OutputSnapshotResponse.model_validate(snapshot.model_dump())


@router.get("/output", response_model=OutputSnapshotResponse)
async def get_output(
    manager: Annotated[OutputManager, Depends(get_output_manager)],
) -> OutputSnapshotResponse:
    return OutputSnapshotResponse.model_validate((await manager.get_state()).model_dump())


@router.get("/mpd", response_model=MPDInfoResponse)
async def get_mpd_info(
    service: Annotated[MPDInfoService, Depends(get_mpd_info_service)],
) -> MPDInfoResponse:
    return MPDInfoResponse.model_validate((await service.get_info()).model_dump())


@router.get("/mpd/connection", response_model=MPDConnectionSnapshot)
async def get_mpd_connection(request: Request) -> MPDConnectionSnapshot:
    try:
        return request.app.state.mpd_connection_service.get()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail={
            "code": "MPD_CONNECTION_READ_FAILED", "message": "Cannot read saved MPD connection",
        }) from exc


@router.put("/mpd/connection", response_model=MPDConnectionSnapshot)
async def save_mpd_connection(address: MPDConnectionAddress, request: Request) -> MPDConnectionSnapshot:
    try:
        return request.app.state.mpd_connection_service.save(address)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail={
            "code": "MPD_CONNECTION_SAVE_FAILED", "message": "Cannot save MPD connection",
        }) from exc
