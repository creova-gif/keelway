"""
Product-Facts & Next.js 15 Sovereign Website Drift Verification Gate.

Verifies that:
1. Every feature claim in `website/public/product-facts.json` (and mirrored
   `website/product-facts.json`) maps to real source files and executable test
   suites on disk, preventing marketing drift.
2. The Next.js 15 App Router website preserves permanent 308 redirects for all
   legacy `.html` bookmarks, serves all 7 primary routes, exposes `/openapi.json`,
   `sitemap.ts`, `robots.ts`, and bundles self-hosted `.woff2` variable fonts.
3. Zero third-party font or stylesheet CDNs (`fonts.googleapis.com`,
   `fonts.gstatic.com`, `cdn.tailwindcss.com`, `cdnjs.cloudflare.com`) appear
   anywhere under `website/src/` or `website/public/`.
4. Official TypeScript SDK (`@keelway/sdk`) maintains zero runtime npm
   dependencies and passes its Node test suite.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

KEELWAY_ROOT = Path(__file__).resolve().parent.parent
WEBSITE_DIR = KEELWAY_ROOT / "website"

FORBIDDEN_CDN_HOSTS = (
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "cdn.tailwindcss.com",
    "cdnjs.cloudflare.com",
)


def test_product_facts_manifest_integrity() -> None:
    public_facts_file = WEBSITE_DIR / "public" / "product-facts.json"
    root_facts_file = WEBSITE_DIR / "product-facts.json"

    assert public_facts_file.exists(), "website/public/product-facts.json must exist"
    assert root_facts_file.exists(), "website/product-facts.json must exist"

    public_data = json.loads(public_facts_file.read_text(encoding="utf-8"))
    root_data = json.loads(root_facts_file.read_text(encoding="utf-8"))
    assert public_data == root_data, (
        "website/product-facts.json and website/public/product-facts.json must stay in sync"
    )

    assert public_data["version"] == "1.0.0"
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
    pkg_file = WEBSITE_DIR / "package.json"
    assert pkg_file.exists(), "website/package.json must exist"
    pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
    deps = pkg.get("dependencies", {})
    assert "next" in deps and deps["next"].lstrip("^~").startswith("15."), (
        f"Expected Next.js 15 in website/package.json, got {deps.get('next')}"
    )

    next_cfg_file = WEBSITE_DIR / "next.config.ts"
    assert next_cfg_file.exists(), "website/next.config.ts must exist"
    next_cfg_text = next_cfg_file.read_text(encoding="utf-8")

    expected_redirects = (
        ("/index.html", "/"),
        ("/docs.html", "/docs"),
        ("/api.html", "/api-reference"),
        ("/brand.html", "/brand"),
    )
    for src, dest in expected_redirects:
        pattern = (
            r'source:\s*"' + re.escape(src) + r'"[\s\S]*?'
            r'destination:\s*"' + re.escape(dest) + r'"[\s\S]*?'
            r"permanent:\s*true"
        )
        assert re.search(pattern, next_cfg_text), (
            f"Missing permanent (308) redirect {src} -> {dest} in website/next.config.ts"
        )

    expected_route_pages = (
        WEBSITE_DIR / "src" / "app" / "page.tsx",
        WEBSITE_DIR / "src" / "app" / "models" / "page.tsx",
        WEBSITE_DIR / "src" / "app" / "governance" / "page.tsx",
        WEBSITE_DIR / "src" / "app" / "pricing" / "page.tsx",
        WEBSITE_DIR / "src" / "app" / "brand" / "page.tsx",
        WEBSITE_DIR / "src" / "app" / "docs" / "page.tsx",
        WEBSITE_DIR / "src" / "app" / "api-reference" / "page.tsx",
    )
    for page_path in expected_route_pages:
        assert page_path.exists(), f"Missing Next.js route file: {page_path}"
        assert page_path.stat().st_size > 100, f"Next.js route file appears empty: {page_path}"

    utils_text = (WEBSITE_DIR / "src" / "lib" / "utils.ts").read_text(encoding="utf-8")
    assert "https://kora-sable.vercel.app" in utils_text

    sitemap_file = WEBSITE_DIR / "src" / "app" / "sitemap.ts"
    assert sitemap_file.exists(), "website/src/app/sitemap.ts must exist"
    sitemap_text = sitemap_file.read_text(encoding="utf-8")
    assert "SITE_URL" in sitemap_text
    for route in ("/", "/models", "/governance", "/pricing", "/docs", "/api-reference", "/brand"):
        assert f'"{route}"' in sitemap_text, f"Route {route} missing from sitemap.ts"

    robots_file = WEBSITE_DIR / "src" / "app" / "robots.ts"
    assert robots_file.exists(), "website/src/app/robots.ts must exist"
    robots_text = robots_file.read_text(encoding="utf-8")
    assert "SITE_URL" in robots_text and "sitemap.xml" in robots_text

    openapi_file = WEBSITE_DIR / "public" / "openapi.json"
    assert openapi_file.exists(), "website/public/openapi.json must exist"
    openapi_doc = json.loads(openapi_file.read_text(encoding="utf-8"))
    assert str(openapi_doc.get("openapi", "")).startswith("3.")
    for required_api_path in ("/health", "/v1/models", "/v1/chat/completions", "/v1/usage"):
        assert required_api_path in openapi_doc.get("paths", {}), (
            f"Missing {required_api_path} in website/public/openapi.json"
        )

    fonts_dir = WEBSITE_DIR / "src" / "fonts"
    assert fonts_dir.exists(), "website/src/fonts directory must exist"
    woff2_files = sorted(fonts_dir.glob("*.woff2"))
    assert len(woff2_files) >= 2, "Expected self-hosted Inter & JetBrains Mono .woff2 fonts in website/src/fonts/"
    for font_file in woff2_files:
        assert font_file.stat().st_size > 1024, f"Font file {font_file} is unexpectedly small"


def test_website_sovereign_zero_third_party_cdn_invariant() -> None:
    scanned_files = []
    for root_dir in (WEBSITE_DIR / "src", WEBSITE_DIR / "public"):
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
    assert pkg_json["version"] == "1.0.0"
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


def test_vercel_flags_ab_experiments_and_funnel_wiring() -> None:
    flags_file = WEBSITE_DIR / "src" / "flags.ts"
    discovery_route = WEBSITE_DIR / "src" / "app" / ".well-known" / "vercel" / "flags" / "route.ts"
    analytics_file = WEBSITE_DIR / "src" / "lib" / "analytics.ts"
    p10_deck_file = WEBSITE_DIR / "src" / "components" / "home" / "P10InteractiveDeck.tsx"
    flag_values_file = WEBSITE_DIR / "src" / "components" / "experiments" / "ExperimentFlagValues.tsx"
    middleware_file = WEBSITE_DIR / "src" / "middleware.ts"

    for required in (flags_file, discovery_route, analytics_file, p10_deck_file, flag_values_file, middleware_file):
        assert required.exists(), f"Missing A/B experimentation file: {required.relative_to(KEELWAY_ROOT)}"

    flags_src = flags_file.read_text(encoding="utf-8")
    for token in (
        "exp-home-gate-v1",
        "control-stepper",
        "interactive-p10-deck",
        "exp-quickstart-cli-v1",
        "code-tabs-default",
        "interactive-tui-boot",
        "vercelAdapter",
    ):
        assert token in flags_src, f"Expected '{token}' in website/src/flags.ts"

    analytics_src = analytics_file.read_text(encoding="utf-8")
    for evt in (
        "experiment_exposed",
        "p10_deck_action",
        "p10_escalation_triggered",
        "cli_tui_command_simulated",
        "$feature_flag_called",
    ):
        assert evt in analytics_src, f"Expected funnel hook '{evt}' in website/src/lib/analytics.ts"

    p10_src = p10_deck_file.read_text(encoding="utf-8")
    assert "Only you can approve" in p10_src
    assert "Approvals are never run from here" in p10_src
    assert "Confirm external send" in p10_src


def test_governance_interactive_tamper_and_drift_labs() -> None:
    tamper_file = WEBSITE_DIR / "src" / "components" / "governance" / "RecordTamperLab.tsx"
    drift_file = WEBSITE_DIR / "src" / "components" / "governance" / "ManifestDriftSimulator.tsx"
    gov_page = WEBSITE_DIR / "src" / "app" / "governance" / "page.tsx"

    assert tamper_file.exists(), "RecordTamperLab.tsx must exist"
    assert drift_file.exists(), "ManifestDriftSimulator.tsx must exist"

    tamper_src = tamper_file.read_text(encoding="utf-8")
    assert len(tamper_src.splitlines()) < 380, "RecordTamperLab.tsx must remain < 380 lines"
    for required_token in (
        "Seq",
        "Timestamp",
        "Actor",
        "Capability",
        "Risk",
        "Prev Hash",
        "Entry SHA-256",
        "License",
        "Hosting",
        "Operator",
        "Data Boundary",
        "⚡ Simulate Tamper on #1279",
        "Verify Chain",
        "Restore Valid Ledger",
        "governance_tamper_simulated",
        "governance_chain_verified",
    ):
        assert required_token in tamper_src, f"Missing '{required_token}' in RecordTamperLab.tsx"

    drift_src = drift_file.read_text(encoding="utf-8")
    assert len(drift_src.splitlines()) < 380, "ManifestDriftSimulator.tsx must remain < 380 lines"
    for required_token in (
        "keelway.agent/v1",
        "keelway-core:7b",
        "Simulate Prompt Update (p-13 → p-14)",
        "Re-Approve Standing Scope",
        "keelway.package/v1",
        "Linear Sprint Triager",
        "shell=True",
    ):
        assert required_token in drift_src, f"Missing '{required_token}' in ManifestDriftSimulator.tsx"

    gov_src = gov_page.read_text(encoding="utf-8")
    assert "RecordTamperLab" in gov_src, "governance/page.tsx must mount RecordTamperLab"
    assert "ManifestDriftSimulator" in gov_src, "governance/page.tsx must mount ManifestDriftSimulator"


def test_unified_10view_playground_route_and_navigation() -> None:
    playground_page = WEBSITE_DIR / "src" / "app" / "playground" / "page.tsx"
    playground_comp = WEBSITE_DIR / "src" / "components" / "playground" / "UnifiedPlatformPlayground.tsx"
    header_file = WEBSITE_DIR / "src" / "components" / "layout" / "Header.tsx"
    sitemap_file = WEBSITE_DIR / "src" / "app" / "sitemap.ts"
    search_index_file = WEBSITE_DIR / "src" / "app" / "api" / "search-index" / "route.ts"

    assert playground_page.exists(), "website/src/app/playground/page.tsx must exist"
    assert playground_comp.exists(), "UnifiedPlatformPlayground.tsx must exist"

    page_src = playground_page.read_text(encoding="utf-8")
    assert len(page_src.splitlines()) < 140, "playground/page.tsx must remain < 140 lines"
    assert 'canonical: "/playground"' in page_src
    assert "UnifiedPlatformPlayground" in page_src

    comp_src = playground_comp.read_text(encoding="utf-8")
    assert len(comp_src.splitlines()) < 550, "UnifiedPlatformPlayground.tsx must remain < 550 lines"
    for view_label in (
        "Builder Mode",
        "Guided Non-Coder Mode",
        "No-Code Builder",
        "Agents",
        "IDE",
        "Project Manager",
        "Product",
        "Automation",
        "Marketplace",
        "Security",
        "Documentation",
        "Operations",
        "Compile Blueprint",
        "HIPAA-ready patient intake",
        "Automated PR security",
        "Multi-currency fintech invoice",
        "P-10",
    ):
        assert view_label in comp_src, f"Missing '{view_label}' in UnifiedPlatformPlayground.tsx"

    header_src = header_file.read_text(encoding="utf-8")
    assert '"/playground"' in header_src and "Playground" in header_src

    sitemap_src = sitemap_file.read_text(encoding="utf-8")
    assert '"/playground"' in sitemap_src

    index_src = search_index_file.read_text(encoding="utf-8")
    assert "/playground" in index_src
    assert "Marketplace" in index_src and "No-Code" in index_src


def test_five_stream_pricing_and_byom_compliance_disclosure() -> None:
    pricing_data_file = WEBSITE_DIR / "src" / "data" / "pricing.ts"
    pricing_tiers_file = WEBSITE_DIR / "src" / "components" / "pricing" / "PricingTiers.tsx"

    data_src = pricing_data_file.read_text(encoding="utf-8")
    tiers_src = pricing_tiers_file.read_text(encoding="utf-8")
    combined_src = data_src + "\n" + tiers_src

    assert len(tiers_src.splitlines()) < 620, "PricingTiers.tsx must remain < 620 lines"

    for stream_token in (
        "Free / Community",
        "Keelway Pro",
        "Bring Your Own Model",
        "BYOM",
        "Keelway Enterprise",
        "Marketplace",
        "85%",
        "15%",
    ):
        assert stream_token in combined_src, f"Missing 5-stream pricing token '{stream_token}'"

    # Mandatory explicit compliance notice in BOTH UI banner/card and FAQ data
    for target_name, target_src in (("PricingTiers.tsx", tiers_src), ("data/pricing.ts", data_src)):
        assert "ChatGPT" in target_src and "Claude" in target_src, (
            f"{target_name} must explicitly reference ChatGPT and Claude consumer subscription rules"
        )
        assert "API" in target_src and ("not automatically grant" in target_src.lower() or "do not grant" in target_src.lower()), (
            f"{target_name} must state consumer web subscriptions do not automatically grant third-party API access"
        )


def test_command_palette_linear_prefix_modes_and_file_size_caps() -> None:
    cmdk_file = WEBSITE_DIR / "src" / "components" / "layout" / "CommandPalette.tsx"
    cmdk_src = cmdk_file.read_text(encoding="utf-8")

    for token in (
        "> Actions",
        "@ Models",
        "/ Docs",
        "# APIs & Governance",
        "Launch 10-View Playground",
        "Simulate Record Tamper Lab",
        "Open No-Code Blueprint Builder",
        "Compare BYOM & Pro Pricing",
    ):
        assert token in cmdk_src, f"Missing '{token}' in CommandPalette.tsx"

    # Strict <750-line invariant across all platform showcase / modified TS & TSX files
    checked_files = (
        WEBSITE_DIR / "src" / "components" / "governance" / "RecordTamperLab.tsx",
        WEBSITE_DIR / "src" / "components" / "governance" / "ManifestDriftSimulator.tsx",
        WEBSITE_DIR / "src" / "components" / "playground" / "UnifiedPlatformPlayground.tsx",
        WEBSITE_DIR / "src" / "app" / "playground" / "page.tsx",
        WEBSITE_DIR / "src" / "app" / "governance" / "page.tsx",
        WEBSITE_DIR / "src" / "data" / "pricing.ts",
        WEBSITE_DIR / "src" / "components" / "pricing" / "PricingTiers.tsx",
        WEBSITE_DIR / "src" / "app" / "pricing" / "page.tsx",
        WEBSITE_DIR / "src" / "components" / "layout" / "CommandPalette.tsx",
        WEBSITE_DIR / "src" / "components" / "layout" / "Header.tsx",
        WEBSITE_DIR / "src" / "app" / "sitemap.ts",
        WEBSITE_DIR / "src" / "app" / "api" / "search-index" / "route.ts",
        WEBSITE_DIR / "src" / "lib" / "analytics.ts",
    )
    for ts_path in checked_files:
        line_count = len(ts_path.read_text(encoding="utf-8").splitlines())
        assert line_count < 750, (
            f"{ts_path.relative_to(KEELWAY_ROOT)} has {line_count} lines (must be strictly < 750)"
        )
