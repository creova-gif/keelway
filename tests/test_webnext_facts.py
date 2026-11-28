"""
Product-Facts & Next.js 15 Sovereign Website Drift Verification Gate.

Verifies that:
1. Every feature claim in `web-next/public/product-facts.json` (and mirrored
   `web-next/product-facts.json`) maps to real source files and executable test
   suites on disk, preventing marketing drift.
2. The Next.js 15 App Router site (`web-next/`, the canonical public surface)
   preserves permanent 308 redirects for all legacy `.html` bookmarks, serves
   all primary routes, exposes `/openapi.json`, `sitemap.ts`, `robots.ts`, and
   bundles self-hosted `.woff2` variable fonts.
3. Zero third-party font or stylesheet CDNs (`fonts.googleapis.com`,
   `fonts.gstatic.com`, `cdn.tailwindcss.com`, `cdnjs.cloudflare.com`) appear
   anywhere under `web-next/src/` or `web-next/public/`.
4. Official TypeScript SDK (`@keelway/sdk`) maintains zero runtime npm
   dependencies and passes its Node test suite.

History: this gate previously bound to the retired `website/` app
(KEEL-WEB-055); `SITE_DIR` now points at `web-next/`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

KEELWAY_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = KEELWAY_ROOT / "web-next"

FORBIDDEN_CDN_HOSTS = (
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "cdn.tailwindcss.com",
    "cdnjs.cloudflare.com",
)


def test_product_facts_manifest_integrity() -> None:
    public_facts_file = SITE_DIR / "public" / "product-facts.json"
    root_facts_file = SITE_DIR / "product-facts.json"

    assert public_facts_file.exists(), "web-next/public/product-facts.json must exist"
    assert root_facts_file.exists(), "web-next/product-facts.json must exist"

    public_data = json.loads(public_facts_file.read_text(encoding="utf-8"))
    root_data = json.loads(root_facts_file.read_text(encoding="utf-8"))
    assert public_data == root_data, (
        "web-next/product-facts.json and web-next/public/product-facts.json must stay in sync"
    )

    assert public_data["version"] == "1.1.0"
    features = public_data["features"]
    assert isinstance(features, dict) and len(features) >= 7

    for feat_name, feat in features.items():
        assert feat.get("status") in ("AVAILABLE", "EXPERIMENTAL"), (
            f"Unexpected status in {feat_name}: {feat.get('status')}"
        )
        assert isinstance(feat.get("claim"), str) and feat["claim"].strip(), (
            f"Missing non-empty claim in {feat_name}"
        )

        if feat["status"] == "AVAILABLE":
            assert feat.get("evidence_test"), f"AVAILABLE feature '{feat_name}' must declare evidence_test"
            assert feat.get("code_path"), f"AVAILABLE feature '{feat_name}' must declare code_path"

        if "evidence_test" in feat:
            tests = [t.strip() for t in feat["evidence_test"].split(",") if t.strip()]
            assert len(tests) >= 1
            for t_path in tests:
                assert (KEELWAY_ROOT / t_path).exists(), (
                    f"Evidence test '{t_path}' for '{feat_name}' not found on disk"
                )

        if "code_path" in feat:
            code_paths = [c.strip() for c in feat["code_path"].split(",") if c.strip()]
            assert len(code_paths) >= 1
            for c_path in code_paths:
                assert (KEELWAY_ROOT / c_path).exists(), (
                    f"Code path '{c_path}' for '{feat_name}' not found on disk"
                )

        if feat["status"] == "EXPERIMENTAL":
            note = feat.get("qualification_note", "")
            assert isinstance(note, str) and note.strip(), (
                f"Experimental feature '{feat_name}' must include a non-empty qualification_note"
            )

    expected_available = (
        "dual_mode_agent_builder_and_cross_repo_runtime",
        "unified_proof_strip_ux",
        "hybrid_opencore_and_frontier_gateway",
        "four_dimension_routing_and_responses_api",
        "multi_tenant_governance_and_spend_caps",
        "official_python_and_typescript_sdks",
    )
    for key in expected_available:
        assert key in features, f"Missing required feature '{key}' in product-facts.json"
        assert features[key]["status"] == "AVAILABLE"

    assert features["tier2_hardware_security_hal"]["status"] == "EXPERIMENTAL"


def test_nextjs_app_router_structure_and_legacy_redirects() -> None:
    pkg_file = SITE_DIR / "package.json"
    assert pkg_file.exists(), "web-next/package.json must exist"
    pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
    deps = pkg.get("dependencies", {})
    assert "next" in deps and deps["next"].lstrip("^~").startswith("15."), (
        f"Expected Next.js 15 in web-next/package.json, got {deps.get('next')}"
    )

    next_cfg_file = SITE_DIR / "next.config.ts"
    assert next_cfg_file.exists(), "web-next/next.config.ts must exist"
    next_cfg_text = next_cfg_file.read_text(encoding="utf-8")

    expected_redirects = (
        ("/index.html", "/"),
        ("/docs.html", "/docs"),
        ("/api.html", "/product"),
        ("/brand.html", "/about"),
    )
    for src, dest in expected_redirects:
        pattern = (
            r'source:\s*"' + re.escape(src) + r'"[\s\S]*?'
            r'destination:\s*"' + re.escape(dest) + r'"[\s\S]*?'
            r"permanent:\s*true"
        )
        assert re.search(pattern, next_cfg_text), (
            f"Missing permanent (308) redirect {src} -> {dest} in web-next/next.config.ts"
        )

    expected_route_pages = (
        SITE_DIR / "src" / "app" / "page.tsx",
        SITE_DIR / "src" / "app" / "product" / "page.tsx",
        SITE_DIR / "src" / "app" / "pricing" / "page.tsx",
        SITE_DIR / "src" / "app" / "docs" / "page.tsx",
        SITE_DIR / "src" / "app" / "changelog" / "page.tsx",
        SITE_DIR / "src" / "app" / "about" / "page.tsx",
        SITE_DIR / "src" / "app" / "contact" / "page.tsx",
        SITE_DIR / "src" / "app" / "legal" / "page.tsx",
        SITE_DIR / "src" / "app" / "blog" / "page.tsx",
        SITE_DIR / "src" / "app" / "sign-in" / "page.tsx",
        SITE_DIR / "src" / "app" / "signup" / "page.tsx",
        SITE_DIR / "src" / "app" / "offline" / "page.tsx",
        SITE_DIR / "src" / "app" / "not-found.tsx",
    )
    for page_path in expected_route_pages:
        assert page_path.exists(), f"Missing Next.js route file: {page_path}"
        assert page_path.stat().st_size > 100, f"Next.js route file appears empty: {page_path}"

    utils_text = (SITE_DIR / "src" / "lib" / "utils.ts").read_text(encoding="utf-8")
    assert "https://kora-sable.vercel.app" in utils_text

    sitemap_file = SITE_DIR / "src" / "app" / "sitemap.ts"
    assert sitemap_file.exists(), "web-next/src/app/sitemap.ts must exist"
    sitemap_text = sitemap_file.read_text(encoding="utf-8")
    assert "SITE_URL" in sitemap_text
    for route in (
        "", "/product", "/pricing", "/docs", "/changelog", "/about",
        "/blog", "/contact", "/legal", "/sign-in", "/signup",
    ):
        assert f'"{route}"' in sitemap_text, f"Route {route} missing from sitemap.ts"

    robots_file = SITE_DIR / "src" / "app" / "robots.ts"
    assert robots_file.exists(), "web-next/src/app/robots.ts must exist"
    robots_text = robots_file.read_text(encoding="utf-8")
    assert "SITE_URL" in robots_text and "sitemap.xml" in robots_text

    manifest_file = SITE_DIR / "src" / "app" / "manifest.ts"
    assert manifest_file.exists(), "web-next/src/app/manifest.ts must exist"
    manifest_text = manifest_file.read_text(encoding="utf-8")
    assert "#08090A" in manifest_text and "/favicon.svg" in manifest_text

    feed_route_file = SITE_DIR / "src" / "app" / "feed.xml" / "route.ts"
    assert feed_route_file.exists(), "web-next/src/app/feed.xml/route.ts must exist"
    feed_text = feed_route_file.read_text(encoding="utf-8")
    assert "application/rss+xml" in feed_text and "SITE_URL" in feed_text

    openapi_file = SITE_DIR / "public" / "openapi.json"
    assert openapi_file.exists(), "web-next/public/openapi.json must exist"
    openapi_doc = json.loads(openapi_file.read_text(encoding="utf-8"))
    assert str(openapi_doc.get("openapi", "")).startswith("3.")
    for required_api_path in ("/health", "/v1/models", "/v1/chat/completions", "/v1/usage"):
        assert required_api_path in openapi_doc.get("paths", {}), (
            f"Missing {required_api_path} in web-next/public/openapi.json"
        )

    fonts_dir = SITE_DIR / "src" / "fonts"
    assert fonts_dir.exists(), "web-next/src/fonts directory must exist"
    woff2_files = sorted(fonts_dir.glob("*.woff2"))
    assert len(woff2_files) >= 2, "Expected self-hosted Inter & JetBrains Mono .woff2 fonts in web-next/src/fonts/"
    for font_file in woff2_files:
        assert font_file.stat().st_size > 1024, f"Font file {font_file} is unexpectedly small"


def test_website_sovereign_zero_third_party_cdn_invariant() -> None:
    scanned_files = []
    for root_dir in (SITE_DIR / "src", SITE_DIR / "public"):
        assert root_dir.exists(), f"Expected directory {root_dir} to exist"
        for ext in ("*.ts", "*.tsx", "*.css", "*.html"):
            scanned_files.extend(root_dir.rglob(ext))

    assert len(scanned_files) >= 15, f"Expected >= 15 website source/public files, found {len(scanned_files)}"

    for file_path in scanned_files:
        content = file_path.read_text(encoding="utf-8")
        for host in FORBIDDEN_CDN_HOSTS:
            assert host not in content, (
                f"Sovereign CDN violation: {file_path.relative_to(KEELWAY_ROOT)} references '{host}'"
            )


def test_official_typescript_sdk_zero_deps_and_node_suite() -> None:
    ts_dir = KEELWAY_ROOT / "sdk" / "typescript"
    pkg_json = json.loads((ts_dir / "package.json").read_text(encoding="utf-8"))

    assert pkg_json["name"] == "@keelway/sdk"
    assert pkg_json["version"] == "1.1.0"
    assert not pkg_json.get("dependencies"), "@keelway/sdk must have zero runtime npm dependencies"
    assert (ts_dir / "dist" / "index.js").exists(), "Compiled sdk/typescript/dist/index.js must exist"
    assert (ts_dir / "dist" / "index.d.ts").exists(), "Compiled sdk/typescript/dist/index.d.ts must exist"

    node_bin = shutil.which("node")
    if node_bin:
        proc = subprocess.run(
            [node_bin, "--test", "test/sdk.test.mjs"],
            cwd=str(ts_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, f"@keelway/sdk Node test suite failed:\n{proc.stdout}\n{proc.stderr}"


def test_web_next_public_surface_facts() -> None:
    """web-next public surface — the marketing copy must carry accurate
    commercial and platform claims only (canonical 4-tier pricing, honest
    labels). Successor to the retired v3 Maritime Instrument surface test."""
    app = SITE_DIR / "src" / "app"

    home = (app / "page.tsx").read_text(encoding="utf-8")
    assert "Agents that answer to you" in home
    assert "signed receipt" in home
    assert "P-10" in home

    pricing = (app / "pricing" / "page.tsx").read_text(encoding="utf-8")
    for token in ("$15", "$29", "0% token markup", "Sovereign VPC", "85 / 15"):
        assert token in pricing, f"pricing page missing canonical fact: {token}"
    assert "$39/seat" not in pricing, "stale $39/seat pricing must not appear on /pricing"

    footer = (SITE_DIR / "src" / "components" / "site" / "footer.tsx").read_text(
        encoding="utf-8"
    )
    assert "Apache-2.0 open core" in footer
    assert "0% token markup" in footer
    assert "Sorvex Labs" in footer

    about = (app / "about" / "page.tsx").read_text(encoding="utf-8")
    assert "Sorvex Labs" in about and "Apache-2.0" in about

    signin = (app / "sign-in" / "page.tsx").read_text(encoding="utf-8")
    assert "Keelway Cloud" in signin
