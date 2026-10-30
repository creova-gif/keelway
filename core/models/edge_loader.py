"""
Kora AI Hybrid Edge Model Runtime & Auto-Quantization Loader.
Transparently routes between a local Ollama daemon and embedded 4-bit GGUF weights,
auto-detecting hardware capabilities to run $0.00 local inference on any laptop.
"""

import os
import platform
import shutil
import urllib.request
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional


class EdgeRuntimeType(str, Enum):
    OLLAMA = "ollama"
    EMBEDDED_GGUF = "embedded_gguf"
    CLOUD_FALLBACK = "cloud_fallback"


@dataclass
class HardwareProfile:
    """Hardware capabilities detected on the host system."""
    arch: str
    is_apple_silicon: bool
    estimated_ram_gb: int
    recommended_model: str
    quantization: str


class EdgeRuntimeManager:
    """Manages zero-cloud local edge models with automatic daemon detection and GGUF fallbacks."""

    DEFAULT_MODELS = {
        "budget": "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
        "standard": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        "workstation": "qwen2.5-coder-14b-instruct-q4_k_m.gguf",
    }

    def __init__(self, ollama_url: str = "http://localhost:11434", cache_dir: Optional[Path] = None):
        self.ollama_url = ollama_url
        self.cache_dir = cache_dir or Path.home() / ".kora" / "models"
        self.hardware = self.detect_hardware()

    def detect_hardware(self) -> HardwareProfile:
        """Inspects host architecture and available memory to select the optimal model tier."""
        system_arch = platform.machine().lower()
        is_mac = platform.system().lower() == "darwin"
        is_apple_m = is_mac and ("arm" in system_arch or "aarch64" in system_arch)

        # Estimate RAM
        ram_gb = 16  # standard baseline
        try:
            if is_mac:
                import subprocess
                out = subprocess.check_output(["sysctl", "-n", "hw.memsize"]).decode().strip()
                ram_gb = int(int(out) / (1024 ** 3))
            elif os.path.exists("/proc/meminfo"):
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            ram_gb = int(int(line.split()[1]) / (1024 ** 2))
                            break
        except Exception:
            pass

        # Select model tier based on RAM
        if ram_gb < 8:
            tier = "budget"
            model_tag = "qwen2.5-coder:1.5b"
        elif ram_gb < 24:
            tier = "standard"
            model_tag = "qwen2.5-coder:7b"
        else:
            tier = "workstation"
            model_tag = "qwen2.5-coder:14b"

        return HardwareProfile(
            arch=system_arch,
            is_apple_silicon=is_apple_m,
            estimated_ram_gb=ram_gb,
            recommended_model=model_tag,
            quantization="Q4_K_M"
        )

    def probe_ollama(self, timeout_sec: float = 0.5) -> bool:
        """Checks if a local Ollama daemon is active and responding."""
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", headers={"User-Agent": "KoraAI/Edge"})
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                return resp.status == 200
        except Exception:
            return False

    def resolve_runtime(self) -> Dict[str, Any]:
        """
        Determines the execution runtime:
        1. If Ollama is running on localhost, bind directly.
        2. If Ollama is absent, configure embedded GGUF weights.
        """
        if self.probe_ollama():
            return {
                "runtime": EdgeRuntimeType.OLLAMA,
                "endpoint": self.ollama_url,
                "model": self.hardware.recommended_model,
                "hardware": self.hardware,
                "zero_daemon": False,
            }

        # Embedded GGUF fallback
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tier_key = "standard" if self.hardware.estimated_ram_gb >= 8 else "budget"
        gguf_filename = self.DEFAULT_MODELS.get(tier_key, "qwen2.5-coder-7b-instruct-q4_k_m.gguf")
        model_file = self.cache_dir / gguf_filename

        return {
            "runtime": EdgeRuntimeType.EMBEDDED_GGUF,
            "model_path": str(model_file),
            "model_file_exists": model_file.exists(),
            "hardware": self.hardware,
            "zero_daemon": True,
            "download_url": f"https://huggingface.co/Qwen/{gguf_filename}",
        }
