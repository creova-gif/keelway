"""Move Ollama models between machines without internet: export to a folder (USB stick, LAN share), import from it.

A bundle is a folder holding `model.gguf` and `keelway-model.json`, which records the GGUF's SHA-256 and size plus
the model's template, system prompt, parameters and licence. Import checks the hash before handing the file to the
local Ollama server through its own API (`/api/blobs`, `/api/create`), so it needs no access to Ollama's model store.
A plain `.gguf` file can be imported too.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

import httpx

from core.config import settings

BUNDLE_MANIFEST = "keelway-model.json"
BUNDLE_FORMAT = "keelway-model-bundle/v1"
MODEL_FILE = "model.gguf"
_CHUNK = 1024 * 1024

_LAYER = "application/vnd.ollama.image."
_TEXT_LAYERS = {"template", "system", "license"}
_UNSUPPORTED_LAYERS = {"adapter", "projector"}

Progress = Optional[Callable[[int, int], None]]


class OfflineModelError(RuntimeError):
    pass


@dataclass
class ImportResult:
    model: str
    sha256: str
    size: int
    uploaded: bool  # False when Ollama already had this exact file


def default_models_dirs() -> List[Path]:
    """Where Ollama keeps models: $OLLAMA_MODELS, the user's ~/.ollama, then the Linux service account's."""
    dirs = [Path(os.environ["OLLAMA_MODELS"])] if os.environ.get("OLLAMA_MODELS") else []
    return dirs + [Path.home() / ".ollama" / "models", Path("/usr/share/ollama/.ollama/models")]


def split_model_name(model: str) -> tuple[str, str, str]:
    """`qwen2.5-coder:7b` -> (registry.ollama.ai, library/qwen2.5-coder, 7b)."""
    name, _, tag = model.partition(":")
    parts = name.split("/")
    if len(parts) == 1:
        host, repo = "registry.ollama.ai", f"library/{parts[0]}"
    elif len(parts) == 2:
        host, repo = "registry.ollama.ai", "/".join(parts)
    else:
        host, repo = parts[0], "/".join(parts[1:])
    if not repo or ".." in repo.split("/") or ".." in (tag or "latest"):
        raise OfflineModelError(f"Not a model name: {model!r}")
    return host, repo, tag or "latest"


def _blob_path(models_dir: Path, digest: str) -> Path:
    algo, _, hexdigest = digest.partition(":")
    if algo != "sha256" or len(hexdigest) != 64 or not all(c in "0123456789abcdef" for c in hexdigest):
        raise OfflineModelError(f"Unexpected blob digest in Ollama manifest: {digest!r}")
    return models_dir / "blobs" / f"sha256-{hexdigest}"


def sha256_file(path: Path, progress: Progress = None) -> str:
    total, done, h = path.stat().st_size, 0, hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    return h.hexdigest()


def _find_manifest(model: str, models_dirs: List[Path]) -> tuple[Path, Dict[str, Any]]:
    host, repo, tag = split_model_name(model)
    for models_dir in models_dirs:
        path = models_dir / "manifests" / host / repo / tag
        try:
            return models_dir, json.loads(path.read_text())
        except FileNotFoundError:
            continue
        except PermissionError:
            raise OfflineModelError(
                f"No permission to read {path}. Run as a user who can read Ollama's models, or set OLLAMA_MODELS."
            ) from None
    searched = ", ".join(str(d) for d in models_dirs)
    raise OfflineModelError(f"Model {model!r} is not installed in Ollama (looked in {searched}). Try `ollama list`.")


def export_bundle(model: str, dest: Path, models_dirs: Optional[List[Path]] = None, progress: Progress = None) -> Path:
    """Copy an installed Ollama model into `dest/<model>/` as a bundle. Returns the bundle folder."""
    models_dir, manifest = _find_manifest(model, models_dirs or default_models_dirs())
    info: Dict[str, Any] = {"format": BUNDLE_FORMAT, "model": model, "file": MODEL_FILE}
    weights = None
    for layer in manifest.get("layers", []):
        kind = str(layer.get("mediaType", "")).removeprefix(_LAYER)
        if kind in _UNSUPPORTED_LAYERS:
            raise OfflineModelError(f"{model} has a {kind} layer; bundles only carry single-file GGUF models for now.")
        if kind == "model":
            weights = layer
        elif kind in _TEXT_LAYERS:
            info[kind] = _blob_path(models_dir, layer["digest"]).read_text(encoding="utf-8")
        elif kind == "params":
            info["parameters"] = json.loads(_blob_path(models_dir, layer["digest"]).read_text(encoding="utf-8"))
    if weights is None:
        raise OfflineModelError(f"{model} has no model weights in its Ollama manifest.")

    bundle = dest / model.replace("/", "_").replace(":", "_")
    bundle.mkdir(parents=True, exist_ok=True)
    source = _blob_path(models_dir, weights["digest"])
    target = bundle / MODEL_FILE
    shutil.copyfile(source, target)
    digest = sha256_file(target, progress)
    if f"sha256:{digest}" != weights["digest"]:
        target.unlink()
        raise OfflineModelError(f"Copied weights don't match Ollama's digest {weights['digest']}; nothing exported.")
    info.update(sha256=digest, size=target.stat().st_size)
    (bundle / BUNDLE_MANIFEST).write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    return bundle


def read_bundle(path: Path) -> tuple[Path, Dict[str, Any]]:
    """Return (gguf path, bundle info) for a bundle folder or a plain .gguf file."""
    if path.is_file():
        if path.suffix.lower() != ".gguf":
            raise OfflineModelError(f"{path} is not a .gguf file or a Keelway model bundle folder.")
        return path, {}
    manifest = path / BUNDLE_MANIFEST
    if not manifest.is_file():
        raise OfflineModelError(f"{path} has no {BUNDLE_MANIFEST}; pass a bundle folder from `keelway models export` or a .gguf file.")
    info = json.loads(manifest.read_text(encoding="utf-8"))
    if info.get("format") != BUNDLE_FORMAT:
        raise OfflineModelError(f"Unknown bundle format {info.get('format')!r}.")
    gguf = path / info.get("file", MODEL_FILE)
    if gguf.parent != path or not gguf.is_file():
        raise OfflineModelError(f"Bundle is missing its weights file {info.get('file')!r}.")
    return gguf, info


def _stream(path: Path, progress: Progress) -> Iterator[bytes]:
    total, done = path.stat().st_size, 0
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            done += len(chunk)
            if progress:
                progress(done, total)
            yield chunk


def import_bundle(
    path: Path,
    name: Optional[str] = None,
    ollama_url: Optional[str] = None,
    progress: Progress = None,
    client: Optional[httpx.Client] = None,
) -> ImportResult:
    """Verify a bundle (or .gguf) and install it into the running Ollama under `name`."""
    ollama_url = ollama_url or settings.ollama_base_url
    gguf, info = read_bundle(path)
    model = name or info.get("model") or gguf.stem
    split_model_name(model)
    size = gguf.stat().st_size
    if info and size != info.get("size"):
        raise OfflineModelError(f"{gguf.name} is {size} bytes but the bundle says {info.get('size')}; the copy is incomplete.")
    digest = sha256_file(gguf, progress)
    if info and digest != info.get("sha256"):
        raise OfflineModelError(f"{gguf.name} does not match the bundle's SHA-256; the file is damaged or was changed.")

    http = client or httpx.Client(base_url=ollama_url, timeout=httpx.Timeout(30.0, read=None, write=None))
    try:
        blob = f"/api/blobs/sha256:{digest}"
        try:
            have = http.head(blob).status_code == 200
        except httpx.HTTPError as e:
            raise OfflineModelError(f"Ollama is not reachable at {ollama_url} ({e}). Start it with `ollama serve`.") from None
        if not have:
            resp = http.post(blob, content=_stream(gguf, progress))
            if resp.status_code not in (200, 201):
                raise OfflineModelError(f"Ollama refused the model file: HTTP {resp.status_code} {resp.text[:200]}")
        body: Dict[str, Any] = {"model": model, "files": {gguf.name: f"sha256:{digest}"}, "stream": False}
        for key in ("template", "system", "parameters", "license"):
            if info.get(key):
                body[key] = info[key]
        resp = http.post("/api/create", json=body)
        if resp.status_code != 200:
            raise OfflineModelError(f"Ollama could not create {model}: HTTP {resp.status_code} {resp.text[:200]}")
    finally:
        if client is None:
            http.close()
    return ImportResult(model=model, sha256=digest, size=size, uploaded=not have)
