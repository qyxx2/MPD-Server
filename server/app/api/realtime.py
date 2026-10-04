import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket

from server.app.services.realtime_connections import RealtimeConnections
from server.app.services.state_service import StateService

from .dependencies import get_state_service
from .realtime_schemas import FullStateSnapshotResponse
from .schemas import ErrorResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["realtime"])


@router.get(
    "/state",
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


@router.websocket("/realtime")
async def realtime(socket: WebSocket) -> None:
    connections = RealtimeConnections(
        state_service=socket.app.state.state_service,
        coordinator=socket.app.state.realtime_coordinator,
        snapshot_encoder=lambda snapshot: FullStateSnapshotResponse.model_validate(
            snapshot.model_dump(),
        ).model_dump(mode="json"),
    )
    await connections.connect(socket)
