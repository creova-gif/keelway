"""
Kora AI Core — FastAPI Application Entrypoint.
"""

from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from fastapi.responses import JSONResponse, HTMLResponse

from core.config import settings
from core.api.routes import router
from core.storage.database import init_db

# Configure logging
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kora.core")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler for startup and shutdown."""
    logger.info("Initializing Kora AI Core...")
    logger.info("Auto-initializing local storage tables...")
    try:
        await init_db()
    except Exception:
        logger.exception("Database initialization failed (database_url=%s)", settings.database_url.split("@")[-1])
        raise

    yield

    logger.info("Shutting down Kora AI Core...")


app = FastAPI(
    title="Kora AI Core",
    version="0.1.0",
    description="Shared Intelligence Infrastructure & Multi-Provider Model Gateway.",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global zero-silent-failure exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": str(exc) if settings.env == "development" else "An unexpected internal error occurred.",
            "path": request.url.path,
        },
    )


# Mount routes
app.include_router(router)

# Mount Kora Dev Studio Web UI
studio_dir = Path(__file__).resolve().parent / "studio"
index_file = studio_dir / "index.html"

@app.get("/studio", response_class=HTMLResponse, tags=["Studio"])
@app.get("/", response_class=HTMLResponse, tags=["Studio"])
async def serve_studio():
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Kora AI Core</h1><p>API is active. Studio assets loading...</p>")

