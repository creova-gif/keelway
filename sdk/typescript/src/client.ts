/**
 * Keelway Client SDK — Zero-Dependency TypeScript Interface for Keelway Unified AI Platform.
 *
 * Uses native Web Fetch, ReadableStream, TextDecoder, and AbortSignal so a single
 * build runs identically across Node 20+, Bun, Deno, Cloudflare Workers, and browsers.
 */

import { ConnectionError, KeelwayError, mapHttpError } from "./errors.js";
import { PlatformNamespace } from "./platform.js";
import type {
  AdaptRecipeRequest,
  ChatCompletionCreateRequest,
  ChatCompletionResponse,
  ChatCompletionStreamRequest,
  ChatMessage,
  ChatStreamChunk,
  CompileModelfileRequest,
  CompileModelfileResponse,
  FetchLike,
  GovernanceAuditResponse,
  GovernanceDecisionResponse,
  GovernanceEvaluateRequest,
  IssuedKeyResponse,
  IssueKeyRequest,
  KeelwayClientOptions,
  LoadOpenCoreModelRequest,
  ModelListResponse,
  ModelsListParams,
  OpenCoreAdaptersResponse,
  OpenCoreStatusResponse,
  OpenCoreWeightManifest,
  RequestOptions,
  ResponseCreateRequest,
  ResponseObject,
  ResponseStreamEvent,
  ResponseStreamRequest,
  RoutingDecisionsResponse,
  RoutingExplainRequest,
  RoutingExplainResponse,
  SwarmEvaluateRequest,
  SwarmEvaluateResponse,
  TenantPolicy,
  TenantPolicyUpsertRequest,
  UsageSummary,
} from "./types.js";

const DEFAULT_BASE_URL = "http://127.0.0.1:7420";
const DEFAULT_TIMEOUT_MS = 30_000;
const SDK_USER_AGENT = "@keelway/sdk/1.0.0";

function normalizeMessages(messages: string | ChatMessage[]): ChatMessage[] {
  if (typeof messages === "string") {
    return [{ role: "user", content: messages }];
  }
  return messages;
}

function buildChatPayload(
  req: ChatCompletionCreateRequest | ChatCompletionStreamRequest,
  stream: boolean,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    messages: normalizeMessages(req.messages),
    temperature: req.temperature ?? 0.2,
    max_tokens: req.max_tokens ?? 4096,
    privacy_level: req.privacy_level ?? "standard",
    stream,
  };
  if (req.model !== undefined) {
    payload.model = req.model;
  }
  if (req.response_format !== undefined) {
    payload.response_format = req.response_format;
  }
  if (req.required_capabilities !== undefined) {
    payload.required_capabilities = req.required_capabilities;
  }
  if (req.max_cost_usd !== undefined) {
    payload.max_cost_usd = req.max_cost_usd;
  }
  return payload;
}

function buildResponsePayload(
  req: ResponseCreateRequest | ResponseStreamRequest,
  stream: boolean,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    input: req.input,
    speculative: req.speculative ?? false,
    privacy_level: req.privacy_level ?? "standard",
    stream,
  };
  if (req.model !== undefined) {
    payload.model = req.model;
  }
  if (req.instructions !== undefined) {
    payload.instructions = req.instructions;
  }
  if (req.previous_response_id !== undefined) {
    payload.previous_response_id = req.previous_response_id;
  }
  if (req.temperature !== undefined) {
    payload.temperature = req.temperature;
  }
  if (req.max_output_tokens !== undefined) {
    payload.max_output_tokens = req.max_output_tokens;
  }
  if (req.text !== undefined) {
    payload.text = req.text;
  }
  if (req.store !== undefined) {
    payload.store = req.store;
  }
  if (req.required_capabilities !== undefined) {
    payload.required_capabilities = req.required_capabilities;
  }
  if (req.max_cost_usd !== undefined) {
    payload.max_cost_usd = req.max_cost_usd;
  }
  if (req.draft_model !== undefined) {
    payload.draft_model = req.draft_model;
  }
  return payload;
}

interface ParsedSseFrame {
  event?: string;
  data: string;
}

/**
 * Chunk-boundary-safe Server-Sent Events (SSE) parser over a Web `ReadableStream`.
 * Handles arbitrary UTF-8 multi-byte splits, CRLF/LF line endings split across chunks,
 * `: keep-alive` comments, `event:` headers, and clean termination on `[DONE]`.
 */
