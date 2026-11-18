import React, { useEffect, useId, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  canRbacMutateStudio, syncKflowStudio,
  type StudioCycleBackEdge, type StudioKflowEdge, type StudioKflowNode,
  type StudioSdkLanguage, type WorkspaceRbacRole,
} from "@/lib/platformStudioApi";

export interface BidirectionalKflowStudioPanelProps {
  workspaceId?: string;
  workflowId?: string;
  activeRbacRole?: WorkspaceRbacRole;
}

const INITIAL_PYTHON_STUDIO_CODE = [
  "from keelway.kflow import KFlowStudio",
  "",
  'studio = KFlowStudio(workflow_id="WF-01", workspace_id="default")',
  "",
  "studio.node(",
  '    id="spec_ingest",',
  '    label="Parse PRD & Threat Scope",',
  '    agent_id="product-strategist",',
  "    depends_on=[],",
  "    requires_p10=False,",
  ")",
  "",
  "studio.node(",
  '    id="patch_synth",',
  '    label="Synthesize & Test Patch",',
  '    agent_id="feature-coder",',
  '    depends_on=["spec_ingest"],',
  "    requires_p10=False,",
  ")",
  "",
  "studio.node(",
  '    id="p10_release_gate",',
  '    label="P-10 Sovereign Release Gate",',
  '    agent_id="security-auditor",',
  '    depends_on=["patch_synth"],',
  "    requires_p10=True,",
  ")",
  "",
  'studio.cycle(from_node="p10_release_gate", to_node="patch_synth", max_iterations=3)',
].join("\n");

const INITIAL_STUDIO_NODES: StudioKflowNode[] = [
  { id: "spec_ingest", label: "Parse PRD & Threat Scope", agent_id: "product-strategist", depends_on: [], requires_p10: false, line_start: 5, line_end: 11, wave: 0, x: 76, y: 86 },
  { id: "patch_synth", label: "Synthesize & Test Patch", agent_id: "feature-coder", depends_on: ["spec_ingest"], requires_p10: false, line_start: 13, line_end: 19, wave: 1, x: 290, y: 86 },
  { id: "p10_release_gate", label: "P-10 Sovereign Release Gate", agent_id: "security-auditor", depends_on: ["patch_synth"], requires_p10: true, line_start: 21, line_end: 27, wave: 2, x: 504, y: 86 },
];

const INITIAL_STUDIO_EDGES: StudioKflowEdge[] = [
  { from: "spec_ingest", to: "patch_synth", is_cycle: false },
  { from: "patch_synth", to: "p10_release_gate", is_cycle: false },
  { from: "p10_release_gate", to: "patch_synth", is_cycle: true },
];

const INITIAL_CYCLES: StudioCycleBackEdge[] = [{ from: "p10_release_gate", to: "patch_synth" }];
const NODE_W = 152;
const NODE_H = 62;

