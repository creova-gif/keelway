# Keelway — AI Agent Capability & Compatibility Matrix

> **Cross-Platform Interoperability Guide**  
> Covers: Google Antigravity, Claude Code, Devin, and gstack

---

## 1. Cross-Platform Feature & Adaptation Matrix

| Capability / Attribute | Google Antigravity | Claude Code | Devin | gstack |
|---|---|---|---|---|
| **Entry Point File** | `GEMINI.md` / `AGENTS.md` | `CLAUDE.md` / `AGENTS.md` | `.devin/config.json` / `AGENTS.md` | `AGENTS.md` / `.agents/skills/` |
| **Tool Execution** | Native CLI tool runner | Terminal shell runner | Native cloud/local VM shell | CLI subprocess execution |
| **Worktree Isolation** | Supported via Git commands | Supported via native worktree / git | Supported via branch isolation | Worktree-aware ship queue |
| **Sandbox Support** | macOS Seatbelt / Linux | Host environment / devcontainer | Sandboxed container VM | Host container / Seatbelt |
| **Structured Skills** | AGY Skills & Native tools | MCP tools & `/slash` commands | Structured playbooks / prompts | Bundled SKILL.md templates |
| **Handoff Mechanism** | Git commit + `docs/agent-operations/` | Git commit + `docs/agent-operations/` | Git commit + `docs/agent-operations/` | `/context-save`, `/context-restore` |
| **Review Capabilities** | Subagent reviews / manual audit | Slash commands (`/review`, `/qa`) | Autonomous self-review & PR | `/office-hours`, `/review`, `/cso` |

---

## 2. Tool-Specific Adaptation Guidelines

### 2.1 Google Antigravity
- **Configuration**: Automatically detects `GEMINI.md` and repository-level `AGENTS.md`.
- **Strengths**: Deep subagent orchestration, tool calling, and structured artifact generation.
- **Rules**: Operate within designated task branch; always run pytest in the active virtualenv.

### 2.2 Claude Code
- **Configuration**: Reads `CLAUDE.md`, which links directly to `AGENTS.md`.
- **Strengths**: Interactive terminal-based agent, fast file searching, gstack integration.
- **Rules**: Always verify `gstack` presence or fallback to repository checklists per `CLAUDE.md`.

### 2.3 Devin
- **Configuration**: Reads `.devin/config.json` and `AGENTS.md`.
- **Strengths**: Autonomous multi-file planning, issue reproduction, and pull request generation.
- **Rules**: Follow explicit acceptance criteria in `docs/agent-operations/tasks/`. Never claim tests pass without terminal evidence.

### 2.4 gstack
- **Configuration**: Uses `.agents/skills/` or `~/.claude/skills/gstack/`.
- **Workflow Pipeline**:
  - `Plan`: `/office-hours` → `/autoplan` → `/plan-eng-review`
  - `Verify`: `/review` → `/qa` → `/cso`
  - `Release`: `/ship` → `/land-and-deploy`
- **Fallback**: If gstack is not installed, all review gates are executed using `docs/engineering/QUALITY_GATES.md` and `scripts/verify_engineering_gates.sh`.
