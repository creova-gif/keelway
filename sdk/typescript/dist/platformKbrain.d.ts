/**
 * Keelway Official TypeScript SDK — Phase 10 KBrain Hybrid BM25/N-Gram Memory
 * & KHub Air-Gapped Skill Mirror Verification.
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */
import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";
export type KbrainScope = "local_session" | "project" | "team" | "org" | (string & {});
export type KbrainFactStatus = "proposed" | "approved" | "conflict" | "rejected" | "superseded" | "corrected" | "withdrawn" | (string & {});
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
export declare class PlatformKbrainDelegate {
    private readonly requestJson;
    constructor(requestJson: PlatformJsonRequester);
    recordKbrainFact(req: RecordKbrainFactRequest, options?: RequestOptions): Promise<KbrainFactRecord>;
    searchKbrainFacts(params?: SearchKbrainFactsParams | string, options?: RequestOptions): Promise<SearchKbrainFactsResponse>;
    resolveKbrainFact(factId: string, req: ResolveKbrainFactRequest | KbrainFactResolution, options?: RequestOptions): Promise<KbrainFactRecord>;
    listKhubSkills(params?: ListKhubSkillsParams | string, options?: RequestOptions): Promise<KhubSkillListResponse>;
    verifyKhubMirror(req?: VerifyKhubMirrorRequest | string[], options?: RequestOptions): Promise<VerifyKhubMirrorResponse>;
}
//# sourceMappingURL=platformKbrain.d.ts.map