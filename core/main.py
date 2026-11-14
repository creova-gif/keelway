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
from core.api.messaging_routes import relay, router as messaging_router
from core.api.sync_routes import router as sync_router
from core.api.opencore_routes import router as opencore_router
from core.api.responses_routes import router as responses_router
from core.api.governance_routes import router as governance_router
import asyncio
from core.security.auth import launch_token
import os
from core.storage.database import init_db

# Configure logging
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
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

    poller = asyncio.create_task(relay.run_telegram_poller()) if relay.config.telegram else None
    if relay.channels():
        logger.info("Approval messaging on: %s (blocked while air-gapped).", ", ".join(relay.channels()))

    yield

    if poller:
        poller.cancel()
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
app.include_router(messaging_router)
app.include_router(sync_router)
app.include_router(opencore_router)
app.include_router(responses_router)
app.include_router(governance_router)

# Mount Keelway Studio Web UI & Unified Sovereign Dev App
studio_dir = Path(__file__).resolve().parent / "studio"
index_file = studio_dir / "index.html"
web_console_file = Path(__file__).resolve().parent.parent / "web-console" / "index.html"
dev_app_dir = Path(__file__).resolve().parent / "dev_app_dist"
dev_app_index = dev_app_dir / "index.html"
app.mount("/studio/assets", StaticFiles(directory=studio_dir / "assets"), name="studio-assets")
if (dev_app_dir / "assets").exists():
    app.mount("/app/assets", StaticFiles(directory=dev_app_dir / "assets"), name="dev-app-assets")

# Studio is local-first: allow self only (scripts/styles/fonts/workers/connect).
_STUDIO_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self' ws: wss:; "
    "worker-src 'self' blob:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)


@app.get("/app", response_class=HTMLResponse, tags=["Studio"], include_in_schema=False)
@app.get("/app/{subpath:path}", response_class=HTMLResponse, tags=["Studio"], include_in_schema=False)
async def serve_unified_dev_app(subpath: str = ""):
    headers = {
        "Content-Security-Policy": _STUDIO_CSP,
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-cache",
    }
    norm = subpath.lstrip("/")
    if norm and (norm == "assets" or norm.startswith("assets/")):
        return HTMLResponse(content="Not Found", status_code=404, headers=headers)
    if dev_app_index.exists():
        return HTMLResponse(content=dev_app_index.read_text(encoding="utf-8"), headers=headers)
    return HTMLResponse(
        content="<h1>Keelway Unified Dev App</h1><p>Compiled dev-app bundle not found.</p>",
        status_code=404,
        headers=headers,
    )


@app.get("/studio", response_class=HTMLResponse, tags=["Studio"])
@app.get("/", response_class=HTMLResponse, tags=["Studio"])
async def serve_studio():
    headers = {
        "Content-Security-Policy": _STUDIO_CSP,
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    }
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"), headers=headers)
    return HTMLResponse(
        content="<h1>Keelway Core</h1><p>API is active. Studio assets loading...</p>",
        headers=headers,
    )

@app.get("/console", response_class=HTMLResponse, tags=["Web Console"])
@app.get("/web-console", response_class=HTMLResponse, tags=["Web Console"])
async def serve_web_console():
    if web_console_file.exists():
        return HTMLResponse(content=web_console_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Keelway Web Console</h1><p>Web Console loading...</p>")

