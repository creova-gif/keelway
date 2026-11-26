"""
Keelway Hybrid AI Platform — Developer CLI Extensions (`opencore`, `route`, `swarm`, `governance`).

Provides ergonomic terminal and CI/CD automation commands with structured `--json` output
for OpenCore foundation weights, Modelfiles, QLoRA adaptation, explainable hybrid routing
provenance, MiroFish multi-agent swarm evaluation, and multi-tenant governance.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.api.schemas import CompletionRequestSchema, MessageSchema, Provider
from core.eval.mirofish_swarm import MiroFishSwarmHarness
from core.models.adapters.open_weight import OpenWeightProviderAdapter
from core.models.gateway import ModelGateway
from core.models.provider import (
    BaseModelProvider,
    ChatCompletionRequest,
    ChatCompletionResponse,
    StreamChunk,
)
from core.models.registry import ModelCategory, ModelFamily, model_registry
from core.opencore.adaptation import (
    AdaptationConfig,
    AdaptationTask,
    DomainDatasetBuilder,
    TargetLanguage,
    generate_peft_config,
    generate_unsloth_recipe,
)
from core.opencore.serving import opencore_serving_engine
from core.opencore.weights import HardwareProfiler, QuantizationLevel, weight_manager
from core.security.airgap import AirGapEnforcer


class _OfflineMockCloudProvider(BaseModelProvider):
    """Deterministic zero-network closed-model mock for fast offline CLI swarm checks."""

    provider = Provider.GEMINI
    provider_id = Provider.GEMINI
    category = ModelCategory.CLOSED_PROPRIETARY
    default_model = "gemini-3.5-flash-lite"

    def is_available(self) -> bool:
        return True

    async def health_check(self) -> Dict[str, Any]:
        return {"up": True, "provider": "gemini"}

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        prompt_text = " ".join(m.content for m in request.messages).lower()
        if "entity_types" in prompt_text or "ontology" in prompt_text:
            payload = {
                "entity_types": [
                    {"name": "Developer", "description": "AI builder", "attributes": ["region"], "examples": ["Nairobi Dev"]},
                    {"name": "Enterprise", "description": "Regulated org", "attributes": ["sector"], "examples": ["FinTech Co"]},
                ],
                "edge_types": [
                    {"name": "ADOPTS", "description": "Platform adoption", "source_targets": ["Developer->Enterprise"], "attributes": []}
                ],
                "analysis_summary": "Hybrid open-weight + frontier routing accelerates regulated AI adoption.",
            }
            content = json.dumps(payload)
        elif "action" in prompt_text and "round" in prompt_text:
            content = json.dumps({"action": "CREATE_POST", "content": "Deploying OpenCore 7B locally cuts inference spend to zero."})
        else:
            content = (
                "Executive Synthesis: Hybrid routing pairs zero-cost OpenCore weights for private "
                "high-volume tasks with frontier cloud verification for complex synthesis."
            )
        return ChatCompletionResponse(
            id="mock-cli-cloud",
            model=request.model or "gemini-3.5-flash-lite",
            provider=Provider.GEMINI,
            category=ModelCategory.CLOSED_PROPRIETARY,
            content=content,
            finish_reason="stop",
            usage={"prompt_tokens": 64, "completion_tokens": 48, "total_tokens": 112},
            latency_ms=12.5,
            cost_usd=0.000024,
            routing_reason="cli_offline_mock",
        )

    async def stream_complete(self, request: ChatCompletionRequest):
        resp = await self.complete(request)
        yield StreamChunk(id=resp.id, model=resp.model, provider=resp.provider, delta_content=resp.content, finish_reason="stop")


def _emit(payload: Dict[str, Any], as_json: bool, human_lines: List[str]) -> int:
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        for line in human_lines:
            print(line)
    return 0


def register_ai_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Attach `opencore`, `route`, `swarm`, and `governance` command trees."""
    # 1. opencore
    oc = subparsers.add_parser("opencore", help="Manage Keelway OpenCore weights, Modelfiles, runtimes & QLoRA recipes")
    oc_sub = oc.add_subparsers(dest="opencore_command", required=True)

    oc_status = oc_sub.add_parser("status", help="Inspect host hardware profile, OpenCore catalog & runtime discovery")
    oc_status.add_argument("--json", action="store_true", help="Emit JSON output")

    oc_weights = oc_sub.add_parser("weights", help="List SHA-256 verified OpenCore weight manifests")
    oc_weights.add_argument("--model", default=None, help="Filter by canonical model ID (e.g., keelway-core:7b)")
    oc_weights.add_argument("--json", action="store_true", help="Emit JSON output")

    oc_mf = oc_sub.add_parser("modelfile", help="Compile an Ollama Modelfile for an OpenCore model")
    oc_mf.add_argument("--model", default="keelway-core:7b", help="OpenCore model ID")
    oc_mf.add_argument("--quantization", default="q4_k_m", choices=[q.value for q in QuantizationLevel])
    oc_mf.add_argument("--system", default="You are Keelway OpenCore, a sovereign hybrid AI assistant.")
    oc_mf.add_argument("--out", type=Path, default=None, help="Optional file path to write Modelfile")
    oc_mf.add_argument("--json", action="store_true", help="Emit JSON output")

    oc_adapt = oc_sub.add_parser("adapt", help="Generate PEFT LoRA config and Unsloth QLoRA training recipe")
    oc_adapt.add_argument("--model", default="keelway-core:7b", help="Base OpenCore model ID")
    oc_adapt.add_argument("--task", default=AdaptationTask.MULTILINGUAL_LOCALIZATION.value, choices=[t.value for t in AdaptationTask])
    oc_adapt.add_argument("--languages", nargs="+", default=["english", "swahili", "yoruba"], choices=[l.value for l in TargetLanguage])
    oc_adapt.add_argument("--out", type=Path, default=None, help="Optional path to save executable Unsloth script")
    oc_adapt.add_argument("--json", action="store_true", help="Emit JSON output")

    # 2. route
    rt = subparsers.add_parser("route", help="Explain deterministic hybrid routing & 4-dimension data provenance")
    rt_sub = rt.add_subparsers(dest="route_command", required=True)
    rt_exp = rt_sub.add_parser("explain", help="Dry-run routing policy and inspect data boundary provenance")
    rt_exp.add_argument("--prompt", default="Implement an async token-bucket rate limiter in Python.")
    rt_exp.add_argument("--model", default=None, help="Explicit model ID")
    rt_exp.add_argument("--privacy", default="standard", choices=["standard", "private", "strict"])
    rt_exp.add_argument("--category", default=None, choices=["open_weight", "closed_proprietary"])
    rt_exp.add_argument("--capabilities", nargs="*", default=[], help="Required capabilities (e.g., complex_reasoning)")
    rt_exp.add_argument("--max-cost", type=float, default=None, help="Maximum budget in USD")
    rt_exp.add_argument("--air-gap", action="store_true", help="Simulate Air-Gap zero-egress enforcement")
    rt_exp.add_argument("--json", action="store_true", help="Emit JSON output")

    # 3. swarm
    sw = subparsers.add_parser("swarm", help="Run MiroFish × Keelway hybrid multi-agent swarm benchmarks")
    sw_sub = sw.add_subparsers(dest="swarm_command", required=True)
    sw_run = sw_sub.add_parser("run", help="Execute 5-stage hybrid OpenCore + Frontier swarm simulation")
    sw_run.add_argument("--goal", default="Evaluate hybrid open-weight + frontier AI adoption across developers")
    sw_run.add_argument("--seed", default="Organizations combine zero-cost local OpenCore 7B models with frontier cloud verification.")
    sw_run.add_argument("--rounds", type=int, default=1, help="Number of OASIS multi-agent simulation rounds")
    sw_run.add_argument("--frontier-model", default="gemini-3.5-flash-lite")
    sw_run.add_argument("--opencore-model", default="keelway-core:7b")
    sw_run.add_argument("--live", action="store_true", help="Use configured live cloud credentials instead of offline mock")
    sw_run.add_argument("--json", action="store_true", help="Emit JSON output")

    # 4. governance
    gv = subparsers.add_parser("governance", help="Inspect tenant policies, scoped API keys & hash-chained audit logs")
    gv_sub = gv.add_subparsers(dest="governance_command", required=True)

    gv_tenants = gv_sub.add_parser("tenants", help="List configured tenant governance policies")
    gv_tenants.add_argument("--json", action="store_true", help="Emit JSON output")

    gv_key = gv_sub.add_parser("issue-key", help="Issue a scoped API key for a tenant")
    gv_key.add_argument("--tenant", default="default", help="Tenant identifier")
    gv_key.add_argument("--name", default="cli-automation-key", help="Human-readable key label")
    gv_key.add_argument("--scopes", nargs="+", default=["inference:read", "inference:write"], help="Granted key scopes")
    gv_key.add_argument("--json", action="store_true", help="Emit JSON output")

    gv_audit = gv_sub.add_parser("audit", help="Verify and inspect hash-chained governance audit records")
    gv_audit.add_argument("--limit", type=int, default=20, help="Max recent entries to display")
    gv_audit.add_argument("--json", action="store_true", help="Emit JSON output")


