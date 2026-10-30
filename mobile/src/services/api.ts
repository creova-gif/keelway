/**
 * Kora Mobile API & WebSocket Live Agent Streamer.
 * Connects to local Dev Studio (LAN/Wi-Fi/Tailscale) or remote Kora nodes.
 */

export interface AgentEvent {
  type: string;
  task_id?: string;
  prompt?: string;
  state?: string;
  diff?: string;
  verification?: string;
  timestamp: string;
}

export class KoraMobileClient {
  private ws: WebSocket | null = null;
  private baseUrl: string;
  private onEventCallback: ((event: AgentEvent) => void) | null = null;

  constructor(host: string = '127.0.0.1:7420') {
    this.baseUrl = host;
  }

  connect(onEvent: (event: AgentEvent) => void) {
    this.onEventCallback = onEvent;
    const protocol = this.baseUrl.startsWith('https') ? 'wss://' : 'ws://';
    const wsUrl = `${protocol}${this.baseUrl}/v1/ws/studio`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (this.onEventCallback) {
          this.onEventCallback(data);
        }
      } catch (err) {
        console.error('Failed to parse agent WS event:', err);
      }
    };

    this.ws.onerror = (err) => {
      console.warn('Kora WS connection error:', err);
    };
  }

  sendInstruction(prompt: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'execute_instruction', prompt }));
    }
  }

  async triggerSelfHealing(testCommand: string): Promise<any> {
    const res = await fetch(`http://${this.baseUrl}/v1/healing/repair`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ test_command: testCommand, max_attempts: 3 }),
    });
    return res.json();
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
