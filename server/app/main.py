import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from server.app.api.history import router as history_router
from server.app.api.library import router as library_router
from server.app.api.playback import router as playback_router
from server.app.api.playlists import router as playlists_router
from server.app.api.realtime import router as realtime_router
from server.app.api.system import health_router
from server.app.api.system import router as system_router
from server.app.config import load_config
from server.app.logging_config import (
    configure_logging,
    log_context,
    log_event,
    request_operation_id,
)
from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.capability_loader import load_capabilities
from server.app.player.mock_mpd import MockMPD
from server.app.player.mpd_adapter import MPDAdapter
from server.app.player.music_uri import MusicUriMapper
from server.app.repositories.database import initialize_database
from server.app.repositories.history_repository import HistoryRepository
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playback_state_repository import PlaybackStateRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.repositories.queue_repository import QueueRepository
from server.app.services.autoplay import AutoPlay
from server.app.services.collection_service import CollectionService
from server.app.services.health_service import HealthService
from server.app.services.history_service import HistoryService
from server.app.services.idempotency_service import IdempotencyService
from server.app.services.library_runtime import LibraryRuntime
from server.app.services.library_scanner import LibraryScanner
from server.app.services.library_service import (
    CollectionSourceNotFoundError,
    LibraryService,
)
from server.app.services.library_sync_service import LibrarySyncService
from server.app.services.mpd_connection_service import (
    MPDConnectionAddress,
    MPDConnectionService,
)
from server.app.services.mpd_info_service import MPDInfoService
from server.app.services.output_manager import OutputManager
from server.app.services.playback_recovery_runner import PlaybackRecoveryRunner
from server.app.services.playback_service import PlaybackService
from server.app.services.playlist_service import PlaylistService
from server.app.services.queue_manager import QueueManager
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.app.services.state_observer import StateObserver
from server.app.services.state_service import StateService

_recovery_owner_lock = Lock()
_recovery_owner: object | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _recovery_owner
    configure_logging()
    config = load_config(os.environ)
    app.state.config = config
    connection = MPDConnectionService(
        config.mpd_connection_path,
        lambda: MPDConnectionAddress(host=config.mpd_host, port=config.mpd_port),
    )
    app.state.mpd_connection_service = connection
    injected_capabilities = getattr(app.state, "mpd_capabilities", None)
    capabilities = injected_capabilities
    if capabilities is None:
        capabilities = (await load_capabilities(
            config.mpd_capabilities_path, host=connection.active.host, port=connection.active.port,
        ) if config.mpd_mode == 'real' else MPDCapabilities.from_commands(set()))
    required = ("read_execution_sample", "queue_entries", "queue_add", "queue_delete", "queue_move")
    default_recovery = (config.mpd_mode == 'real' and config.mpd_capabilities_path is not None
                        and all(capabilities.supports_operation(op) for op in required))
    recovery_enabled = bool(getattr(app.state, "recovery_enabled", default_recovery)
                            and (injected_capabilities is not None or default_recovery))
    owner = object()
    if recovery_enabled:
        required = ("read_execution_sample", "queue_entries", "queue_add", "queue_delete", "queue_move")
        if not all(capabilities.supports_operation(operation) for operation in required):
            raise RuntimeError("Playback recovery capabilities are not verified")
        # Process-local exclusion only; deployment must use one control process.
        with _recovery_owner_lock:
            if _recovery_owner is not None:
                raise RuntimeError("Playback recovery control owner already exists")
            _recovery_owner = owner
    owned_player = None
    try:
        database_path = str(config.database_path)
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
        player = getattr(app.state, "player", None)
        if player is None:
            player = (MockMPD() if config.mpd_mode == 'mock' else MPDAdapter(
                connection.active.host, port=connection.active.port, password=config.mpd_password,
                uri_mapper=MusicUriMapper(config.music_root, config.mpd_uri_prefix),
            ))
            owned_player = player
            if config.mpd_mode == 'real':
                player = VerifiedPlayerPort(player, capabilities)
        if recovery_enabled and not isinstance(player, VerifiedPlayerPort):
            player = VerifiedPlayerPort(player, capabilities)
        library_sync = LibrarySyncService(
            library_scanner, player, config.music_root, event_publisher=coordinator,
        )
        library_runtime = LibraryRuntime(
            library_sync, config.music_root,
            scan_interval_seconds=config.scan_interval_seconds,
            debounce_seconds=config.debounce_seconds,
        )
        app.state.library_sync_service = library_sync
        app.state.library_runtime = library_runtime
        playback_service = PlaybackService(
            queue_manager=queue_manager,
            history_service=history_service,
            autoplay=autoplay,
            player=player,
            library_repository=library_repository,
            coordinator=coordinator, event_publisher=coordinator,
        )

        selector = getattr(app.state, "output_selector", None)
        if selector is None and config.output_name is not None:
            def selector(outputs):
                matches = [output for output in outputs
                           if output.name == config.output_name and output.plugin == config.output_plugin]
                return matches[0] if len(matches) == 1 else None
        app.state.output_manager = OutputManager(
            player=player,
            capabilities=capabilities,
            operation_runner=playback_service.run_output_operation,
            selector=selector,
            event_publisher=getattr(app.state, 'event_publisher', None) or coordinator,
            coordinator=coordinator,
        )
        app.state.mpd_info_service = MPDInfoService(player=player, capabilities=capabilities)
        app.state.health_service = HealthService(database_path, player, coordinator.get_library_sync)

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
        # Complete existing local Queue initialization before read-only tasks run.
        await queue_repository.get_snapshot()
        observer = StateObserver(playback=playback_service, output=app.state.output_manager)
        playback_service.set_observation_request(observer.request_observation)
        app.state.state_observer = observer
        task = asyncio.create_task(observer.run(), name='state-observer')
        app.state.state_observer_task = task
        runner = PlaybackRecoveryRunner(playback_service) if recovery_enabled else None
        recovery_task = (asyncio.create_task(runner.run(), name='playback-recovery')
                         if runner is not None else None)
        app.state.playback_recovery_runner = runner
        app.state.playback_recovery_task = recovery_task
        library_task = asyncio.create_task(library_runtime.run(), name="library-runtime")
        app.state.library_runtime_task = library_task
        log_event('application_started')
        try:
            yield
        finally:
            log_event('application_stopping')
            await library_runtime.close()
            await asyncio.gather(library_task, return_exceptions=True)
            if runner is not None:
                await runner.close()
                await asyncio.gather(recovery_task, return_exceptions=True)
            playback_service.set_observation_request(None)
            await observer.close()
            await asyncio.gather(task, return_exceptions=True)
            coordinator.close()
    finally:
        if owned_player is not None and hasattr(owned_player, 'close'):
            await owned_player.close()
        if recovery_enabled:
            with _recovery_owner_lock:
                if _recovery_owner is owner:
                    _recovery_owner = None


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


