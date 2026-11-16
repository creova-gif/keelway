/**
 * Keelway Dev — Official VS Code & Cursor Extension Entrypoint (`activate` / `deactivate`).
 * Wires loopback Debugger Bridge, URI handler, 4D CodeLens, SecretStorage auth, and Studio Webview.
 */
import { type BridgeDebugSession, type BridgeDistillationPromotionEvaluation, type BridgeDistillationPromotionOptions, type BridgeHarnessTicketRecord, KeelwayBridgeClient } from "./bridgeClient.js";
export type { BridgeDistillationPromotionEvaluation, BridgeDistillationPromotionOptions, BridgeHarnessTicketRecord };
import { KeelwayCodeLensProvider } from "./codeLensProvider.js";
import type { VsCodeExtensionContext, VsCodeHostApi } from "./vscodeTypes.js";
export interface ActivateExtensionOptions {
    readonly hostApi?: VsCodeHostApi;
    readonly fetchImpl?: typeof fetch;
}
export interface ActivatedKeelwayExtension {
    readonly bridgeClient: KeelwayBridgeClient;
    readonly codeLensProvider: KeelwayCodeLensProvider;
    getActiveSession(): BridgeDebugSession | null;
}
export declare function activate(context: VsCodeExtensionContext, options?: ActivateExtensionOptions): Promise<ActivatedKeelwayExtension>;
export declare function deactivate(): void;
//# sourceMappingURL=extension.d.ts.map