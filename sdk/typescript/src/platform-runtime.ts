/**
 * Keelway Official TypeScript SDK — Phase 4 & Phase 5 Platform Runtime Operations + SSE Parser.
 * Zero external dependencies: uses Web `ReadableStream`, `TextDecoder`, and `TextEncoder`.
 */

import type { PlatformJsonRequester } from "./platform.js";
import type * as PT from "./platform-types.js";
import type { RequestOptions } from "./types.js";

export interface ParsedSseFrame {
  event?: string;
  data: string;
}

export type PlatformSseRequester = (
  method: string,
  path: string,
  params?: { query?: Record<string, string>; body?: Record<string, unknown>; options?: RequestOptions },
) => AsyncGenerator<ParsedSseFrame, void, unknown>;

function seg(value: string, fieldName: string): string {
  const clean = value.trim();
  if (!clean) throw new Error(`${fieldName} must be non-empty.`);
  return encodeURIComponent(clean);
}

/**
 * Chunk-boundary-safe Server-Sent Events (SSE) parser over a Web `ReadableStream`.
 * Handles UTF-8 multi-byte splits, CRLF/LF line splits, `: keep-alive` comments, and `[DONE]`.
 */
export async function* parseSseFrames(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<ParsedSseFrame, void, unknown> {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let currentEvent: string | undefined;
  let dataLines: string[] = [];

  const flushFrame = (): ParsedSseFrame | "DONE" | null => {
    if (dataLines.length === 0) {
      currentEvent = undefined;
      return null;
    }
    const joined = dataLines.join("\n").trim();
    const evt = currentEvent;
    currentEvent = undefined;
    dataLines = [];
    if (!joined) return null;
    if (joined === "[DONE]") return "DONE";
    return { event: evt, data: joined };
  };

  const processLine = (rawLine: string): ParsedSseFrame | "DONE" | null => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    if (line === "") return flushFrame();
    if (line.startsWith(":")) return null;
    if (line.startsWith("event:")) {
      currentEvent = line.slice(6).trim();
      return null;
    }
    if (line.startsWith("data:")) {
      const value = line.slice(5).trimStart();
      if (value.trim() === "[DONE]" && dataLines.length === 0) {
        currentEvent = undefined;
        return "DONE";
      }
      dataLines.push(value);
    }
    return null;
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        buffer += decoder.decode();
        break;
      }
      if (value) buffer += decoder.decode(value, { stream: true });
      let newlineIdx = buffer.indexOf("\n");
      while (newlineIdx !== -1) {
        const rawLine = buffer.slice(0, newlineIdx);
        buffer = buffer.slice(newlineIdx + 1);
        const result = processLine(rawLine);
        if (result === "DONE") {
          await reader.cancel().catch(() => undefined);
          return;
        }
        if (result !== null) yield result;
        newlineIdx = buffer.indexOf("\n");
      }
    }
    if (buffer.length > 0) {
      const trailing = processLine(buffer);
      if (trailing === "DONE") return;
      if (trailing !== null) yield trailing;
    }
    const finalFrame = flushFrame();
    if (finalFrame !== null && finalFrame !== "DONE") yield finalFrame;
  } finally {
    reader.releaseLock();
  }
}

function wsId(params?: PT.PlatformOverviewParams | string): string {
  return typeof params === "string" ? (params || "default") : (params?.workspace_id ?? "default");
}

function docBody(req: PT.UpsertDocRequest): Record<string, unknown> {
  const body: Record<string, unknown> = {
    title: req.title,
    diataxis_kind: req.diataxis_kind ?? "reference",
    summary: req.summary ?? "",
    body: req.body ?? "",
    workspace_id: req.workspace_id ?? "default",
  };
  if (req.linked_prd_id !== undefined) body.linked_prd_id = req.linked_prd_id;
  return body;
}

export class PlatformRuntimeDelegate {
  constructor(
    private readonly requestJson: PlatformJsonRequester,
    private readonly requestSse?: PlatformSseRequester,
  ) {}

