from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="MPD-Server")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"

if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
