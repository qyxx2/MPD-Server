from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from server.app.models.library import Song
from server.app.services.collection_service import CollectionService
from server.app.services.library_service import LibraryService
from server.app.services.playlist_service import (
    DuplicatePlaylistSongError,
    PlaylistNotFoundError,
    PlaylistService,
    SystemPlaylistModificationError,
)

from .dependencies import (
    get_library_service,
    get_playlist_service,
    resolve_collection_service,
)
from .schemas import (
    CollectionResponse,
    PlaylistCreateRequest,
    PlaylistListResponse,
    PlaylistOrderRequest,
    PlaylistResponse,
    PlaylistSongRequest,
    PlaylistUpdateRequest,
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


def _playlist_not_found(playlist_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "code": "PLAYLIST_NOT_FOUND",
            "message": f"playlist not found: {playlist_id}",
            "details": None,
        },
    )


@router.get("/api/playlists", response_model=PlaylistListResponse)
async def list_playlists(
    service: Annotated[PlaylistService, Depends(get_playlist_service)],
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
    service: Annotated[PlaylistService, Depends(get_playlist_service)],
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
    playlist_service: Annotated[PlaylistService, Depends(get_playlist_service)],
    library_service: Annotated[LibraryService, Depends(get_library_service)],
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
    collection_service: Annotated[
        CollectionService, Depends(resolve_collection_service)
    ],
) -> CollectionResponse:
    return _collection_response(
        await collection_service.get_collection(source_type="FAVORITES")
    )


def _raise_playlist_http_error(exc: Exception) -> None:
    if isinstance(exc, PlaylistNotFoundError):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PLAYLIST_NOT_FOUND",
                "message": f"playlist not found: {exc.args[0]}",
                "details": None,
            },
        ) from exc
    if isinstance(exc, (DuplicatePlaylistSongError, SystemPlaylistModificationError)):
        raise HTTPException(
            status_code=409,
            detail={
                "code": (
                    "DUPLICATE_PLAYLIST_SONG"
                    if isinstance(exc, DuplicatePlaylistSongError)
                    else "SYSTEM_PLAYLIST_MODIFICATION"
                ),
                "message": str(exc),
                "details": None,
            },
        ) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "PLAYLIST_REQUEST_INVALID",
                "message": str(exc),
                "details": None,
            },
        ) from exc
    raise exc


@router.post("/api/playlists", response_model=PlaylistResponse, status_code=201)
async def create_playlist(
    request: PlaylistCreateRequest,
    service: Annotated[PlaylistService, Depends(get_playlist_service)],
) -> PlaylistResponse:
    created = await service.create_playlist(request.name)
    playlist = await service.get_playlist(created.playlist_id)
    if playlist is None:
        raise _playlist_not_found(created.playlist_id)
    return _playlist_response(
        playlist,
        await service.list_song_ids(playlist.playlist_id),
    )


@router.patch("/api/playlists/{playlist_id}", response_model=PlaylistResponse)
async def update_playlist(
    playlist_id: str,
    request: PlaylistUpdateRequest,
    service: Annotated[PlaylistService, Depends(get_playlist_service)],
) -> PlaylistResponse:
    try:
        await service.update_playlist(playlist_id, request.name)
        playlist = await service.get_playlist(playlist_id)
        if playlist is None:
            raise _playlist_not_found(playlist_id)
        return _playlist_response(
            playlist,
            await service.list_song_ids(playlist_id),
        )
    except Exception as exc:
        _raise_playlist_http_error(exc)
        raise


@router.delete("/api/playlists/{playlist_id}", status_code=204)
async def delete_playlist(
    playlist_id: str,
    service: Annotated[PlaylistService, Depends(get_playlist_service)],
) -> None:
    try:
        await service.delete_playlist(playlist_id)
    except Exception as exc:
        _raise_playlist_http_error(exc)
        raise


@router.post(
    "/api/playlists/{playlist_id}/songs",
    response_model=PlaylistResponse,
)
async def add_playlist_song(
    playlist_id: str,
    request: PlaylistSongRequest,
    service: Annotated[PlaylistService, Depends(get_playlist_service)],
) -> PlaylistResponse:
    try:
        await service.add_song(
            playlist_id,
            request.song_id,
            position=request.position,
        )
        playlist = await service.get_playlist(playlist_id)
        if playlist is None:
            raise _playlist_not_found(playlist_id)
        return _playlist_response(
            playlist,
            await service.list_song_ids(playlist_id),
        )
    except Exception as exc:
        _raise_playlist_http_error(exc)
        raise


@router.delete(
    "/api/playlists/{playlist_id}/songs/{song_id}",
    status_code=204,
)
async def remove_playlist_song(
    playlist_id: str,
    song_id: str,
    service: Annotated[PlaylistService, Depends(get_playlist_service)],
) -> None:
    try:
        await service.remove_song(playlist_id, song_id)
    except Exception as exc:
        _raise_playlist_http_error(exc)
        raise


@router.put(
    "/api/playlists/{playlist_id}/songs/order",
    response_model=PlaylistResponse,
)
async def reorder_playlist(
    playlist_id: str,
    request: PlaylistOrderRequest,
    service: Annotated[PlaylistService, Depends(get_playlist_service)],
) -> PlaylistResponse:
    try:
        await service.reorder_playlist(playlist_id, request.ordered_song_ids)
        playlist = await service.get_playlist(playlist_id)
        if playlist is None:
            raise _playlist_not_found(playlist_id)
        return _playlist_response(
            playlist,
            await service.list_song_ids(playlist_id),
        )
    except Exception as exc:
        _raise_playlist_http_error(exc)
        raise


@router.put("/api/favorites/{song_id}", response_model=CollectionResponse)
async def favorite_song(
    song_id: str,
    service: Annotated[PlaylistService, Depends(get_playlist_service)],
    collection_service: Annotated[
        CollectionService, Depends(resolve_collection_service)
    ],
) -> CollectionResponse:
    await service.set_favorite(song_id, True)
    return _collection_response(
        await collection_service.get_collection(source_type="FAVORITES")
    )


@router.delete("/api/favorites/{song_id}", status_code=204)
async def unfavorite_song(
    song_id: str,
    service: Annotated[PlaylistService, Depends(get_playlist_service)],
) -> None:
    await service.set_favorite(song_id, False)
