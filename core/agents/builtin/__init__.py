"""Canonical builtin keelway.agent/v1 lifecycle manifests.

The twelve lifecycle agents surfaced by the platform workspace hub are authored
here as version-controlled manifests. Registration into the SQLite-backed
manifest registry happens via POST /v1/agents/registry; this directory is the
auditable source of truth for what those agents are permitted to do.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

BUILTIN_DIR = Path(__file__).parent


def load_builtin_manifests() -> List[Dict[str, Any]]:
    """Load every builtin lifecycle manifest, sorted by agent name."""
    out = []
    for path in sorted(BUILTIN_DIR.glob("*.agent.json")):
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out
