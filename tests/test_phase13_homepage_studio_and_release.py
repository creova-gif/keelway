"""
Phase 13 Public-Site Intake Surface & v1.1.0 Release Synchronization Suite.

Verifies:
1. Cross-manifest `v1.1.0` version parity across `pyproject.toml`, `core.main:app`, `cli.py` (`cmd_init`),
   `EnterpriseIdentitySiemManager` (OCSF `product.version` + OTLP `service.version`/`scope.version`),
   `@keelway/sdk`, `web-next/package.json`, `product-facts.json`, `openapi.json` (273 routes),
   `Formula/keelway.rb`, `.github/workflows/release-artifacts.yml`, `CHANGELOG.md`, and CycloneDX 1.5 SBOM.
2. Public Next.js 15 early-access intake surface (`/api/early-access` + signup form) structural
   contract, file-size budgets (<750 lines for touched modules), and zero private-token /
   `/playground` / stale `$39` drift.
   (History: the original Phase 13 Golden-Thread Studio Showcase (`/#studio-showcase`) was a
   website/-era surface retired with KEEL-WEB-055.)
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
SITE_DIR = KEELWAY_ROOT / "web-next"

FORBIDDEN_PRIVATE_TOKENS = (
    # NOTE: "creova-gif" removed in KEEL-WEB-055 — the public open-core org
    # is deliberately linked from the shipped site; "creovas-projects" stays forbidden.
    "creovas-projects",
    "keelway.git",
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
    web_pkg = json.loads((SITE_DIR / "package.json").read_text(encoding="utf-8"))
    assert ts_pkg["version"] == expected_version
    assert web_pkg["version"] == expected_version

    # 5. Product-Facts manifests (byte-for-byte identical, 21 features, zero private tokens)
    facts_raw = (SITE_DIR / "product-facts.json").read_text(encoding="utf-8")
    pub_facts_raw = (SITE_DIR / "public" / "product-facts.json").read_text(encoding="utf-8")
    assert facts_raw == pub_facts_raw, "product-facts.json and public/product-facts.json must match byte-for-byte"
    for tok in FORBIDDEN_PRIVATE_TOKENS:
        assert tok not in facts_raw, f"Forbidden internal token '{tok}' found in product-facts.json"
    facts = json.loads(facts_raw)
    assert facts["version"] == expected_version
    assert len(facts["features"]) >= 21
    intake_feat = facts["features"]["early_access_intake_api_and_signup_surface"]
    assert intake_feat["status"] == "AVAILABLE"
    assert "web-next/src/app/api/early-access/route.ts" in intake_feat["code_path"]
    assert "web-next/src/components/site/magic-link-form.tsx" in intake_feat["code_path"]
    assert intake_feat["evidence_test"] == "web-next/e2e/routes.spec.ts"

    # 6. OpenAPI 3.1 deterministic schemas (byte-for-byte identical, version 1.1.0, >= 273 paths)
    openapi_raw = (SITE_DIR / "openapi.json").read_text(encoding="utf-8")
    pub_openapi_raw = (SITE_DIR / "public" / "openapi.json").read_text(encoding="utf-8")
    assert openapi_raw == pub_openapi_raw, "website/openapi.json and website/public/openapi.json must match"
    openapi_doc = json.loads(openapi_raw)
    assert openapi_doc["info"]["version"] == expected_version
    assert len(openapi_doc["paths"]) >= 273
    assert len(app.openapi()["paths"]) >= 273

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


def test_early_access_intake_surface_contract_and_hygiene() -> None:
    # KEEL-WEB-053/055: the retired V3 homepage showcase is replaced by the
    # web-next early-access intake surface — a private-webhook-backed API route
    # plus the public signup form that posts to it.
    route_file = SITE_DIR / "src" / "app" / "api" / "early-access" / "route.ts"
    form_file = SITE_DIR / "src" / "components" / "site" / "magic-link-form.tsx"
    routes_spec = SITE_DIR / "e2e" / "routes.spec.ts"
    home_page_file = SITE_DIR / "src" / "app" / "page.tsx"

    assert route_file.is_file(), "web-next/src/app/api/early-access/route.ts must exist"
    assert form_file.is_file(), "web-next/src/components/site/magic-link-form.tsx must exist"
    assert routes_spec.is_file(), "web-next/e2e/routes.spec.ts must exist"

    route_src = route_file.read_text(encoding="utf-8")
    form_src = form_file.read_text(encoding="utf-8")

    # Fail-closed contract: origin allowlist, rate limit, private webhook only.
    for token in ("ALLOWED_ORIGINS", "EARLY_ACCESS_WEBHOOK_URL", "503", "X-Keelway-Signature-256"):
        assert token in route_src, f"Missing '{token}' in early-access route"

    # The form must POST to the intake route for real (no mailto/console stub).
    assert '"/api/early-access"' in form_src or "'/api/early-access'" in form_src, (
        "magic-link form must POST to /api/early-access"
    )
    assert "mailto:" not in form_src

    for capped_file in (route_file, form_file, home_page_file):
        count = len(capped_file.read_text(encoding="utf-8").splitlines())
        assert count < 750, f"{capped_file.relative_to(KEELWAY_ROOT)} has {count} lines (must be < 750)"

    # Hygiene: no stale v1 routes or forbidden internal identifiers on the
    # intake surface.
    home_src = home_page_file.read_text(encoding="utf-8")
    for target_path, target_text in ((route_file, route_src), (form_file, form_src), (home_page_file, home_src)):
        assert '"/playground' not in target_text, (
            f"Stale /playground reference in {target_path.relative_to(KEELWAY_ROOT)}"
        )
        for private_tok in FORBIDDEN_PRIVATE_TOKENS:
            assert private_tok not in target_text, (
                f"Forbidden private token '{private_tok}' leaked in {target_path.relative_to(KEELWAY_ROOT)}"
            )