  public async listDocs(params: PT.ListDocsParams | string = {}, options?: RequestOptions): Promise<PT.PlatformDocListResponse> {
    const query: Record<string, string> = { workspace_id: wsId(params) };
    const kind = typeof params === "string" ? undefined : params.diataxis_kind;
    if (kind !== undefined) query.diataxis_kind = kind;
    const res = await this.requestJson<PT.PlatformDocListResponse>("GET", "/v1/platform/docs", { query, options });
    if (kind !== undefined && Array.isArray(res.docs)) {
      const docs = res.docs.filter((d) => d.diataxis_kind === kind);
      return { ...res, docs, count: docs.length };
    }
    return res;
  }

  public createDoc(req: PT.UpsertDocRequest, options?: RequestOptions): Promise<PT.PlatformDocRecord> {
    return this.requestJson("POST", "/v1/platform/docs", { body: docBody(req), options });
  }

  public updateDoc(docId: string, req: PT.UpsertDocRequest, options?: RequestOptions): Promise<PT.PlatformDocRecord> {
    return this.requestJson("PUT", `/v1/platform/docs/${seg(docId, "docId")}`, { body: docBody(req), options });
  }

  public updateIssue(issueId: string, patch: PT.UpdateIssueRequest, options?: RequestOptions): Promise<PT.PlatformIssueRecord> {
    const body: Record<string, unknown> = { workspace_id: patch.workspace_id ?? "default" };
    for (const k of ["title", "status", "priority", "sprint_id", "prd_id", "assignee_agent", "description", "dependencies"] as const) {
      if (patch[k] !== undefined) body[k] = patch[k];
    }
    return this.requestJson("PATCH", `/v1/platform/pm/issues/${seg(issueId, "issueId")}`, {
      query: patch.workspace_id ? { workspace_id: patch.workspace_id } : undefined,
      body,
      options,
    });
  }

  public listFeedback(params: PT.PlatformOverviewParams | string = {}, options?: RequestOptions): Promise<PT.PlatformFeedbackListResponse> {
    return this.requestJson("GET", "/v1/platform/product/feedback", { query: { workspace_id: wsId(params) }, options });
  }

  public createFeedback(req: PT.CreateFeedbackRequest, options?: RequestOptions): Promise<PT.PlatformFeedbackRecord> {
    const body: Record<string, unknown> = {
      persona: req.persona,
      quote: req.quote,
      impact_score: req.impact_score ?? 8.5,
      workspace_id: req.workspace_id ?? "default",
    };
    if (req.linked_prd_id !== undefined) body.linked_prd_id = req.linked_prd_id;
    return this.requestJson("POST", "/v1/platform/product/feedback", { body, options });
  }

  public scanWorkspaceSecurity(req: PT.WorkspaceSecurityScanRequest, options?: RequestOptions): Promise<PT.WorkspaceSecurityScanReport> {
    const content = req.content ?? req.snippet ?? "";
    const target = req.target_name ?? req.target_path ?? "workspace-snippet";
    const body: Record<string, unknown> = {
      target_name: target,
      target_path: target,
      content,
      snippet: content,
      workspace_id: req.workspace_id ?? "default",
    };
    if (req.write_paths !== undefined) body.write_paths = req.write_paths;
    return this.requestJson("POST", "/v1/platform/security/scan", { body, options });
  }

  public listWorkspaces(options?: RequestOptions): Promise<PT.PlatformWorkspaceListResponse> {
    return this.requestJson("GET", "/v1/platform/workspaces", { options });
  }

  public createWorkspace(req: PT.CreateWorkspaceRequest, options?: RequestOptions): Promise<PT.PlatformWorkspaceRecord> {
    const body: Record<string, unknown> = {
      name: req.name,
      branch: req.branch ?? "main",
      isolation_mode: req.isolation_mode ?? "seatbelt_local",
    };
    const resolvedId = req.id ?? req.workspace_id;
    if (resolvedId !== undefined) body.id = resolvedId;
    if (req.description !== undefined) body.description = req.description;
    return this.requestJson("POST", "/v1/platform/workspaces", { body, options });
  }

