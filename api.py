"""FastAPI entrypoint for the Nabt Jordan educational website."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="نَبْت الأردن", description="دليل النباتات البرية في الأردن")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    """Serve the Arabic single-page experience."""
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "nabt-jordan"}
