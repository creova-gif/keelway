# Keelway — Testing Strategy & Execution Guidelines

> **Standard**: Production-Grade Verification for Hybrid AI and Autonomous Systems  
> **Test Framework**: `pytest` 7.4+ / 9.2+, `pytest-asyncio` / `anyio`, `httpx`

---

## 1. Testing Pyramid & Taxonomy

```
                [ E2E / Journey Tests ]       --> Studio, mobile approvals, CLI flow
              [ Security / Invariant Tests ]  --> Air-gap fail-closed, tape redaction
            [ Provider Contract Tests ]       --> SSE streaming, error normalization
          [ Subsystem Integration Tests ]     --> Gateway routing, KFlow DAG, KHub
        [ Unit / Component Tests ]            --> Registry, pricing, schemas, utils
```

### 1.1 Unit Tests (`tests/test_*.py`)
- Test isolated classes and functions with zero external dependencies.
- Sub-second execution time.
- Examples: `test_hybrid_model_registry.py`, `test_state_machine.py`.

### 1.2 Provider Contract Tests (`tests/test_hybrid_adapters.py`)
- Exercise `BaseModelProviderAdapter` implementations using in-memory mock HTTP handlers (`httpx.MockTransport`).
- Verify exact serialization of OpenAI and Ollama formats.
- Assert chunk-by-chunk delivery of SSE streams and error code translation.
- **Golden Rule**: Never treat a mock transport test as proof that a live external cloud provider is working or configured with valid credentials.

### 1.3 Security & Governance Invariant Tests (`tests/test_package_*.py`, `tests/test_redact.py`)
- Specifically target adversarial conditions:
  - Inject private payloads and verify cloud calls are blocked with `AirGapViolationError`.
  - Pass raw API keys into commands and assert they are stripped before tape persistence.
  - Attempt path traversal in sandboxed worktrees.

### 1.4 Live Verification (`verify_live_keys.py`, `tests.release_live_gate`)
- Real network connections with live credentials. Run only in release verification environments; skipped in offline CI.

---

## 2. Asynchronous Test Conventions

Keelway's `pytest.ini` configures:
```ini
[pytest]
testpaths = tests
pythonpath = .
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```

When authoring async tests:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from core.main import app

@pytest.mark.asyncio
async def test_endpoint_async():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/models")
        assert resp.status_code == 200
```

---

## 3. UI, Mobile & Design Token Testing

- Frontend components (`website/`, `web-console/`, `mobile/`) must align with approved Figma tokens:
  - **Typography**: Archivo (Display), Instrument Sans (Body), Martian Mono (Code).
  - **Color Palette**: Void Black (`#0a0b0d`), Graphite Surface (`#14171c`), Border Subtle (`#222731`), Keelway Teal Accent (`#14b8a6`).
- Test responsiveness across mobile (375px), tablet (768px), and desktop (1280px+).
- Verify keyboard focus states, WCAG 2.1 AA color contrast, and RTL layout support.

---

## 4. Test Execution Cheatsheet

```bash
# Fast test run for active development
pytest tests/test_hybrid_routing_and_api.py -v

# Run all hybrid AI tests
pytest tests/test_hybrid_model_registry.py tests/test_hybrid_adapters.py tests/test_hybrid_routing_and_api.py -v

# Run full test suite with coverage
pytest --cov=core tests/
```
