from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from server.app.models.library import ScanResult, Song
from server.app.services.collection_service import CollectionService
from server.app.services.library_scanner import LibraryScanError, LibraryScanner
from server.app.services.library_service import (
    ArtworkNotFoundError,
    ArtworkReadError,
    LibraryService,
)
from server.app.repositories.playlist_repository import PlaylistNotFoundError

from .dependencies import (
    get_collection_service,
    get_library_scanner,
    get_library_service,
    resolve_collection_service,
)
from .schemas import (
    AlbumListResponse,
    AlbumSummaryResponse,
    ArtistListResponse,
    ArtistSummaryResponse,
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
        detail={"code": "VALIDATION_ERROR", "message": message},
    )


@router.get("", response_model=CollectionResponse)
async def library_collection(
    collection_service: CollectionService = Depends(get_collection_service),
) -> CollectionResponse:
    return _collection_response(
        await collection_service.get_collection(source_type="LIBRARY")
    )


@router.get("/songs", response_model=SongListResponse)
async def list_songs(
    service: LibraryService = Depends(get_library_service),
) -> SongListResponse:
    return SongListResponse(
        items=[_song_response(song) for song in await service.list_songs()]
    )


@router.get("/songs/{song_id}/artwork")
async def get_song_artwork(
    song_id: str,
    service: LibraryService = Depends(get_library_service),
):
    try:
        data, mime_type = await service.read_artwork(song_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "SONG_NOT_FOUND", "message": f"song not found: {song_id}"},
        ) from exc
    except ArtworkNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ARTWORK_NOT_FOUND",
                "message": f"artwork not found: {song_id}",
            },
        ) from exc
    except (ArtworkReadError, RuntimeError) as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "ARTWORK_READ_ERROR", "message": str(exc)},
        ) from exc

    from fastapi.responses import Response

    return Response(content=data, media_type=mime_type)


@router.get("/songs/{song_id}", response_model=SongResponse)
async def get_song(
    song_id: str,
    service: LibraryService = Depends(get_library_service),
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
    service: LibraryService = Depends(get_library_service),
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
                artwork=(
                    representative.artwork.model_dump(mode="json")
                    if representative.artwork
                    else None
                ),
            )
        )
    return AlbumListResponse(items=items)


@router.get("/artists", response_model=ArtistListResponse)
async def list_artists(
    service: LibraryService = Depends(get_library_service),
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
        ArtistSummaryResponse(name=name, song_count=len(song_ids))
        for name, song_ids in sorted(
            groups.values(), key=lambda value: value[0].casefold()
        )
    ]
    return ArtistListResponse(items=items)


@router.get("/genres", response_model=GenreListResponse)
async def list_genres(
    service: LibraryService = Depends(get_library_service),
) -> GenreListResponse:
    return GenreListResponse(
        items=_name_summary(
            await service.list_available_songs(),
            lambda song: song.genres,
            GenreSummaryResponse,
        )
    )


@router.get("/years", response_model=YearListResponse)
async def list_years(
    service: LibraryService = Depends(get_library_service),
) -> YearListResponse:
    songs = await service.list_available_songs()
    counts: dict[int, set[str]] = {}
    for song in songs:
        if song.year is None or song.song_id is None:
            continue
        counts.setdefault(song.year, set()).add(song.song_id)
    return YearListResponse(
        items=[
            YearSummaryResponse(value=year, song_count=len(song_ids))
            for year, song_ids in sorted(counts.items())
        ]
    )


@router.get("/tags", response_model=TagListResponse)
async def list_tags(
    service: LibraryService = Depends(get_library_service),
) -> TagListResponse:
    return TagListResponse(
        items=_name_summary(
            await service.list_available_songs(),
            lambda song: song.tag_names,
            TagSummaryResponse,
        )
    )


@router.get("/search", response_model=CollectionResponse)
async def search(
    request,
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


@router.get("/collections/{source_type}", response_model=CollectionResponse)
async def get_collection(
    request,
    source_type: str,
    source_id: str | None = Query(default=None),
    song_id: list[str] | None = Query(default=None),
    randomize: bool = Query(default=False),
    random_seed: int | None = Query(default=None, ge=0),
    query: str | None = Query(default=None),
) -> CollectionResponse:
    source_type = source_type.upper()
    if source_type not in {
        "ALBUM",
        "ARTIST",
        "GENRE",
        "YEAR",
        "TAG",
        "SEARCH",
        "PLAYLIST",
        "FAVORITES",
        "LIBRARY",
        "SONGS",
    }:
        raise _validation_error(f"unsupported collection source_type: {source_type}")
    if source_type in _REQUIRED_SOURCE_ID and not source_id:
        raise _validation_error(
            f"source_id is required for {source_type}"
        )
    if source_type == "SEARCH" and query is None and not source_id:
        raise _validation_error("query is required for SEARCH")
    if source_type == "SONGS":
        song_id = song_id or []

    collection_service = await resolve_collection_service(request)
    try:
        collection = await collection_service.get_collection(
            source_type=source_type,
            source_id=source_id,
            query=query,
            song_ids=song_id,
            randomize=randomize,
            random_seed=random_seed,
        )
    except PlaylistNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PLAYLIST_NOT_FOUND",
                "message": f"playlist not found: {exc.args[0]}",
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": str(exc)},
        ) from exc
    return _collection_response(collection)


@router.post("/scan", response_model=ScanResultResponse)
async def scan_library(
    request: ScanRequest,
    scanner: LibraryScanner = Depends(get_library_scanner),
) -> ScanResultResponse:
    try:
        result: ScanResult = await scanner.scan_full(Path(request.root))
    except LibraryScanError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "LIBRARY_SCAN_ERROR", "message": str(exc)},
        ) from exc
    return ScanResultResponse.model_validate(result)


def _name_summary(songs, getter, model):
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
        model(name=name, song_count=len(song_ids))
        for name, song_ids in sorted(
            groups.values(), key=lambda value: value[0].casefold()
        )
    ]