async function* parseSseFrames(
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
    if (!joined) {
      return null;
    }
    if (joined === "[DONE]") {
      return "DONE";
    }
    return { event: evt, data: joined };
  };

  const processLine = (rawLine: string): ParsedSseFrame | "DONE" | null => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    if (line === "") {
      return flushFrame();
    }
    if (line.startsWith(":")) {
      return null;
    }
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
      return null;
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
      if (value) {
        buffer += decoder.decode(value, { stream: true });
      }
      let newlineIdx = buffer.indexOf("\n");
      while (newlineIdx !== -1) {
        const rawLine = buffer.slice(0, newlineIdx);
        buffer = buffer.slice(newlineIdx + 1);
        const result = processLine(rawLine);
        if (result === "DONE") {
          await reader.cancel().catch(() => undefined);
          return;
        }
        if (result !== null) {
          yield result;
        }
        newlineIdx = buffer.indexOf("\n");
      }
    }

    if (buffer.length > 0) {
      const trailingResult = processLine(buffer);
      if (trailingResult === "DONE") {
        return;
      }
      if (trailingResult !== null) {
        yield trailingResult;
      }
    }
    const finalFrame = flushFrame();
    if (finalFrame !== null && finalFrame !== "DONE") {
      yield finalFrame;
    }
  } finally {
    reader.releaseLock();
  }
}

interface TimeoutControllerHandle {
  signal: AbortSignal;
  didTimeout: () => boolean;
  cleanup: () => void;
}

function createTimeoutController(
  timeoutMs: number,
  externalSignal?: AbortSignal,
): TimeoutControllerHandle {
  const controller = new AbortController();
  let timedOut = false;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const onExternalAbort = () => {
    controller.abort(externalSignal?.reason ?? new DOMException("Aborted", "AbortError"));
  };

  if (externalSignal) {
    if (externalSignal.aborted) {
      onExternalAbort();
    } else {
      externalSignal.addEventListener("abort", onExternalAbort, { once: true });
    }
  }

  if (timeoutMs > 0 && !controller.signal.aborted) {
    timer = setTimeout(() => {
      timedOut = true;
      controller.abort(new DOMException(`Request timed out after ${timeoutMs}ms`, "TimeoutError"));
    }, timeoutMs);
  }

  const cleanup = () => {
    if (timer !== undefined) {
      clearTimeout(timer);
      timer = undefined;
    }
    if (externalSignal) {
      externalSignal.removeEventListener("abort", onExternalAbort);
    }
  };

  return {
    signal: controller.signal,
    didTimeout: () => timedOut,
    cleanup,
  };
}

/**
 * Official Keelway Platform Client (`@keelway/sdk` v1.0.0).
 */
export class KeelwayClient {
  public readonly baseUrl: string;
  public readonly timeoutMs: number;
  private readonly apiKey?: string;
  private readonly fetchImpl: FetchLike;
  private readonly defaultHeaders: Record<string, string>;

  public readonly models: {
    list: (params?: ModelsListParams, options?: RequestOptions) => Promise<ModelListResponse>;
  };

  public readonly usage: {
    get: (options?: RequestOptions) => Promise<UsageSummary>;
  };

  public readonly chat: {
    completions: {
      create: (
        request: ChatCompletionCreateRequest,
        options?: RequestOptions,
      ) => Promise<ChatCompletionResponse>;
      stream: (
        request: ChatCompletionStreamRequest,
        options?: RequestOptions,
      ) => AsyncGenerator<ChatStreamChunk, void, unknown>;
    };
  };

  public readonly responses: {
    create: (request: ResponseCreateRequest, options?: RequestOptions) => Promise<ResponseObject>;
    get: (responseId: string, options?: RequestOptions) => Promise<ResponseObject>;
    stream: (
      request: ResponseStreamRequest,
      options?: RequestOptions,
    ) => AsyncGenerator<ResponseStreamEvent, void, unknown>;
  };

  public readonly routing: {
    explain: (
      request: RoutingExplainRequest,
      options?: RequestOptions,
    ) => Promise<RoutingExplainResponse>;
    decisions: (
      params?: { limit?: number },
      options?: RequestOptions,
    ) => Promise<RoutingDecisionsResponse>;
  };

