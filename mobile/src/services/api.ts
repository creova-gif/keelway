/**
 * Keelway mobile API client: talks to a Keelway on your LAN/Tailscale with your Studio token.
 * Polls instead of holding a WebSocket so it survives flaky mobile networks and sleeps cleanly.
 */

export interface Connection {
  baseUrl: string; // e.g. http://192.168.1.20:7420
  token: string;
}

export interface PendingApproval {
  task_id: string;
  tool_name: string;
  arguments: Record<string, any>;
  is_mutation: boolean;
  step_id?: string | null;
}

export interface AgentRun {
  task_id: string;
  goal: string;
  status: string;
  policy: string;
  steps_total: number;
  steps_done: number;
  pending_approval: PendingApproval | null;
}

export interface StudioStatus {
  air_gapped: boolean;
  local_model: string;
  version: string;
  git?: { branch: string | null; sha: string | null };
}

export interface WhoAmI {
  actor: string;
  role: string;
  permissions: string[];
}

export class KeelwayError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

/** Accepts the link `keelway dev` prints: http://host:port/?token=... (no token when AUTH_REQUIRED=false). */
export function parseStudioLink(link: string): Connection | null {
  const m = link.trim().match(/^(https?:\/\/[^/?#\s]+)\/?[^?#\s]*(?:\?([^#\s]*))?(?:#\S*)?$/i);
  if (!m) return null;
  const raw = (m[2] || '').split('&').find((p) => p.startsWith('token='))?.slice(6) ?? '';
  try {
    return { baseUrl: m[1], token: decodeURIComponent(raw) };
  } catch {
    return null;
  }
}

export class KeelwayClient {
  constructor(private conn: Connection, private timeoutMs = 8000) {}

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const res = await fetch(`${this.conn.baseUrl}${path}`, {
        ...init,
        signal: controller.signal,
        headers: {
          ...(this.conn.token ? { Authorization: `Bearer ${this.conn.token}` } : {}),
          'Content-Type': 'application/json',
          ...(init.headers || {}),
        },
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new KeelwayError(body.detail || `HTTP ${res.status}`, res.status);
      return body as T;
    } finally {
      clearTimeout(timer);
    }
  }

  whoami() {
    return this.request<WhoAmI>('/v1/auth/whoami');
  }

  status() {
    return this.request<StudioStatus>('/v1/studio/status');
  }

  async runs() {
    return (await this.request<{ runs: AgentRun[] }>('/v1/agent/runs')).runs;
  }

  decide(taskId: string, approved: boolean) {
    return this.request(`/v1/agent/approve/${encodeURIComponent(taskId)}`, {
      method: 'POST',
      body: JSON.stringify({ approved }),
    });
  }

  setAirGap(enabled: boolean) {
    return this.request('/v1/studio/airgap', { method: 'POST', body: JSON.stringify({ enabled }) });
  }
}
