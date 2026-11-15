"""
Phase 13 Homepage Golden-Thread Studio Showcase & v1.1.0 Release Synchronization Suite.

Verifies:
1. Cross-manifest `v1.1.0` version parity across `pyproject.toml`, `core.main:app`, `cli.py` (`cmd_init`),
   `EnterpriseIdentitySiemManager` (OCSF `product.version` + OTLP `service.version`/`scope.version`),
   `@keelway/sdk`, `website/package.json`, `product-facts.json`, `openapi.json` (273 routes),
   `Formula/keelway.rb`, `.github/workflows/release-artifacts.yml`, `CHANGELOG.md`, and CycloneDX 1.5 SBOM.
2. Public Next.js 15 Homepage Golden-Thread Studio Showcase (`/#studio-showcase`) structural contract,
   file-size budgets (<500 lines for new modules, <750 lines for touched modules), search-index sync,
   and zero private-token / `/playground` / stale `$39` drift.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from cli import cmd_init
from core.main import app
from core.platform.enterprise_identity_siem import EnterpriseIdentitySiemManager
from core.security.sbom import SBOMGenerator, SBOMVerifier

KEELWAY_ROOT = Path(__file__).resolve().parent.parent
WEBSITE_DIR = KEELWAY_ROOT / "website"

FORBIDDEN_PRIVATE_TOKENS = (
    "creova-gif",
    "creovas-projects",
    "kora.git",
    "KEEL-",
    "Antigravity",
    "gstack",
    "verify_engineering_gates.sh",
)


def test_v1_1_0_cross_manifest_version_parity_and_changelog(tmp_path: Path) -> None:
    expected_version = "1.1.0"

    # 1. pyproject.toml & FastAPI app
    pyproject = tomllib.loads((KEELWAY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["name"] == "keelway"
    assert pyproject["project"]["version"] == expected_version
    assert app.version == expected_version

    # 2. CLI workspace initialization config
    init_ws = tmp_path / "release_ws"
    init_ws.mkdir()
    assert cmd_init(path=init_ws, quiet=True) == 0
    init_cfg = json.loads((init_ws / ".keelway" / "config.json").read_text(encoding="utf-8"))
    assert init_cfg["version"] == expected_version

    # 3. Enterprise SIEM OCSF product.version & OTLP resource/scope versions
    ent_mgr = EnterpriseIdentitySiemManager(db_path=tmp_path / "ent_v110.db")
    try:
        ocsf = ent_mgr.export_siem("ws-v110", export_format="ocsf", limit=5)
        assert ocsf["records"][0]["metadata"]["product"]["version"] == expected_version
        otlp = ent_mgr.get_observability_metrics("ws-v110", metrics_format="otlp_json")
        res_attrs = {
            a["key"]: a["value"]["stringValue"]
            for a in otlp["otlp_resource_metrics"]["resource"]["attributes"]
        }
        assert res_attrs["service.version"] == expected_version
        scope_ver = otlp["otlp_resource_metrics"]["scopeMetrics"][0]["scope"]["version"]
        assert scope_ver == expected_version
    finally:
        ent_mgr.close()

    # 4. TypeScript SDK & Website package.json
    ts_pkg = json.loads((KEELWAY_ROOT / "sdk" / "typescript" / "package.json").read_text(encoding="utf-8"))
    web_pkg = json.loads((WEBSITE_DIR / "package.json").read_text(encoding="utf-8"))
    assert ts_pkg["version"] == expected_version
    assert web_pkg["version"] == expected_version

    # 5. Product-Facts manifests (byte-for-byte identical, 21 features, zero private tokens)
    facts_raw = (WEBSITE_DIR / "product-facts.json").read_text(encoding="utf-8")
    pub_facts_raw = (WEBSITE_DIR / "public" / "product-facts.json").read_text(encoding="utf-8")
    assert facts_raw == pub_facts_raw, "product-facts.json and public/product-facts.json must match byte-for-byte"
    for tok in FORBIDDEN_PRIVATE_TOKENS:
        assert tok not in facts_raw, f"Forbidden internal token '{tok}' found in product-facts.json"
    facts = json.loads(facts_raw)
    assert facts["version"] == expected_version
    assert len(facts["features"]) == 21
    showcase_feat = facts["features"]["zero_install_homepage_golden_thread_studio_showcase"]
    assert showcase_feat["status"] == "AVAILABLE"
    assert "GoldenThreadStudioShowcase.tsx" in showcase_feat["code_path"]
    assert "goldenThreadShowcaseEngine.ts" in showcase_feat["code_path"]
    assert showcase_feat["evidence_test"] == "tests/test_phase13_homepage_studio_and_release.py"

    # 6. OpenAPI 3.1 deterministic schemas (byte-for-byte identical, version 1.1.0, 273 paths)
    openapi_raw = (WEBSITE_DIR / "openapi.json").read_text(encoding="utf-8")
    pub_openapi_raw = (WEBSITE_DIR / "public" / "openapi.json").read_text(encoding="utf-8")
    assert openapi_raw == pub_openapi_raw, "website/openapi.json and website/public/openapi.json must match"
    openapi_doc = json.loads(openapi_raw)
    assert openapi_doc["info"]["version"] == expected_version
    assert len(openapi_doc["paths"]) == 273
    assert len(app.openapi()["paths"]) == 282

    # 7. Homebrew Formula, GitHub Release Workflow & CHANGELOG.md
    formula_raw = (KEELWAY_ROOT / "Formula" / "keelway.rb").read_text(encoding="utf-8")
    assert 'tag: "v1.1.0"' in formula_raw

    release_wf_raw = (KEELWAY_ROOT / ".github" / "workflows" / "release-artifacts.yml").read_text(encoding="utf-8")
    assert 'default: "v1.1.0"' in release_wf_raw

    ci_wf_raw = (KEELWAY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "keelway-1.0.0-py3-none-any.whl" not in ci_wf_raw
    assert "keelway-*-py3-none-any.whl" in ci_wf_raw

    changelog_raw = (KEELWAY_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    idx_110 = changelog_raw.find("## [1.1.0]")
    idx_100 = changelog_raw.find("## [1.0.0]")
    assert idx_110 != -1 and idx_100 != -1 and idx_110 < idx_100, (
        "CHANGELOG.md must define ## [1.1.0] above ## [1.0.0]"
    )
    for changelog_token in (
        "/#studio-showcase",
        "/v1/platform/studio/kflow/sync",
        "/v1/platform/traces/ingest",
        "/v1/platform/migrate/langgraph",
        "/v1/platform/kbrain/facts",
        "/v1/platform/khub/mirror/export",
        "/v1/platform/enterprise/p10-quorum/approve",
    ):
        assert changelog_token in changelog_raw, f"Missing '{changelog_token}' in CHANGELOG.md [1.1.0] entry"

    # 8. CycloneDX 1.5 SBOM generation & HMAC-SHA256 verification
    sbom_manifest = SBOMGenerator.generate(KEELWAY_ROOT).to_dict()
    verified_ok, verified_status, verified_meta = SBOMVerifier.verify(sbom_manifest)
    assert verified_ok is True and verified_status == "VERIFIED", (verified_ok, verified_status, verified_meta)


def test_homepage_golden_thread_studio_showcase_contract_and_hygiene() -> None:
    engine_file = WEBSITE_DIR / "src" / "lib" / "goldenThreadShowcaseEngine.ts"
    showcase_file = WEBSITE_DIR / "src" / "components" / "home" / "GoldenThreadStudioShowcase.tsx"
    home_page_file = WEBSITE_DIR / "src" / "app" / "page.tsx"
    cmdk_file = WEBSITE_DIR / "src" / "components" / "layout" / "CommandPalette.tsx"
    search_route_file = WEBSITE_DIR / "src" / "app" / "api" / "search-index" / "route.ts"
    analytics_file = WEBSITE_DIR / "src" / "lib" / "analytics.ts"
    verify_skill_file = (
        KEELWAY_ROOT / ".cursor" / "skills" / "verify-keelway" / "features" / "homepage-golden-thread-showcase.md"
    )

    assert engine_file.is_file(), "website/src/lib/goldenThreadShowcaseEngine.ts must exist"
    assert showcase_file.is_file(), "website/src/components/home/GoldenThreadStudioShowcase.tsx must exist"
    assert verify_skill_file.is_file(), "homepage-golden-thread-showcase.md verification skill must exist"

    engine_src = engine_file.read_text(encoding="utf-8")
    showcase_src = showcase_file.read_text(encoding="utf-8")
    home_src = home_page_file.read_text(encoding="utf-8")
    search_src = search_route_file.read_text(encoding="utf-8")
    verify_skill_src = verify_skill_file.read_text(encoding="utf-8")

    # Line-count caps: <500 for new showcase files, <750 for modified website files, <120 for verify doc
    assert len(engine_src.splitlines()) < 500, "goldenThreadShowcaseEngine.ts must be < 500 lines"
    assert len(showcase_src.splitlines()) < 500, "GoldenThreadStudioShowcase.tsx must be < 500 lines"
    assert len(verify_skill_src.splitlines()) < 120, "homepage-golden-thread-showcase.md must be < 120 lines"

    for capped_file in (home_page_file, cmdk_file, search_route_file, analytics_file):
        count = len(capped_file.read_text(encoding="utf-8").splitlines())
        assert count < 750, f"{capped_file.relative_to(KEELWAY_ROOT)} has {count} lines (must be < 750)"

    # Showcase component structural & accessibility invariants
    for showcase_token in (
        'id="studio-showcase"',
        "Plan & Import",
        "Build & Sync Studio",
        "Scrub & Blast-Radius",
        "Govern & Ship",
        "useReducedMotion",
        "<svg",
        "P-10",
        "keelway==1.1.0",
    ):
        assert showcase_token in showcase_src, (
            f"Missing required token '{showcase_token}' in GoldenThreadStudioShowcase.tsx"
        )

    # Pure engine presets & bidirectional/gate exports
    for engine_token in (
        "langgraph-refund-cycle",
        "pr-security-sentinel",
        "clinical-hipaa-intake",
        "syncShowcaseCodeToGraph",
        "syncShowcaseGraphToCode",
        "evaluateShowcasePromptGate",
    ):
        assert engine_token in engine_src, (
            f"Missing required token '{engine_token}' in goldenThreadShowcaseEngine.ts"
        )

    # Hygiene: zero "/playground or forbidden internal identifiers
    for target_path, target_text in ((engine_file, engine_src), (showcase_file, showcase_src)):
        assert '"/playground' not in target_text, (
            f"Stale /playground reference in {target_path.relative_to(KEELWAY_ROOT)}"
        )
        for private_tok in FORBIDDEN_PRIVATE_TOKENS:
            assert private_tok not in target_text, (
                f"Forbidden private token '{private_tok}' leaked in {target_path.relative_to(KEELWAY_ROOT)}"
            )

    # Homepage mount & Search Index synchronization
    assert "GoldenThreadStudioShowcase" in home_src, "website/src/app/page.tsx must mount GoldenThreadStudioShowcase"
    assert "#studio-showcase" in search_src, "search-index/route.ts must index #studio-showcase"
    assert "$29 Pro" in search_src, "search-index/route.ts must reference calibrated '$29 Pro' pricing"
    assert "$39" not in search_src, "search-index/route.ts must not contain stale '$39' pricing"
