export type ShowcasePresetId = "langgraph-refund-cycle" | "pr-security-sentinel" | "clinical-hipaa-intake";
export type GoldenThreadStageId = "plan-import" | "build-sync" | "scrub-radar" | "govern-ship";
export type ShowcaseLanguage = "python" | "typescript";

export interface ShowcaseNode {
  id: string; label: string; kind: "agent" | "tool" | "router" | "p10_human_gate";
  requiresP10: boolean; model: string; lineStart: number; lineEnd: number; x: number; y: number;
}
export interface ShowcaseEdge {
  from: string; to: string; isCycleBackEdge: boolean; condition?: string; maxIterations?: number;
}
export interface ShowcaseSpan {
  stepIndex: number; nodeId: string; label: string; durationMs: number; tokens: number;
  costUsd: number; forkedCostUsd: number; cachedUpstream: boolean; summary: string; forkSummary: string;
}
export interface BlastRadiusProbe {
  id: string; surface: "filesystem" | "network" | "env"; target: string; verdict: "ALLOWED" | "BLOCKED"; reason: string;
}
export interface PromptGateVerdict {
  verdict: "PASS" | "BLOCK"; score: number; gateRunId: string; gateSha256: string; costDeltaUsd: number; findings: string[];
}
export interface ShowcasePreset {
  id: ShowcasePresetId; title: string; privacyNote: string; defaultPrompt: string; blastReceiptId: string;
  initialSource: string; nodes: ShowcaseNode[]; edges: ShowcaseEdge[]; spans: ShowcaseSpan[]; probes: BlastRadiusProbe[];
}

function deterministicHex(seed: string, length: number): string {
  let h1 = 0x811c9dc5;
  let h2 = 0x9e3779b9;
  for (let i = 0; i < seed.length; i += 1) {
    const ch = seed.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 0x01000193) >>> 0;
    h2 = Math.imul(h2 ^ (ch + i), 0x85ebca6b) >>> 0;
  }
  const base = `${h1.toString(16).padStart(8, "0")}${h2.toString(16).padStart(8, "0")}`;
  return base.repeat(Math.ceil(length / 16)).slice(0, length);
}

function layoutWaveCoords(index: number, total: number): { x: number; y: number } {
  const step = Math.min(150, Math.floor(580 / Math.max(total, 1)));
  return { x: 18 + index * step, y: index % 2 === 0 ? 104 : 84 };
}

const SHARED_PROBES: BlastRadiusProbe[] = [
  { id: "prb-fs-ast", surface: "filesystem", target: "./src/workflows/*.py (read-only AST)", verdict: "ALLOWED", reason: "Scoped workspace worktree read permitted by Seatbelt profile." },
  { id: "prb-net-imds", surface: "network", target: "http://169.254.169.254/latest/meta-data/", verdict: "BLOCKED", reason: "Cloud metadata SSRF blocked by zero-egress network namespace." },
  { id: "prb-fs-ssh", surface: "filesystem", target: "~/.ssh/id_ed25519", verdict: "BLOCKED", reason: "Host credential directory denied outside ephemeral sandbox root." },
  { id: "prb-env-secret", surface: "env", target: "os.environ['STRIPE_LIVE_SECRET']", verdict: "BLOCKED", reason: "Unscoped host environment secret scrubbed before tool spawn." },
];

export const SHOWCASE_PRESET_ORDER: ShowcasePresetId[] = ["langgraph-refund-cycle", "pr-security-sentinel", "clinical-hipaa-intake"];

