# ADR-005: Deterministic Execution Flight Recorder & Time-Travel Debugging Engine

**Status:** Approved  
**Date:** 2026-10-30  
**Deciders:** Keelway Core Engineering & Research Team  
**Consulted:** Reprise MCP Record-Replay Spec, Temporal Durable Execution Patterns, rr Deterministic Time-Travel Systems

---

## 1. Context & The "Flawless Agent" Problem

As AI agents perform complex, multi-step tasks across codebases and APIs, developers hit the single most frustrating bottleneck in modern AI engineering: **Non-Deterministic Debugging Nightmares.**
1. **The Phantom Bug:** An agent fails on step 28 of a 40-step migration, but re-running the prompt fails to reproduce the error because token sampling, timestamps, and tool returns drift.
2. **The Expensive Iteration Cycle:** Fixing prompt or tool definition errors requires re-running steps 1–27, burning thousands of tokens, waiting minutes for network roundtrips, and risking secondary side-effects.
3. **The Audit Proof Vacuum:** Regulated enterprise clients (banks, defense, healthcare) and independent developers require forensic proof of *exactly why* an autonomous agent made a specific commit or tool call.

---

## 2. Decision & Architectural Implementations

Keelway implements a built-in **Deterministic Flight Recorder & Time-Travel Debugger (`core/orchestration/flight_recorder.py`)**:

### Pillar I: Zero-Overhead Flight Recording
* **Event Interception Layer:** Intercepts every model prompt, tool call input, tool output, state transition, and environment header.
* **Deterministic Event Serialization:** Serializes events into a tamper-evident, append-only JSON tape (`.keelway/recordings/<task_id>.flight.json`) paired with a cryptographic SHA-256 seal.

### Pillar II: Time-Travel & Deterministic Offline Replay (`keelway replay`)
* **Zero-Cost, Zero-Network Replay:** During replay, model generations and tool outputs are served byte-for-byte directly from the recorded tape.
* **Step-by-Step Rewind & Inspection:** Allows developers to step backward and forward through the execution graph, inspecting memory context, token usage, and variable states at each instant.

### Pillar III: Fork & Branch Debugging ("Time-Travel Hot-Fixing")
* **Intermediate Step Forking:** Allows developers to rewind to step $N$, modify the agent's prompt or tool parameters, and branch into a new execution tree without paying compute fees or re-executing steps $1 \dots N-1$.

---

## 3. Consequences

### Positive
- **"If you can't replay it, you can't ship it":** Guarantees 100% reproducible debugging for AI agents anywhere in the world.
- **Offline Forensics:** Developers in intermittent or low-connectivity environments can debug complex multi-step failures without needing internet access or API credits.
- **Enterprise Verification:** Flight logs serve as verifiable legal and security audit trails.
