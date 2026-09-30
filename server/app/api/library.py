from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from server.app.models.library import ScanResult, Song
from server.app.repositories.playlist_repository import PlaylistNotFoundError
from server.app.services.library_scanner import LibraryScanError
from server.app.services.library_service import (
    ArtworkNotFoundError,
    ArtworkReadError,
    LibraryService,
    library_entity_id,
)

from .dependencies import (
    get_library_service,
    resolve_collection_service,
    resolve_library_scanner,
)
from .schemas import (
    AlbumListResponse,
    AlbumSummaryResponse,
    ArtistListResponse,
    ArtistSummaryResponse,
    CollectionRequest,
    CollectionResponse,
    GenreListResponse,
    GenreSummaryResponse,
    ScanRequest,
    ScanResultResponse,
    SongListResponse,
    SongResponse,
    TagListResponse,
    TagSummaryResponse,
    YearListResponse,
    YearSummaryResponse,
)

router = APIRouter(prefix="/api/library", tags=["library"])

_REQUIRED_SOURCE_ID = {"ALBUM", "ARTIST", "GENRE", "YEAR", "TAG", "PLAYLIST"}


def _song_response(song: Song) -> SongResponse:
    return SongResponse.model_validate(song)


def _collection_response(collection) -> CollectionResponse:
    return CollectionResponse.model_validate(collection.model_dump())


def _validation_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={"code": "VALIDATION_ERROR", "message": message, "details": None},
    )


async def _songs_from_collection(
    collection,
    library_service: LibraryService,
) -> SongListResponse:
    songs: list[SongResponse] = []
    for song_id in collection.song_ids:
        song = await library_service.get_song(song_id)
        if song is not None and song.availability_status == "AVAILABLE":
            songs.append(_song_response(song))
    return SongListResponse(items=songs, count=len(songs))


@router.get("/songs", response_model=SongListResponse)
async def list_songs(
    service: Annotated[LibraryService, Depends(get_library_service)],
) -> SongListResponse:
    items = [_song_response(song) for song in await service.list_songs()]
    return SongListResponse(items=items, count=len(items))


@router.get("/songs/{song_id}/artwork")
async def get_song_artwork(
    song_id: str,
    service: Annotated[LibraryService, Depends(get_library_service)],
):
    try:
        data, mime_type = await service.read_artwork(song_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SONG_NOT_FOUND",
                "message": f"song not found: {song_id}",
                "details": None,
            },
        ) from exc
    except ArtworkNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ARTWORK_NOT_FOUND",
                "message": f"artwork not found: {song_id}",
                "details": None,
            },
        ) from exc
    except (ArtworkReadError, RuntimeError) as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "ARTWORK_READ_ERROR",
                "message": str(exc),
                "details": None,
            },
        ) from exc

    return Response(content=data, media_type=mime_type)


@router.get("/songs/{song_id}", response_model=SongResponse)
async def get_song(
    song_id: str,
    service: Annotated[LibraryService, Depends(get_library_service)],
) -> SongResponse:
    song = await service.get_song(song_id)
    if song is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SONG_NOT_FOUND",
                "message": f"song not found: {song_id}",
            },
        )
    return _song_response(song)


@router.get("/albums", response_model=AlbumListResponse)
async def list_albums(
    service: Annotated[LibraryService, Depends(get_library_service)],
) -> AlbumListResponse:
    songs = await service.list_available_songs()
    groups: dict[str, list[Song]] = {}
    for song in songs:
        if song.album_id is not None and song.album is not None:
            groups.setdefault(song.album_id, []).append(song)

    items: list[AlbumSummaryResponse] = []
    for album_id, members in sorted(
        groups.items(),
        key=lambda item: (
            min(member.album.casefold() for member in item[1] if member.album),
            item[0],
        ),
    ):
        ordered = sorted(
            members,
            key=lambda song: (
                song.disc_number is None,
                song.disc_number if song.disc_number is not None else 0,
                song.track_number is None,
                song.track_number if song.track_number is not None else 0,
                song.file_uri,
                song.song_id or "",
            ),
        )
        representative = ordered[0]
        items.append(
            AlbumSummaryResponse(
                album_id=album_id,
                title=representative.album or "",
                album_artists=representative.album_artists,
                year=representative.year,
                date=representative.date,
                song_count=len({song.song_id for song in members if song.song_id}),
                artwork=representative.artwork,
            )
        )
    return AlbumListResponse(items=items, count=len(items))


@router.get("/albums/{album_id}/songs", response_model=SongListResponse)
async def list_album_songs(
    album_id: str,
    request: Request,
    library_service: Annotated[LibraryService, Depends(get_library_service)],
) -> SongListResponse:
    collection_service = await resolve_collection_service(request)
    collection = await collection_service.get_collection(
        source_type="ALBUM",
        source_id=album_id,
    )
    return await _songs_from_collection(collection, library_service)


@router.get("/artists", response_model=ArtistListResponse)
async def list_artists(
    service: Annotated[LibraryService, Depends(get_library_service)],
) -> ArtistListResponse:
    songs = sorted(
        await service.list_available_songs(),
        key=lambda song: (song.file_uri, song.song_id or ""),
    )
    groups: dict[str, tuple[str, set[str]]] = {}
    for song in songs:
        if song.song_id is None:
            continue
        for name in (*song.artists, *song.album_artists):
            normalized = name.casefold()
            current = groups.get(normalized)
            if current is None:
                groups[normalized] = (name, {song.song_id})
            else:
                current[1].add(song.song_id)
    items = [
        ArtistSummaryResponse(
            artist_id=library_entity_id("artists", name),
            name=name,
            song_count=len(song_ids),
        )
        for name, song_ids in sorted(
            groups.values(), key=lambda value: value[0].casefold()
        )
    ]
    return ArtistListResponse(items=items, count=len(items))


