# TASK: KEEL-SEC-002 — Linux Command Sandbox Bubblewrap CI Hardening

## 1. METADATA
- **TASK ID**: KEEL-SEC-002
- **CATEGORY**: SECURITY
- **CREATOR**: Engineering Architecture Team
- **ASSIGNED AGENT**: Google Antigravity (Sandbox & CI Security Lead)
- **STATUS**: READY_FOR_REVIEW
- **TARGET BRANCH**: `feature/KEEL-SEC-002-bwrap-ci` (currently on `main` working tree per parallel agent session)
- **BASE COMMIT**: `5b2fbc3`

---

## 2. OBJECTIVE & MOTIVATION
Harden Keelway's Linux command execution confinement backend (`BubblewrapBackend` in `core/agents/sandbox.py`) and GitHub Actions Ubuntu 24.04 (`ubuntu-latest`) CI pipeline so agent shell execution is verifiably isolated across both macOS (`sandbox-exec` Seatbelt) and Linux (`bwrap` Bubblewrap), fails closed when unverified, and surfaces deterministic root-cause diagnostics when kernel AppArmor or user-namespace policies block `bwrap`.

---

## 3. ACCEPTANCE CRITERIA
- [x] **Criterion 1**: `BubblewrapBackend.wrap(...)` enforces deterministic Ubuntu 24.04 mount-tree ordering (`--ro-bind / /` -> `--dev /dev` -> `--proc /proc` -> `--tmpfs /tmp` -> `--tmpfs` on hidden user roots -> `--dir` before child `--ro-bind`/`--bind` inside masked tmpfs roots -> protected `.git` read-only bind and `.keelway`/`.kora` read-only tmpfs masks -> non-recursive `--remount-ro` on hidden roots -> `--chdir` -> `--unshare-net --unshare-pid --unshare-ipc --unshare-uts --die-with-parent --new-session` -> `--clearenv` + `--setenv` -> `--` + `argv`).
- [x] **Criterion 2**: `BubblewrapBackend.wrap(...)` validates all sandbox paths against ASCII control characters (`NUL`, `\n`, `\r`, `\t`, `DEL`) and rejects unsafe environment keys/values with `ValueError`; broken symlinks, missing `read_roots`, and `HOME=/root` never crash `wrap()` or mask `/`.
- [x] **Criterion 3**: `_default_read_roots()` never adds `$HOME` itself or `/` to `read_roots`, preventing accidental unmasking of host home directories.
- [x] **Criterion 4**: `BubblewrapBackend.diagnostic_reason()` and `Sandbox.diagnose()` inspect `sys.platform`, `shutil.which("bwrap")`, `/proc/sys/kernel/apparmor_restrict_unprivileged_userns`, `/proc/sys/kernel/unprivileged_userns_clone`, `/proc/sys/user/max_user_namespaces`, and `bwrap` probe `stderr`.
- [x] **Criterion 5**: Cross-platform unit tests, simulated Ubuntu mount-order & leak-detection tests, `@needs_any_os_sandbox` live tests, and `@needs_bubblewrap` (`@pytest.mark.live_bubblewrap`) live confinement proofs added to `tests/test_agent_sandbox.py` while keeping all 13 `@pytest.mark.live_seatbelt` proofs 100% intact for `tests/release_live_gate.py`.
- [x] **Criterion 6**: `.github/workflows/ci.yml` runs an explicit fail-closed `Verify Linux Bubblewrap Sandbox Confinement` step executing `Sandbox.require_verified()` (`backend_name == 'bubblewrap'`) and `pytest tests/test_agent_sandbox.py -v`.
- [x] **Criterion 7**: Zero security or privacy regressions; fail-closed invariants preserved.

---

## 4. AFFECTED FILES & COMPONENTS
- Primary Files:
  - `core/agents/sandbox.py`: Hardened `BubblewrapBackend` (`wrap`, `available`, `diagnostic_reason`, `_hidden_roots`, `_probe_command`), added `_bwrap_path` control-character path validation, normalized `bwrap: execvp` missing-command exit code (`127`), hardened `_default_read_roots()`, and added `Sandbox.diagnose()`.
  - `.github/workflows/ci.yml`: Added fail-closed `Verify Linux Bubblewrap Sandbox Confinement` CI gate step and userns sysctl setup on `ubuntu-latest`.
- Test Files:
  - `tests/test_agent_sandbox.py`: Preserved all 13 `live_seatbelt` proofs; added deterministic `BubblewrapBackend` mount-ordering, root-home safety, control-char rejection, diagnostic simulation, `BubblewrapBackend` leak self-test rejection, `@needs_any_os_sandbox` cross-platform live suite, and `@needs_bubblewrap` (`@pytest.mark.live_bubblewrap`) live confinement suite.
- Documentation:
  - `docs/agent-operations/tasks/KEEL-SEC-002.md`: Task specification, security audit notes, and cross-agent handoff record.

---

