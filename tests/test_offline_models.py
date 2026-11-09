"""Offline model bundles: export from an Ollama model store, verify, and install through Ollama's API."""

import hashlib
import json

import httpx
import pytest

from core.models.offline_bundle import (
    BUNDLE_MANIFEST, OfflineModelError, export_bundle, import_bundle, split_model_name,
)

WEIGHTS = b"GGUF" + bytes(range(256)) * 64


def _digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _store(tmp_path, layers_extra=()):
    models = tmp_path / "ollama"
    (models / "blobs").mkdir(parents=True)
    blobs = {"model": WEIGHTS, "template": b"{{ .Prompt }}", "system": b"Be brief.", "params": b'{"stop": ["<|im_end|>"]}'}
    layers = []
    for kind, data in blobs.items():
        (models / "blobs" / _digest(data).replace(":", "-")).write_bytes(data)
        layers.append({"mediaType": f"application/vnd.ollama.image.{kind}", "digest": _digest(data), "size": len(data)})
    layers += list(layers_extra)
    manifest = models / "manifests" / "registry.ollama.ai" / "library" / "tiny" / "1b"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"layers": layers}))
    return models


class FakeOllama:
    def __init__(self):
        self.blobs, self.created = {}, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.startswith("/api/blobs/"):
            digest = path.rsplit("/", 1)[1]
            if request.method == "HEAD":
                return httpx.Response(200 if digest in self.blobs else 404)
            body = request.read()
            if _digest(body) != digest:
                return httpx.Response(400, text="digest mismatch")
            self.blobs[digest] = body
            return httpx.Response(201)
        if path == "/api/create":
            self.created.append(json.loads(request.content))
            return httpx.Response(200, json={"status": "success"})
        return httpx.Response(404)


def _client(fake):
    return httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(fake))


def test_export_then_import_round_trip(tmp_path):
    bundle = export_bundle("tiny:1b", tmp_path / "usb", models_dirs=[_store(tmp_path)])
    info = json.loads((bundle / BUNDLE_MANIFEST).read_text())
    assert (bundle / "model.gguf").read_bytes() == WEIGHTS
    assert info["sha256"] == hashlib.sha256(WEIGHTS).hexdigest() and info["size"] == len(WEIGHTS)
    assert info["template"] == "{{ .Prompt }}" and info["system"] == "Be brief."
    assert info["parameters"] == {"stop": ["<|im_end|>"]}

    fake = FakeOllama()
    res = import_bundle(bundle, client=_client(fake))
    assert res.model == "tiny:1b" and res.uploaded
    assert fake.created == [{
        "model": "tiny:1b", "files": {"model.gguf": _digest(WEIGHTS)}, "stream": False,
        "template": "{{ .Prompt }}", "system": "Be brief.", "parameters": {"stop": ["<|im_end|>"]},
    }]
    again = import_bundle(bundle, name="tiny-copy:1b", client=_client(fake))
    assert not again.uploaded and fake.created[-1]["model"] == "tiny-copy:1b"


def test_damaged_bundle_is_refused_before_ollama_sees_it(tmp_path):
    bundle = export_bundle("tiny:1b", tmp_path / "usb", models_dirs=[_store(tmp_path)])
    data = bytearray(WEIGHTS)
    data[100] ^= 1
    (bundle / "model.gguf").write_bytes(bytes(data))
    fake = FakeOllama()
    with pytest.raises(OfflineModelError, match="SHA-256"):
        import_bundle(bundle, client=_client(fake))
    (bundle / "model.gguf").write_bytes(WEIGHTS[:-1])
    with pytest.raises(OfflineModelError, match="incomplete"):
        import_bundle(bundle, client=_client(fake))
    assert fake.blobs == {} and fake.created == []


def test_plain_gguf_imports_under_its_file_name(tmp_path):
    gguf = tmp_path / "my-model.gguf"
    gguf.write_bytes(WEIGHTS)
    fake = FakeOllama()
    res = import_bundle(gguf, client=_client(fake))
    assert res.model == "my-model"
    assert fake.created[0]["files"] == {"my-model.gguf": _digest(WEIGHTS)}


def test_missing_model_and_unsupported_layers(tmp_path):
    store = _store(tmp_path, [{"mediaType": "application/vnd.ollama.image.projector", "digest": _digest(b"p"), "size": 1}])
    with pytest.raises(OfflineModelError, match="projector"):
        export_bundle("tiny:1b", tmp_path / "usb", models_dirs=[store])
    with pytest.raises(OfflineModelError, match="not installed"):
        export_bundle("other:7b", tmp_path / "usb", models_dirs=[store])


def test_bundle_cannot_point_outside_its_folder(tmp_path):
    bundle = export_bundle("tiny:1b", tmp_path / "usb", models_dirs=[_store(tmp_path)])
    info = json.loads((bundle / BUNDLE_MANIFEST).read_text())
    (tmp_path / "secret.gguf").write_bytes(WEIGHTS)
    info["file"] = "../secret.gguf"
    (bundle / BUNDLE_MANIFEST).write_text(json.dumps(info))
    with pytest.raises(OfflineModelError, match="missing its weights"):
        import_bundle(bundle, client=_client(FakeOllama()))


@pytest.mark.parametrize("bad", ["../x:1b", "a/../../b", "tiny:../../etc"])
def test_model_names_cannot_escape_the_store(bad):
    with pytest.raises(OfflineModelError):
        split_model_name(bad)


def test_ollama_down_is_a_clear_error(tmp_path):
    gguf = tmp_path / "m.gguf"
    gguf.write_bytes(WEIGHTS)

    def down(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(OfflineModelError, match="ollama serve"):
        import_bundle(gguf, client=httpx.Client(base_url="http://x", transport=httpx.MockTransport(down)))
