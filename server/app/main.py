import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server.app.api.history import router as history_router
from server.app.api.library import router as library_router
from server.app.api.playback import router as playback_router
from server.app.api.playlists import router as playlists_router
from server.app.api.realtime import router as realtime_router
from server.app.api.system import router as system_router
from server.app.player.capabilities import MPDCapabilities
from server.app.player.mpd_adapter import MPDAdapter
from server.app.repositories.database import initialize_database
from server.app.repositories.history_repository import HistoryRepository
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playback_state_repository import PlaybackStateRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.repositories.queue_repository import QueueRepository
from server.app.services.autoplay import AutoPlay
from server.app.services.collection_service import CollectionService
from server.app.services.history_service import HistoryService
from server.app.services.idempotency_service import IdempotencyService
from server.app.services.library_scanner import LibraryScanner
from server.app.services.library_service import (
    CollectionSourceNotFoundError,
    LibraryService,
)
from server.app.services.mpd_info_service import MPDInfoService
from server.app.services.output_manager import OutputManager
from server.app.services.playback_service import PlaybackService
from server.app.services.playlist_service import PlaylistService
from server.app.services.queue_manager import QueueManager
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.app.services.state_observer import StateObserver
from server.app.services.state_service import StateService


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_path = os.environ.get("DATABASE_PATH", "music-server.db")
    await initialize_database(database_path)

    library_repository = LibraryRepository(database_path)
    playlist_repository = PlaylistRepository(database_path)
    queue_repository = QueueRepository(database_path)
    playback_state_repository = PlaybackStateRepository(database_path)
    history_repository = HistoryRepository(database_path)
    idempotency_repository = IdempotencyRepository(database_path)

    coordinator = RealtimeCoordinator(database_path, getattr(app.state, 'event_publisher', None))
    library_service = LibraryService(library_repository)
    library_scanner = LibraryScanner(
        library_repository, coordinator=coordinator, event_publisher=coordinator,
    )
    playlist_service = PlaylistService(
        playlist_repository, coordinator=coordinator, event_publisher=coordinator,
    )
    collection_service = CollectionService(library_service, playlist_service)
    queue_manager = QueueManager(
        queue_repository,
        playback_state_repository,
        playlist_repository,
    )
    history_service = HistoryService(queue_repository, history_repository)
    autoplay = AutoPlay(
        queue_repository,
        library_repository,
        playback_state_repository,
    )
    player = MPDAdapter(
        os.environ.get("MPD_HOST", "127.0.0.1"),
        port=int(os.environ.get("MPD_PORT", "6600")),
        password=os.environ.get("MPD_PASSWORD"),
    )
    playback_service = PlaybackService(
        queue_manager=queue_manager,
        history_service=history_service,
        autoplay=autoplay,
        player=player,
        library_repository=library_repository,
        coordinator=coordinator, event_publisher=coordinator,
    )

    # Capability loading belongs to Task 10. Until verification is explicitly
    # injected, system reads report unavailable facts without running a probe.
    capabilities = getattr(app.state, "mpd_capabilities", None)
    if capabilities is None:
        capabilities = MPDCapabilities.from_commands(set())
    app.state.output_manager = OutputManager(
        player=player,
        capabilities=capabilities,
        operation_runner=playback_service.run_output_operation,
        selector=getattr(app.state, "output_selector", None),
        event_publisher=getattr(app.state, 'event_publisher', None) or coordinator,
        coordinator=coordinator,
    )
    app.state.mpd_info_service = MPDInfoService(player=player, capabilities=capabilities)

    app.state.library_service = library_service
    app.state.library_scanner = library_scanner
    app.state.playlist_service = playlist_service
    app.state.collection_service = collection_service
    app.state.queue_manager = queue_manager
    app.state.playback_service = playback_service
    app.state.history_service = history_service
    app.state.idempotency_service = IdempotencyService(idempotency_repository)

    app.state.realtime_coordinator = coordinator
    app.state.state_service = StateService(
        coordinator=coordinator, queue_manager=queue_manager, history_service=history_service,
        library_service=library_service, playback_service=playback_service,
        output_snapshot=app.state.output_manager.get_cached_state,
        output_observation=app.state.output_manager.get_observation,
    )
    observer = StateObserver(playback=playback_service, output=app.state.output_manager)
    app.state.state_observer = observer
    task = asyncio.create_task(observer.run(), name='state-observer')
    app.state.state_observer_task = task
    try:
        yield
    finally:
        await observer.close()
        await asyncio.gather(task, return_exceptions=True)
        coordinator.close()


app = FastAPI(title="MPD-Server", lifespan=lifespan)


_IDEMPOTENCY_EXEMPT_PATHS = {"/api/library/collections"}


@app.middleware("http")
async def handle_idempotent_mutation(request: Request, call_next):
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and request.url.path.startswith("/api/")
        and request.url.path not in _IDEMPOTENCY_EXEMPT_PATHS
        and not request.headers.get("Idempotency-Key")
    ):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "IDEMPOTENCY_KEY_REQUIRED",
                    "message": "Idempotency-Key header is required for mutations",
                    "details": None,
                }
            },
        )
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and request.url.path.startswith("/api/")
        and request.url.path not in _IDEMPOTENCY_EXEMPT_PATHS
    ):
        service: IdempotencyService = request.app.state.idempotency_service
        return await service.execute(request, call_next)
    return await call_next(request)


@app.exception_handler(CollectionSourceNotFoundError)
async def collection_source_exception_handler(
    request: Request,
    exc: CollectionSourceNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "COLLECTION_SOURCE_NOT_FOUND",
                "message": str(exc),
                "details": {
                    "source_type": exc.source_type,
                    "source_id": exc.source_id,
                },
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    messages = [
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "; ".join(messages) or "request validation failed",
                "details": None,
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    if isinstance(exc.detail, dict):
        error = {
            "code": exc.detail.get("code", f"HTTP_{exc.status_code}"),
            "message": exc.detail.get("message", str(exc.detail)),
            "details": exc.detail.get("details"),
        }
    else:
        error = {
            "code": f"HTTP_{exc.status_code}",
            "message": str(exc.detail),
            "details": None,
        }
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error},
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "internal server error",
                "details": None,
            }
        },
    )


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(history_router)
app.include_router(library_router)
app.include_router(playlists_router)
app.include_router(playback_router)
app.include_router(system_router)
app.include_router(realtime_router)


WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"

if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