  public readonly opencore: {
    status: (options?: RequestOptions) => Promise<OpenCoreStatusResponse>;
    weights: (options?: RequestOptions) => Promise<OpenCoreWeightManifest[]>;
    compileModelfile: (
      req: CompileModelfileRequest,
      options?: RequestOptions,
    ) => Promise<CompileModelfileResponse>;
    adapters: (
      params?: { base_model_id?: string },
      options?: RequestOptions,
    ) => Promise<OpenCoreAdaptersResponse>;
    loadModel: (
      req: LoadOpenCoreModelRequest,
      options?: RequestOptions,
    ) => Promise<Record<string, unknown>>;
    unloadModel: (
      modelId: string,
      options?: RequestOptions,
    ) => Promise<Record<string, unknown>>;
    adaptRecipe: (
      req: AdaptRecipeRequest,
      options?: RequestOptions,
    ) => Promise<Record<string, unknown>>;
  };

  public readonly governance: {
    upsertPolicy: (
      policy: TenantPolicyUpsertRequest,
      options?: RequestOptions,
    ) => Promise<TenantPolicy>;
    getPolicy: (tenantId: string, options?: RequestOptions) => Promise<TenantPolicy>;
    listPolicies: (options?: RequestOptions) => Promise<TenantPolicy[]>;
    issueKey: (req: IssueKeyRequest, options?: RequestOptions) => Promise<IssuedKeyResponse>;
    verifyAudit: (
      params?: { tenant_id?: string; limit?: number },
      options?: RequestOptions,
    ) => Promise<GovernanceAuditResponse>;
    evaluate: (
      req: GovernanceEvaluateRequest,
      options?: RequestOptions,
    ) => Promise<GovernanceDecisionResponse>;
  };

  public readonly swarm: {
    evaluate: (
      req: SwarmEvaluateRequest,
      options?: RequestOptions,
    ) => Promise<SwarmEvaluateResponse>;
  };

  public readonly platform: PlatformNamespace;

