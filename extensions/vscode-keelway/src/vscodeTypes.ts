/**
 * Structural VS Code & Cursor Extension Host API interfaces.
 * Zero external `@types/vscode` dependency for offline deterministic compilation.
 */

export interface VsCodeDisposable {
  dispose(): void;
}
export interface VsCodePosition {
  readonly line: number;
  readonly character: number;
}
export interface VsCodeRange {
  readonly start: VsCodePosition;
  readonly end: VsCodePosition;
}
export interface VsCodeCommand {
  readonly title: string;
  readonly command: string;
  readonly tooltip?: string;
  readonly arguments?: unknown[];
}
export interface VsCodeCodeLens {
  readonly range: VsCodeRange;
  command?: VsCodeCommand;
  readonly isResolved?: boolean;
}
export interface VsCodeTextLine {
  readonly lineNumber: number;
  readonly text: string;
}
export interface VsCodeDocumentUri {
  readonly fsPath?: string;
  readonly path: string;
  toString(): string;
}
export interface VsCodeTextDocument {
  readonly uri: VsCodeDocumentUri;
  readonly languageId: string;
  readonly lineCount: number;
  getText(): string;
  lineAt(line: number): VsCodeTextLine;
}
export interface VsCodeCodeLensProvider {
  provideCodeLenses(document: VsCodeTextDocument): Promise<VsCodeCodeLens[]> | VsCodeCodeLens[];
}
export interface VsCodeSecretStorage {
  get(key: string): PromiseLike<string | undefined>;
  store(key: string, value: string): PromiseLike<void>;
  delete(key: string): PromiseLike<void>;
}
export interface VsCodeExtensionContext {
  readonly subscriptions: VsCodeDisposable[];
  readonly secrets: VsCodeSecretStorage;
}
export interface VsCodeUri {
  readonly scheme: string;
  readonly authority: string;
  readonly path: string;
  readonly query: string;
  toString(): string;
}
export interface VsCodeUriHandler {
  handleUri(uri: VsCodeUri): PromiseLike<void> | void;
}
export interface VsCodeWebview {
  html: string;
  onDidReceiveMessage(listener: (message: unknown) => unknown): VsCodeDisposable;
  postMessage(message: unknown): PromiseLike<boolean>;
}
export interface VsCodeWebviewPanel {
  readonly webview: VsCodeWebview;
  reveal(viewColumn?: number): void;
  onDidDispose(listener: () => unknown): VsCodeDisposable;
  dispose(): void;
}
export interface VsCodeConfiguration {
  get<T>(section: string, defaultValue: T): T;
}
export interface VsCodeTextEditor {
  readonly document: VsCodeTextDocument;
  readonly selection: { readonly active: VsCodePosition };
}
export interface VsCodeHostApi {
  readonly commands: {
    registerCommand(command: string, callback: (...args: unknown[]) => unknown): VsCodeDisposable;
    executeCommand(command: string, ...rest: unknown[]): PromiseLike<unknown>;
  };
  readonly languages: {
    registerCodeLensProvider(selector: { language: string } | Array<{ language: string }>, provider: VsCodeCodeLensProvider): VsCodeDisposable;
  };
  readonly window: {
    activeTextEditor?: VsCodeTextEditor;
    registerUriHandler(handler: VsCodeUriHandler): VsCodeDisposable;
    createWebviewPanel(viewType: string, title: string, showOptions: number, options: { enableScripts: boolean; retainContextWhenHidden?: boolean }): VsCodeWebviewPanel;
    showInformationMessage(message: string): PromiseLike<string | undefined>;
    showErrorMessage(message: string): PromiseLike<string | undefined>;
    showInputBox(options: { prompt: string; placeHolder?: string; value?: string; password?: boolean }): PromiseLike<string | undefined>;
  };
  readonly workspace: { getConfiguration(section?: string): VsCodeConfiguration };
}
