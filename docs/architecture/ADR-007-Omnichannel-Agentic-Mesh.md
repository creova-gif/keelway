# ADR-007: Omnichannel Messaging, Hybrid Edge Inference & P2P Team Mesh

## Status
Accepted

## Context
Following the executive `/autoplan` review and approval gate decisions, three strategic capabilities are established to ensure Keelway serves developers and engineering teams worldwide with zero cloud dependency and zero geographic friction:

1. **Omnichannel Approval & Mobile Experience (Decision 2):**
   - Developers need to supervise long-running agent workflows (self-healing loops, migrations, builds) from anywhere.
   - Traditional tools rely on web dashboards or IDE push notifications that require being glued to a laptop.
   - Developers can choose between **Telegram** (rich markdown, inline buttons) and **WhatsApp** (interactive buttons/lists) as their primary review interface, with automatic fallback to **USSD / SMS** for remote 2G/3G regions.
   - Prepares REST/WebSocket session primitives for the upcoming native **Keelway Mobile App** (`keelway://` deep-linking and biometric approvals).

2. **Hybrid Edge Model Runtime (Decision 1):**
   - High friction of requiring external daemons (like Ollama or LM Studio) turns off non-technical users or developers in locked-down enterprise environments.
   - System transparently auto-probes for an active Ollama instance (`http://localhost:11434`); if absent, it falls back to an embedded 4-bit GGUF weight loader (`~/.keelway/models/`) tailored to host RAM (1.5B for <8GB, 7B for 8-16GB, 14B for >16GB). Zero external daemons required.

3. **Peer-to-Peer Local Team Mesh & GPU Pooling (Decision 3):**
   - Individual developers on a team often have asymmetric hardware (e.g. one M3 Max workstation and several lightweight laptops).
   - `LocalTeamMesh` broadcasts node presence via mDNS (`_keelway-agent._tcp.local.`) on local office Wi-Fi or ad-hoc hotspots.
   - Heavy AST repair or fine-tuning tasks are automatically routed to the peer node with the highest available free VRAM without touching the internet.
   - Supports an optional Tailscale WireGuard overlay for remote team members.

---

## Architectural Data Flow

```
                                [ OMNICHANNEL HUMAN-IN-THE-LOOP ]
                                                |
               +----------------+---------------+----------------+----------------+
               |                |                                |                |
               v                v                                v                v
         [ Telegram ]     [ WhatsApp ]                     [ Keelway Mobile ]  [ USSD / SMS ]
         (Inline Button)  (Cloud API Button)               (Deep-link Push) (Numeric Menu)
               |                |                                |                |
               +----------------+---------------+----------------+----------------+
                                                |
                                                v
                                  +---------------------------+
                                  |   OmnichannelDispatcher   |
                                  |   (core/api/messaging.py) |
                                  +---------------------------+
                                                |
                                                v
                                  +---------------------------+
                                  |  Keelway Autonomous Engine   |
                                  +---------------------------+
                                   /                         \
                                  /                           \
                                 v                             v
                   +---------------------------+  +---------------------------+
                   |    EdgeRuntimeManager     |  |      LocalTeamMesh        |
                   |   (core/models/edge.py)   |  |   (core/orchestration)    |
                   |                           |  |                           |
                   | • Ollama (if active)      |  | • mDNS Local Wi-Fi        |
                   | • Embedded 4-bit GGUF     |  | • GPU/VRAM Pooling        |
                   | • Hardware Auto-Profile   |  | • Tailscale Overlay       |
                   +---------------------------+  +---------------------------+
```

---

## Consequences
- **Positive:**
  - Engineers can review and merge autonomous patches with one tap while away from their desks.
  - Zero daemon installation required to start local $0.00 coding agents.
  - Development teams can share local GPU power with zero cloud bills.
- **Negative:**
  - Embedded GGUF loader requires local disk space for model weights (~1GB for 1.5B, ~4.5GB for 7B).