def _build_provenance(primary: Optional[Provider], model_id: Optional[str]) -> Dict[str, str]:
    meta = model_registry.get(model_id) if model_id else None
    if primary == Provider.LOCAL or (meta and meta.category == ModelCategory.OPEN_WEIGHT):
        return {
            "weight_ownership_license": meta.license if meta else "Apache-2.0 (Open-Weight)",
            "hosting_location": "local_on_device_or_self_hosted_vpc",
            "service_operator": "customer_self_operated",
            "data_processing_boundary": "zero_external_egress",
        }
    if primary is None:
        return {
            "weight_ownership_license": "none (fail-closed)",
            "hosting_location": "blocked",
            "service_operator": "none",
            "data_processing_boundary": "rejected_by_policy",
        }
    return {
        "weight_ownership_license": meta.license if meta else "Proprietary Commercial Terms",
        "hosting_location": f"{primary.value}_managed_cloud_region",
        "service_operator": f"{primary.value}_commercial_api",
        "data_processing_boundary": "external_commercial_inference_endpoint",
    }


def _handle_opencore(args: argparse.Namespace) -> int:
    cmd = args.opencore_command
    as_json = getattr(args, "json", False)

    if cmd == "status":
        hw = HardwareProfiler.detect()
        oc_models = [m.model_dump(mode="json") for m in model_registry.list_models() if m.family == ModelFamily.KEELWAY_CORE]
        telemetry = opencore_serving_engine.get_cluster_telemetry().model_dump(mode="json")
        runtimes: Any = {}
        try:
            from core.opencore import runtime as oc_rt

            async def _probe() -> Dict[str, Any]:
                discovery = oc_rt.runtime_discovery
                ollama, vllm = await asyncio.gather(
                    discovery.discover_ollama(), discovery.discover_vllm()
                )
                return {
                    "ollama": ollama.model_dump(mode="json"),
                    "vllm": vllm.model_dump(mode="json"),
                }

            runtimes = asyncio.run(_probe())
        except Exception:
            runtimes = {"in_process_opencore": "ready"}
        payload = {"hardware": hw.model_dump(mode="json"), "models": oc_models, "telemetry": telemetry, "runtimes": runtimes}
        lines = [
            f"[+] Keelway OpenCore Status — {hw.os_name}/{hw.machine} ({hw.total_ram_gb} GB RAM, Metal={hw.has_metal}, CUDA={hw.has_cuda})",
            f"    Recommended Quantization: {hw.recommended_quantization.value}",
            f"    Registered OpenCore Models ({len(oc_models)}): " + ", ".join(m["id"] for m in oc_models),
        ]
        return _emit(payload, as_json, lines)

    if cmd == "weights":
        manifests = weight_manager.list_manifests(model_id=args.model)
        items = [
            {**m.model_dump(mode="json"), "cached": weight_manager.is_cached(m), "local_path": str(weight_manager.get_local_path(m))}
            for m in manifests
        ]
        lines = [f"[+] OpenCore Weight Manifests ({len(items)}):"] + [
            f"  • {it['model_id']} [{it['quantization']}] {it['minimum_vram_gb']}GB VRAM | cached={it['cached']} | sha256={it['sha256_checksum'][:12]}..."
            for it in items
        ]
        return _emit({"manifests": items}, as_json, lines)

    if cmd == "modelfile":
        quant = QuantizationLevel(args.quantization)
        manifest = weight_manager.get_manifest(args.model, quant)
        modelfile_text = ""
        try:
            from core.opencore import runtime as oc_rt

            compiler = oc_rt.OpenCoreModelfileCompiler(manager=weight_manager)
            spec = compiler.build_spec(
                model_id=args.model, quantization=quant, system_prompt=args.system
            )
            modelfile_text = compiler.render(spec)
        except Exception:
            modelfile_text = ""
        if not modelfile_text:
            from_target = str(weight_manager.get_local_path(manifest)) if manifest else "qwen2.5:7b"
            ctx = manifest.context_length if manifest else 32768
            modelfile_text = (
                f"# Keelway OpenCore Modelfile ({args.model} @ {quant.value})\n"
                f"FROM {from_target}\n"
                f"PARAMETER num_ctx {ctx}\n"
                f"PARAMETER temperature 0.2\n"
                f'SYSTEM "{args.system}"\n'
            )
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(modelfile_text, encoding="utf-8")
        payload = {"model": args.model, "quantization": quant.value, "modelfile": modelfile_text, "written_to": str(args.out) if args.out else None}
        return _emit(payload, as_json, [modelfile_text.rstrip()])

    if cmd == "adapt":
        cfg = AdaptationConfig(
            base_model_id=args.model,
            task=AdaptationTask(args.task),
            target_languages=[TargetLanguage(lang) for lang in args.languages],
        )
        peft_cfg = generate_peft_config(cfg)
        recipe = generate_unsloth_recipe(cfg)
        samples = DomainDatasetBuilder.get_multilingual_samples(cfg.target_languages)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(recipe, encoding="utf-8")
        payload = {"config": cfg.model_dump(mode="json"), "peft_config": peft_cfg, "sample_count": len(samples), "written_to": str(args.out) if args.out else None, "recipe": recipe}
        lines = [
            f"[+] Generated OpenCore QLoRA Adaptation Recipe for {cfg.base_model_id} ({cfg.task.value})",
            f"    Languages: {', '.join(l.value for l in cfg.target_languages)} | Seed Samples: {len(samples)} | LoRA r={cfg.lora_r}",
        ]
        return _emit(payload, as_json, lines)

    return 1