@router.get("/artists/{artist_id}/songs", response_model=SongListResponse)
async def list_artist_songs(
    artist_id: str,
    request: Request,
    library_service: Annotated[LibraryService, Depends(get_library_service)],
) -> SongListResponse:
    collection_service = await resolve_collection_service(request)
    collection = await collection_service.get_collection(
        source_type="ARTIST",
        source_id=artist_id,
    )
    return await _songs_from_collection(collection, library_service)


@router.get("/genres", response_model=GenreListResponse)
async def list_genres(
    service: Annotated[LibraryService, Depends(get_library_service)],
) -> GenreListResponse:
    items = _name_summary(
        await service.list_available_songs(),
        lambda song: song.genres,
        GenreSummaryResponse,
        "genres",
    )
    return GenreListResponse(items=items, count=len(items))


@router.get("/genres/{genre_id}/songs", response_model=SongListResponse)
async def list_genre_songs(
    genre_id: str,
    request: Request,
    library_service: Annotated[LibraryService, Depends(get_library_service)],
) -> SongListResponse:
    collection_service = await resolve_collection_service(request)
    collection = await collection_service.get_collection(
        source_type="GENRE",
        source_id=genre_id,
    )
    return await _songs_from_collection(collection, library_service)


@router.get("/years", response_model=YearListResponse)
async def list_years(
    service: Annotated[LibraryService, Depends(get_library_service)],
) -> YearListResponse:
    songs = await service.list_available_songs()
    counts: dict[int, set[str]] = {}
    for song in songs:
        if song.year is None or song.song_id is None:
            continue
        counts.setdefault(song.year, set()).add(song.song_id)
    items = [
        YearSummaryResponse(value=year, song_count=len(song_ids))
        for year, song_ids in sorted(counts.items())
    ]
    return YearListResponse(items=items, count=len(items))


@router.get("/years/{year}/songs", response_model=SongListResponse)
async def list_year_songs(
    year: str,
    request: Request,
    library_service: Annotated[LibraryService, Depends(get_library_service)],
) -> SongListResponse:
    collection_service = await resolve_collection_service(request)
    collection = await collection_service.get_collection(
        source_type="YEAR",
        source_id=year,
    )
    return await _songs_from_collection(collection, library_service)


@router.get("/tags", response_model=TagListResponse)
async def list_tags(
    service: Annotated[LibraryService, Depends(get_library_service)],
) -> TagListResponse:
    items = _name_summary(
        await service.list_available_songs(),
        lambda song: song.tag_names,
        TagSummaryResponse,
        "tags",
    )
    return TagListResponse(items=items, count=len(items))


@router.get("/tags/{tag_id}/songs", response_model=SongListResponse)
async def list_tag_songs(
    tag_id: str,
    request: Request,
    library_service: Annotated[LibraryService, Depends(get_library_service)],
) -> SongListResponse:
    collection_service = await resolve_collection_service(request)
    collection = await collection_service.get_collection(
        source_type="TAG",
        source_id=tag_id,
    )
    return await _songs_from_collection(collection, library_service)


@router.get("/search", response_model=CollectionResponse)
async def search(
    request: Request,
    q: str | None = Query(default=None),
) -> CollectionResponse:
    if q is None:
        raise _validation_error("query.q: Field required")
    collection_service = await resolve_collection_service(request)
    return _collection_response(
        await collection_service.get_collection(
            source_type="SEARCH",
            query=q,
        )
    )


@router.post("/collections", response_model=CollectionResponse)
async def create_collection(
    body: CollectionRequest,
    request: Request,
) -> CollectionResponse:
    collection_service = await resolve_collection_service(request)
    try:
        collection = await collection_service.get_collection(
            source_type=body.source_type,
            source_id=body.source_id,
            query=body.query,
            song_ids=body.song_ids,
            randomize=body.randomize,
            random_seed=body.random_seed,
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
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_COLLECTION",
                "message": str(exc),
                "details": None,
            },
        ) from exc
    return _collection_response(collection)


@router.post("/scan", response_model=ScanResultResponse)
async def scan_library(
    body: ScanRequest,
    request: Request,
) -> ScanResultResponse:
    scanner = await resolve_library_scanner(request)
    try:
        result: ScanResult = await scanner.scan_full(Path(body.root))
    except LibraryScanError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "LIBRARY_SCAN_ERROR",
                "message": str(exc),
                "details": None,
            },
        ) from exc
    return ScanResultResponse.model_validate(result.model_dump())


def _name_summary(songs, getter, model, entity_kind):
    groups: dict[str, tuple[str, set[str]]] = {}
    for song in songs:
        if song.song_id is None:
            continue
        for name in getter(song):
            normalized = name.casefold()
            current = groups.get(normalized)
            if current is None:
                groups[normalized] = (name, {song.song_id})
            else:
                current[1].add(song.song_id)
    return [
        model(
            **(
                {"name": name}
                if entity_kind is None
                else {f"{entity_kind[:-1]}_id": library_entity_id(entity_kind, name), "name": name}
            ),
            song_count=len(song_ids),
        )
        for name, song_ids in sorted(
            groups.values(), key=lambda value: value[0].casefold()
        )
    ]
