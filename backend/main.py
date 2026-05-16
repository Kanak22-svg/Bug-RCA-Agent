"""FastAPI entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.investigations import router as investigations_router
from .config import get_settings
from .db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Bug Investigation Copilot", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(investigations_router)


@app.get("/health")
async def health() -> dict[str, str]:
    s = get_settings()
    return {
        "status": "ok",
        "issue_provider": s.issue_provider,
        "docs_provider": s.docs_provider,
        "code_provider": s.code_provider,
    }


# --- Frontend (static) ---
_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_frontend_dir)), name="static")

    @app.get("/")
    async def root() -> FileResponse:
        return FileResponse(_frontend_dir / "index.html")


def main() -> None:
    import uvicorn

    s = get_settings()
    uvicorn.run("backend.main:app", host=s.app_host, port=s.app_port, reload=False)


if __name__ == "__main__":
    main()