def _handle_route(args: argparse.Namespace) -> int:
    gw = ModelGateway(air_gap_enforcer=AirGapEnforcer(enabled=bool(args.air_gap)))
    req = CompletionRequestSchema(
        model=args.model,
        messages=[MessageSchema(role="user", content=args.prompt)],
        privacy_level="private" if args.privacy in ("private", "strict") else "standard",
        category_preference=args.category,
        required_capabilities=list(args.capabilities or []),
        max_cost_usd=args.max_cost,
    )
    order, reason = gw.explain_route(req)
    if args.air_gap:
        order = [p for p in order if p == Provider.LOCAL]
    primary = order[0] if order else None
    est_cost = round(gw.estimate_cost_usd(primary, req), 6) if primary else 0.0
    provenance = _build_provenance(primary, args.model)
    payload = {
        "selected_provider": primary.value if primary else None,
        "candidate_chain": [p.value for p in order],
        "reason": reason,
        "air_gap_enabled": bool(args.air_gap),
        "estimated_upper_bound_cost_usd": est_cost,
        "provenance": provenance,
    }
    lines = [
        f"[+] Routing Explanation: selected={payload['selected_provider'] or 'BLOCKED'} | chain={payload['candidate_chain']}",
        f"    Reason:        {reason}",
        f"    Est. Max Cost: ${est_cost:.6f}",
        f"    Provenance:    license='{provenance['weight_ownership_license']}', boundary='{provenance['data_processing_boundary']}'",
    ]
    return _emit(payload, getattr(args, "json", False), lines)