  constructor(options: KeelwayClientOptions = {}) {
    const rawBase = options.baseUrl ?? DEFAULT_BASE_URL;
    this.baseUrl = rawBase.replace(/\/+$/, "");
    this.apiKey = options.apiKey ?? options.token;
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.defaultHeaders = { ...(options.defaultHeaders ?? {}) };

    if (options.fetchImpl) {
      this.fetchImpl = options.fetchImpl;
    } else if (typeof globalThis.fetch === "function") {
      this.fetchImpl = globalThis.fetch.bind(globalThis);
    } else {
      throw new KeelwayError(
        "Global fetch API is unavailable; provide options.fetchImpl.",
        "CONFIGURATION_ERROR",
      );
    }

    this.models = {
      list: (params, opts) => {
        const query: Record<string, string> = {};
        if (params?.category !== undefined) query.category = params.category;
        if (params?.provider !== undefined) query.provider = params.provider;
        if (params?.capability !== undefined) query.capability = params.capability;
        return this.requestJson<ModelListResponse>("GET", "/v1/models", {
          query,
          options: opts,
        });
      },
    };

    this.usage = {
      get: (opts) => this.requestJson<UsageSummary>("GET", "/v1/usage", { options: opts }),
    };

    this.chat = {
      completions: {
        create: (req, opts) =>
          this.requestJson<ChatCompletionResponse>("POST", "/v1/chat/completions", {
            body: buildChatPayload(req, false),
            options: opts,
          }),
        stream: (req, opts) => this.streamChatCompletions(req, opts),
      },
    };

    this.responses = {
      create: (req, opts) =>
        this.requestJson<ResponseObject>("POST", "/v1/responses", {
          body: buildResponsePayload(req, false),
          options: opts,
        }),
      get: (responseId, opts) =>
        this.requestJson<ResponseObject>(
          "GET",
          `/v1/responses/${encodeURIComponent(responseId)}`,
          { options: opts },
        ),
      stream: (req, opts) => this.streamResponses(req, opts),
    };

    this.routing = {
      explain: (req, opts) => {
        const body: Record<string, unknown> = {
          privacy_level: req.privacy_level ?? "standard",
        };
        if (req.messages !== undefined) {
          body.messages = normalizeMessages(req.messages);
        }
        if (req.prompt !== undefined) {
          body.prompt = req.prompt;
        }
        if (req.model !== undefined) {
          body.model = req.model;
        }
        if (req.max_tokens !== undefined) {
          body.max_tokens = req.max_tokens;
        }
        if (req.required_capabilities !== undefined) {
          body.required_capabilities = req.required_capabilities;
        }
        if (req.max_cost_usd !== undefined) {
          body.max_cost_usd = req.max_cost_usd;
        }
        if (req.preferred_provider !== undefined) {
          body.preferred_provider = req.preferred_provider;
        }
        if (req.category_preference !== undefined) {
          body.category_preference = req.category_preference;
        }
        if (req.endpoint_url !== undefined) {
          body.endpoint_url = req.endpoint_url;
        }
        return this.requestJson<RoutingExplainResponse>("POST", "/v1/routing/explain", {
          body,
          options: opts,
        });
      },
      decisions: (params, opts) => {
        const query: Record<string, string> = {};
        if (params?.limit !== undefined) {
          query.limit = String(params.limit);
        }
        return this.requestJson<RoutingDecisionsResponse>("GET", "/v1/routing/decisions", {
          query,
          options: opts,
        });
      },
    };

    this.opencore = {
      status: (opts) =>
        this.requestJson<OpenCoreStatusResponse>("GET", "/v1/opencore/status", {
          options: opts,
        }),
      weights: (opts) =>
        this.requestJson<OpenCoreWeightManifest[]>("GET", "/v1/opencore/weights", {
          options: opts,
        }),
      compileModelfile: (req, opts) => {
        const body: Record<string, unknown> = {
          model_id: req.model_id ?? "keelway-core:7b",
          quantization: req.quantization ?? "q4_k_m",
        };
        if (req.base_source !== undefined) body.base_source = req.base_source;
        if (req.adapter_id !== undefined) body.adapter_id = req.adapter_id;
        if (req.temperature !== undefined) body.temperature = req.temperature;
        if (req.top_p !== undefined) body.top_p = req.top_p;
        if (req.num_ctx !== undefined) body.num_ctx = req.num_ctx;
        if (req.modelfile_path !== undefined) body.modelfile_path = req.modelfile_path;
        return this.requestJson<CompileModelfileResponse>("POST", "/v1/opencore/modelfile", {
          body,
          options: opts,
        });
      },
      adapters: (params, opts) => {
        const query: Record<string, string> = {};
        if (params?.base_model_id !== undefined) {
          query.base_model_id = params.base_model_id;
        }
        return this.requestJson<OpenCoreAdaptersResponse>("GET", "/v1/opencore/adapters", {
          query,
          options: opts,
        });
      },
      loadModel: (req, opts) => {
        const body: Record<string, unknown> = {
          model_id: req.model_id,
          backend: req.backend ?? "mock",
        };
        if (req.quantization !== undefined) body.quantization = req.quantization;
        if (req.base_model_override !== undefined) {
          body.base_model_override = req.base_model_override;
        }
        return this.requestJson<Record<string, unknown>>("POST", "/v1/opencore/models/load", {
          body,
          options: opts,
        });
      },
      unloadModel: (modelId, opts) =>
        this.requestJson<Record<string, unknown>>("POST", "/v1/opencore/models/unload", {
          body: { model_id: modelId },
          options: opts,
        }),
      adaptRecipe: (req, opts) => {
        const body: Record<string, unknown> = {
          base_model_id: req.base_model_id ?? "keelway-core:7b",
          task: req.task ?? "multilingual_localization",
        };
        if (req.target_languages !== undefined) {
          body.target_languages = req.target_languages.map((lang) => lang.toLowerCase());
        }
        return this.requestJson<Record<string, unknown>>("POST", "/v1/opencore/adapt/recipe", {
          body,
          options: opts,
        });
      },
    };

    this.governance = {
      upsertPolicy: async (policy, opts) => {
        try {
          return await this.requestJson<TenantPolicy>("POST", "/v1/governance/tenants", {
            body: { ...policy },
            options: opts,
          });
        } catch (err) {
          if (err instanceof KeelwayError && err.status === 409) {
            const { tenant_id, ...patchBody } = policy;
            return await this.requestJson<TenantPolicy>(
              "PATCH",
              `/v1/governance/tenants/${encodeURIComponent(tenant_id)}`,
              {
                body: patchBody,
                options: opts,
              },
            );
          }
          throw err;
        }
      },
      getPolicy: (tenantId, opts) =>
        this.requestJson<TenantPolicy>(
          "GET",
          `/v1/governance/tenants/${encodeURIComponent(tenantId)}`,
          { options: opts },
        ),
      listPolicies: (opts) =>
        this.requestJson<TenantPolicy[]>("GET", "/v1/governance/tenants", { options: opts }),
      issueKey: (req, opts) => {
        const body: Record<string, unknown> = {
          tenant_id: req.tenant_id,
          name: req.name,
          scopes: req.scopes ?? ["models:read", "inference:write"],
        };
        if (req.expires_at !== undefined) {
          body.expires_at = req.expires_at;
        }
        return this.requestJson<IssuedKeyResponse>("POST", "/v1/governance/keys", {
          body,
          options: opts,
        });
      },
      verifyAudit: (params, opts) => {
        const query: Record<string, string> = {};
        if (params?.tenant_id !== undefined) query.tenant_id = params.tenant_id;
        if (params?.limit !== undefined) query.limit = String(params.limit);
        return this.requestJson<GovernanceAuditResponse>("GET", "/v1/governance/audit", {
          query,
          options: opts,
        });
      },
      evaluate: (req, opts) =>
        this.requestJson<GovernanceDecisionResponse>("POST", "/v1/governance/evaluate", {
          body: { ...req },
          options: opts,
        }),
    };

    this.swarm = {
      evaluate: (req, opts) => {
        const body: Record<string, unknown> = {
          rounds: req.rounds ?? 2,
          mode: req.mode ?? "mock",
        };
        if (req.seed_text !== undefined) body.seed_text = req.seed_text;
        if (req.simulation_goal !== undefined) body.simulation_goal = req.simulation_goal;
        if (req.entities_spec !== undefined) body.entities_spec = req.entities_spec;
        if (req.injected_event !== undefined) body.injected_event = req.injected_event;
        if (req.frontier_model !== undefined) body.frontier_model = req.frontier_model;
        if (req.opencore_model !== undefined) body.opencore_model = req.opencore_model;
        if (req.draft_model !== undefined) body.draft_model = req.draft_model;
        return this.requestJson<SwarmEvaluateResponse>("POST", "/v1/eval/swarm", {
          body,
          options: opts,
        });
      },
    };

    this.platform = new PlatformNamespace((method, path, params) =>
      this.requestJson(method, path, params),
    );
  }

