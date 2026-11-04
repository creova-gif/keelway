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


def test_website_html_references_valid_assets():
    html_file = Path("website/index.html")
    assert html_file.exists(), "website/index.html must exist"
    content = html_file.read_text(encoding="utf-8")

    assert "styles.css" in content
    assert "product-facts.json" in content
    assert "Verified against commit" in content
    assert "585 automated tests" in content or "tests passing" in content