def _handle_swarm(args: argparse.Namespace) -> int:
    local_adapter = OpenWeightProviderAdapter(base_url="http://127.0.0.1:9")
    target_adapter: BaseModelProvider
    if args.live:
        gw = ModelGateway()
        live_adapter = gw.adapters[Provider.GEMINI]
        assert isinstance(live_adapter, BaseModelProvider)
        target_adapter = live_adapter
    else:
        mock_cloud = _OfflineMockCloudProvider()
        gw = ModelGateway(adapters={Provider.LOCAL: local_adapter, Provider.GEMINI: mock_cloud, Provider.GOOGLE: mock_cloud})
        target_adapter = mock_cloud

    harness = MiroFishSwarmHarness(
        gateway=gw,
        draft_provider=local_adapter,
        target_provider=target_adapter,
        frontier_model=args.frontier_model,
        opencore_model=args.opencore_model,
    )
    entities = [
        {"name": "Amina Okafor", "entity_type": "Developer", "summary": "Fintech ML engineer deploying OpenCore locally"},
        {"name": "Kofi Mensah", "entity_type": "Enterprise", "summary": "CTO balancing data residency and frontier reasoning"},
    ]
    report = asyncio.run(harness.run_full_experiment(
        seed_text=args.seed,
        simulation_goal=args.goal,
        entities_spec=entities,
        rounds=max(1, args.rounds),
    ))
    payload = asdict(report)
    lines = [
        f"[+] MiroFish × Keelway Swarm Complete (graph={report.graph_id}, {report.elapsed_ms:.1f} ms)",
        f"    Calls: {report.total_calls} total ({report.open_weight_calls} OpenCore $0.00 + {report.closed_cloud_calls} Frontier)",
        f"    Cost:  ${report.total_cost_usd:.6f} (Savings: {report.savings_pct}% vs all-cloud)",
        f"    Security Invariants: {report.security_checks}",
    ]
    return _emit(payload, getattr(args, "json", False), lines)


