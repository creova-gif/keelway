"""
FastAPI ASGI & CLI integration tests for the Unified Sovereign Dev App (/app).

Verifies:
1. /app serves compiled static assets under strict _STUDIO_CSP (default-src 'self'),
   X-Content-Type-Options: nosniff, Referrer-Policy: no-referrer, and zero third-party CDNs.
2. Compiled JS & CSS bundles expose epistemic honesty & safety invariants
   ("sent: unmeasured", "Approvals are never run from here", "Only you can approve",
   --attn-ochre, [data-reduce-motion=true]).
3. SPA client subpaths (/app/settings) resolve index.html while missing /app/assets/*
   files strictly return 404 (never 200 HTML), and legacy /studio remains untouched.
4. cli.py `dev` & `desktop` default to `/app` with `--legacy-studio` fallback to `/`.
"""

from __future__ import annotations

import re
import pytest
from httpx import ASGITransport, AsyncClient

import cli
from core.main import _STUDIO_CSP, app


FORBIDDEN_CDNS = (
    "cdn.tailwindcss.com",
    "cdnjs.cloudflare.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "unpkg.com",
    "jsdelivr.net",
)


@pytest.mark.asyncio
async def test_unified_dev_app_served_under_strict_self_csp():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/app")
        assert resp.status_code == 200
        assert "Content-Security-Policy" in resp.headers
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("Referrer-Policy") == "no-referrer"
        assert resp.headers.get("Cache-Control") == "no-cache"

        html = resp.text
        assert "Keelway" in html
        assert "/app/assets/" in html
        for forbidden_cdn in FORBIDDEN_CDNS:
            assert forbidden_cdn not in html

        js_match = re.search(r'src="(/app/assets/[^"]+\.js)"', html)
        assert js_match is not None, "Compiled /app/assets/*.js bundle link missing"
        bundle_resp = await client.get(js_match.group(1))
        assert bundle_resp.status_code == 200
        assert "sent: unmeasured" in bundle_resp.text
        assert "Approvals are never run from here" in bundle_resp.text
        assert "Only you can approve" in bundle_resp.text

        css_match = re.search(r'href="(/app/assets/[^"]+\.css)"', html)
        assert css_match is not None, "Compiled /app/assets/*.css bundle link missing"
        css_resp = await client.get(css_match.group(1))
        assert css_resp.status_code == 200
        assert "--attn-ochre" in css_resp.text
        assert (
            '[data-reduce-motion="true"]' in css_resp.text
            or "[data-reduce-motion=true]" in css_resp.text
        )


@pytest.mark.asyncio
async def test_unified_dev_app_spa_subpath_and_missing_asset_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        slash_resp = await client.get("/app/")
        assert slash_resp.status_code == 200
        assert slash_resp.headers.get("Content-Security-Policy") == _STUDIO_CSP
        assert slash_resp.headers.get("Cache-Control") == "no-cache"
        assert "/app/assets/" in slash_resp.text

        subpath_resp = await client.get("/app/settings")
        assert subpath_resp.status_code == 200
        assert subpath_resp.headers.get("Content-Security-Policy") == _STUDIO_CSP
        assert subpath_resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert subpath_resp.headers.get("Referrer-Policy") == "no-referrer"
        assert subpath_resp.headers.get("Cache-Control") == "no-cache"
        assert "/app/assets/" in subpath_resp.text

        missing_asset_resp = await client.get("/app/assets/nonexistent-chunk.js")
        assert missing_asset_resp.status_code == 404

        double_slash_missing_resp = await client.get("/app//assets/missing.js")
        assert double_slash_missing_resp.status_code == 404

        legacy_studio_resp = await client.get("/studio")
        assert legacy_studio_resp.status_code == 200
        assert "Keelway Studio" in legacy_studio_resp.text
        assert "/studio/assets/studio.js" in legacy_studio_resp.text


def test_cli_dev_defaults_to_unified_app_with_legacy_studio_flag():
    parser = cli.build_parser()

    default_args = parser.parse_args(["dev"])
    assert default_args.legacy_studio is False

    legacy_args = parser.parse_args(["dev", "--legacy-studio"])
    assert legacy_args.legacy_studio is True

    desktop_legacy_args = parser.parse_args(["desktop", "--legacy-studio"])
    assert desktop_legacy_args.legacy_studio is True

    assert cli._resolve_dev_launch_path(legacy_studio=False) == "/app"
    assert cli._resolve_dev_launch_path(legacy_studio=True) == "/"
