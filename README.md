<div align="center">

# Keelway by Sorvex Labs

Local developer tree for the Keelway studio, the governance server, and the static marketing site.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![CI](https://github.com/creova-gif/kora/actions/workflows/ci.yml/badge.svg)](https://github.com/creova-gif/kora/actions/workflows/ci.yml)

The repository on GitHub is [creova-gif/kora](https://github.com/creova-gif/kora). A clone creates a directory named `kora`.

</div>

## What this document is

These instructions match the commands in this tree. They do not quote a test pass count, and they do not certify a published install or a hosted product.

Package B owns runtime labels in the studio, evidence room, mesh, and chat. Package C owns fail-closed authentication, command isolation, and default-config behavior. Those checkpoints were not available when this text was written. This page does not describe that intended behavior as something the tree already does. Recheck the commands below if those packages change runtime behavior.

## Three different things

| Surface | What it is | How you start it |
|---|---|---|
| Local Studio | Web IDE from `core/studio`, served by `core.main:app` | `python3 cli.py dev` or `python3 cli.py desktop` |
| Governance server | Dashboard and API in `keelway/api/app.py` | `make serve` or `keelway-core serve` |
| Static marketing site | Files in `website/` | Open the files, or the host that publishes that directory |

`vercel.json` sets `outputDirectory` to `website` and leaves the install and build commands empty. The static site does not start Studio or the governance server.

The container `ENTRYPOINT` is `python -m keelway.cli.main serve`. The image copies the `keelway/` package. It does not copy `cli.py` or `core/studio`.

## Install from this repository

There is no install step in this document that uses a PyPI distribution named `keelway`. `keelway.dev` and `get.keelway.dev` are not install hosts here.

From the clone:

```bash
git clone https://github.com/creova-gif/kora.git
cd kora
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`pyproject.toml` registers two console scripts after that editable install:

- `keelway` → `cli:main` (the developer CLI in `cli.py`)
- `keelway-core` → `keelway.cli.main:main` (the governance CLI)

Without the editable install, run the modules from the repository root. `./bin/keelway` is a wrapper that executes `cli.py` with `PYTHONPATH` set to the repo. It is the developer CLI.

`website/install.sh` (the same steps as `bin/install.sh`) clones `https://github.com/creova-gif/kora.git` into `~/.keelway/app` by default, creates a virtualenv there, and runs `pip install -e` on that checkout. Run it from a clone if you want that layout. Its header is not a `curl` URL.

Python 3.11 or newer is the declared requirement. The `[dev]` extra installs pytest and ruff. If `python3 -m venv` cannot create an environment on your machine, install those dependencies onto the interpreter you use to run `cli.py`. A missing virtualenv does not add a PyPI package named `keelway`.

## Local Studio

Studio listens on `127.0.0.1` port `7420` unless you pass `--host` or `--port`.

```bash
python3 cli.py dev
python3 cli.py desktop
```

`python3 cli.py dev` starts Uvicorn on `core.main:app` and opens a browser. `python3 cli.py desktop` and `python3 cli.py dev --desktop` call the same server and then look for macOS Google Chrome or a `google-chrome`, `chromium`, or `msedge` binary and pass `--app=<url>`. Otherwise they open a normal browser. There is no Electron or Tauri app in this tree.

`make studio` runs `python3 cli.py dev`. `make desktop` runs `python3 cli.py desktop`.

When `AUTH_REQUIRED` is on, `cli.py dev` prints a launch token in the Studio URL. This README does not change that behavior and does not tell you to turn authentication off.

In this tree, `AutonomousAgentLoop.formulate_plan` chooses a fixed step list from keywords in the goal. That path is not a model-written plan. Chat and evidence-room labeling belong to package B and are not certified here.

## Governance server

```bash
make serve
```

That target runs:

```bash
python3 -m keelway.cli.main serve --host 127.0.0.1 --port 8000
```

After `pip install -e ".[dev]"`, the same command is `keelway-core serve`. The developer script `keelway` has no `serve` subcommand. Both parsers set `prog="keelway"`, so `python3 -m keelway.cli.main --help` prints `usage: keelway`. That label is the help text. The console script for the governance module is `keelway-core`. `python3 cli.py serve` is rejected. `cli.py` also has its own `run` subcommand, which is separate from `keelway-core run`.

The governance CLI's other subcommands are `run`, `verify`, `export`, `status`, `init-demo`, and `runner`. See `python3 -m keelway.cli.main --help`. The default provider on `keelway.models.gateway.ModelGateway` in this tree is `ProviderKind.DETERMINISTIC_MOCK` unless the caller passes another provider. A governed `run` is a separate process from Studio, and this README does not call it a live model agent.

## Static site

`website/index.html`, `website/docs.html`, and `website/api.html` are the marketing and reference pages. `website/product-facts.json` is copy checked into that site. It is not a test report. The in-browser synthesizer and terminal panels do not call `cli.py`.

## Local smoke for templates

From the repository root, with dependencies importable:

```bash
python3 cli.py build templates
```

That subcommand prints guided-builder archetype names from `core/orchestration/guided_builder.py` and exits. It does not call a model and it does not need network access to list templates. Generating a tree is a different subcommand: `python3 cli.py build app "<intent>" --template fastapi-service`. The page text `keelway build --intent ... --template ...` does not match this parser. Intent is a positional argument of `build plan` or `build app`.

## Tests

```bash
make test
```

`make test` runs `PYTHONPATH=. python3 -m pytest tests -q`. This README does not state how many tests pass. Use the command output, or the GitHub Actions workflow linked above, as the record for a specific commit. `make help` does not print a pass count.

## Other developer commands

`python3 cli.py --help` lists the developer subcommands, including `doctor`, `bench`, `build`, `mcp`, and `token`. `make help` lists Makefile targets. Those help texts name the targets. They are not a test report and they are not a hardware certificate.

Tier 2 modules live under `keelway/hal/`. `make tier2-status` and `make tier2-verify` run `cli.py tier2`. They are in-repo commands. This README does not certify field hardware.

## Modules named in this tree

The following names are modules and tests that exist as files. Listing them does not certify a security review, a production deployment, or fail-closed authentication.

| Topic | Modules | Tests present in the tree |
|---|---|---|
| Workspace clone helper | `keelway/sandbox/workspace.py` | `tests/test_end_to_end_workflow.py` |
| Policy engine | `keelway/policy/engine.py` | `tests/test_policy_engine.py` |
| Policy bundles | `keelway/policy/bundle.py` | `tests/test_policy_bundle.py` |
| Approvals | `keelway/approvals/service.py` | `tests/test_approvals.py` |
| Quorum | `keelway/approvals/quorum.py` | `tests/test_quorum.py` |
| Hash-chained audit | `keelway/audit/recorder.py` | `tests/test_audit_chain.py` |
| SQLite audit store | `keelway/audit/store.py` | `tests/test_audit_store.py` |
| Audit export | `keelway/audit/export.py` | `tests/test_audit_export.py` |
| Runner daemon | `keelway/runner/daemon.py` | `tests/test_runner_daemon.py` |
| Quarantine helper | `keelway/security/quarantine.py` | `tests/test_quarantine.py` |
| Retry helper | `keelway/core/retry.py` | `tests/test_retry.py` |
| Governance model gateway | `keelway/models/gateway.py` | `tests/test_model_gateway.py` |

## Layout

```text
kora/                         # clone of creova-gif/kora
├── cli.py                    # developer CLI (Studio, build, and the other cli.py commands)
├── bin/keelway               # wrapper around cli.py
├── Makefile                  # local targets; see `make help`
├── pyproject.toml            # package name keelway; scripts keelway and keelway-core
├── core/                     # Studio API, studio assets, orchestration
│   └── studio/               # local Studio UI
├── keelway/                  # governance package, including `keelway/api` and `keelway/cli`
├── website/                  # static marketing site
├── docs/                     # design notes and docs/DEVELOPER_QUICKSTART.md
├── examples/
└── tests/
```

`Dockerfile` and `docker-compose.yml` are present. This document does not claim a successful image run. `make docker-up` is `docker compose up -d`.
