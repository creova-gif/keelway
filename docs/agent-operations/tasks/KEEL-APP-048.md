# KEEL-APP-048 — Agents View: Live Agent-Manifest Registry Read

- **STATUS**: VERIFIED_COMPLETE
- **DATE**: 2026-11-19
- **BRANCH**: `feature/keel-app-048-agents-registry-read`
- **SCOPE**: `dev-app/` frontend data layer (read-only overlay)

## OBJECTIVE & ACCEPTANCE CRITERIA

- [x] Typed decoder for the live `GET /v1/agents/registry` envelope (`{manifests:[{id,name,version,owner,description,digest,enabled,created_at,updated_at}]}`) — `decodeAgentRegistry` in `apiDecoders.ts`, `AgentRegistryRecord` in `types.ts`.
- [x] `fetchAgentRegistry()` in `api.ts` via same-origin `/v1/*` + `requestSameOriginDecoded`; returns `null` when unavailable (offline/test fallback → `null`, never fabricated records).
- [x] `useUnifiedPlatformState` fetches the registry once at mount and exposes `agentRegistry: Map<string, AgentRegistryRecord> | null` keyed by manifest name.
- [x] `AgentsWorkspaceView` overlays live registry truth on the `INITIAL_LIFECYCLE_AGENTS` seed (which owns presentation fields the registry doesn't have: roleTitle, stage, tools, promptVersion, UI status):
  - Header badge: `12 manifests registered · N enabled` when live; `N agents · registry unverified` when unavailable — no "registered" claim without verification.
  - Per card: `Live · digest xxxxxxxx` for enabled records, `Disabled` (locked) for kill-switched records, `Unregistered` (unmeasured) when the registry loaded but has no record; nothing when registry is unavailable.
- [x] No runtime statuses invented: registry has no run-state field, so cards keep their seed status badge and registry state is a *separate* epistemic badge.
- [x] Live-verified on an isolated stack: 12 manifests registered at bootstrap; POST toggle `devops-sre` → `enabled:false` → header `11 enabled` + `Disabled` badge on that card.
- [x] Tests: `fetchAgentRegistry` live-envelope decode (enabled + disabled records) added to `tokens-and-badges.test.tsx`; `111/111` vitest green incl. axe gate; `tsc --noEmit` clean; Vite build clean, `core/dev_app_dist` rebuilt.

## FILES MODIFIED

- `dev-app/src/lib/types.ts` — `AgentRegistryRecord` interface.
- `dev-app/src/lib/apiDecoders.ts` — `decodeAgentRegistry` (envelope unwrap, tolerant field defaults).
- `dev-app/src/lib/api.ts` — `fetchAgentRegistry` (null-on-failure contract).
- `dev-app/src/components/platform/useUnifiedPlatformState.tsx` — mount-time registry fetch, `agentRegistry` map exposed to the view.
- `dev-app/src/components/platform/AgentsWorkspaceView.tsx` — optional `agentRegistry` prop, honest header badge, per-card registry overlay.
- `dev-app/src/__tests__/tokens-and-badges.test.tsx` — live-envelope fetch test.
- `core/dev_app_dist` — rebuilt bundle.

## LIVE EVIDENCE

- `/tmp/keelway-evidence-reg/agents-view.aria.txt` — header `OpenCore · 12 manifests registered · 12 enabled`, per-card `Live · digest …`.
- `/tmp/keelway-evidence-reg/agents-disabled.aria.txt` — after `POST /v1/agents/registry/devops-sre/1.0.0/toggle {"enabled":false}` (200): header `11 enabled`, `devops-sre` card shows `Disabled`; other 11 cards still `Live · digest …`.
- `/tmp/keelway-evidence-reg/agents-disabled.png` — visual capture.

## HONEST LIMITS / FOLLOW-UPS

- Registry is read at mount; live toggle changes require a page reload to re-render. A re-fetch/optimistic-update path can ride along with any future card-level toggle UI.
- Custom (user-created) agents have no manifest record — they render `Unregistered`, which is accurate.
- `fetchAgentManifests` (`/v1/studio/manifests`) remains the studio-surface client — intentionally untouched; the two endpoints return different shapes.
- Follow-ups still parked: `golden-eval` compare_to/drift wiring, `cli.py kstack execute`, handlers for process skills (`plan`, `review`), card-level kill-switch toggle UI (endpoint + request body `{enabled}` already exist and are exercised by the backend tests).
