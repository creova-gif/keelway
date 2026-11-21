import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  BUILTIN_MCP_TOOLS, canRbacInvokeMcpOrEval, canRbacManageMcpServers, deleteMcpServer,
  fetchMcpServers, fetchMcpTools, getSeedMcpServers, MCP_PROTOCOL_VERSION,
  postCallMcpTool, postRegisterMcpServer, validateMcpServerClient,
  type McpServerItem, type McpToolCallResult, type McpToolItem, type McpTransport,
} from "@/lib/platformMcpEvalApi";
import type { RbacRoleId } from "@/lib/platformRuntimeApi";

export interface McpInspectorPanelProps {
  workspaceId?: string;
  activeRbacRole?: RbacRoleId;
}

export function McpInspectorPanel({
  workspaceId = "default",
  activeRbacRole = "owner",
}: McpInspectorPanelProps): React.JSX.Element {
  const canManageServers = canRbacManageMcpServers(activeRbacRole);
  const canInvokeTools = canRbacInvokeMcpOrEval(activeRbacRole);

  const [servers, setServers] = useState<McpServerItem[]>(() => getSeedMcpServers(workspaceId));
  const [tools, setTools] = useState<McpToolItem[]>(BUILTIN_MCP_TOOLS);
  const [protocolVersion, setProtocolVersion] = useState<string>(MCP_PROTOCOL_VERSION);

  const [serverName, setServerName] = useState("");
  const [transport, setTransport] = useState<McpTransport>("sse");
  const [endpoint, setEndpoint] = useState("");
  const [mcpAlert, setMcpAlert] = useState<string | null>(null);

  const [selectedTool, setSelectedTool] = useState<string>("workspace.list_files");
  const [rawJsonArgs, setRawJsonArgs] = useState<string>('{"subpath": "core", "limit": 5}');
  const [invoking, setInvoking] = useState(false);
  const [callResult, setCallResult] = useState<McpToolCallResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    setServers((prev) => [...getSeedMcpServers(workspaceId), ...prev.filter((s) => !s.builtin)]);
    void fetchMcpServers(workspaceId, activeRbacRole).then((remote) => {
      if (cancelled || !remote?.length) return;
      setServers((prev) => {
        const byId = new Map(prev.map((s) => [s.id, s]));
        remote.forEach((r) => byId.set(r.id, r));
        return Array.from(byId.values());
      });
    });
    void fetchMcpTools(workspaceId, activeRbacRole).then((remoteTools) => {
      if (cancelled || !remoteTools) return;
      setProtocolVersion(remoteTools.protocolVersion);
      setTools((prev) => {
        const byName = new Map(prev.map((t) => [t.name, t]));
        remoteTools.tools.forEach((t) => byName.set(t.name, t));
        return Array.from(byName.values());
      });
    });
    return () => { cancelled = true; };
  }, [activeRbacRole, workspaceId]);

  const handleRegisterServer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManageServers) return;
    const precheck = validateMcpServerClient(transport, endpoint);
    if (!precheck.valid) {
      setMcpAlert(precheck.reason ?? "SSRF / Unsafe MCP Target Blocked");
      return;
    }
    setMcpAlert(null);
    const res = await postRegisterMcpServer({
      workspaceId, name: serverName.trim() || "loopback-mcp-server", transport, endpoint: endpoint.trim(), role: activeRbacRole,
    });
    if (!res.ok || !res.server) {
      setMcpAlert(res.error ?? "SSRF / Policy Blocked");
      return;
    }
    setServers((prev) => [...prev.filter((s) => s.id !== res.server!.id && s.endpoint !== res.server!.endpoint), res.server!]);
    setServerName("");
    setEndpoint("");
  };

  const handleRemoveServer = (srv: McpServerItem) => {
    if (!canManageServers || srv.builtin) return;
    setServers((prev) => prev.filter((s) => s.id !== srv.id));
    void deleteMcpServer(srv.id, workspaceId, activeRbacRole);
  };

  const handleInvokeTool = async () => {
    if (!canInvokeTools || invoking) return;
    let parsedArgs: Record<string, unknown> = {};
    const trimmed = rawJsonArgs.trim();
    if (trimmed) {
      try {
        const candidate: unknown = JSON.parse(trimmed);
        if (typeof candidate !== "object" || candidate === null || Array.isArray(candidate)) {
          setMcpAlert("Invalid MCP Arguments: Tool arguments must be a JSON object.");
          return;
        }
        parsedArgs = candidate as Record<string, unknown>;
      } catch {
        setMcpAlert("Invalid MCP Arguments: Malformed JSON object.");
        return;
      }
    }
    setMcpAlert(null);
    setInvoking(true);
    try {
      const res = await postCallMcpTool({ workspaceId, toolName: selectedTool, arguments: parsedArgs, role: activeRbacRole });
      setCallResult(res);
    } finally {
      setInvoking(false);
    }
  };

  return (
    <section aria-label="Model Context Protocol server and tool inspector" className="space-y-4 rounded-md border border-border-strong bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
        <div>
          <h2 className="text-sm font-semibold text-fg">Model Context Protocol (MCP) Server &amp; Tool Inspector</h2>
          <p className="text-xs text-fg-muted">
            {`Scoped SSE & stdio MCP registry (protocol: ${protocolVersion}) with cloud-metadata SSRF guard, DLP redaction, and SHA-256 call receipts.`}
          </p>
        </div>
        <SemanticBadge kind="opencore" labelOverride={`protocol: ${protocolVersion}`} />
      </div>

      {!canInvokeTools ? (
        <div role="status" className="rounded-xs border border-warning/45 bg-warning-subtle px-3 py-1.5 font-mono text-xs text-fg">
          {`MCP Read-Only Mode (${activeRbacRole}): Server registration and live tool invocation are disabled for viewer role.`}
        </div>
      ) : null}

      {mcpAlert ? (
        <div role="alert" className="rounded-xs border border-danger/50 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg">
          <span className="font-semibold text-danger">{mcpAlert}</span>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <h3 className="text-xs font-semibold text-fg">{`Active MCP Servers (${servers.length})`}</h3>
          <ul className="space-y-2 text-xs">
            {servers.map((srv) => (
              <li key={srv.id} className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border bg-canvas px-3 py-2">
                <div className="space-y-0.5">
                  <div className="flex flex-wrap items-center gap-2 font-mono">
                    <span className="font-semibold text-fg">{srv.name}</span>
                    {srv.id !== srv.name ? <code className="text-[10px] text-fg-muted">{srv.id}</code> : null}
                    <span className="rounded-xs border border-accent/40 bg-accent-subtle px-1.5 py-0.5 text-[10px] text-accent">
                      {`${srv.transport} · protocol: ${srv.protocol_version ?? protocolVersion}`}
                    </span>
                  </div>
                  <div className="font-mono text-[11px] text-fg-muted">
                    {`${srv.endpoint} · ${srv.tools_count} tools · ${srv.builtin ? "Built-in" : srv.status}`}
                  </div>
                </div>
                {!srv.builtin ? (
                  <Button size="sm" variant="ghost" disabled={!canManageServers} aria-label={`Remove MCP server ${srv.name}`} onClick={() => handleRemoveServer(srv)}>
                    Remove
                  </Button>
                ) : (
                  <SemanticBadge kind="live" labelOverride="Built-in" />
                )}
              </li>
            ))}
          </ul>

          <form onSubmit={(e) => { void handleRegisterServer(e); }} className="grid gap-2.5 rounded-sm border border-border bg-chrome p-3 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Server name</span>
              <input type="text" aria-label="MCP server name" value={serverName} onChange={(e) => setServerName(e.target.value)} placeholder="local-ast-mcp" disabled={!canManageServers} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg" />
            </label>
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Transport</span>
              <select aria-label="MCP transport" value={transport} onChange={(e) => setTransport(e.target.value as McpTransport)} disabled={!canManageServers} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg">
                <option value="sse">sse</option>
                <option value="stdio">stdio</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Endpoint or command</span>
              <input type="text" aria-label="MCP endpoint or command" value={endpoint} onChange={(e) => setEndpoint(e.target.value)} placeholder="http://127.0.0.1:8788/sse" disabled={!canManageServers} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg" />
            </label>
            <div className="flex flex-wrap items-center justify-between gap-2 sm:col-span-3">
              <span className="font-mono text-[11px] text-fg-muted">Owner/Admin RBAC · SSRF &amp; shell-metacharacter guarded</span>
              <Button type="submit" size="sm" variant="primary" disabled={!canManageServers}>Register MCP Server</Button>
            </div>
          </form>
        </div>

        <div className="space-y-3">
          <h3 className="text-xs font-semibold text-fg">Live MCP Tool Call Tester</h3>
          <div className="space-y-2.5 rounded-sm border border-border bg-chrome p-3">
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>Scoped MCP tool</span>
              <select aria-label="MCP tool selector" value={selectedTool} onChange={(e) => setSelectedTool(e.target.value)} disabled={!canInvokeTools} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg">
                {tools.map((tool) => (
                  <option key={tool.name} value={tool.name}>{`${tool.name} — ${tool.description}`}</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-fg-muted">
              <span>JSON arguments</span>
              <input type="text" aria-label="MCP tool JSON arguments" value={rawJsonArgs} onChange={(e) => setRawJsonArgs(e.target.value)} disabled={!canInvokeTools} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg" />
            </label>
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[11px] text-fg-muted">Seatbelt confined · Record SHA-256 receipt logged</span>
              <Button size="sm" variant="primary" loading={invoking} disabled={!canInvokeTools} onClick={() => { void handleInvokeTool(); }}>Invoke MCP Tool</Button>
            </div>
          </div>

          {callResult ? (
            <div role="region" aria-label="MCP tool execution result" className="space-y-2 rounded-sm border border-ok/40 bg-canvas p-3 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-[11px]">
                <span className="font-semibold text-ok">{`${callResult.tool_name} · ${callResult.duration_ms}ms`}</span>
                <div className="flex flex-wrap items-center gap-1.5">
                  {callResult.redacted ? <SemanticBadge kind="reconfirm" labelOverride="DLP Redacted" /> : null}
                  <code title={callResult.receipt_sha256} className="max-w-[260px] truncate rounded-xs border border-border bg-chrome px-1.5 py-0.5 text-fg">{callResult.receipt_sha256}</code>
                </div>
              </div>
              <pre className="overflow-x-auto rounded-xs border border-border bg-code p-2.5 font-mono text-[11px] text-fg">
                <code>{JSON.stringify(callResult.result, null, 2)}</code>
              </pre>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
