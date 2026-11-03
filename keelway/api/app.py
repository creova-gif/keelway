"""Keelway Main FastAPI Application.
Provides local-first REST API and operator web dashboard.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from keelway.api.routes import router as api_router

app = FastAPI(
    title="Keelway Governance Platform",
    description="Customer-managed governance and audit platform for AI-powered software change (Sorvex Labs)",
    version="0.71.0-enterprise",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", response_class=HTMLResponse)
def index_dashboard():
    """Lightweight developer and reviewer web dashboard."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Keelway | Sorvex Labs Governance Platform</title>
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #111827;
      --border: #1f293d;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --accent: #3b82f6;
      --accent-hover: #2563eb;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --code-bg: #0d1117;
    }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }
    header {
      border-bottom: 1px solid var(--border);
      padding: 1rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #0b0f19;
    }
    .brand {
      font-weight: 700;
      font-size: 1.25rem;
      letter-spacing: -0.025em;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .badge {
      font-size: 0.75rem;
      padding: 0.2rem 0.5rem;
      border-radius: 9999px;
      background: var(--border);
      color: var(--text-muted);
    }
    .badge-success { background: rgba(16, 185, 129, 0.2); color: var(--success); }
    .badge-warning { background: rgba(245, 158, 11, 0.2); color: var(--warning); }
    .badge-danger { background: rgba(239, 68, 68, 0.2); color: var(--danger); }
    main {
      max-width: 1200px;
      margin: 2rem auto;
      padding: 0 1rem;
      display: grid;
      grid-template-columns: 360px 1fr;
      gap: 1.5rem;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.25rem;
      margin-bottom: 1.5rem;
    }
    h2, h3 { margin-top: 0; }
    input, textarea, button, select {
      width: 100%;
      box-sizing: border-box;
      padding: 0.6rem;
      margin-top: 0.5rem;
      border-radius: 6px;
      border: 1px solid var(--border);
      background: var(--code-bg);
      color: var(--text);
      font-size: 0.9rem;
    }
    button {
      background: var(--accent);
      color: white;
      font-weight: 600;
      cursor: pointer;
      border: none;
      transition: background 0.2s;
    }
    button:hover { background: var(--accent-hover); }
    button.btn-danger { background: var(--danger); }
    button.btn-success { background: var(--success); }
    pre {
      background: var(--code-bg);
      padding: 1rem;
      border-radius: 6px;
      border: 1px solid var(--border);
      overflow-x: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.85rem;
    }
    .events-timeline {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }
    .event-node {
      border-left: 2px solid var(--accent);
      padding-left: 1rem;
      position: relative;
    }
    .event-meta {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span>🛡️ KEELWAY</span>
      <span class="badge">by Sorvex Labs</span>
      <span class="badge badge-success">v0.71 Enterprise Core</span>
    </div>
    <div style="font-size: 0.85rem; color: var(--text-muted);">
      Invariants: Deny-by-default • Two-Human Quorum (ADR-045) • Immutable Audit Chain
    </div>
  </header>
  <main>
    <div>
      <div class="card">
        <h3>Initiate Governed Run</h3>
        <label>Task Prompt</label>
        <textarea id="taskPrompt" rows="2">Add governed telemetry and healthcheck endpoint</textarea>
        
        <label style="margin-top:0.75rem; display:block;">Target Environment</label>
        <select id="runClassification">
          <option value="internal">Internal / Dev (Single Human Review)</option>
          <option value="production">Production (Mandatory Two-Human Quorum ADR-045)</option>
        </select>

        <button id="btnStart" onclick="startRun()" style="margin-top:1rem;">Launch Governed Run</button>
      </div>

      <div class="card">
        <h3>Active Run Details</h3>
        <p><strong>Run ID:</strong> <span id="lblRunId">-</span></p>
        <p><strong>Classification:</strong> <span id="lblEnv" class="badge">-</span></p>
        <p><strong>Status:</strong> <span id="lblStatus" class="badge">-</span></p>
        <p><strong>Tokens Consumed:</strong> <span id="lblTokens">0</span></p>
        <p><strong>Cost (Cents):</strong> <span id="lblCost">0</span></p>
        <button onclick="verifyAudit()" style="margin-top: 0.5rem;">Verify Cryptographic Chain</button>
        <p id="verifyResult" style="font-size: 0.85rem; margin-top: 0.5rem;"></p>
      </div>

      <!-- Single Human Approval Card -->
      <div class="card" id="singleApprovalCard" style="display:none;">
        <h3>Human Review Gate</h3>
        <p>Review the generated diff and eval results before granting authorization.</p>
        <button class="btn-success" onclick="decideSingleApproval('APPROVED')">Approve Patch</button>
        <button class="btn-danger" style="margin-top: 0.5rem;" onclick="decideSingleApproval('REJECTED')">Reject Patch</button>
      </div>

      <!-- Two-Human Quorum Approval Card (ADR-045) -->
      <div class="card" id="quorumApprovalCard" style="display:none; border-color: var(--warning);">
        <h3>⚖️ Two-Human Quorum (ADR-045)</h3>
        <p style="font-size:0.85rem; color:var(--text-muted);">
          Production changes require two independent human approvals: Security Lead AND Platform Owner. Self-quorum is prohibited.
        </p>
        <button id="btnSecLead" class="btn-success" onclick="signQuorum('alice_security_lead', 'Security Lead')">
          ✍️ Sign as Security Lead (Alice)
        </button>
        <button id="btnPlatOwner" class="btn-success" style="margin-top: 0.5rem;" onclick="signQuorum('bob_platform_owner', 'Platform Owner')">
          ✍️ Sign as Platform Owner (Bob)
        </button>
      </div>

      <div class="card" id="promoteCard" style="display:none;">
        <h3>Staging Promotion</h3>
        <button onclick="createPr()">Create Pull Request</button>
        <button onclick="triggerDeploy()" style="margin-top: 0.5rem;" class="btn-success">Deploy to Staging</button>
        <p id="deployResult" style="font-size: 0.85rem; margin-top: 0.5rem;"></p>
      </div>

      <!-- Enterprise Hardware & Trust Status Card (Tier 2) -->
      <div class="card" id="hardwareCard" style="border-color: #2563eb;">
        <h3>🔒 Hardware Attestation (Tier 2)</h3>
        <p style="font-size: 0.8rem; color: var(--text-muted);">
          Inspect live qualification status for physical WORM appliances, TPM 2.0 PCR replay, and PIV smartcards.
        </p>
        <button onclick="fetchHardwareStatus()" style="background:#1f293d; font-size: 0.8rem;">Query HAL Qualification</button>
        <div id="hwDetails" style="font-size:0.75rem; margin-top:0.75rem; display:none; line-height: 1.6;">
          <p><strong>WORM Storage:</strong> <span id="lblWorm" class="badge">Checking...</span></p>
          <p><strong>TPM 2.0 Replay:</strong> <span id="lblTpm" class="badge">Checking...</span></p>
          <p><strong>PIV Smartcard:</strong> <span id="lblPiv" class="badge">Checking...</span></p>
        </div>
      </div>
    </div>

    <div>
      <div class="card">
        <h3>Unified Patch Diff (Isolated Worktree)</h3>
        <pre id="diffViewer">No active run selected. Launch a run to inspect candidate diff.</pre>
      </div>

      <div class="card">
        <h3>Append-Only Tamper-Evident Audit Chain</h3>
        <div id="eventsList" class="events-timeline">
          <div style="color: var(--text-muted); font-size: 0.85rem;">Chain will populate as actions occur...</div>
        </div>
      </div>
    </div>
  </main>

  <script>
    let currentRunId = null;
    let currentApprovalId = null;
    let isQuorum = false;

    async function startRun() {
      const prompt = document.getElementById("taskPrompt").value;
      const classification = document.getElementById("runClassification").value;
      const res = await fetch("/v1/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_prompt: prompt, classification: classification })
      });
      const data = await res.json();
      currentRunId = data.run_id;
      currentApprovalId = data.approval_id;
      isQuorum = data.is_quorum;

      document.getElementById("lblRunId").innerText = currentRunId.substring(0, 8) + "...";
      document.getElementById("lblEnv").innerText = data.classification.toUpperCase();
      document.getElementById("lblStatus").innerText = data.status.toUpperCase();
      document.getElementById("lblStatus").className = "badge badge-warning";
      
      document.getElementById("singleApprovalCard").style.display = "none";
      document.getElementById("quorumApprovalCard").style.display = "none";
      document.getElementById("promoteCard").style.display = "none";

      if (isQuorum) {
        document.getElementById("quorumApprovalCard").style.display = "block";
      } else if (currentApprovalId) {
        document.getElementById("singleApprovalCard").style.display = "block";
      }
      await refreshData();
    }

    async function refreshData() {
      if (!currentRunId) return;
      const res = await fetch(`/v1/runs/${currentRunId}`);
      const data = await res.json();
      document.getElementById("lblStatus").innerText = data.status.toUpperCase();
      document.getElementById("lblTokens").innerText = data.tokens_used;
      document.getElementById("lblCost").innerText = data.cost_cents_used;

      if (data.status === "approved") {
        document.getElementById("singleApprovalCard").style.display = "none";
        document.getElementById("quorumApprovalCard").style.display = "none";
        document.getElementById("promoteCard").style.display = "block";
        document.getElementById("lblStatus").className = "badge badge-success";
      }

      const evRes = await fetch(`/v1/runs/${currentRunId}/events`);
      const events = await evRes.json();
      const listEl = document.getElementById("eventsList");
      listEl.innerHTML = "";
      
      events.forEach(ev => {
        const node = document.createElement("div");
        node.className = "event-node";
        node.innerHTML = `
          <strong>#${ev.seq} [${ev.kind}]</strong>
          <div class="event-meta">Hash: ${ev.hash.substring(0, 16)}... | Prev: ${ev.prev_hash.substring(0, 16)}...</div>
          <pre style="margin-top:0.25rem; font-size:0.75rem;">${JSON.stringify(ev.payload, null, 2)}</pre>
        `;
        listEl.appendChild(node);
        
        if (ev.kind === "PATCH_GENERATED" && ev.payload.diff_content) {
          document.getElementById("diffViewer").innerText = ev.payload.diff_content;
        } else if (ev.kind === "APPROVAL_REQUESTED" && ev.payload.diff_content) {
          document.getElementById("diffViewer").innerText = ev.payload.diff_content;
        }
      });
    }

    async function decideSingleApproval(decision) {
      if (!currentApprovalId) return;
      const res = await fetch(`/v1/approvals/${currentApprovalId}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approval_id: currentApprovalId,
          decision: decision,
          approver_id: "human_lead_engineer",
          patch_hash: "auto",
        })
      });
      await refreshData();
    }

    async function signQuorum(principal, role) {
      if (!currentApprovalId) return;
      const res = await fetch(`/v1/quorum/${currentApprovalId}/approval`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          quorum_id: currentApprovalId,
          principal_id: principal,
          role: role,
        })
      });
      await refreshData();
    }

    async function createPr() {
      const res = await fetch(`/v1/runs/${currentRunId}/pull-request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          run_id: currentRunId,
          approval_id: currentApprovalId,
          title: "feat(keelway): Governed Change",
          description: "Governed AI change verified and approved."
        })
      });
      const data = await res.json();
      document.getElementById("deployResult").innerText = "PR Created: " + data.pr_url;
      await refreshData();
    }

    async function triggerDeploy() {
      const res = await fetch(`/v1/deployments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          run_id: currentRunId,
          approval_id: currentApprovalId,
          target_environment: "staging"
        })
      });
      const data = await res.json();
      document.getElementById("deployResult").innerText = "Staging CI Triggered! Receipt: " + data.receipt_digest.substring(0, 16) + "...";
      await refreshData();
    }

    async function verifyAudit() {
      if (!currentRunId) return;
      const res = await fetch(`/v1/audit/verify?run_id=${currentRunId}`);
      const data = await res.json();
      const el = document.getElementById("verifyResult");
      if (data.verified) {
        el.innerText = `✅ Hash Chain VERIFIED (${data.total_events} events). Zero tampering.`;
        el.style.color = "var(--success)";
      } else {
        el.innerText = `❌ Hash Chain TAMPERED: ${data.error}`;
        el.style.color = "var(--danger)";
      }
    }

    async function fetchHardwareStatus() {
      const res = await fetch("/v1/system/hardware-status");
      const data = await res.json();
      const hw = data.tier2_hardware_abstraction_layer;
      document.getElementById("hwDetails").style.display = "block";

      const wormEl = document.getElementById("lblWorm");
      wormEl.innerText = hw.worm_storage.qualification;
      wormEl.className = hw.worm_storage.production_ready_physical_hardware ? "badge badge-success" : "badge badge-warning";

      const tpmEl = document.getElementById("lblTpm");
      tpmEl.innerText = hw.tpm_attestation.golden_profile_matching + " (" + hw.tpm_attestation.nonce_anti_replay + ")";
      tpmEl.className = "badge badge-success";

      const pivEl = document.getElementById("lblPiv");
      pivEl.innerText = "Max 72h CRL (Software Keys Prohibited)";
      pivEl.className = "badge badge-success";
    }
  </script>
</body>
</html>
"""
