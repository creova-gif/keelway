"""Zero-dependency static fallback server for `keelway dev`.

Engages only when the ASGI stack (uvicorn/FastAPI) is unavailable and
``AUTH_REQUIRED=false``. Per ADR-0045 this server owns no ``/v1/*`` paths: the
authoritative API is ``core.main:app``. It serves the Studio shell and
``/health`` (reporting degraded) and answers every ``/v1`` request with
``503 api_available: false`` — never stub resource data, never direct
service-layer calls.
"""

from __future__ import annotations

import http.server
import json
import socketserver
from pathlib import Path

_FALLBACK_CSP = (
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

_DEFAULT_STUDIO_HTML = Path(__file__).resolve().parent.parent / "studio" / "index.html"


class StaticFallbackHandler(http.server.SimpleHTTPRequestHandler):
    """Static-only Studio server; /v1 paths degrade honestly (ADR-0045)."""

    studio_html_path: Path = _DEFAULT_STUDIO_HTML

    def _send_json(self, status: int, payload: dict) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def _send_api_unavailable(self) -> None:
        self._send_json(503, {
            "error": "Keelway API unavailable — the ASGI server is required for /v1 routes.",
            "api_available": False,
        })

    def do_GET(self) -> None:  # noqa: N802 - stdlib signature
        path = self.path.split("?", 1)[0]
        if path in ("/", "/studio", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy", _FALLBACK_CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(self.studio_html_path.read_bytes())
        elif path == "/health":
            self._send_json(200, {"status": "degraded", "mode": "static_fallback", "api_available": False})
        elif path.startswith("/v1/"):
            self._send_api_unavailable()
        else:
            super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - stdlib signature
        if self.path.split("?", 1)[0].startswith("/v1/"):
            self._send_api_unavailable()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
        pass


class _ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def serve_static_fallback(host: str, port: int) -> None:
    """Serve the static Studio shell until interrupted. No /v1 API surface."""
    print(f"[✓] Sovereign Dev Studio live at http://{host}:{port}")
    print("    Static fallback mode — /v1 API routes return 503 unavailable.")
    print("    Press Ctrl+C to stop.\n")
    with _ReusableTCPServer((host, port), StaticFallbackHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[+] Studio stopped cleanly.")
