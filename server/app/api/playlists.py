from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from server.app.models.library import Song
from server.app.repositories.playlist_repository import PlaylistNotFoundError
from server.app.services.library_service import LibraryService
from server.app.services.playlist_service import PlaylistService

from .dependencies import (
    get_library_service,
    get_playlist_service,
    resolve_collection_service,
)
from .schemas import (
    CollectionResponse,
    PlaylistListResponse,
    PlaylistResponse,
    SongListResponse,
    SongResponse,
)

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
    return CollectionResponse.model_validate(collection.model_dump())


def _song_response(song: Song) -> SongResponse:
    return SongResponse.model_validate(song)


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
    return PlaylistListResponse(items=items, count=len(items))


@router.get("/api/playlists/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(
    playlist_id: str,
    request: Request,
    service: PlaylistService = Depends(get_playlist_service),
) -> PlaylistResponse:
    playlist = await service.get_playlist(playlist_id)
    if playlist is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PLAYLIST_NOT_FOUND",
                "message": f"playlist not found: {playlist_id}",
                "details": None,
            },
        )

    collection_service = await resolve_collection_service(request)
    try:
        collection = await collection_service.get_collection(
            source_type="PLAYLIST",
            source_id=playlist_id,
        )
    except PlaylistNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PLAYLIST_NOT_FOUND",
                "message": f"playlist not found: {exc.args[0]}",
                "details": None,
            },
        ) from exc
    return _playlist_response(playlist, list(collection.song_ids))


@router.get("/api/playlists/{playlist_id}/songs", response_model=SongListResponse)
async def list_playlist_songs(
    playlist_id: str,
    request: Request,
    playlist_service: PlaylistService = Depends(get_playlist_service),
    library_service: LibraryService = Depends(get_library_service),
) -> SongListResponse:
    playlist = await playlist_service.get_playlist(playlist_id)
    if playlist is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PLAYLIST_NOT_FOUND",
                "message": f"playlist not found: {playlist_id}",
                "details": None,
            },
        )

    collection_service = await resolve_collection_service(request)
    try:
        collection = await collection_service.get_collection(
            source_type="PLAYLIST",
            source_id=playlist_id,
        )
    except PlaylistNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PLAYLIST_NOT_FOUND",
                "message": f"playlist not found: {exc.args[0]}",
                "details": None,
            },
        ) from exc

    items: list[SongResponse] = []
    for song_id in collection.song_ids:
        song = await library_service.get_song(song_id)
        if song is not None and song.availability_status == "AVAILABLE":
            items.append(_song_response(song))
    return SongListResponse(items=items, count=len(items))


@router.get("/api/favorites", response_model=CollectionResponse)
async def get_favorites(
    collection_service: CollectionService = Depends(resolve_collection_service),
) -> CollectionResponse:
    return _collection_response(
        await collection_service.get_collection(source_type="FAVORITES")
    )
