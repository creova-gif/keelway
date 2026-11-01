"""
Keelway Core — FastAPI Application Entrypoint.
"""

from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.security.origin import extra_origins, origin_allowed
from core.api.routes import router
from core.api.studio import router as studio_router
from core.api.auth_routes import router as auth_router
from core.security.auth import launch_token
import os
from core.storage.database import init_db

# Configure logging
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("keelway.core")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler for startup and shutdown."""
    logger.info("Initializing Keelway Core...")
    logger.info("Auto-initializing local storage tables...")
    try:
        await init_db()
    except Exception:
        logger.exception("Database initialization failed (database_url=%s)", settings.database_url.split("@")[-1])
        raise

    if settings.auth_required and not settings.keelway_api_token and not os.environ.get("KEELWAY_DEV_CLI"):
        logger.info("API auth on. Launch token for this process (owner role): %s", launch_token())
        logger.info("Open the Studio at /?token=<launch token>, or set KEELWAY_API_TOKEN to pin it.")
    elif not settings.auth_required:
        logger.warning("AUTH_REQUIRED=false: every request is treated as the local owner.")

    yield

    logger.info("Shutting down Keelway Core...")


app = FastAPI(
    title="Keelway Core",
    version="0.1.0",
    description="Shared Intelligence Infrastructure & Multi-Provider Model Gateway.",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=extra_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def reject_foreign_origins(request: Request, call_next):
    # CORS only hides responses from foreign pages; this stops the request from executing at all.
    if not origin_allowed(request.headers.get("origin"), request.headers.get("host")):
        return JSONResponse(status_code=403, content={"detail": "Origin not allowed."})
    return await call_next(request)


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
app.include_router(studio_router)
app.include_router(auth_router)

# Mount Keelway Studio Web UI
studio_dir = Path(__file__).resolve().parent / "studio"
index_file = studio_dir / "index.html"
app.mount("/studio/assets", StaticFiles(directory=studio_dir / "assets"), name="studio-assets")

@app.get("/studio", response_class=HTMLResponse, tags=["Studio"])
@app.get("/", response_class=HTMLResponse, tags=["Studio"])
async def serve_studio():
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Keelway Core</h1><p>API is active. Studio assets loading...</p>")