export function BidirectionalKflowStudioPanel({
  workspaceId = "default", workflowId = "WF-01", activeRbacRole = "owner",
}: BidirectionalKflowStudioPanelProps): React.JSX.Element {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const canMutate = canRbacMutateStudio(activeRbacRole);

  const [language, setLanguage] = useState<StudioSdkLanguage>("python");
  const [nodes, setNodes] = useState<StudioKflowNode[]>(INITIAL_STUDIO_NODES);
  const [edges, setEdges] = useState<StudioKflowEdge[]>(INITIAL_STUDIO_EDGES);
  const [cycleBackEdges, setCycleBackEdges] = useState<StudioCycleBackEdge[]>(INITIAL_CYCLES);
  const [sourceCode, setSourceCode] = useState<string>(INITIAL_PYTHON_STUDIO_CODE);
  const [syncSha256, setSyncSha256] = useState<string>(
    "sha256:8f4e2c19a0b73d56e1c2948573a6b0d14f8c2e90a1b2c3d4e5f60718293a4b5c",
  );
  const [selectedNodeId, setSelectedNodeId] = useState<string>("spec_ingest");
  const [newNodeLabel, setNewNodeLabel] = useState<string>("");
  const [syncing, setSyncing] = useState<boolean>(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void syncKflowStudio(
      { workspace_id: workspaceId, workflow_id: workflowId, direction: "code_to_graph", language: "python", source_code: INITIAL_PYTHON_STUDIO_CODE, persist: false },
      activeRbacRole,
    )
      .then((res) => {
        if (cancelled) return;
        setNodes(res.nodes);
        setEdges(res.edges);
        setCycleBackEdges(res.cycle_back_edges);
        setSourceCode(res.source_code);
        setSyncSha256(res.sync_sha256);
        setSelectedNodeId((prev) => (res.nodes.some((n) => n.id === prev) ? prev : (res.nodes[0]?.id ?? "")));
      })
      .catch((err) => { if (!cancelled) setErrorBanner(err instanceof Error ? err.message : "Failed to load KFlow studio graph."); });
    return () => { cancelled = true; };
  }, [workspaceId, workflowId]);

  const selectedNode = useMemo(() => nodes.find((n) => n.id === selectedNodeId) ?? nodes[0] ?? null, [nodes, selectedNodeId]);
  const nodeById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const codeLines = useMemo(() => sourceCode.split("\n"), [sourceCode]);
  const svgViewWidth = useMemo(() => Math.max(680, nodes.reduce((acc, n) => Math.max(acc, n.x + NODE_W + 32), 680)), [nodes]);
  const inspectorScrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (inspectorScrollRef.current && selectedNode) {
      inspectorScrollRef.current.scrollTop = Math.max(0, (selectedNode.line_start - 3) * 20);
    }
  }, [selectedNode, sourceCode]);

  const applySyncResult = (res: Awaited<ReturnType<typeof syncKflowStudio>>) => {
    setNodes(res.nodes);
    setEdges(res.edges);
    setCycleBackEdges(res.cycle_back_edges);
    setSourceCode(res.source_code);
    setSyncSha256(res.sync_sha256);
    setLanguage(res.language);
    setSelectedNodeId((prev) => (res.nodes.some((n) => n.id === prev) ? prev : (res.nodes[0]?.id ?? "")));
  };

  const handleToggleP10Lock = async (targetNodeId: string) => {
    if (!canMutate || syncing) return;
    setSyncing(true);
    setErrorBanner(null);
    const updated = nodes.map((n) => (n.id === targetNodeId ? { ...n, requires_p10: !n.requires_p10 } : n));
    try {
      const res = await syncKflowStudio(
        { workspace_id: workspaceId, workflow_id: workflowId, direction: "graph_to_code", language, nodes: updated, persist: true },
        activeRbacRole,
      );
      applySyncResult(res);
      setSelectedNodeId(targetNodeId);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to sync P-10 lock to code.");
    } finally {
      setSyncing(false);
    }
  };

  const handleAddStudioNode = async () => {
    if (!canMutate || syncing) return;
    setSyncing(true);
    setErrorBanner(null);
    const idx = nodes.length + 1;
    const labelText = newNodeLabel.trim() || `Canary Verification Gate ${idx}`;
    const slug = labelText.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 24) || `studio_step_${idx}`;
    const uniqueId = nodes.some((n) => n.id === slug) ? `${slug}_${idx}` : slug;
    const prevId = nodes[nodes.length - 1]?.id;
    const appended = [...nodes, { id: uniqueId, label: labelText, agent_id: "qa-verifier", depends_on: prevId ? [prevId] : [], requires_p10: false }];
    try {
      const res = await syncKflowStudio(
        { workspace_id: workspaceId, workflow_id: workflowId, direction: "graph_to_code", language, nodes: appended, persist: true },
        activeRbacRole,
      );
      applySyncResult(res);
      setSelectedNodeId(uniqueId);
      setNewNodeLabel("");
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to append studio node.");
    } finally {
      setSyncing(false);
    }
  };

  const handleSyncCodeToGraph = async () => {
    if (syncing) return;
    setSyncing(true);
    setErrorBanner(null);
    try {
      const res = await syncKflowStudio(
        { workspace_id: workspaceId, workflow_id: workflowId, direction: "code_to_graph", language, source_code: sourceCode, persist: canMutate },
        activeRbacRole,
      );
      applySyncResult(res);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to parse studio code into KFlow graph.");
    } finally {
      setSyncing(false);
    }
  };

  const handleSwitchLanguage = async (nextLang: StudioSdkLanguage) => {
    if (nextLang === language || syncing) return;
    setLanguage(nextLang);
    if (!canMutate) return;
    setSyncing(true);
    setErrorBanner(null);
    try {
      const res = await syncKflowStudio(
        { workspace_id: workspaceId, workflow_id: workflowId, direction: "graph_to_code", language: nextLang, nodes, persist: false },
        activeRbacRole,
      );
      applySyncResult(res);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to switch SDK language.");
    } finally {
      setSyncing(false);
    }
  };

  const p10LockedCount = nodes.filter((n) => n.requires_p10).length;

  return (
    <section aria-label="Bidirectional KFlow visual and AST code studio" className="space-y-4 rounded-md border border-border-strong bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-fg">Bidirectional KFlow Topology ↔ AST Code Split Studio</h2>
            <SemanticBadge kind="opencore" labelOverride={`Zero-Drift · ${workflowId}`} />
            {cycleBackEdges.length > 0 ? (
              <span className="inline-flex items-center gap-1 rounded-xs border border-ochre/45 bg-ochre-subtle px-1.5 py-0.5 font-mono text-[11px] font-medium text-ochre">
                <span aria-hidden="true">↻</span>
                <span>Cycle (Bounded)</span>
              </span>
            ) : null}
          </div>
          <p className="text-xs text-fg-muted">
            Direct-manipulation SVG wave blueprint paired with a live AST-synced Python &amp; TypeScript KFlow SDK editor. Click any node to illuminate its exact source span or toggle P-10 human locks.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SemanticBadge kind={p10LockedCount > 0 ? "needs-approval" : "passed"} labelOverride={`${p10LockedCount} P-10 Gate${p10LockedCount === 1 ? "" : "s"}`} />
          <code title={syncSha256} className="max-w-[240px] truncate rounded-xs border border-border bg-canvas px-2 py-0.5 font-mono text-[11px] text-teal-accent">
            {syncSha256}
          </code>
        </div>
      </div>

      {!canMutate ? (
        <div className="rounded-xs border border-warning/45 bg-warning-subtle px-3 py-1.5 font-mono text-xs text-fg">
          {`Studio Read-Only Mode (${activeRbacRole}): Read-only code_to_graph inspection is enabled; graph_to_code mutations (P-10 lock toggles and adding studio nodes) are locked for viewer role.`}
        </div>
      ) : null}

      {errorBanner ? (
        <div role="alert" className="rounded-xs border border-danger/50 bg-danger-subtle px-3 py-2 font-mono text-xs text-danger">
          {errorBanner}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="space-y-3 lg:col-span-7">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border bg-chrome px-2.5 py-2">
            <span className="font-mono text-[11px] font-semibold text-fg">{`Topological Blueprint (${nodes.length} nodes · ${edges.length} edges)`}</span>
            <div className="flex flex-wrap items-center gap-1.5">
              <input
                type="text" aria-label="New studio node label" value={newNodeLabel}
                onChange={(e) => setNewNodeLabel(e.target.value)} disabled={!canMutate}
                placeholder="New node label (optional)"
                className="min-h-ctrl-sm w-44 rounded-xs border border-border-control bg-canvas px-2 py-0.5 text-xs text-fg disabled:opacity-55"
              />
              <Button size="sm" variant="secondary" disabled={!canMutate || syncing} onClick={() => { void handleAddStudioNode(); }}>
                + Add Studio Node
              </Button>
            </div>
          </div>

          <div className="overflow-hidden rounded-sm border border-border-strong bg-code p-2">
            <svg role="img" aria-label="KFlow topological SVG graph" viewBox={`0 0 ${svgViewWidth} 214`} className="h-auto w-full select-none">
              <defs>
                <pattern id={`kflow-grid-${uid}`} width="20" height="20" patternUnits="userSpaceOnUse">
                  <circle cx="2" cy="2" r="1" fill="rgba(148, 163, 184, 0.18)" />
                </pattern>
                <marker id={`arrow-fwd-${uid}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#2dd4bf" />
                </marker>
                <marker id={`arrow-cyc-${uid}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#e4e4e7" />
                </marker>
              </defs>
              <rect x="0" y="0" width={svgViewWidth} height="214" fill={`url(#kflow-grid-${uid})`} />

              {edges.map((edge, idx) => {
                const src = nodeById.get(edge.from);
                const dst = nodeById.get(edge.to);
                if (!src || !dst) return null;
                if (edge.is_cycle) {
                  const startX = src.x + NODE_W / 2;
                  const startY = src.y + NODE_H;
                  const endX = dst.x + NODE_W / 2;
                  const endY = dst.y + NODE_H;
                  const arcY = Math.max(startY, endY) + 46;
                  const midX = (startX + endX) / 2;
                  return (
                    <g key={`cyc-${edge.from}-${edge.to}-${idx}`}>
                      <path d={`M ${startX} ${startY} C ${startX} ${arcY}, ${endX} ${arcY}, ${endX} ${endY}`} fill="none" stroke="#e4e4e7" strokeWidth="2" strokeDasharray="5 3" markerEnd={`url(#arrow-cyc-${uid})`} />
                      <rect x={midX - 58} y={arcY - 18} width="116" height="18" rx="4" fill="#09090b" stroke="#e4e4e7" strokeWidth="1" />
                      <text x={midX} y={arcY - 6} textAnchor="middle" fill="#e4e4e7" fontSize="9.5" fontFamily="monospace">↻ Cycle (Bounded)</text>
                    </g>
                  );
                }
                const x1 = src.x + NODE_W;
                const y1 = src.y + NODE_H / 2;
                const x2 = dst.x;
                const y2 = dst.y + NODE_H / 2;
                const dx = Math.max(36, Math.abs(x2 - x1) * 0.45);
                return (
                  <path key={`fwd-${edge.from}-${edge.to}-${idx}`} d={`M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`} fill="none" stroke="#2dd4bf" strokeWidth="2" markerEnd={`url(#arrow-fwd-${uid})`} />
                );
              })}

              {nodes.map((node) => {
                const isSelected = selectedNode?.id === node.id;
                const strokeColor = node.requires_p10 ? "#e4e4e7" : isSelected ? "#2dd4bf" : "#71717a";
                return (
                  <g key={`svg-node-${node.id}`} transform={`translate(${node.x}, ${node.y})`}>
                    <rect x="0" y="0" width={NODE_W} height={NODE_H} rx="6" fill={isSelected ? "rgba(45, 212, 191, 0.14)" : "#121215"} stroke={strokeColor} strokeWidth={isSelected ? "2.2" : "1.2"} />
                    <text x="8" y="16" fill="#2dd4bf" fontSize="9.5" fontFamily="monospace" fontWeight="bold">{`W${node.wave} · L${node.line_start}–L${node.line_end}`}</text>
                    {node.requires_p10 ? <text x={NODE_W - 8} y="16" textAnchor="end" fill="#e4e4e7" fontSize="9.5" fontFamily="monospace">⚿ P-10</text> : null}
                    <text x="8" y="34" fill="#fafafa" fontSize="10.5" fontFamily="monospace" fontWeight="600">{node.id.slice(0, 18)}</text>
                    <text x="8" y="50" fill="#a1a1aa" fontSize="9.5" fontFamily="sans-serif">{node.agent_id.slice(0, 20)}</text>
                  </g>
                );
              })}
            </svg>
          </div>

          <div role="group" aria-label="Interactive KFlow studio nodes" className="grid gap-2 sm:grid-cols-2">
            {nodes.map((node) => {
              const isSelected = selectedNode?.id === node.id;
              return (
                <div key={node.id} className={`flex items-center justify-between gap-2 rounded-sm border p-2 transition-colors ${isSelected ? "border-teal-accent/65 bg-teal-surface" : "border-border-strong bg-chrome hover:border-border-control"}`}>
                  <button
                    type="button" aria-label={`Select studio node ${node.id}`} aria-pressed={isSelected}
                    onClick={() => setSelectedNodeId(node.id)}
                    className="flex min-w-0 flex-1 flex-col items-start gap-0.5 text-left focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-teal-accent"
                  >
                    <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
                      <span className="rounded-xs border border-teal-accent/40 bg-canvas px-1 py-0.2 text-[10px] font-bold text-teal-accent">{`W${node.wave}`}</span>
                      <span className="font-semibold text-fg">{node.id}</span>
                      <span className="rounded-xs border border-border bg-canvas px-1 py-0.2 text-[10px] text-fg-muted">{`L${node.line_start}–L${node.line_end}`}</span>
                    </div>
                    <span className="w-full truncate text-[11px] text-fg">{node.label}</span>
                    <span className="font-mono text-[10px] text-fg-dim">{`agent: ${node.agent_id}`}</span>
                  </button>
                  <button
                    type="button" aria-label={`Toggle P-10 lock for ${node.id}`} aria-pressed={node.requires_p10}
                    disabled={!canMutate || syncing} onClick={() => { void handleToggleP10Lock(node.id); }}
                    className={`shrink-0 rounded-xs border px-2 py-1 font-mono text-[10px] font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-teal-accent disabled:cursor-not-allowed disabled:opacity-55 ${node.requires_p10 ? "border-ochre/55 bg-ochre-subtle text-ochre" : "border-border-control bg-canvas text-fg-muted hover:text-fg"}`}
                  >
                    {node.requires_p10 ? "⚿ P-10 Locked" : "○ Lock P-10"}
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex flex-col gap-3 lg:col-span-5">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border bg-chrome px-2.5 py-2">
            <div role="group" aria-label="Studio SDK language" className="inline-flex items-center rounded-xs border border-border-control/70 bg-surface p-0.5">
              <button type="button" aria-pressed={language === "python"} onClick={() => { void handleSwitchLanguage("python"); }} className={`rounded-xs px-2 py-0.5 font-mono text-[11px] font-medium ${language === "python" ? "bg-teal-surface text-teal-accent" : "text-fg-muted hover:text-fg"}`}>
                python
              </button>
              <button type="button" aria-pressed={language === "typescript"} onClick={() => { void handleSwitchLanguage("typescript"); }} className={`rounded-xs px-2 py-0.5 font-mono text-[11px] font-medium ${language === "typescript" ? "bg-teal-surface text-teal-accent" : "text-fg-muted hover:text-fg"}`}>
                typescript
              </button>
            </div>
            <Button size="sm" variant="primary" aria-label="Sync code to visual KFlow graph" loading={syncing} onClick={() => { void handleSyncCodeToGraph(); }}>
              Sync Code → Graph
            </Button>
          </div>

          <textarea
            aria-label="Bidirectional studio source code" value={sourceCode}
            onChange={(e) => setSourceCode(e.target.value)} rows={12} spellCheck={false}
            className="w-full rounded-sm border border-border-control bg-code p-2.5 font-mono text-xs leading-relaxed text-fg focus:outline-none focus-visible:border-teal-accent"
          />

          <div role="group" aria-label="Highlighted AST line inspector" className="space-y-1.5 rounded-sm border border-border-strong bg-code p-2.5">
            <div className="flex flex-wrap items-center justify-between gap-1.5 border-b border-border pb-1.5 font-mono text-[11px]">
              <span className="font-semibold text-teal-accent">
                {selectedNode ? `Active AST Span: ${selectedNode.id} (L${selectedNode.line_start}–L${selectedNode.line_end})` : "Active AST Span"}
              </span>
              <span className="rounded-xs border border-teal-accent/40 bg-teal-surface px-1.5 py-0.5 text-[10px] text-teal-accent">
                Zero-Drift Synced
              </span>
            </div>
            <div ref={inspectorScrollRef} className="max-h-40 overflow-y-auto font-mono text-[11px] leading-5">
              {codeLines.map((lineText, idx) => {
                const lineNum = idx + 1;
                const inSpan = Boolean(selectedNode && lineNum >= selectedNode.line_start && lineNum <= selectedNode.line_end);
                const highlightClasses = inSpan
                  ? selectedNode?.requires_p10 ? "border-s-2 border-ochre bg-ochre-subtle text-fg font-medium" : "border-s-2 border-teal-accent bg-teal-surface text-fg font-medium"
                  : "text-fg-dim";
                return (
                  <div key={`ast-line-${lineNum}`} data-highlighted={inSpan ? "true" : undefined} className={`flex items-baseline gap-2 px-1.5 ${highlightClasses}`}>
                    <span className="w-7 shrink-0 select-none text-right text-[10px] opacity-75">{`L${lineNum}`}</span>
                    <span className="whitespace-pre-wrap break-all">{lineText || " "}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
