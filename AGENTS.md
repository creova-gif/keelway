# Agent instructions for Keelway

These apply to every coding agent working in this repo (Claude Code, Cursor,
Codex, Devin and others).

## gstack (required)

This repo uses [gstack](https://github.com/garrytan/gstack) for AI-assisted work.
The install check, and what to do when gstack is missing, are in the
`## gstack` section of [CLAUDE.md](CLAUDE.md). Follow it on every host.

Install it once per machine for the agent you use (needs Git and Bun 1.3.3+):

```bash
git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack && ./setup --team               # Claude Code
cd ~/.claude/skills/gstack && ./setup --host cursor        # Cursor
cd ~/.claude/skills/gstack && ./setup --host codex         # Codex CLI
cd ~/.claude/skills/gstack && ./setup --host auto          # every agent found on this machine
```

Claude Code uses the skills as `/office-hours`, `/review`, `/qa`, `/cso` and
`/ship`. Other hosts name them `gstack-<skill>`, e.g. ask for `gstack-review`.
Agents that read rules but can't install skills follow
`~/.claude/skills/gstack/agents-digest/gstack-AGENTS.md`.

## Repo checks

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
ruff check .
pytest -q
```

If you change classes in `core/studio/index.html` or `core/studio/assets/studio.js`,
rebuild the generated stylesheet and verify freshness:

```bash
make studio-css        # regenerate core/studio/assets/studio.css (committed)
make studio-css-check  # fails if the committed css is stale
```
