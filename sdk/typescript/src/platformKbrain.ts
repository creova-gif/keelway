/**
 * Keelway Official TypeScript SDK — Phase 10 KBrain Hybrid BM25/N-Gram Memory
 * & KHub Air-Gapped Skill Mirror Verification.
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */

import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";

export type KbrainScope = "local_session" | "project" | "team" | "org" | (string & {});

export type KbrainFactStatus =
  | "proposed"
  | "approved"
  | "conflict"
  | "rejected"
  | "superseded"
  | "corrected"
  | "withdrawn"
  | (string & {});

export type KbrainFactResolution = "approve" | "reject" | (string & {});

export interface RecordKbrainFactRequest {
  workspace_id?: string;
  key: string;
  statement: string;
  scope?: KbrainScope;
  provenance_uri?: string;
  tags?: string[];
  auto_approve?: boolean;
}

export interface KbrainFactRecord {
  id: string;
  workspace_id: string;
  key: string;
  statement: string;
  scope: KbrainScope;
  status: KbrainFactStatus;
  conflict_with_fact_id?: string | null;
  provenance_uri: string;
  tags: string[];
  created_by?: string;
  fact_sha256: string;
  created_at: string;
  [key: string]: unknown;
}

export interface SearchKbrainFactsParams {
  workspace_id?: string;
  query?: string;
  max_scope?: KbrainScope;
  include_conflicts?: boolean;
  limit?: number;
}

export interface KbrainSearchResultItem extends KbrainFactRecord {
  score?: number;
  bm25_score?: number;
  ngram_score?: number;
}

export interface SearchKbrainFactsResponse {
  workspace_id: string;
  query: string;
  max_scope: KbrainScope;
  total_matches: number;
  results: KbrainSearchResultItem[];
  [key: string]: unknown;
}

export interface ResolveKbrainFactRequest {
  workspace_id?: string;
  resolution: KbrainFactResolution;
}

export interface ListKhubSkillsParams {
  workspace_id?: string;
}

export interface KhubSkillDescriptor {
  skill_id?: string;
  id?: string;
  name?: string;
  description?: string;
  version?: string;
  source?: string;
  source_type?: string;
  bundle_digest_sha256?: string;
  digest_sha256?: string;
  files_count?: number;
  air_gap_compliant?: boolean;
  air_gap_ready?: boolean;
  [key: string]: unknown;
}

export interface KhubSkillListResponse {
  workspace_id: string;
  total_skills: number;
  air_gap_compliant: boolean;
  catalog_digest_sha256: string;
  skills: KhubSkillDescriptor[];
  [key: string]: unknown;
}

export interface VerifyKhubMirrorRequest {
  workspace_id?: string;
  skill_ids?: string[];
}

export interface VerifyKhubMirrorResponse {
  workspace_id: string;
  verified: boolean;
  mirror_format: string;
  skills_verified: number;
  catalog_digest_sha256: string;
  verified_at: string;
  [key: string]: unknown;
}

function kbrainSeg(value: string, fieldName: string): string {
  const clean = value.trim();
  if (!clean) throw new Error(`${fieldName} must be non-empty.`);
  return encodeURIComponent(clean);
}

function kbrainWsId(params?: { workspace_id?: string } | string): string {
  return typeof params === "string" ? (params || "default") : (params?.workspace_id ?? "default");
}

export class PlatformKbrainDelegate {
  constructor(private readonly requestJson: PlatformJsonRequester) {}

  public recordKbrainFact(
    req: RecordKbrainFactRequest,
    options?: RequestOptions,
  ): Promise<KbrainFactRecord> {
    const cleanKey = req.key.trim();
    if (!cleanKey) throw new Error("key must be non-empty.");
    const cleanStatement = req.statement.trim();
    if (!cleanStatement) throw new Error("statement must be non-empty.");
    return this.requestJson("POST", "/v1/platform/kbrain/facts", {
      body: {
        workspace_id: req.workspace_id ?? "default",
        key: cleanKey,
        statement: cleanStatement,
        scope: req.scope ?? "project",
        provenance_uri: req.provenance_uri ?? "workspace",
        tags: req.tags ?? [],
        auto_approve: req.auto_approve ?? true,
      },
      options,
    });
  }

  public searchKbrainFacts(
    params: SearchKbrainFactsParams | string = {},
    options?: RequestOptions,
  ): Promise<SearchKbrainFactsResponse> {
    const isStr = typeof params === "string";
    const query: Record<string, string> = {
      workspace_id: isStr ? "default" : (params.workspace_id ?? "default"),
      query: isStr ? params : (params.query ?? ""),
      max_scope: isStr ? "org" : (params.max_scope ?? "org"),
      include_conflicts: String(isStr ? false : (params.include_conflicts ?? false)),
      limit: String(isStr ? 10 : (params.limit ?? 10)),
    };
    return this.requestJson("GET", "/v1/platform/kbrain/search", { query, options });
  }

  public resolveKbrainFact(
    factId: string,
    req: ResolveKbrainFactRequest | KbrainFactResolution,
    options?: RequestOptions,
  ): Promise<KbrainFactRecord> {
    const resolution = (typeof req === "string" ? req : req.resolution).trim();
    if (!resolution) throw new Error("resolution must be non-empty.");
    return this.requestJson("POST", `/v1/platform/kbrain/facts/${kbrainSeg(factId, "factId")}/resolve`, {
      body: {
        workspace_id: typeof req === "string" ? "default" : (req.workspace_id ?? "default"),
        resolution,
      },
      options,
    });
  }

  public listKhubSkills(
    params: ListKhubSkillsParams | string = {},
    options?: RequestOptions,
  ): Promise<KhubSkillListResponse> {
    return this.requestJson("GET", "/v1/platform/khub/skills", {
      query: { workspace_id: kbrainWsId(params) },
      options,
    });
  }

  public verifyKhubMirror(
    req: VerifyKhubMirrorRequest | string[] = {},
    options?: RequestOptions,
  ): Promise<VerifyKhubMirrorResponse> {
    const body = Array.isArray(req)
      ? { workspace_id: "default", skill_ids: req }
      : { workspace_id: req.workspace_id ?? "default", skill_ids: req.skill_ids ?? [] };
    return this.requestJson("POST", "/v1/platform/khub/mirror/verify", { body, options });
  }
}
