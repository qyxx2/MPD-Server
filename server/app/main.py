import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server.app.api.library import router as library_router
from server.app.api.playlists import router as playlists_router
from server.app.repositories.database import initialize_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_path = os.environ.get("DATABASE_PATH", "music-server.db")
    await initialize_database(database_path)
    yield


app = FastAPI(title="MPD-Server", lifespan=lifespan)


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


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(library_router)
app.include_router(playlists_router)


WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"

if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
