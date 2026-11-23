export interface EarlyAccessResponse {
  status(code: number): EarlyAccessResponse;
  setHeader(key: string, value: string): void;
  end(chunk?: string): void;
}

export interface EarlyAccessRequest {
  method?: string;
  headers?: Record<string, string | string[] | undefined>;
  body?: unknown;
  socket?: { remoteAddress?: string };
}

export interface EarlyAccessHandler {
  (req: EarlyAccessRequest, res: EarlyAccessResponse): Promise<void>;
  MAX_BODY_BYTES: number;
  isValidWorkEmail(email: unknown): boolean;
  isOriginAllowed(origin: unknown): boolean;
  validatePrivateWebhookUrl(url: unknown): string | null;
  _resetRateLimitForTests(): void;
}

declare const handler: EarlyAccessHandler;
export = handler;
