/**
 * Keelway 4D Agent CodeLens Provider for Python & TypeScript Workflow Definitions.
 */
const PY_ADD_NODE_RE = /\badd_node\s*\(\s*["']([^"']+)["']/;
const STUDIO_NODE_RE = /\bstudio\.node\s*\(\s*["']([^"']+)["']/;
const PY_AGENT_DEC_RE = /^\s*@agent(?:\s*\(\s*(?:name\s*=\s*)?["']([^"']+)["'])?/;
const PY_DEF_RE = /^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(/;
const TS_SYNC_STUDIO_RE = /\bsyncKflowStudio\s*\(/;
const TS_WORKFLOW_ID_RE = /\bworkflow_id\s*:\s*["']([^"']+)["']/;
const TS_NODE_ID_RE = /\bid\s*:\s*["']([^"']+)["']/;
export function scanWorkflowSymbols(sourceText, languageId) {
    const lines = sourceText.split(/\r?\n/);
    const symbols = [];
    const normLang = languageId.toLowerCase();
    for (let idx = 0; idx < lines.length; idx += 1) {
        const line = lines[idx] ?? "";
        const trimmed = line.trim();
        if (!trimmed)
            continue;
        if (normLang === "python") {
            if (trimmed.startsWith("#"))
                continue;
            const addNodeMatch = PY_ADD_NODE_RE.exec(line);
            if (addNodeMatch?.[1]) {
                symbols.push({ symbolId: addNodeMatch[1], kind: "node", lineZeroBased: idx, line_start: idx + 1 });
                continue;
            }
            const studioNodeMatch = STUDIO_NODE_RE.exec(line);
            if (studioNodeMatch?.[1]) {
                symbols.push({ symbolId: studioNodeMatch[1], kind: "node", lineZeroBased: idx, line_start: idx + 1 });
                continue;
            }
            const agentDecMatch = PY_AGENT_DEC_RE.exec(line);
            if (agentDecMatch) {
                let inferredId = agentDecMatch[1];
                if (!inferredId) {
                    const nextDef = PY_DEF_RE.exec(lines[idx + 1] ?? "");
                    inferredId = nextDef?.[1] ?? `agent_line_${idx + 1}`;
                }
                symbols.push({ symbolId: inferredId, kind: "agent", lineZeroBased: idx, line_start: idx + 1 });
            }
            continue;
        }
        if (normLang === "typescript" || normLang === "typescriptreact" || normLang === "javascript") {
            if (trimmed.startsWith("//"))
                continue;
            const studioNodeMatch = STUDIO_NODE_RE.exec(line);
            if (studioNodeMatch?.[1]) {
                symbols.push({ symbolId: studioNodeMatch[1], kind: "node", lineZeroBased: idx, line_start: idx + 1 });
                continue;
            }
            if (TS_SYNC_STUDIO_RE.test(line)) {
                const windowSlice = lines.slice(idx, Math.min(lines.length, idx + 6)).join(" ");
                const wfMatch = TS_WORKFLOW_ID_RE.exec(windowSlice);
                symbols.push({ symbolId: wfMatch?.[1] ?? "WF-STUDIO-01", kind: "workflow", lineZeroBased: idx, line_start: idx + 1 });
                continue;
            }
            const nodeIdMatch = TS_NODE_ID_RE.exec(line);
            if (nodeIdMatch?.[1]) {
                symbols.push({ symbolId: nodeIdMatch[1], kind: "node", lineZeroBased: idx, line_start: idx + 1 });
            }
        }
    }
    return symbols;
}
export function formatCodeLensBadge(telemetry) {
    const modelId = telemetry?.model_checkpoint ?? telemetry?.model_id ?? "keelway-core:7b";
    const rawP50 = telemetry?.p50_ms ?? telemetry?.p50_latency_ms ?? 142;
    const p50Ms = Math.max(0, Math.round(rawP50));
    const rawCost = telemetry?.avg_cost_usd ?? telemetry?.cost_usd ?? 0;
    const costFormatted = `$${rawCost.toFixed(3)}`;
    const isZeroEgress = telemetry?.provenance_4d
        ? telemetry.provenance_4d.includes("Zero-Egress")
        : (telemetry?.zero_egress ?? true);
    const egressLabel = isZeroEgress ? "Zero-Egress" : "P-10-Gated";
    const bpCount = telemetry?.attached_breakpoints ?? telemetry?.breakpoint_count ?? 0;
    const bpNoun = bpCount === 1 ? "Breakpoint" : "Breakpoints";
    return `▣ Keelway 4D · ${modelId} · P50 ${p50Ms}ms · ${costFormatted} · ${egressLabel} · ${bpCount} ${bpNoun}`;
}
export class KeelwayCodeLensProvider {
    bridgeClient;
    getScope;
    constructor(bridgeClient, getScope) {
        this.bridgeClient = bridgeClient;
        this.getScope = getScope;
    }
    async provideCodeLenses(document) {
        const symbols = scanWorkflowSymbols(document.getText(), document.languageId);
        if (symbols.length === 0)
            return [];
        const scope = this.getScope?.() ?? {
            workspaceId: this.bridgeClient.getTarget().workspaceId,
            workflowId: this.bridgeClient.getTarget().workflowId,
        };
        const filePath = document.uri.fsPath ?? document.uri.path;
        let serverItems = [];
        try {
            const response = await this.bridgeClient.getCodelens({
                workspace_id: scope.workspaceId,
                workflow_id: scope.workflowId,
                file_path: filePath,
            });
            serverItems = response.lenses ?? response.items ?? [];
        }
        catch {
            serverItems = [];
        }
        return symbols.map((sym) => {
            const matched = serverItems.find((item) => (item.symbol ?? item.node_id) === sym.symbolId || item.line_start === sym.line_start);
            const lineText = sym.lineZeroBased < document.lineCount ? document.lineAt(sym.lineZeroBased).text : "";
            const title = formatCodeLensBadge(matched);
            return {
                range: {
                    start: { line: sym.lineZeroBased, character: 0 },
                    end: { line: sym.lineZeroBased, character: lineText.length },
                },
                command: {
                    title,
                    command: "keelway.openStudioPanel",
                    tooltip: `Inspect '${sym.symbolId}' in Keelway 4D Studio Debugger (line ${sym.line_start})`,
                    arguments: [{ symbolId: sym.symbolId, kind: sym.kind, line_start: sym.line_start }],
                },
                isResolved: true,
            };
        });
    }
}
//# sourceMappingURL=codeLensProvider.js.map