import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from server.app.services.state_service import StateService

from .dependencies import get_state_service
from .realtime_schemas import FullStateSnapshotResponse
from .schemas import ErrorResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/state", tags=["realtime"])


@router.get(
    "",
    response_model=FullStateSnapshotResponse,
    response_model_by_alias=False,
    responses={503: {"model": ErrorResponse}},
)
async def get_state(
    service: Annotated[StateService, Depends(get_state_service)],
) -> FullStateSnapshotResponse:
    try:
        snapshot = await service.get_full_snapshot()
        return FullStateSnapshotResponse.model_validate(snapshot.model_dump())
    except Exception as exc:
        logger.exception("State snapshot unavailable")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "STATE_SNAPSHOT_UNAVAILABLE",
                "message": "State snapshot is unavailable",
            },
        ) from exc
