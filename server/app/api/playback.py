from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from server.app.models.queue import PlaybackState, QueueItem
from server.app.player.ports import PlayerCommandError, PlayerUnavailable
from server.app.services.collection_service import CollectionService
from server.app.services.playback_service import PlaybackService
from server.app.services.playlist_service import PlaylistService
from server.app.services.queue_manager import (
    CurrentTrackDeletionError,
    QueueItemNotFoundError,
    QueueManager,
    QueueRevisionConflictError,
)

from .dependencies import (
    get_collection_service,
    get_playback_service,
    get_playlist_service,
    get_queue_manager,
)
from .schemas import (
    CollectionRequest,
    PlaybackContextResponse,
    PlaybackStateResponse,
    PlaylistResponse,
    QueueItemResponse,
    QueueListResponse,
    QueueReorderRequest,
    SaveQueueAsPlaylistRequest,
    SeekRequest,
)

router = APIRouter(prefix="/api/playback", tags=["playback"])


def _playback_state_response(
    state: PlaybackState | None,
) -> PlaybackStateResponse | None:
    if state is None:
        return None
    return PlaybackStateResponse.model_validate(state.model_dump())


def _queue_item_response(item: QueueItem) -> QueueItemResponse:
    return QueueItemResponse.model_validate(item.model_dump())


def _queue_response(items: list[QueueItem]) -> QueueListResponse:
    return QueueListResponse(
        items=[_queue_item_response(item) for item in items],
        count=len(items),
    )


def _playlist_response(playlist, song_ids: list[str] | None = None) -> PlaylistResponse:
    return PlaylistResponse(
        playlist_id=playlist.playlist_id,
        name=playlist.name,
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
        is_system=playlist.is_system,
        song_ids=song_ids or [],
    )


def _raise_playback_http_error(exc: Exception) -> None:
    if isinstance(exc, PlayerUnavailable):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "PLAYER_UNAVAILABLE",
                "message": str(exc),
                "details": None,
            },
        ) from exc
    if isinstance(exc, PlayerCommandError):
        raise HTTPException(
            status_code=502,
            detail={
                "code": "PLAYER_COMMAND_FAILED",
                "message": str(exc),
                "details": {
                    "command": exc.command,
                    "error_code": exc.error_code,
                    "command_list_index": exc.command_list_index,
                },
            },
        ) from exc
    if isinstance(exc, QueueRevisionConflictError):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "QUEUE_REVISION_CONFLICT",
                "message": str(exc),
                "details": {
                    "expected_revision": exc.expected_revision,
                    "actual_revision": exc.actual_revision,
                },
            },
        ) from exc
    if isinstance(exc, QueueItemNotFoundError):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "QUEUE_ITEM_NOT_FOUND",
                "message": str(exc),
                "details": None,
            },
        ) from exc
    if isinstance(exc, CurrentTrackDeletionError):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CURRENT_TRACK_DELETE_CONFLICT",
                "message": str(exc),
                "details": None,
            },
        ) from exc
    if isinstance(exc, ValueError):
        message = str(exc)
        status_code = 404 if message.startswith(
            ("song not found:", "song is not available:")
        ) else 400
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": "PLAYBACK_REQUEST_INVALID",
                "message": message,
                "details": None,
            },
        ) from exc
    raise exc


@router.get("/state", response_model=PlaybackStateResponse | None)
async def get_playback_state(
    service: Annotated[QueueManager, Depends(get_queue_manager)],
) -> PlaybackStateResponse | None:
    return _playback_state_response(await service.get_playback_state())


@router.get("/queue", response_model=QueueListResponse)
async def get_queue(
    service: Annotated[QueueManager, Depends(get_queue_manager)],
) -> QueueListResponse:
    return _queue_response(await service.list_items())


@router.post(
    "/tracks/{song_id}/play",
    response_model=PlaybackContextResponse,
)
async def play_track(
    song_id: str,
    service: Annotated[PlaybackService, Depends(get_playback_service)],
) -> PlaybackContextResponse:
    try:
        context = await service.start_track(song_id)
    except Exception as exc:
        _raise_playback_http_error(exc)
        raise
    return PlaybackContextResponse(
        context_id=context.context_id,
        source_type=context.source_type,
        source_id=context.source_id,
        ordered_song_ids=list(context.ordered_song_ids),
        random_seed=context.random_seed,
    )


@router.post(
    "/queue/items/{queue_item_id}/play",
    response_model=QueueItemResponse,
)
async def play_queue_item(
    queue_item_id: str,
    service: Annotated[PlaybackService, Depends(get_playback_service)],
) -> QueueItemResponse:
    try:
        return _queue_item_response(await service.play_now(queue_item_id))
    except Exception as exc:
        _raise_playback_http_error(exc)
        raise


