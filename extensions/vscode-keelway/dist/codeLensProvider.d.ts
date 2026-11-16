/**
 * Keelway 4D Agent CodeLens Provider for Python & TypeScript Workflow Definitions.
 */
import type { BridgeCodelensItem, KeelwayBridgeClient } from "./bridgeClient.js";
import type { VsCodeCodeLens, VsCodeCodeLensProvider, VsCodeTextDocument } from "./vscodeTypes.js";
export type WorkflowSymbolKind = "node" | "agent" | "workflow";
export interface ScannedWorkflowSymbol {
    readonly symbolId: string;
    readonly kind: WorkflowSymbolKind;
    readonly lineZeroBased: number;
    readonly line_start: number;
}
export declare function scanWorkflowSymbols(sourceText: string, languageId: string): ScannedWorkflowSymbol[];
export declare function formatCodeLensBadge(telemetry?: BridgeCodelensItem): string;
export declare class KeelwayCodeLensProvider implements VsCodeCodeLensProvider {
    private readonly bridgeClient;
    private readonly getScope?;
    constructor(bridgeClient: KeelwayBridgeClient, getScope?: (() => {
        workspaceId: string;
        workflowId?: string;
    }) | undefined);
    provideCodeLenses(document: VsCodeTextDocument): Promise<VsCodeCodeLens[]>;
}
//# sourceMappingURL=codeLensProvider.d.ts.map