from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from server.app.player.ports import PlayerCommandError, PlayerUnavailable
from server.app.services.mpd_info_service import MPDInfoService
from server.app.services.output_manager import OutputError, OutputManager

from .dependencies import get_mpd_info_service, get_output_manager
from .system_schemas import (
    MPDInfoResponse,
    OutputSetRequest,
    OutputSnapshotResponse,
)

router = APIRouter(prefix="/api/system", tags=["system"])


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
