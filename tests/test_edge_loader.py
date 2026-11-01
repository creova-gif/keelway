"""
Standard library unit tests for Keelway Hybrid Edge Model Runtime & Auto-Quantization Loader.
"""

import tempfile
import unittest
from pathlib import Path
from core.models.edge_loader import EdgeRuntimeManager, EdgeRuntimeType


class TestEdgeRuntimeManager(unittest.TestCase):
    def test_hardware_detection(self):
        manager = EdgeRuntimeManager()
        profile = manager.hardware
        self.assertIsNotNone(profile.arch)
        self.assertGreater(profile.estimated_ram_gb, 0)
        self.assertIn("qwen", profile.recommended_model)
        self.assertEqual(profile.quantization, "Q4_K_M")

    def test_embedded_gguf_resolution_when_ollama_absent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir)
            # Point to invalid port so Ollama probe returns False
            manager = EdgeRuntimeManager(ollama_url="http://127.0.0.1:59999", cache_dir=cache_path)
            res = manager.resolve_runtime()

            self.assertEqual(res["runtime"], EdgeRuntimeType.EMBEDDED_GGUF)
            self.assertTrue(res["zero_daemon"])
            self.assertIn("qwen2.5-coder", res["model_path"])
            self.assertTrue(res["download_url"].startswith("https://huggingface.co/"))


if __name__ == "__main__":
    unittest.main()
