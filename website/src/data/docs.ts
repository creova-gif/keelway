/**
 * Docs hub content — capability matrix and troubleshooting table
 * rows for /docs. Keeps DocsHub.tsx under the curation line cap;
 * update alongside product surface changes.
 */
export interface CapabilityRow {
  domain: string;
  title: string;
  summary: string;
  cliOrSpec: string;
}

export interface TroubleshootingRow {
  symptom: string;
  resolution: string;
}

export const CAPABILITY_MATRIX: CapabilityRow[] = [
  {
    domain: "4-K Sovereign Architecture",
    title: "KFlow, KSpaces, KBrain & KHub Core",
    summary:
      "Topological KFlow DAGs, KSpaces CRDT sync, KBrain hybrid BM25 + n-gram memory, and KHub air-gapped skill mirrors (.skill.tar.gz).",
    cliOrSpec: "keelway hub · .skill.tar.gz",
  },
  {
    domain: "Visual & Code Sync",
    title: "Golden-Thread Bidirectional KFlow Studio",
    summary:
      "Round-trip Python/TypeScript workflows with Seatbelt Blast-Radius Radar and inline Prompt Regression Gate checks.",
    cliOrSpec: "kflow-sync · blast-radius · prompt-gate",
  },
  {
    domain: "Observability & Evals",
    title: "OpenTelemetry GenAI Flight-Tape Time-Travel Debugging",
    summary:
      "Deterministic step replay, 1-click Trace-to-Eval Promotion into the 16-probe Golden Benchmark, and Static AST LangGraph import.",
    cliOrSpec: "migrate-langgraph · OpenTelemetry OTLP",
  },
  {
    domain: "MCP & Supply Chain",
    title: "Model Context Protocol (2025-06-18) & Signed Artifacts",
    summary:
      "Zero-trust tool discovery, Ed25519 Marketplace verification, and reproducible CycloneDX 1.5 SBOM release attestations.",
    cliOrSpec: "MCP 2025-06-18 · CycloneDX 1.5 SBOM",
  },
  {
    domain: "Enterprise Identity & SIEM",
    title: "Enterprise SSO, SCIM 2.0 & Dual-Human P-10 Quorum",
    summary:
      "Directory-synced RBAC, two-person approval receipts for high-impact actions, and streaming OCSF, CEF, and JSONL audit exports. OIDC uses a self-issued HS256 token profile (`federation_profile: self_issued_hs256`) for sovereign deployments; external IdP discovery/JWKS federation and SAML are not yet implemented.",
    cliOrSpec: "OIDC HS256 · SCIM 2.0 · OCSF / CEF / JSONL",
  },
];

export const TROUBLESHOOTING_ROWS: TroubleshootingRow[] = [
  {
    symptom: "AirGapViolationError (HTTP 403)",
    resolution:
      "A private/air-gap request attempted cloud egress — by design. Re-route to an open_weight model or lower the privacy level.",
  },
  {
    symptom: "P-10 gate stuck pending",
    resolution:
      "High-impact action requires human approval (or 2-of-2 quorum in Enterprise). Check `keelway mobile status` for paired approvers.",
  },
  {
    symptom: "Credential type unsupported",
    resolution:
      "Consumer subscription credentials are rejected — use a metered API key or BYOM open-weight route.",
  },
  {
    symptom: "Ledger verification failure",
    resolution:
      "Audit hash-chain mismatch — the append-only record was modified. Preserve the DB and report to your security review; do not truncate.",
  },
];
