/**
 * Release history — sourced from the repository CHANGELOG.md
 * (Keep a Changelog + SemVer). Update alongside each release.
 */
export interface ReleaseEntry {
  version: string;
  date: string;
  tag: "latest" | "stable";
  highlights: string[];
}

export const RELEASES: ReleaseEntry[] = [
  {
    version: "1.1.0",
    date: "2026-11-15",
    tag: "latest",
    highlights: [
      "Zero-install Golden-Thread Studio showcase — browser-native LangGraph → KFlow conversion with bidirectional Python/TypeScript codegen and Flight-Tape waterfall scrubbing",
      "Golden-Thread 4-Stage Journey Bar, bidirectional KFlow ↔ Code Split Studio, and Seatbelt/Bubblewrap blast-radius probe radar",
      "Flight-Tape time-travel debugger: OTel GenAI trace wedge, $0 cached counterfactual forks, and 1-click trace-to-eval promotion",
      "KBrain hybrid BM25/3-gram memory graph and KHub air-gapped .tar.gz skill mirror with Ed25519/SHA-256 verification",
      "Enterprise OIDC federation, SCIM 2.0 provisioning, 2-of-2 dual-human P-10 quorum, and DLP-redacted OCSF/CEF SIEM audit export",
      "OpenTelemetry OTLP + Prometheus metrics and CycloneDX 1.5 SBOM release attestation",
    ],
  },
  {
    version: "1.0.0",
    date: "2026-11-15",
    tag: "stable",
    highlights: [
      "Unified 10-view Sovereign Dev Tool (/app) with axe-core WCAG 2.2 AA verified workspace",
      "KFlow deterministic DAG engine with Kahn topological sorting, per-run token budgets, and P-10 pause/resume gates",
      "KSpaces CRDT state sync with Lamport-clock LWW persistence in SQLite WAL",
      "MCP 2025-06-18 control plane with SSRF guards and automatic DLP secret redaction",
      "16-probe Golden Evaluation suite with signed SHA-256 receipts",
      "Official tri-language SDK parity: Python, TypeScript (@keelway/sdk), and Go",
      "Calibrated 5-tier pricing: Community $0, BYOM $15/seat, Pro $29/seat, Team $49/seat, Enterprise custom — 0% token markup",
      "Zero-friction packaging: Python wheel, Homebrew formula, hardened multi-stage Docker image",
    ],
  },
];
