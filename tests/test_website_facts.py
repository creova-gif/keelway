"""
Test that every claim in website/product-facts.json maps to an existing file
and valid test suite in the codebase, preventing marketing drift.
"""

import json
from pathlib import Path


def test_product_facts_manifest_integrity():
    facts_file = Path("website/product-facts.json")
    assert facts_file.exists(), "website/product-facts.json must exist"

    data = json.loads(facts_file.read_text(encoding="utf-8"))
    assert data["version"] == "0.1.0"
    features = data["features"]

    for feat_name, feat in features.items():
        assert "status" in feat, f"Missing status in {feat_name}"
        assert "claim" in feat, f"Missing claim in {feat_name}"

        # If available, all test evidence and code paths must exist on disk
        if feat["status"] == "AVAILABLE":
            if "evidence_test" in feat:
                tests = [t.strip() for t in feat["evidence_test"].split(",")]
                for t_path in tests:
                    assert Path(t_path).exists(), f"Evidence test '{t_path}' for '{feat_name}' not found on disk"

            if "code_path" in feat:
                code_paths = [c.strip() for c in feat["code_path"].split(",")]
                for c_path in code_paths:
                    assert Path(c_path).exists(), f"Code path '{c_path}' for '{feat_name}' not found on disk"

        elif feat["status"] == "EXPERIMENTAL":
            assert "qualification_note" in feat, f"Experimental feature '{feat_name}' must have a qualification_note"

    # Specific checks for Dual-Mode and Proof Strip
    assert "dual_mode_agent_builder_and_cross_repo_runtime" in features
    assert "unified_proof_strip_ux" in features
    assert features["tier2_hardware_security_hal"]["status"] == "EXPERIMENTAL"


def test_website_html_references_valid_assets():
    html_file = Path("website/index.html")
    assert html_file.exists(), "website/index.html must exist"
    content = html_file.read_text(encoding="utf-8")

    assert "styles.css" in content
    assert "product-facts.json" in content
    assert "docs.html" in content
    assert "api.html" in content
    assert "brand.html" in content

    # Assert SEO & documentation files exist
    docs_file = Path("website/docs.html")
    assert docs_file.exists(), "website/docs.html must exist"
    docs_content = docs_file.read_text(encoding="utf-8")
    assert "Keelway Architecture" in docs_content
    assert "Dual-Mode Sovereign Architecture" in docs_content
    assert "Unified 6-Stage Proof Strip UX" in docs_content
    assert "kstack" in docs_content
    assert "kbrain" in docs_content

    robots_file = Path("website/robots.txt")
    assert robots_file.exists(), "website/robots.txt must exist"
    assert "sitemap.xml" in robots_file.read_text(encoding="utf-8")

    sitemap_file = Path("website/sitemap.xml")
    assert sitemap_file.exists(), "website/sitemap.xml must exist"
    assert "https://kora-sable.vercel.app/" in sitemap_file.read_text(encoding="utf-8")


def test_website_pages_load_no_third_party_fonts_or_styles():
    for page in Path("website").glob("*.html"):
        html = page.read_text(encoding="utf-8")
        for host in ("fonts.googleapis.com", "fonts.gstatic.com", "cdn.tailwindcss.com", "cdnjs.cloudflare.com"):
            assert host not in html, f"{page} loads {host}; serve it from website/ instead"