def _handle_governance(args: argparse.Namespace) -> int:
    as_json = getattr(args, "json", False)
    cmd = args.governance_command
    try:
        from core.security import tenant_governance as tg
        engine = tg.tenant_governance
        if cmd == "tenants":
            tenants = [t.model_dump(mode="json") for t in engine.list_tenants()]
            lines = [f"[+] Configured Governance Tenants ({len(tenants)}):"] + [
                f"  • {t.get('tenant_id', 'default')} | residency={t.get('residency_zone', 'global')}" for t in tenants
            ]
            return _emit({"tenants": tenants}, as_json, lines)
        if cmd == "issue-key":
            meta, _ = engine.issue_key(tenant_id=args.tenant, name=args.name, scopes=list(args.scopes))
            safe_payload = {
                "tenant_id": meta.tenant_id,
                "key_id": meta.key_id,
                "key_prefix": meta.key_prefix,
                "scopes": meta.scopes,
            }
            lines = [f"[+] Issued Scoped Key '{args.name}' for tenant '{args.tenant}' (id={meta.key_id}, prefix={meta.key_prefix})"]
            return _emit(safe_payload, as_json, lines)
        if cmd == "audit":
            is_valid, broken_at = engine.audit_log.verify_integrity()
            entries = [e.model_dump(mode="json") for e in engine.audit_log.list_entries(limit=args.limit)]
            payload = {"chain_valid": is_valid, "broken_at_seq": broken_at, "entry_count": len(entries), "entries": entries}
            lines = [f"[+] Governance Audit Chain Verified: valid={is_valid} | entries={len(entries)}"]
            return _emit(payload, as_json, lines)
    except Exception as exc:
        payload = {"status": "governance_fallback", "detail": str(exc)}
        return _emit(payload, as_json, [f"[-] Governance module unavailable: {exc}"])
    return 1


def dispatch_ai_command(args: argparse.Namespace) -> Optional[int]:
    """Dispatch AI platform CLI commands if `args.command` matches; otherwise return None."""
    if args.command == "opencore":
        return _handle_opencore(args)
    if args.command == "route":
        return _handle_route(args)
    if args.command == "swarm":
        return _handle_swarm(args)
    if args.command == "governance":
        return _handle_governance(args)
    return None