  /**
   * Probe Keelway daemon health (`/health`).
   */
  public async health(options?: RequestOptions): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>("GET", "/health", { options });
  }

  private buildUrl(path: string, query?: Record<string, string>): string {
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    const full = `${this.baseUrl}${normalizedPath}`;
    if (!query || Object.keys(query).length === 0) {
      return full;
    }
    const search = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined) {
        search.set(k, v);
      }
    }
    const qs = search.toString();
    return qs ? `${full}?${qs}` : full;
  }

  private buildHeaders(
    extraHeaders?: Record<string, string>,
    hasJsonBody = false,
    acceptSse = false,
  ): Record<string, string> {
    const headers: Record<string, string> = {
      "User-Agent": SDK_USER_AGENT,
      Accept: acceptSse ? "text/event-stream" : "application/json",
      ...this.defaultHeaders,
      ...(extraHeaders ?? {}),
    };
    if (hasJsonBody && !headers["Content-Type"] && !headers["content-type"]) {
      headers["Content-Type"] = "application/json";
    }
    if (this.apiKey && !headers.Authorization && !headers.authorization) {
      headers.Authorization = `Bearer ${this.apiKey}`;
    }
    return headers;
  }

  private mapTransportException(
    err: unknown,
    handle: TimeoutControllerHandle,
    effectiveTimeoutMs: number,
  ): never {
    if (err instanceof KeelwayError) {
      throw err;
    }
    if (handle.didTimeout()) {
      throw new ConnectionError(
        `Keelway daemon request timed out after ${effectiveTimeoutMs}ms`,
        { timeoutMs: effectiveTimeoutMs },
      );
    }
    const msg = err instanceof Error ? err.message : String(err);
    if (
      (err instanceof Error && (err.name === "AbortError" || err.name === "TimeoutError")) ||
      msg.toLowerCase().includes("aborted") ||
      msg.toLowerCase().includes("timed out")
    ) {
      throw new ConnectionError(`Keelway daemon request aborted: ${msg}`);
    }
    throw new ConnectionError(`Failed to connect to Keelway daemon at ${this.baseUrl}: ${msg}`);
  }

  private async requestJson<T>(
    method: string,
    path: string,
    params: {
      query?: Record<string, string>;
      body?: Record<string, unknown>;
      options?: RequestOptions;
    } = {},
  ): Promise<T> {
    const url = this.buildUrl(path, params.query);
    const hasBody = params.body !== undefined;
    const headers = this.buildHeaders(params.options?.headers, hasBody, false);
    const effectiveTimeoutMs = params.options?.timeoutMs ?? this.timeoutMs;
    const handle = createTimeoutController(effectiveTimeoutMs, params.options?.signal);

    try {
      const response = await this.fetchImpl(url, {
        method,
        headers,
        body: hasBody ? JSON.stringify(params.body) : undefined,
        signal: handle.signal,
      });

      const rawText = await response.text();
      if (!response.ok) {
        let extraDetails: Record<string, unknown> | undefined;
        try {
          const parsedErr: unknown = JSON.parse(rawText);
          if (parsedErr && typeof parsedErr === "object") {
            const detailVal = (parsedErr as Record<string, unknown>).detail;
            if (detailVal && typeof detailVal === "object" && !Array.isArray(detailVal)) {
              extraDetails = { ...(detailVal as Record<string, unknown>), status: response.status };
            }
          }
        } catch {
          // non-JSON error payload
        }
        throw mapHttpError(response.status, rawText, extraDetails);
      }
      if (!rawText) {
        return undefined as T;
      }
      try {
        return JSON.parse(rawText) as T;
      } catch {
        return rawText as unknown as T;
      }
    } catch (err) {
      return this.mapTransportException(err, handle, effectiveTimeoutMs);
    } finally {
      handle.cleanup();
    }
  }

  private async *streamChatCompletions(
    request: ChatCompletionStreamRequest,
    options?: RequestOptions,
  ): AsyncGenerator<ChatStreamChunk, void, unknown> {
    const url = this.buildUrl("/v1/chat/completions");
    const headers = this.buildHeaders(options?.headers, true, true);
    const effectiveTimeoutMs = options?.timeoutMs ?? this.timeoutMs;
    const handle = createTimeoutController(effectiveTimeoutMs, options?.signal);

    try {
      const response = await this.fetchImpl(url, {
        method: "POST",
        headers,
        body: JSON.stringify(buildChatPayload(request, true)),
        signal: handle.signal,
      });

      if (!response.ok) {
        const errBody = await response.text();
        throw mapHttpError(response.status, errBody);
      }
      if (!response.body) {
        return;
      }

      for await (const frame of parseSseFrames(response.body)) {
        const parsed = JSON.parse(frame.data) as ChatStreamChunk;
        yield parsed;
      }
    } catch (err) {
      this.mapTransportException(err, handle, effectiveTimeoutMs);
    } finally {
      handle.cleanup();
    }
  }

  private async *streamResponses(
    request: ResponseStreamRequest,
    options?: RequestOptions,
  ): AsyncGenerator<ResponseStreamEvent, void, unknown> {
    const url = this.buildUrl("/v1/responses");
    const headers = this.buildHeaders(options?.headers, true, true);
    const effectiveTimeoutMs = options?.timeoutMs ?? this.timeoutMs;
    const handle = createTimeoutController(effectiveTimeoutMs, options?.signal);

    try {
      const response = await this.fetchImpl(url, {
        method: "POST",
        headers,
        body: JSON.stringify(buildResponsePayload(request, true)),
        signal: handle.signal,
      });

      if (!response.ok) {
        const errBody = await response.text();
        throw mapHttpError(response.status, errBody);
      }
      if (!response.body) {
        return;
      }

      for await (const frame of parseSseFrames(response.body)) {
        const parsed = JSON.parse(frame.data) as ResponseStreamEvent;
        if (frame.event && !parsed.event) {
          parsed.event = frame.event;
        }
        yield parsed;
      }
    } catch (err) {
      this.mapTransportException(err, handle, effectiveTimeoutMs);
    } finally {
      handle.cleanup();
    }
  }
}
