from __future__ import annotations

import os

from fastapi import Request

from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.history_repository import HistoryRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.repositories.playback_state_repository import PlaybackStateRepository
from server.app.repositories.queue_repository import QueueRepository
from server.app.services.collection_service import CollectionService
from server.app.services.library_scanner import LibraryScanner
from server.app.services.autoplay import AutoPlay
from server.app.services.history_service import HistoryService
from server.app.services.library_service import LibraryService
from server.app.services.playback_service import PlaybackService
from server.app.services.playlist_service import PlaylistService
from server.app.player.mpd_adapter import MPDAdapter


def _database_path() -> str:
    return os.environ.get("DATABASE_PATH", "music-server.db")


async def resolve_library_service(request: Request) -> LibraryService:
    service = getattr(request.app.state, "library_service", None)
    if service is not None:
        return service

    path = _database_path()
    service = LibraryService(LibraryRepository(path))
    request.app.state.library_service = service
    return service


async def get_library_service(request: Request) -> LibraryService:
    return await resolve_library_service(request)


async def resolve_playlist_service(request: Request) -> PlaylistService:
    service = getattr(request.app.state, "playlist_service", None)
    if service is not None:
        return service

    path = _database_path()
    service = PlaylistService(PlaylistRepository(path))
    request.app.state.playlist_service = service
    return service


async def get_playlist_service(request: Request) -> PlaylistService:
    return await resolve_playlist_service(request)


async def resolve_collection_service(request: Request) -> CollectionService:
    service = getattr(request.app.state, "collection_service", None)
    if service is not None:
        return service

    library_service = await resolve_library_service(request)
    playlist_service = await resolve_playlist_service(request)
    service = CollectionService(library_service, playlist_service)
    request.app.state.collection_service = service
    return service


async def get_collection_service(request: Request) -> CollectionService:
    return await resolve_collection_service(request)


async def resolve_queue_manager(request: Request):
    manager = getattr(request.app.state, "queue_manager", None)
    if manager is not None:
        return manager

    path = _database_path()
    manager = QueueManager(
        QueueRepository(path),
        PlaybackStateRepository(path),
        PlaylistRepository(path),
    )
    request.app.state.queue_manager = manager
    return manager


async def get_queue_manager(request: Request):
    return await resolve_queue_manager(request)


async def resolve_playback_service(request: Request):
    service = getattr(request.app.state, "playback_service", None)
    if service is not None:
        return service

    path = _database_path()
    queue_manager = await resolve_queue_manager(request)
    history_service = HistoryService(
        QueueRepository(path),
        HistoryRepository(path),
    )
    autoplay = AutoPlay(
        QueueRepository(path),
        LibraryRepository(path),
        PlaybackStateRepository(path),
    )
    player = MPDAdapter(
        os.environ.get("MPD_HOST", "127.0.0.1"),
        port=int(os.environ.get("MPD_PORT", "6600")),
        password=os.environ.get("MPD_PASSWORD"),
    )
    service = PlaybackService(
        queue_manager=queue_manager,
        history_service=history_service,
        autoplay=autoplay,
        player=player,
        library_repository=LibraryRepository(path),
    )
    request.app.state.playback_service = service
    return service


async def get_playback_service(request: Request):
    return await resolve_playback_service(request)


async def resolve_library_scanner(request: Request) -> LibraryScanner:
    service = getattr(request.app.state, "library_scanner", None)
    if service is not None:
        return service

    path = _database_path()
    service = LibraryScanner(LibraryRepository(path))
    request.app.state.library_scanner = service
    return service


async def get_library_scanner(request: Request) -> LibraryScanner:
    return await resolve_library_scanner(request)