export const SHOWCASE_PRESETS: Record<ShowcasePresetId, ShowcasePreset> = {
  "langgraph-refund-cycle": {
    id: "langgraph-refund-cycle",
    title: "LangGraph Refund Cycle",
    privacyNote: "Hybrid Local + Frontier · P-10 > $250",
    defaultPrompt: "Verify order receipt policy, cap refunds at $250 without human sign-off, and return typed JSON.",
    blastReceiptId: "blast-9f4c2e18a7b0",
    initialSource: 'from langgraph.graph import StateGraph\nfrom langgraph.types import interrupt\n\ngraph = StateGraph(RefundState)\ngraph.add_node("ingest_claim", ingest_claim_fn)\ngraph.add_node("verify_policy", verify_policy_fn)\ngraph.add_node("draft_refund", draft_refund_fn)\ngraph.add_node("approve_payout", lambda s: interrupt("Approve refund > $250"))\ngraph.add_edge("ingest_claim", "verify_policy")\ngraph.add_edge("verify_policy", "draft_refund")\ngraph.add_conditional_edges("draft_refund", route_fn, {"retry": "verify_policy", "ok": "approve_payout"})',
    nodes: [
      { id: "ingest_claim", label: "Ingest Claim", kind: "agent", requiresP10: false, model: "keelway-core:7b", lineStart: 5, lineEnd: 5, x: 18, y: 104 },
      { id: "verify_policy", label: "Verify Policy", kind: "router", requiresP10: false, model: "keelway-core:7b", lineStart: 6, lineEnd: 6, x: 168, y: 84 },
      { id: "draft_refund", label: "Draft Refund", kind: "tool", requiresP10: false, model: "gemini-3.5-flash-lite", lineStart: 7, lineEnd: 7, x: 318, y: 104 },
      { id: "approve_payout", label: "Approve > $250", kind: "p10_human_gate", requiresP10: true, model: "human-quorum", lineStart: 8, lineEnd: 8, x: 468, y: 84 },
    ],
    edges: [
      { from: "ingest_claim", to: "verify_policy", isCycleBackEdge: false },
      { from: "verify_policy", to: "draft_refund", isCycleBackEdge: false },
      { from: "draft_refund", to: "verify_policy", isCycleBackEdge: true, condition: "retry", maxIterations: 4 },
      { from: "draft_refund", to: "approve_payout", isCycleBackEdge: false, condition: "ok" },
    ],
    spans: [
      { stepIndex: 1, nodeId: "ingest_claim", label: "01 · ingest_claim", durationMs: 140, tokens: 420, costUsd: 0.0, forkedCostUsd: 0.0, cachedUpstream: true, summary: "Parsed invoice #8841 ($410.00) on local OpenCore ($0.00).", forkSummary: "Reused deterministic tape snapshot #1 ($0.00 upstream cache)." },
      { stepIndex: 2, nodeId: "verify_policy", label: "02 · verify_policy", durationMs: 185, tokens: 510, costUsd: 0.0004, forkedCostUsd: 0.0, cachedUpstream: true, summary: "Matched 30-day warranty rule; flagged >$250 threshold.", forkSummary: "Cached policy AST verdict replayed with zero token spend ($0.00)." },
      { stepIndex: 3, nodeId: "draft_refund", label: "03 · draft_refund (cycle 2/4)", durationMs: 310, tokens: 890, costUsd: 0.0018, forkedCostUsd: 0.0003, cachedUpstream: false, summary: "Cloud model drafted $410 credit memo after 1 policy retry.", forkSummary: "Forked to local keelway-core:7b; drafted identical memo (-83% cost)." },
      { stepIndex: 4, nodeId: "approve_payout", label: "04 · approve_payout (P-10)", durationMs: 95, tokens: 120, costUsd: 0.0, forkedCostUsd: 0.0, cachedUpstream: false, summary: "Paused at P-10 Human Quorum before Stripe refund mutation.", forkSummary: "Sealed SHA-256 counterfactual diff ready for human sign-off." },
    ],
    probes: SHARED_PROBES,
  },
  "pr-security-sentinel": {
    id: "pr-security-sentinel",
    title: "Multi-Agent PR Sentinel",
    privacyNote: "Seatbelt Isolated Pytest · P-10 Merge Gate",
    defaultPrompt: "Audit unified git diff for auth regressions, run isolated pytest, and require P-10 sign-off before merge.",
    blastReceiptId: "blast-4d8a1c72e319",
    initialSource: 'from core.sdk import KeelwayClient\n\nstudio = KeelwayClient(privacy="private").platform.kflow_studio("pr-sentinel")\nstudio.node("scan_diff", kind="agent", model="keelway-coder:7b", requires_p10=False)\nstudio.node("run_pytest", kind="tool", model="sandbox-seatbelt", requires_p10=False)\nstudio.node("risk_router", kind="router", model="keelway-core:7b", requires_p10=False)\nstudio.node("p10_merge", kind="p10_human_gate", model="human-quorum", requires_p10=True)\nstudio.edge("scan_diff", "run_pytest")\nstudio.edge("run_pytest", "risk_router")\nstudio.cycle("risk_router", "run_pytest", max_iterations=4)\nstudio.edge("risk_router", "p10_merge")',
    nodes: [
      { id: "scan_diff", label: "AST Diff Scan", kind: "agent", requiresP10: false, model: "keelway-coder:7b", lineStart: 4, lineEnd: 4, x: 18, y: 104 },
      { id: "run_pytest", label: "Seatbelt Pytest", kind: "tool", requiresP10: false, model: "sandbox-seatbelt", lineStart: 5, lineEnd: 5, x: 168, y: 84 },
      { id: "risk_router", label: "Risk Router", kind: "router", requiresP10: false, model: "keelway-core:7b", lineStart: 6, lineEnd: 6, x: 318, y: 104 },
      { id: "p10_merge", label: "P-10 Merge Gate", kind: "p10_human_gate", requiresP10: true, model: "human-quorum", lineStart: 7, lineEnd: 7, x: 468, y: 84 },
    ],
    edges: [
      { from: "scan_diff", to: "run_pytest", isCycleBackEdge: false },
      { from: "run_pytest", to: "risk_router", isCycleBackEdge: false },
      { from: "risk_router", to: "run_pytest", isCycleBackEdge: true, condition: "flaky_retry", maxIterations: 4 },
      { from: "risk_router", to: "p10_merge", isCycleBackEdge: false, condition: "green" },
    ],
    spans: [
      { stepIndex: 1, nodeId: "scan_diff", label: "01 · scan_diff", durationMs: 210, tokens: 640, costUsd: 0.0, forkedCostUsd: 0.0, cachedUpstream: true, summary: "Inspected 14 AST symbols across 3 modified modules ($0.00).", forkSummary: "Cached AST symbol table replayed instantaneously ($0.00)." },
      { stepIndex: 2, nodeId: "run_pytest", label: "02 · run_pytest", durationMs: 420, tokens: 190, costUsd: 0.0, forkedCostUsd: 0.0, cachedUpstream: true, summary: "Executed 48 unit tests inside Seatbelt read-only sandbox.", forkSummary: "Reused deterministic sandbox exit receipt (0 egress)." },
      { stepIndex: 3, nodeId: "risk_router", label: "03 · risk_router", durationMs: 160, tokens: 380, costUsd: 0.0009, forkedCostUsd: 0.0, cachedUpstream: false, summary: "Classified migration touchpoint as Risk Tier B.", forkSummary: "Forked router strictness to require dual reviewer quorum ($0.00 local)." },
      { stepIndex: 4, nodeId: "p10_merge", label: "04 · p10_merge (P-10)", durationMs: 80, tokens: 95, costUsd: 0.0, forkedCostUsd: 0.0, cachedUpstream: false, summary: "Held git branch push pending human cryptographic sign-off.", forkSummary: "Counterfactual merge receipt verified against SHA-256 chain." },
    ],
    probes: SHARED_PROBES,
  },
  "clinical-hipaa-intake": {
    id: "clinical-hipaa-intake",
    title: "HIPAA Zero-Egress Triage",
    privacyNote: 'privacy="private" · $0.00 Local OpenCore',
    defaultPrompt: "Summarize patient intake locally with privacy='private', redact PHI identifiers, and route to clinician P-10 review.",
    blastReceiptId: "blast-7c21e094b6f2",
    initialSource: 'from core.sdk import KeelwayClient\n\nstudio = KeelwayClient(privacy="private").platform.kflow_studio("hipaa-intake")\nstudio.node("scrub_phi", kind="tool", model="keelway-core:7b", requires_p10=False)\nstudio.node("triage_note", kind="agent", model="keelway-core:7b", requires_p10=False)\nstudio.node("icd_check", kind="router", model="keelway-core:7b", requires_p10=False)\nstudio.node("clinician_p10", kind="p10_human_gate", model="human-quorum", requires_p10=True)\nstudio.edge("scrub_phi", "triage_note")\nstudio.edge("triage_note", "icd_check")\nstudio.cycle("icd_check", "triage_note", max_iterations=4)\nstudio.edge("icd_check", "clinician_p10")',
    nodes: [
      { id: "scrub_phi", label: "Scrub PHI", kind: "tool", requiresP10: false, model: "keelway-core:7b", lineStart: 4, lineEnd: 4, x: 18, y: 104 },
      { id: "triage_note", label: "Clinical Summary", kind: "agent", requiresP10: false, model: "keelway-core:7b", lineStart: 5, lineEnd: 5, x: 168, y: 84 },
      { id: "icd_check", label: "ICD-10 Check", kind: "router", requiresP10: false, model: "keelway-core:7b", lineStart: 6, lineEnd: 6, x: 318, y: 104 },
      { id: "clinician_p10", label: "Clinician P-10", kind: "p10_human_gate", requiresP10: true, model: "human-quorum", lineStart: 7, lineEnd: 7, x: 468, y: 84 },
    ],
    edges: [
      { from: "scrub_phi", to: "triage_note", isCycleBackEdge: false },
      { from: "triage_note", to: "icd_check", isCycleBackEdge: false },
      { from: "icd_check", to: "triage_note", isCycleBackEdge: true, condition: "cite_gap", maxIterations: 4 },
      { from: "icd_check", to: "clinician_p10", isCycleBackEdge: false, condition: "verified" },
    ],
    spans: [
      { stepIndex: 1, nodeId: "scrub_phi", label: "01 · scrub_phi", durationMs: 115, tokens: 310, costUsd: 0.0, forkedCostUsd: 0.0, cachedUpstream: true, summary: "Redacted MRN & DOB locally; 0 bytes external egress.", forkSummary: "Cached zero-egress PHI redaction envelope reused ($0.00)." },
      { stepIndex: 2, nodeId: "triage_note", label: "02 · triage_note", durationMs: 290, tokens: 780, costUsd: 0.0, forkedCostUsd: 0.0, cachedUpstream: true, summary: "Generated SOAP intake summary on local keelway-core:7b.", forkSummary: "Upstream SOAP note snapshot cached locally ($0.00)." },
      { stepIndex: 3, nodeId: "icd_check", label: "03 · icd_check", durationMs: 175, tokens: 430, costUsd: 0.0, forkedCostUsd: 0.0, cachedUpstream: false, summary: "Verified ICD-10 citations with 0 cloud API calls.", forkSummary: "Forked citation threshold to strict evidence mode ($0.00 local)." },
      { stepIndex: 4, nodeId: "clinician_p10", label: "04 · clinician_p10 (P-10)", durationMs: 90, tokens: 110, costUsd: 0.0, forkedCostUsd: 0.0, cachedUpstream: false, summary: "Queued EHR chart write behind attending clinician P-10 gate.", forkSummary: "Clinician sign-off envelope sealed with SHA-256 provenance." },
    ],
    probes: SHARED_PROBES,
  },
};