class RequestDiagnosticsMiddleware:
    """Keep diagnostics in the caller task so cancellation remains observable."""

    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.application(scope, receive, send)
            return
        key = Request(scope).headers.get('Idempotency-Key')
        operation_id = request_operation_id(key) if key else uuid4().hex[:16]

        async def observed_send(message):
            if message['type'] == 'http.response.start' and message['status'] >= 400:
                log_event('api_failed', level=30, status_code=message['status'])
            await send(message)

        with log_context(operation_id=operation_id):
            try:
                await self.application(scope, receive, observed_send)
            except Exception:
                log_event('api_failed', level=40, status_code=500)
                raise


app.add_middleware(RequestDiagnosticsMiddleware)


app.include_router(history_router)
app.include_router(library_router)
app.include_router(playlists_router)
app.include_router(playback_router)
app.include_router(health_router)
app.include_router(system_router)
app.include_router(realtime_router)


WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


class SPAStaticFiles(StaticFiles):
    """Serve client routes while preserving API and missing-asset errors."""

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            await send({'type': 'websocket.close', 'code': 1000})
            return
        await super().__call__(scope, receive, send)

    async def get_response(self, path, scope):
        if path == 'api' or path.startswith('api/'):
            raise HTTPException(status_code=404, detail='Not Found')
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if (exc.status_code != 404
                    or scope['method'] not in {'GET', 'HEAD'}
                    or path.startswith('assets/') or Path(path).suffix):
                raise
            return await super().get_response('index.html', scope)


def mount_web(application: FastAPI, directory: Path) -> None:
    application.mount('/', SPAStaticFiles(directory=directory, html=True), name='web')


if WEB_DIST.is_dir():
    mount_web(app, WEB_DIST)


def run_server() -> None:
    import uvicorn

    config = load_config(os.environ)
    uvicorn.run('server.app.main:app', host=config.http_host, port=config.http_port,
                workers=config.workers)


if __name__ == '__main__':
    run_server()