@router.post("/songs/{song_id}/play-next", response_model=QueueItemResponse)
async def play_song_next(
    song_id: str,
    service: Annotated[PlaybackService, Depends(get_playback_service)],
) -> QueueItemResponse:
    try:
        return _queue_item_response(await service.play_next(song_id))
    except Exception as exc:
        _raise_playback_http_error(exc)
        raise


@router.post("/songs/{song_id}/queue", response_model=QueueItemResponse)
async def queue_song(
    song_id: str,
    service: Annotated[PlaybackService, Depends(get_playback_service)],
) -> QueueItemResponse:
    try:
        return _queue_item_response(await service.add_to_queue(song_id))
    except Exception as exc:
        _raise_playback_http_error(exc)
        raise


@router.post("/pause", response_model=PlaybackStateResponse | None)
async def pause(
    service: Annotated[PlaybackService, Depends(get_playback_service)],
) -> PlaybackStateResponse | None:
    try:
        return _playback_state_response(await service.pause())
    except Exception as exc:
        _raise_playback_http_error(exc)
        raise


@router.post("/stop", response_model=PlaybackStateResponse | None)
async def stop(
    service: Annotated[PlaybackService, Depends(get_playback_service)],
) -> PlaybackStateResponse | None:
    try:
        return _playback_state_response(await service.stop())
    except Exception as exc:
        _raise_playback_http_error(exc)
        raise


@router.post("/next", response_model=PlaybackStateResponse | None)
async def next_track(
    service: Annotated[PlaybackService, Depends(get_playback_service)],
) -> PlaybackStateResponse | None:
    try:
        return _playback_state_response(await service.next())
    except Exception as exc:
        _raise_playback_http_error(exc)
        raise


@router.post("/previous", response_model=PlaybackStateResponse | None)
async def previous_track(
    service: Annotated[PlaybackService, Depends(get_playback_service)],
) -> PlaybackStateResponse | None:
    try:
        return _playback_state_response(await service.previous())
    except Exception as exc:
        _raise_playback_http_error(exc)
        raise


@router.post("/seek", response_model=PlaybackStateResponse | None)
async def seek(
    request: SeekRequest,
    service: Annotated[PlaybackService, Depends(get_playback_service)],
) -> PlaybackStateResponse | None:
    try:
        return _playback_state_response(await service.seek(request.seconds))
    except Exception as exc:
        _raise_playback_http_error(exc)
        raise


@router.post("/collections/play", response_model=PlaybackStateResponse | None)
async def play_collection(
    request: CollectionRequest,
    collection_service: Annotated[
        CollectionService, Depends(get_collection_service)
    ],
    playback_service: Annotated[PlaybackService, Depends(get_playback_service)],
) -> PlaybackStateResponse | None:
    try:
        collection = await collection_service.get_collection(
            source_type=request.source_type,
            source_id=request.source_id,
            query=request.query,
            song_ids=request.song_ids,
            randomize=request.randomize,
            random_seed=request.random_seed,
        )
        context = collection_service.create_playback_context(collection)
        return _playback_state_response(await playback_service.play_context(context))
    except Exception as exc:
        _raise_playback_http_error(exc)
        raise


@router.put(
    "/queue/items/{queue_item_id}",
    response_model=QueueListResponse,
)
async def reorder_queue_item(
    queue_item_id: str,
    request: QueueReorderRequest,
    service: Annotated[QueueManager, Depends(get_queue_manager)],
) -> QueueListResponse:
    try:
        items = await service.reorder(
            queue_item_id,
            request.before_queue_item_id,
        )
        return _queue_response(items)
    except Exception as exc:
        _raise_playback_http_error(exc)
        raise


@router.delete("/queue/items/{queue_item_id}", status_code=204)
async def delete_queue_item(
    queue_item_id: str,
    service: Annotated[QueueManager, Depends(get_queue_manager)],
) -> None:
    try:
        await service.delete(queue_item_id)
    except Exception as exc:
        _raise_playback_http_error(exc)
        raise


@router.delete("/queue", status_code=204)
async def clear_queue(
    service: Annotated[QueueManager, Depends(get_queue_manager)],
) -> None:
    try:
        await service.clear()
    except Exception as exc:
        _raise_playback_http_error(exc)
        raise


@router.post("/queue/save-as-playlist", response_model=PlaylistResponse)
async def save_queue_as_playlist(
    request: SaveQueueAsPlaylistRequest,
    queue_manager: Annotated[QueueManager, Depends(get_queue_manager)],
    playlist_service: Annotated[
        PlaylistService, Depends(get_playlist_service)
    ],
) -> PlaylistResponse:
    try:
        playlist = await queue_manager.save_as_playlist(request.name)
        return _playlist_response(
            playlist,
            await playlist_service.list_song_ids(playlist.playlist_id),
        )
    except Exception as exc:
        _raise_playback_http_error(exc)
        raise