  public listRbacMembers(params: PT.PlatformOverviewParams | string = {}, options?: RequestOptions): Promise<PT.RbacMemberListResponse> {
    return this.requestJson("GET", "/v1/platform/rbac/members", { query: { workspace_id: wsId(params) }, options });
  }

  public upsertRbacMember(req: PT.UpsertRbacMemberRequest, options?: RequestOptions): Promise<PT.RbacMemberRecord> {
    const body: Record<string, unknown> = { workspace_id: req.workspace_id ?? "default", actor_id: req.actor_id, role: req.role };
    if (req.display_name !== undefined) body.display_name = req.display_name;
    return this.requestJson("POST", "/v1/platform/rbac/members", { body, options });
  }

  public checkRbac(req: PT.CheckRbacRequest, options?: RequestOptions): Promise<PT.CheckRbacResponse> {
    const body: Record<string, unknown> = { workspace_id: req.workspace_id ?? "default", permission: req.permission };
    if (req.actor_id !== undefined) body.actor_id = req.actor_id;
    if (req.role !== undefined) body.role = req.role;
    return this.requestJson("POST", "/v1/platform/rbac/check", { body, options });
  }

  public listSecrets(params: PT.ListSecretsParams | string = {}, options?: RequestOptions): Promise<PT.VaultSecretListResponse> {
    const query: Record<string, string> = { workspace_id: typeof params === "string" ? (params || "default") : (params.workspace_id ?? "default") };
    if (typeof params !== "string" && params.namespace !== undefined) query.namespace = params.namespace;
    return this.requestJson("GET", "/v1/platform/vault/secrets", { query, options });
  }

  public putSecret(req: PT.PutSecretRequest, options?: RequestOptions): Promise<PT.VaultSecretMetadata> {
    const body: Record<string, unknown> = {
      name: req.name,
      secret_value: req.secret_value,
      workspace_id: req.workspace_id ?? "default",
      namespace: req.namespace ?? "byom",
    };
    if (req.description !== undefined) body.description = req.description;
    return this.requestJson("POST", "/v1/platform/vault/secrets", { body, options });
  }

  public rotateSecret(name: string, req: PT.RotateSecretRequest | string, options?: RequestOptions): Promise<PT.VaultSecretMetadata> {
    const body: Record<string, unknown> = typeof req === "string"
      ? { secret_value: req, workspace_id: "default" }
      : { secret_value: req.secret_value, workspace_id: req.workspace_id ?? "default", ...(req.namespace ? { namespace: req.namespace } : {}) };
    return this.requestJson("POST", `/v1/platform/vault/secrets/${seg(name, "name")}/rotate`, { body, options });
  }

  public deleteSecret(name: string, params: PT.PlatformOverviewParams | string = {}, options?: RequestOptions): Promise<PT.DeleteSecretResponse> {
    return this.requestJson("DELETE", `/v1/platform/vault/secrets/${seg(name, "name")}`, { query: { workspace_id: wsId(params) }, options });
  }

  public listWebhooks(params: PT.PlatformOverviewParams | string = {}, options?: RequestOptions): Promise<PT.WebhookListResponse> {
    return this.requestJson("GET", "/v1/platform/webhooks", { query: { workspace_id: wsId(params) }, options });
  }

  public createWebhook(req: PT.CreateWebhookRequest, options?: RequestOptions): Promise<PT.WebhookRecord> {
    const body: Record<string, unknown> = {
      url: req.url,
      events: req.events ?? ["*"],
      description: req.description ?? "",
      workspace_id: req.workspace_id ?? "default",
    };
    if (req.secret !== undefined) body.secret = req.secret;
    return this.requestJson("POST", "/v1/platform/webhooks", { body, options });
  }

  public deleteWebhook(webhookId: string, params: PT.PlatformOverviewParams | string = {}, options?: RequestOptions): Promise<PT.DeleteWebhookResponse> {
    return this.requestJson("DELETE", `/v1/platform/webhooks/${seg(webhookId, "webhookId")}`, { query: { workspace_id: wsId(params) }, options });
  }

