from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from server.app.models.history import HistoryEvent
from server.app.models.queue import QueueItem
from server.app.services.history_service import HistoryService

from .dependencies import get_history_service
from .schemas import (
    HistoryEventResponse,
    HistoryListResponse,
    QueueItemResponse,
    QueueListResponse,
)

router = APIRouter(prefix="/api/history", tags=["history"])


def _history_response(event: HistoryEvent) -> HistoryEventResponse:
    return HistoryEventResponse.model_validate(event.model_dump())


def _history_list_response(events: list[HistoryEvent]) -> HistoryListResponse:
    items = [_history_response(event) for event in events]
    return HistoryListResponse(items=items, count=len(items))


def _played_list_response(items: list[QueueItem]) -> QueueListResponse:
    response_items = [
        QueueItemResponse.model_validate(item.model_dump()) for item in items
    ]
    return QueueListResponse(items=response_items, count=len(response_items))


@router.get("", response_model=HistoryListResponse)
async def list_history(
    service: Annotated[HistoryService, Depends(get_history_service)],
) -> HistoryListResponse:
    return _history_list_response(await service.list_history())


@router.get("/played", response_model=QueueListResponse)
async def list_played(
    service: Annotated[HistoryService, Depends(get_history_service)],
) -> QueueListResponse:
    return _played_list_response(await service.list_played())
