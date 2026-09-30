from __future__ import annotations

import os

from fastapi import Request

from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.services.collection_service import CollectionService
from server.app.services.library_scanner import LibraryScanner
from server.app.services.library_service import LibraryService
from server.app.services.playback_service import PlaybackService
from server.app.services.playlist_service import PlaylistService
from server.app.services.playback_service import PlaybackService
from server.app.services.queue_manager import QueueManager


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


async def resolve_queue_manager(request: Request) -> QueueManager:
    manager = getattr(request.app.state, "queue_manager", None)
    if manager is None:
        raise RuntimeError("queue manager is not configured")
    return manager


async def get_queue_manager(request: Request) -> QueueManager:
    return await resolve_queue_manager(request)


async def resolve_playback_service(request: Request) -> PlaybackService:
    service = getattr(request.app.state, "playback_service", None)
    if service is None:
        raise RuntimeError("playback service is not configured")
    return service


async def get_playback_service(request: Request) -> PlaybackService:
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
