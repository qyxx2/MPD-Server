from typing import Annotated

from fastapi import APIRouter, Depends

from server.app.services.mpd_info_service import MPDInfoService
from server.app.services.output_manager import OutputManager

from .dependencies import get_mpd_info_service, get_output_manager
from .system_schemas import MPDInfoResponse, OutputSnapshotResponse

router = APIRouter(prefix="/api/system", tags=["system"])


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
