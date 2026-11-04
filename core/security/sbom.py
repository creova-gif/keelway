"""
Keelway Software Bill of Materials (SBOM) & Supply Chain Provenance (WP17).
Generates and cryptographically verifies CycloneDX-compatible SBOM manifests with SHA-256 component digests.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_PROVENANCE_KEY = b"KEELWAY_SUPPLY_CHAIN_PROVENANCE_KEY_2026"


@dataclass
class ComponentProvenance:
    name: str
    version: str
    component_type: str  # "library" | "application" | "file" | "data"
    purl: str
    sha256: str
    supplier: str = "Sorvex Labs"


@dataclass
class SBOMManifest:
    serial_number: str
    version: int
    bom_format: str
    spec_version: str
    timestamp_utc: str
    metadata: Dict[str, Any]
    components: List[Dict[str, Any]]
    root_digest_sha256: str
    provenance_signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SBOMGenerator:
    """Generates verifiable Software Bill of Materials for Keelway deployments."""

    @classmethod
    def generate(
        cls,
        repo_root: Optional[Path] = None,
        signing_key: bytes = DEFAULT_PROVENANCE_KEY,
    ) -> SBOMManifest:
        root = Path(repo_root or ".").resolve()
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        components: List[ComponentProvenance] = []

        # 1. Parse Python requirements
        req_file = root / "requirements.txt"
        if req_file.exists():
            for line in req_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("==") if "==" in line else line.split(">=")
                name = parts[0].strip()
                version = parts[1].strip() if len(parts) > 1 else "latest"
                pkg_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()
                components.append(ComponentProvenance(
                    name=name,
                    version=version,
                    component_type="library",
                    purl=f"pkg:pypi/{name}@{version}",
                    sha256=pkg_hash,
                ))

        # 2. Add Core Keelway Modules
        for pkg_name in ["keelway", "core", "keelway_core"]:
            pkg_dir = root / pkg_name
            if pkg_dir.is_dir():
                file_hashes = []
                for p in sorted(pkg_dir.rglob("*.py")):
                    if "__pycache__" in str(p):
                        continue
                    file_hashes.append(hashlib.sha256(p.read_bytes()).hexdigest())
                combined_hash = hashlib.sha256("".join(file_hashes).encode("utf-8")).hexdigest() if file_hashes else "0" * 64
                components.append(ComponentProvenance(
                    name=f"keelway/{pkg_name}",
                    version="0.1.0",
                    component_type="application",
                    purl=f"pkg:keelway/{pkg_name}@0.1.0",
                    sha256=combined_hash,
                ))

        # 3. Calculate root Merkle digest of components
        comp_dicts = [asdict(c) for c in components]
        canonical_comps = json.dumps(comp_dicts, sort_keys=True, separators=(",", ":")).encode("utf-8")
        root_digest = hashlib.sha256(canonical_comps).hexdigest()

        # 4. Sign provenance manifest
        sig = hmac.new(signing_key, f"{root_digest}:{now_iso}".encode("utf-8"), hashlib.sha256).hexdigest()

        serial = f"urn:uuid:{hashlib.md5(f'{root_digest}:{now_iso}'.encode()).hexdigest()}"

        return SBOMManifest(
            serial_number=serial,
            version=1,
            bom_format="CycloneDX",
            spec_version="1.5",
            timestamp_utc=now_iso,
            metadata={
                "tool": "Keelway Supply Chain Provenance Builder",
                "organization": "Sorvex Labs",
                "product": "Keelway",
                "license": "Apache-2.0 / Commercial",
            },
            components=comp_dicts,
            root_digest_sha256=root_digest,
            provenance_signature=sig,
        )


class SBOMVerifier:
    """Cryptographically verifies SBOM manifests and provenance signatures."""

    @classmethod
    def verify(
        cls,
        sbom_data: Dict[str, Any],
        signing_key: bytes = DEFAULT_PROVENANCE_KEY,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        components = sbom_data.get("components", [])
        claimed_root = sbom_data.get("root_digest_sha256", "")
        claimed_sig = sbom_data.get("provenance_signature", "")
        timestamp = sbom_data.get("timestamp_utc", "")

        # 1. Recalculate root digest
        canonical_comps = json.dumps(components, sort_keys=True, separators=(",", ":")).encode("utf-8")
        calc_root = hashlib.sha256(canonical_comps).hexdigest()

        if calc_root != claimed_root:
            return False, "ROOT_DIGEST_MISMATCH", {"calculated": calc_root, "claimed": claimed_root}

        # 2. Verify signature
        expected_sig = hmac.new(signing_key, f"{claimed_root}:{timestamp}".encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, claimed_sig):
            return False, "INVALID_PROVENANCE_SIGNATURE", {"calculated": expected_sig, "claimed": claimed_sig}

        return True, "VERIFIED", {
            "components_count": len(components),
            "root_digest": calc_root,
            "bom_format": sbom_data.get("bom_format"),
        }
