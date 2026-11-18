# Install Matrix

| Platform | Status | Evidence |
|---|---|---|
| macOS arm64 (this host) | WORKING_E2E | venv + `pip install -e .[dev]`, `pytest -q` 936 pass, `keelway dev` serves Studio on :7420/:7421, live browser verification across sessions |
| Ubuntu x86_64 | UNVERIFIED | CI workflow exists; not executed in this audit |
| Docker | UNVERIFIED | `deploy/` present; image build not executed |
| Windows | NOT SUPPORTED per docs | N/A |

Env config: `env.example` documents 24 vars (provider keys + KEELWAY_*). No default admin credentials found; auth token is generated per-process when AUTH_REQUIRED=true and printed to console only.
