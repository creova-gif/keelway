/**
 * Keelway 4D Studio Step-Debugger Webview Renderer & Message Dispatcher.
 * Strict `default-src 'none'` nonce CSP, zero external CDNs, zero inline browser `fetch()`.
 */
import type { BridgeBreakpointRecord, BridgeDebugSession, KeelwayBridgeClient } from "./bridgeClient.js";
export type StudioWebviewMessage = {
    readonly type: "step_over";
    readonly sessionId: string;
    readonly workspaceId?: string;
} | {
    readonly type: "step_into";
    readonly sessionId: string;
    readonly workspaceId?: string;
} | {
    readonly type: "continue";
    readonly sessionId: string;
    readonly workspaceId?: string;
} | {
    readonly type: "mutate_state";
    readonly sessionId: string;
    readonly workspaceId?: string;
    readonly statePatch: Record<string, unknown>;
} | {
    readonly type: "refresh_sessions";
    readonly workspaceId?: string;
};
export type WebviewDispatchResult = {
    readonly kind: "session";
    readonly session: BridgeDebugSession;
} | {
    readonly kind: "sessions";
    readonly sessions: BridgeDebugSession[];
};
export interface StudioWebviewState {
    readonly workspaceId: string;
    readonly workflowId: string;
    readonly controlPlaneUrl: string;
    readonly activeSession?: BridgeDebugSession | null;
    readonly sessions?: BridgeDebugSession[];
    readonly breakpoints?: BridgeBreakpointRecord[];
}
export declare function createCspNonce(length?: number): string;
export declare function renderStudioWebviewHtml(state: StudioWebviewState, nonce?: string): string;
export declare function handleWebviewMessage(msg: StudioWebviewMessage, bridgeClient: KeelwayBridgeClient): Promise<WebviewDispatchResult>;
//# sourceMappingURL=studioWebview.d.ts.map