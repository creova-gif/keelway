"""Builtin KStack skill execution handlers.

Handlers are the only sanctioned way a skill executes: each entry maps a skill
name to a real platform service call. A skill without a registered handler is
never executed — the API surfaces 501 rather than echo output, so a
SkillExecutionProof always reflects a real service result (or a real service
failure recorded as success=False).
"""

from typing import Any, Callable, Dict

from core.kbrain import KnowledgeScope, kbrain_store
from core.models.cost_ledger import cost_ledger
from core.orchestration.p2p_mesh import get_shared_mesh
from core.orchestration.scheduler import flow_scheduler
from core.security.airgap_auditor import AirGapAuditor
from core.security.merkle_audit import AuditMerkleTree
from core.security.sbom import SBOMGenerator
from evals.drift_detector import DriftDetector, EvaluationReceiptStore


def _scope(value: Any) -> KnowledgeScope:
    try:
        return KnowledgeScope(str(value or "project"))
    except ValueError:
        return KnowledgeScope.PROJECT


def _airgap_verify(inputs: Dict[str, Any]) -> Dict[str, Any]:
    report = AirGapAuditor.audit_environment()
    return report.to_dict()


def _flight_tape_verify(inputs: Dict[str, Any]) -> Dict[str, Any]:
    leaf_hash = inputs.get("leaf_hash", "")
    proof = inputs.get("proof", [])
    root_hash = inputs.get("root_hash", "")
    if not leaf_hash or not isinstance(proof, list) or not root_hash:
        raise ValueError("inputs 'leaf_hash' (str), 'proof' (list), and 'root_hash' (str) are required")
    return {"valid": AuditMerkleTree.verify_proof(leaf_hash, proof, root_hash)}


def _cost_ledger(inputs: Dict[str, Any]) -> Dict[str, Any]:
    report = cost_ledger.get_economics_report()
    summary = cost_ledger.get_summary()
    report["total_cost_usd"] = report.get(
        "billed_cloud_expenditure_usd", summary.get("total_external_cost_usd", 0.0)
    )
    report["currency"] = "USD"
    report["entries_recorded"] = summary.get("total_inferences", 0)
    return report


def _finops_forecast(inputs: Dict[str, Any]) -> Dict[str, Any]:
    report = cost_ledger.get_economics_report()
    summary = cost_ledger.get_summary()
    out = {
        "local_spend_usd": 0.0,
        "external_spend_usd": report.get("billed_cloud_expenditure_usd", 0.0),
        "savings_usd": report.get("quantified_local_savings_usd", 0.0),
        "net_economic_benefit_usd": report.get("net_economic_benefit_usd", 0.0),
        "entries_recorded": summary.get("total_inferences", 0),
        "local_inference_ratio": report.get("local_inference_ratio", 0.0),
        "projections": report.get("projections", {}),
        "currency": "USD",
    }
    projected = inputs.get("projected_tokens")
    if projected is not None:
        out["projection_note"] = (
            "forward projection requires measured token volume; "
            "ledger token totals are reported under projections"
        )
    return out


def _kbrain_fact(inputs: Dict[str, Any]) -> Dict[str, Any]:
    key = str(inputs.get("key", "")).strip()
    statement = str(inputs.get("statement", "")).strip()
    scope = _scope(inputs.get("scope"))
    if key and statement:
        fact = kbrain_store.record_fact(
            key=key,
            statement=statement,
            scope=scope,
            provenance_uri=str(inputs.get("provenance_uri", "")),
            provenance_reason=str(inputs.get("provenance_reason", "")),
            created_by=str(inputs.get("actor", "kstack")),
            auto_approve=bool(inputs.get("auto_approve", True)),
        )
        return {"recorded": True, "fact": fact.to_dict()}
    facts = kbrain_store.query_facts(
        max_scope=scope,
        search_text=inputs.get("search"),
        key=key or None,
    )
    return {"recorded": False, "matched": [f.to_dict() for f in facts]}


def _mesh_verify(inputs: Dict[str, Any]) -> Dict[str, Any]:
    action = str(inputs.get("action", "status")).lower()
    mesh = get_shared_mesh()
    if action == "status":
        return {
            "local_node": mesh.get_local_advertisement(),
            "active_peers_count": len(mesh.active_peers()),
            "total_pooled_vram_mb": mesh.total_pooled_vram_mb(),
            "delegation_history_count": len(mesh.delegation_history),
        }
    if action == "peers":
        return {
            "peers": [p.to_dict() for p in mesh.peers.values()],
            "active_peers": [p.to_dict() for p in mesh.active_peers()],
            "total_pooled_vram_mb": mesh.total_pooled_vram_mb(),
        }
    raise ValueError(
        f"action '{action}' is mutating mesh state; only 'status' and 'peers' "
        "are exposed through the builtin handler"
    )


def _sbom_audit(inputs: Dict[str, Any]) -> Dict[str, Any]:
    sbom = SBOMGenerator.generate()
    payload = sbom.to_dict()
    components = payload.get("components", [])
    return {
        "sbom": payload,
        "component_count": len(components) if isinstance(components, list) else 0,
    }


def _schedule_ops(inputs: Dict[str, Any]) -> Dict[str, Any]:
    action = str(inputs.get("action", "list")).lower()
    if action == "list":
        return {"schedules": flow_scheduler.list(), "persistent": flow_scheduler.persistent}
    if action == "create":
        flow_id = str(inputs.get("flow_id", "")).strip()
        interval = inputs.get("interval_seconds")
        if not flow_id or not isinstance(interval, int) or interval <= 0:
            raise ValueError("create requires 'flow_id' (str) and 'interval_seconds' (positive int)")
        sched = flow_scheduler.add(flow_id, interval)
        return {"created": True, "schedule": sched.to_dict()}
    raise ValueError(f"unknown action '{action}'; supported: list, create")


async def _golden_eval(inputs: Dict[str, Any]) -> Dict[str, Any]:
    compare_to = inputs.get("compare_to")
    receipts_dir = inputs.get("receipts_dir")
    store = (
        EvaluationReceiptStore(receipts_dir)
        if inputs.get("save_receipt", True) or compare_to
        else None
    )
    receipt = await DriftDetector.run_evaluation_and_create_receipt(
        model_name=str(inputs.get("model_name") or "keelway-local-default"),
        store=store if inputs.get("save_receipt", True) else None,
    )
    out = receipt.to_dict()
    if compare_to:
        if store is None:
            store = EvaluationReceiptStore(receipts_dir)
        if str(compare_to) == "latest":
            baseline = next(
                (
                    r
                    for r in (
                        store.get_receipt(entry["eval_run_id"])
                        for entry in store.list_receipts()
                    )
                    if r is not None and r.eval_run_id != receipt.eval_run_id
                ),
                None,
            )
        else:
            baseline = store.get_receipt(str(compare_to))
        if baseline is None:
            raise ValueError(f"baseline receipt '{compare_to}' not found in {store.receipts_dir}")
        out["drift"] = DriftDetector.compare(baseline, receipt).to_dict()
    return out


BUILTIN_HANDLERS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "kstack/airgap-verify": _airgap_verify,
    "kstack/flight-tape-verify": _flight_tape_verify,
    "kstack/cost-ledger": _cost_ledger,
    "kstack/finops-forecast": _finops_forecast,
    "kstack/kbrain-fact": _kbrain_fact,
    "kstack/mesh-verify": _mesh_verify,
    "kstack/sbom-audit": _sbom_audit,
    "kstack/schedule-ops": _schedule_ops,
    "kstack/golden-eval": _golden_eval,
}