  public testWebhook(webhookId: string, req: PT.TestWebhookRequest = {}, options?: RequestOptions): Promise<PT.WebhookTestReceipt> {
    const body: Record<string, unknown> = {
      event_type: req.event_type ?? "agent.run.completed",
      workspace_id: req.workspace_id ?? "default",
    };
    if (req.payload !== undefined) body.payload = req.payload;
    return this.requestJson("POST", `/v1/platform/webhooks/${seg(webhookId, "webhookId")}/test`, { body, options });
  }

  public verifyWebhook(req: PT.VerifyWebhookRequest, options?: RequestOptions): Promise<PT.VerifyWebhookResponse> {
    const body: Record<string, unknown> = {
      payload: req.payload,
      signature: req.signature,
      secret: req.secret,
      tolerance_seconds: req.tolerance_seconds ?? 300,
    };
    if (req.timestamp !== undefined) body.timestamp = req.timestamp;
    return this.requestJson("POST", "/v1/platform/webhooks/verify", { body, options });
  }

  public startExecutionRun(req: PT.StartExecutionRunRequest, options?: RequestOptions): Promise<PT.ExecutionRunSnapshot> {
    const body: Record<string, unknown> = {
      kind: req.kind ?? "agent",
      target_id: req.target_id,
      objective: req.objective,
      workspace_id: req.workspace_id ?? "default",
      requires_p10: req.requires_p10 ?? true,
      stream: false,
    };
    if (req.actor_role !== undefined) body.actor_role = req.actor_role;
    if (req.metadata !== undefined) body.metadata = req.metadata;
    return this.requestJson("POST", "/v1/platform/execution/runs", { body, options });
  }

  public resolveExecutionP10(runId: string, req: PT.ResolveExecutionP10Request, options?: RequestOptions): Promise<PT.ExecutionRunSnapshot> {
    const body: Record<string, unknown> = {
      decision: req.decision,
      approver: req.approver ?? req.actor_id ?? "local-operator",
      reason: req.reason ?? "",
    };
    if (req.actor_id !== undefined) body.actor_id = req.actor_id;
    if (req.role !== undefined) body.role = req.role;
    if (req.workspace_id !== undefined) body.workspace_id = req.workspace_id;
    return this.requestJson("POST", `/v1/platform/execution/runs/${seg(runId, "runId")}/p10`, { body, options });
  }

  public async *streamExecutionEvents(
    runId: string,
    options?: PT.StreamExecutionEventsOptions,
  ): AsyncGenerator<Record<string, unknown>, void, unknown> {
    const path = `/v1/platform/execution/runs/${seg(runId, "runId")}/events`;
    const query = options?.workspace_id ? { workspace_id: options.workspace_id } : undefined;
    const reqOpts: RequestOptions | undefined = options
      ? { signal: options.signal, timeoutMs: options.timeoutMs, headers: options.headers }
      : undefined;

    if (this.requestSse) {
      for await (const frame of this.requestSse("GET", path, { query, options: reqOpts })) {
        const parsed = JSON.parse(frame.data) as Record<string, unknown>;
        if (frame.event && parsed.event === undefined) parsed.event = frame.event;
        yield parsed;
      }
      return;
    }

    const raw = await this.requestJson<string>("GET", path, {
      query,
      options: { ...reqOpts, headers: { Accept: "text/event-stream", ...(reqOpts?.headers ?? {}) } },
    });
    const bytes = new TextEncoder().encode(typeof raw === "string" ? raw : JSON.stringify(raw));
    const fallback = new ReadableStream<Uint8Array>({ start(c) { c.enqueue(bytes); c.close(); } });
    for await (const frame of parseSseFrames(fallback)) {
      const parsed = JSON.parse(frame.data) as Record<string, unknown>;
      if (frame.event && parsed.event === undefined) parsed.event = frame.event;
      yield parsed;
    }
  }
}