export function syncShowcaseCodeToGraph(sourceCode: string, presetId: ShowcasePresetId) {
  const preset = SHOWCASE_PRESETS[presetId];
  const lines = sourceCode.split("\n");
  const parsedNodes: Omit<ShowcaseNode, "x" | "y">[] = [];
  const nodeDeclRe = /(?:add_node|studio\.node)\(\s*["']([a-zA-Z0-9_-]+)["']|id:\s*["']([a-zA-Z0-9_-]+)["']/;

  for (let i = 0; i < lines.length; i += 1) {
    const match = lines[i].match(nodeDeclRe);
    const id = match?.[1] ?? match?.[2];
    if (!id || parsedNodes.some((n) => n.id === id)) continue;
    let endIdx = i;
    while (endIdx + 1 < Math.min(lines.length, i + 6) && !/[)}]/.test(lines[endIdx])) endIdx += 1;
    const snippet = lines.slice(i, endIdx + 1).join(" ");
    const fallback = preset.nodes.find((n) => n.id === id);
    const requiresP10 = /interrupt\(|requires_p10\s*=\s*True|requiresP10:\s*true|p10_human_gate/.test(snippet);
    const modelMatch = snippet.match(/model\s*[=:]\s*["']([^"']+)["']/);
    const kind: ShowcaseNode["kind"] = requiresP10 ? "p10_human_gate" : /router|verify|icd|risk/.test(snippet + id) ? "router" : /tool|pytest|draft|scrub/.test(snippet + id) ? "tool" : fallback?.kind ?? "agent";
    parsedNodes.push({
      id,
      label: fallback?.label ?? id.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      kind,
      requiresP10,
      model: modelMatch?.[1] ?? (requiresP10 ? "human-quorum" : fallback?.model ?? "keelway-core:7b"),
      lineStart: i + 1,
      lineEnd: endIdx + 1,
    });
  }

  const totalLines = Math.max(lines.length, 1);
  const baseNodes = parsedNodes.length > 0 ? parsedNodes : preset.nodes;
  const nodes: ShowcaseNode[] = baseNodes.map((n, idx) => ({
    ...n,
    lineStart: Math.min(Math.max(1, n.lineStart), totalLines),
    lineEnd: Math.min(Math.max(n.lineStart, n.lineEnd), totalLines),
    ...layoutWaveCoords(idx, baseNodes.length),
  }));

  const nodeOrder = new Map(nodes.map((n, idx) => [n.id, idx]));
  const parsedEdges: ShowcaseEdge[] = [];
  for (const line of lines) {
    const direct = line.match(/(?:add_edge|studio\.edge)\(\s*["']([^"']+)["']\s*,\s*["']([^"']+)["']/) ?? line.match(/from:\s*["']([^"']+)["']\s*,\s*to:\s*["']([^"']+)["']/);
    if (direct && nodeOrder.has(direct[1]) && nodeOrder.has(direct[2])) {
      const isBack = /isCycleBackEdge:\s*true/.test(line) || (nodeOrder.get(direct[2]) ?? 0) <= (nodeOrder.get(direct[1]) ?? 0);
      parsedEdges.push({ from: direct[1], to: direct[2], isCycleBackEdge: isBack, maxIterations: isBack ? 4 : undefined });
    }
    const cyc = line.match(/studio\.cycle\(\s*["']([^"']+)["']\s*,\s*["']([^"']+)["'](?:.*max_iterations\s*=\s*(\d+))?/);
    if (cyc && nodeOrder.has(cyc[1]) && nodeOrder.has(cyc[2])) {
      parsedEdges.push({ from: cyc[1], to: cyc[2], isCycleBackEdge: true, maxIterations: Number(cyc[3] ?? 4) });
    }
    if (line.includes("add_conditional_edges")) {
      const src = line.match(/add_conditional_edges\(\s*["']([^"']+)["']/)?.[1];
      for (const t of line.matchAll(/["']([^"']+)["']\s*:\s*["']([^"']+)["']/g)) {
        if (src && nodeOrder.has(src) && nodeOrder.has(t[2])) {
          const isBack = (nodeOrder.get(t[2]) ?? 0) <= (nodeOrder.get(src) ?? 0);
          parsedEdges.push({ from: src, to: t[2], isCycleBackEdge: isBack, condition: t[1], maxIterations: isBack ? 4 : undefined });
        }
      }
    }
  }

  const edges = parsedEdges.length > 0 ? parsedEdges : preset.edges;
  const cycleBackEdges = edges.filter((e) => e.isCycleBackEdge);
  const blueprintDigest = deterministicHex(`${presetId}:${JSON.stringify(nodes)}:${JSON.stringify(edges)}`, 12);
  return { nodes, edges, cycleBackEdges, blueprintDigest };
}

export function syncShowcaseGraphToCode(nodes: ShowcaseNode[], edges: ShowcaseEdge[], language: ShowcaseLanguage) {
  switch (language) {
    case "python": {
      const lines = ["from core.sdk import KeelwayClient", "", 'client = KeelwayClient(privacy="private")', 'studio = client.platform.kflow_studio("golden-thread")', ""];
      const syncedNodes = nodes.map((node) => {
        const lineStart = lines.length + 1;
        lines.push("studio.node(", `    "${node.id}", kind="${node.kind}", model="${node.model}", requires_p10=${node.requiresP10 ? "True" : "False"}`, ")");
        return { ...node, lineStart, lineEnd: lines.length };
      });
      lines.push("");
      for (const edge of edges) {
        lines.push(edge.isCycleBackEdge ? `studio.cycle("${edge.from}", "${edge.to}", max_iterations=${edge.maxIterations ?? 4})` : `studio.edge("${edge.from}", "${edge.to}")`);
      }
      const code = lines.join("\n");
      return { code, nodes: syncedNodes, blueprintDigest: deterministicHex(code, 12) };
    }
    case "typescript": {
      const lines = ['import { KeelwayClient } from "@keelway/sdk";', "", 'const client = new KeelwayClient({ baseUrl: "http://127.0.0.1:7420" });', "await client.platform.syncKflowStudio({", '  workflowId: "golden-thread",', "  nodes: ["];
      const syncedNodes = nodes.map((node) => {
        const lineStart = lines.length + 1;
        lines.push(`    { id: "${node.id}",`, `      kind: "${node.kind}", model: "${node.model}", requiresP10: ${node.requiresP10} },`);
        return { ...node, lineStart, lineEnd: lines.length };
      });
      lines.push("  ],", "  edges: [");
      for (const edge of edges) {
        lines.push(`    { from: "${edge.from}", to: "${edge.to}", isCycleBackEdge: ${edge.isCycleBackEdge}${edge.isCycleBackEdge ? `, maxIterations: ${edge.maxIterations ?? 4}` : ""} },`);
      }
      lines.push("  ],", "});");
      const code = lines.join("\n");
      return { code, nodes: syncedNodes, blueprintDigest: deterministicHex(code, 12) };
    }
    default: {
      const _exhaustive: never = language;
      return _exhaustive;
    }
  }
}

export function evaluateShowcasePromptGate(candidatePrompt: string): PromptGateVerdict {
  const findings: string[] = [];
  if (/sk-[a-zA-Z0-9_-]{3,}|\bsk-/i.test(candidatePrompt)) findings.push("DLP Secret Leak: API key prefix 'sk-' detected inside prompt payload.");
  if (/AKIA[0-9A-Z]*/.test(candidatePrompt)) findings.push("DLP Cloud Key Leak: AWS access key prefix 'AKIA' blocked before egress.");
  if (/ignore previous instructions/i.test(candidatePrompt)) findings.push("Prompt Injection: 'ignore previous instructions' override pattern rejected.");
  if (/bypass p-10/i.test(candidatePrompt)) findings.push("Governance Violation: Attempt to bypass P-10 human approval quorum.");
  if (/shell\s*=\s*True/i.test(candidatePrompt)) findings.push("Sandbox Escape Sink: Unsandboxed 'shell=True' execution forbidden.");
  if (/rm\s+-rf/i.test(candidatePrompt)) findings.push("Destructive Command: 'rm -rf' filesystem wipe blocked by policy gate.");

  const digest = deterministicHex(candidatePrompt || "empty", 16);
  const blocked = findings.length > 0;
  return {
    verdict: blocked ? "BLOCK" : "PASS",
    score: blocked ? 0.25 : 1.0,
    gateRunId: `pgate-${digest.slice(0, 8)}`,
    gateSha256: `sha256:${digest}`,
    costDeltaUsd: blocked ? 0.0 : -0.0042,
    findings,
  };
}