## 5. SECURITY & PRIVACY CONSIDERATIONS
- **Privacy Fail-Closed Verification**: Yes — `Sandbox.verify()` and `Sandbox.require_verified()` refuse execution (`SandboxUnavailable`) whenever `bwrap` or `sandbox-exec` is absent or fails any of the 7 live escape probes (outside-workspace read/write, loopback TCP connect, `.git` write, `.keelway` read/write).
- **Credential Handling / Secret Redaction**: Yes — `scrubbed_env()` strips parent API keys/tokens/cloud credentials, and `BubblewrapBackend.wrap(..., env=env)` passes `--clearenv` plus explicit `--setenv` pairs so child processes inherit only the allowlisted environment.
- **Autonomy Tier Level**: Tier 2 Governed (local workspace test execution and sandbox hardening; no external network egress or git push).

---

## 6. VALIDATION & TEST PLAN
```bash
cd keelway
PYTHONPATH=. /Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/kora-ai.nosync/.venv/bin/pytest tests/test_agent_sandbox.py -v
python3 -m py_compile core/agents/sandbox.py tests/test_agent_sandbox.py
```

---

## 7. EXECUTION LOG & AGENT HANDOFF HISTORY

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-SEC-002
- **TASK TITLE**: Linux Command Sandbox Bubblewrap CI Hardening
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Antigravity
- **DATE**: 2026-11-13
- **BRANCH**: `main` (target branch `feature/KEEL-SEC-002-bwrap-ci`)
- **HEAD COMMIT**: `5b2fbc3` (with scoped working-tree modifications)

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Harden `BubblewrapBackend.wrap()` mount-tree ordering (`--tmpfs` -> `--dir` -> `--ro-bind`/`--bind` -> `.git`/`.keelway`/`.kora` masks -> `--remount-ro` on hidden parents) and `--clearenv`/`--setenv` isolation (`core/agents/sandbox.py`)
- [x] Validate sandbox paths against control characters (`_bwrap_path`) and harden `_default_read_roots()` (`core/agents/sandbox.py`)
- [x] Implement `BubblewrapBackend.diagnostic_reason()` and `Sandbox.diagnose()` inspecting AppArmor & userns sysctls (`core/agents/sandbox.py`)
- [x] Expand unit, cross-platform (`@needs_any_os_sandbox`), and Linux live (`@pytest.mark.live_bubblewrap`) tests while preserving all 13 `@pytest.mark.live_seatbelt` tests (`tests/test_agent_sandbox.py`)
- [x] Add fail-closed `Verify Linux Bubblewrap Sandbox Confinement` step in GitHub Actions (`/.github/workflows/ci.yml`)

#### WORK COMPLETED & FILES MODIFIED
- `core/agents/sandbox.py`: Hardened `BubblewrapBackend` mount ordering, `--dir` creation under masked tmpfs parents without touching read-only bind ancestors, `.git`/`.keelway`/`.kora` directory & file protection, `--clearenv` + `--setenv`, control-character path validation, `execvp` exit-code `127` normalization, `BubblewrapBackend.diagnostic_reason()`, and `Sandbox.diagnose()`.
- `tests/test_agent_sandbox.py`: Added 11 new test executions (deterministic Ubuntu mount-order assertions, `HOME=/root` guard, parametrized control-character path rejection, AppArmor/userns diagnostic tests, simulated `BubblewrapBackend` leak detection, cross-platform live confinement suite, and `@pytest.mark.live_bubblewrap` live confinement suite) with zero changes to existing `live_seatbelt` node IDs.
- `.github/workflows/ci.yml`: Added `Verify Linux Bubblewrap Sandbox Confinement` step enforcing `sb.backend_name == 'bubblewrap'` and `sb.require_verified()` plus `pytest tests/test_agent_sandbox.py -v` on `ubuntu-latest`.
- `docs/agent-operations/tasks/KEEL-SEC-002.md`: Authored complete task specification, security review, and handoff record.

#### TESTS EXECUTED & EVIDENCE
- `PYTHONPATH=. /Users/justinmafie/Documents/antigravity/mysterious-brahmagupta/kora-ai.nosync/.venv/bin/pytest tests/test_agent_sandbox.py -v`: `36 passed, 2 skipped in 10.74s` (the 2 skips on macOS are the Linux-only `@pytest.mark.live_bubblewrap` tests, which execute live on `ubuntu-latest` CI).
- `python3 -m py_compile core/agents/sandbox.py tests/test_agent_sandbox.py`: `exit code 0`.

#### KNOWN RISKS & BLOCKERS
- Local verification ran on macOS (`darwin`), exercising live `SeatbeltBackend` confinement plus deterministic `BubblewrapBackend` command-line, diagnostic, and leak-detection unit tests; live `bwrap` kernel execution is gated fail-closed on `ubuntu-latest` in `.github/workflows/ci.yml`.

#### NEXT RECOMMENDED ACTION
- Lead Coordinator: update `docs/agent-operations/ACTIVE_TASKS.md` to mark `KEEL-SEC-002` as `READY_FOR_REVIEW` / `VERIFIED_COMPLETE`, run `./scripts/verify_engineering_gates.sh`, and push branch to trigger the hardened `Verify Linux Bubblewrap Sandbox Confinement` job on `ubuntu-latest`.
