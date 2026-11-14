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
export type PlatformSseRequester = (method: string, path: string, params?: {
    query?: Record<string, string>;
    body?: Record<string, unknown>;
    options?: RequestOptions;
}) => AsyncGenerator<ParsedSseFrame, void, unknown>;
/**
 * Chunk-boundary-safe Server-Sent Events (SSE) parser over a Web `ReadableStream`.
 * Handles UTF-8 multi-byte splits, CRLF/LF line splits, `: keep-alive` comments, and `[DONE]`.
 */
export declare function parseSseFrames(stream: ReadableStream<Uint8Array>): AsyncGenerator<ParsedSseFrame, void, unknown>;
export declare class PlatformRuntimeDelegate {
    private readonly requestJson;
    private readonly requestSse?;
    constructor(requestJson: PlatformJsonRequester, requestSse?: PlatformSseRequester | undefined);
    listDocs(params?: PT.ListDocsParams | string, options?: RequestOptions): Promise<PT.PlatformDocListResponse>;
    createDoc(req: PT.UpsertDocRequest, options?: RequestOptions): Promise<PT.PlatformDocRecord>;
    updateDoc(docId: string, req: PT.UpsertDocRequest, options?: RequestOptions): Promise<PT.PlatformDocRecord>;
    updateIssue(issueId: string, patch: PT.UpdateIssueRequest, options?: RequestOptions): Promise<PT.PlatformIssueRecord>;
    listFeedback(params?: PT.PlatformOverviewParams | string, options?: RequestOptions): Promise<PT.PlatformFeedbackListResponse>;
    createFeedback(req: PT.CreateFeedbackRequest, options?: RequestOptions): Promise<PT.PlatformFeedbackRecord>;
    scanWorkspaceSecurity(req: PT.WorkspaceSecurityScanRequest, options?: RequestOptions): Promise<PT.WorkspaceSecurityScanReport>;
    listWorkspaces(options?: RequestOptions): Promise<PT.PlatformWorkspaceListResponse>;
    createWorkspace(req: PT.CreateWorkspaceRequest, options?: RequestOptions): Promise<PT.PlatformWorkspaceRecord>;
    listRbacMembers(params?: PT.PlatformOverviewParams | string, options?: RequestOptions): Promise<PT.RbacMemberListResponse>;
    upsertRbacMember(req: PT.UpsertRbacMemberRequest, options?: RequestOptions): Promise<PT.RbacMemberRecord>;
    checkRbac(req: PT.CheckRbacRequest, options?: RequestOptions): Promise<PT.CheckRbacResponse>;
    listSecrets(params?: PT.ListSecretsParams | string, options?: RequestOptions): Promise<PT.VaultSecretListResponse>;
    putSecret(req: PT.PutSecretRequest, options?: RequestOptions): Promise<PT.VaultSecretMetadata>;
    rotateSecret(name: string, req: PT.RotateSecretRequest | string, options?: RequestOptions): Promise<PT.VaultSecretMetadata>;
    deleteSecret(name: string, params?: PT.PlatformOverviewParams | string, options?: RequestOptions): Promise<PT.DeleteSecretResponse>;
    listWebhooks(params?: PT.PlatformOverviewParams | string, options?: RequestOptions): Promise<PT.WebhookListResponse>;
    createWebhook(req: PT.CreateWebhookRequest, options?: RequestOptions): Promise<PT.WebhookRecord>;
    deleteWebhook(webhookId: string, params?: PT.PlatformOverviewParams | string, options?: RequestOptions): Promise<PT.DeleteWebhookResponse>;
    testWebhook(webhookId: string, req?: PT.TestWebhookRequest, options?: RequestOptions): Promise<PT.WebhookTestReceipt>;
    verifyWebhook(req: PT.VerifyWebhookRequest, options?: RequestOptions): Promise<PT.VerifyWebhookResponse>;
    startExecutionRun(req: PT.StartExecutionRunRequest, options?: RequestOptions): Promise<PT.ExecutionRunSnapshot>;
    resolveExecutionP10(runId: string, req: PT.ResolveExecutionP10Request, options?: RequestOptions): Promise<PT.ExecutionRunSnapshot>;
    streamExecutionEvents(runId: string, options?: PT.StreamExecutionEventsOptions): AsyncGenerator<Record<string, unknown>, void, unknown>;
    simulatePricing(req?: PT.PricingSimulationRequest, options?: RequestOptions): Promise<Record<string, unknown>>;
}
//# sourceMappingURL=platform-runtime.d.ts.map