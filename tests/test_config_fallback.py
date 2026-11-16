"""Regression tests for the no-pydantic fallback shim in core/config.py.

KEEL-ENG-036: the fallback Field() previously rejected default_factory=,
crashing `Settings()` (and therefore `cli.py doctor`) in minimal environments.
"""

import builtins
import importlib
import sys


def _import_without_pydantic():
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "dotenv" or name.startswith("pydantic"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    builtins.__import__ = fake_import
    try:
        for mod in list(sys.modules):
            if mod == "core.config" or mod.startswith("pydantic") or mod == "dotenv":
                del sys.modules[mod]
        return importlib.import_module("core.config")
    finally:
        builtins.__import__ = real_import
        # Restore the real module for the rest of the test session.
        for mod in list(sys.modules):
            if mod == "core.config":
                del sys.modules[mod]
        importlib.import_module("core.config")


def test_fallback_field_accepts_default_factory():
    cfg = _import_without_pydantic()
    assert cfg.settings.database_url.startswith("sqlite+aiosqlite:///")
    assert cfg.settings.env == "development"
    assert cfg.settings.port == 8000
    assert cfg.settings.default_local_model == "qwen3.5:latest"
