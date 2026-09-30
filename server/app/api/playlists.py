from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from server.app.repositories.playlist_repository import PlaylistNotFoundError
from server.app.services.collection_service import CollectionService
from server.app.services.playlist_service import PlaylistService

from .dependencies import get_collection_service, get_playlist_service
from .schemas import CollectionResponse, PlaylistListResponse, PlaylistResponse

router = APIRouter(tags=["playlists"])


def _playlist_response(playlist, song_ids: list[str]) -> PlaylistResponse:
    return PlaylistResponse(
        playlist_id=playlist.playlist_id,
        name=playlist.name,
        created_at=playlist.created_at,
        updated_at=playlist.updated_at,
        is_system=playlist.is_system,
        song_ids=song_ids,
    )


def _collection_response(collection) -> CollectionResponse:
    return CollectionResponse.model_validate(collection)


@router.get("/api/playlists", response_model=PlaylistListResponse)
async def list_playlists(
    service: PlaylistService = Depends(get_playlist_service),
) -> PlaylistListResponse:
    playlists = await service.list_playlists()
    items = [
        _playlist_response(
            playlist,
            await service.list_song_ids(playlist.playlist_id),
        )
        for playlist in playlists
    ]
    return PlaylistListResponse(items=items)


@router.get("/api/playlists/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(
    playlist_id: str,
    service: PlaylistService = Depends(get_playlist_service),
) -> PlaylistResponse:
    playlist = await service.get_playlist(playlist_id)
    if playlist is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PLAYLIST_NOT_FOUND",
                "message": f"playlist not found: {playlist_id}",
            },
        )
    try:
        song_ids = await service.list_song_ids(playlist_id)
    except PlaylistNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PLAYLIST_NOT_FOUND",
                "message": f"playlist not found: {exc.args[0]}",
            },
        ) from exc
    return _playlist_response(playlist, song_ids)


@router.get("/api/favorites", response_model=CollectionResponse)
async def get_favorites(
    collection_service: CollectionService = Depends(get_collection_service),
) -> CollectionResponse:
    return _collection_response(
        await collection_service.get_collection(source_type="FAVORITES")
    )
