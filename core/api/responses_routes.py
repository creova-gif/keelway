"""Keelway Unified Responses (`/v1/responses`), Routing Provenance (`/v1/routing/*`), and Eval APIs (`/v1/eval/*`)."""
from __future__ import annotations

import json, logging, re, time, uuid
from collections import OrderedDict
from dataclasses import asdict
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, Tuple, Union
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.api.schemas import MessageSchema, Provider
from core.eval.hybrid_benchmark import BenchmarkReport, HybridBenchmarkRunner
from core.eval.mirofish_swarm import MiroFishSwarmHarness
from core.models.adapters.open_weight import OpenWeightProviderAdapter
from core.models.gateway import ModelGateway, gateway
from core.models.provider import BaseModelProvider, ChatCompletionRequest, ChatCompletionResponse, StreamChunk
from core.models.registry import DeploymentType, ModelCategory, ModelMetadata, model_registry
from core.models.speculative import SpeculativeConfig, SpeculativeDecodingEngine
from core.security.auth import current_principal, require
from core.security.error_disclosure import public_inference_detail
from core.security.rbac import Permission
from core.security.redact import redact_payload, redact_text
from core.security.style import StyleEngine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Responses & Routing"])


def _clean_text(text: str) -> str:
    cleaned, _ = redact_text(text or "")
    return cleaned


class StoredResponseEntry(BaseModel):
    response: Dict[str, Any]
    messages: List[MessageSchema]


class ResponseStore:
    """Bounded FIFO/LRU in-memory store (max 500) for stateful `/v1/responses` chaining."""
    def __init__(self, max_entries: int = 500):
        self.max_entries = max_entries
        self._entries: "OrderedDict[str, StoredResponseEntry]" = OrderedDict()

    def save(self, response_id: str, response_obj: Dict[str, Any], messages: List[MessageSchema]) -> None:
        clean_resp, _ = redact_payload(response_obj)
        if isinstance(clean_resp.get("output_text"), str):
            clean_resp["output_text"] = _clean_text(clean_resp["output_text"])
        for item in clean_resp.get("output", []):
            for blk in item.get("content", []):
                if isinstance(blk, dict) and isinstance(blk.get("text"), str):
                    blk["text"] = _clean_text(blk["text"])
        clean_msgs = [MessageSchema(role=m.role, content=_clean_text(m.content)) for m in messages]
        if response_id in self._entries:
            self._entries.move_to_end(response_id)
        self._entries[response_id] = StoredResponseEntry(response=clean_resp, messages=clean_msgs)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def get(self, response_id: str) -> Optional[StoredResponseEntry]:
        return self._entries.get(response_id)

    def clear(self) -> None:
        self._entries.clear()


class RoutingDecisionLedger:
    """Bounded ledger of explainable hybrid routing decisions and 4D provenance."""
    def __init__(self, max_entries: int = 500):
        self.max_entries = max_entries
        self._records: List[Dict[str, Any]] = []

    def record(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        clean_entry, _ = redact_payload(entry)
        self._records.append(clean_entry)
        if len(self._records) > self.max_entries:
            self._records = self._records[-self.max_entries :]
        return clean_entry

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(reversed(self._records[-limit:]))

    def clear(self) -> None:
        self._records.clear()


response_store = ResponseStore(max_entries=500)
routing_ledger = RoutingDecisionLedger(max_entries=500)


class ResponsesCreateRequest(BaseModel):
    model: Optional[str] = None
    input: Union[str, List[Dict[str, Any]]]
    instructions: Optional[str] = None
    previous_response_id: Optional[str] = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=4096, ge=1, le=128000)
    text: Optional[Dict[str, Any]] = None
    stream: bool = False
    store: bool = True
    privacy_level: str = "standard"
    required_capabilities: List[str] = Field(default_factory=list)
    max_cost_usd: Optional[float] = None
    speculative: bool = False
    draft_model: str = "keelway-nano:1.5b"


class RoutingExplainRequest(BaseModel):
    model: Optional[str] = None
    prompt: str = "Evaluate candidate routing policy."
    messages: Optional[List[MessageSchema]] = None
    max_tokens: int = Field(default=1024, ge=1, le=128000)
    privacy_level: str = "standard"
    required_capabilities: List[str] = Field(default_factory=list)
    max_cost_usd: Optional[float] = None
    preferred_provider: Optional[Provider] = None
    category_preference: Optional[ModelCategory] = None
    endpoint_url: Optional[str] = None


class SwarmEvalRequest(BaseModel):
    seed_text: str = "Keelway launches unified hybrid AI routing with zero-egress OpenCore and frontier reasoning."
    simulation_goal: str = "Evaluate developer adoption, cost arbitrage, and enterprise security posture."
    entities_spec: List[Dict[str, Any]] = Field(default_factory=lambda: [
        {"name": "Adaeze Okafor", "type": "Architect", "summary": "Evaluates hybrid AI latency and spend.", "tier": "influencer"},
        {"name": "Kwame Mensah", "type": "SecurityLead", "summary": "Enforces zero-egress PII containment.", "tier": "citizen"},
    ])
    rounds: int = Field(default=2, ge=1, le=5)
    injected_event: Optional[str] = None
    mode: Literal["mock", "live"] = "mock"
    frontier_model: str = "gemini-3.5-flash-lite"
    opencore_model: str = "keelway-core:7b"
    draft_model: str = "keelway-nano:1.5b"


class BenchmarkEvalRequest(BaseModel):
    models: Optional[List[str]] = None
    open_weight_model: str = "keelway-core:7b"
    closed_model: str = "gpt-4o"
    mode: Literal["mock", "live"] = "mock"


def _normalize_input_items(raw_input: Union[str, List[Dict[str, Any]]]) -> List[MessageSchema]:
    if isinstance(raw_input, str):
        if not raw_input.strip():
            raise HTTPException(status_code=400, detail="Input text must not be empty.")
        return [MessageSchema(role="user", content=raw_input)]
    if not raw_input:
        raise HTTPException(status_code=400, detail="Input items list must not be empty.")
    normalized: List[MessageSchema] = []
    for item in raw_input:
        r = str(item.get("role", "user")).lower()
        role = "system" if r == "developer" else (r if r in ("system", "user", "assistant") else "user")
        c = item.get("content", "")
        if isinstance(c, str):
            text_val = c
        elif isinstance(c, list):
            text_val = "\n".join(str(b.get("text", "")) for b in c if isinstance(b, dict) and b.get("text"))
        else:
            text_val = str(c)
        if text_val:
            normalized.append(MessageSchema(role=role, content=text_val))
    if not normalized:
        raise HTTPException(status_code=400, detail="No valid message content found in input.")
    return normalized


def _extract_response_format(text_cfg: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    fmt = text_cfg.get("format") if isinstance(text_cfg, dict) else None
    return {"type": "json_object"} if isinstance(fmt, dict) and fmt.get("type") in ("json_object", "json_schema") else None


def _classify_endpoint_host(endpoint_url: Optional[str]) -> str:
    if not endpoint_url:
        return "default"
    host = (urlparse(endpoint_url).hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return "loopback"
    if host.endswith((".internal", ".local", ".vpc", ".corp", ".lan")) or host.startswith(("10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.", "172.2", "172.30.", "172.31.")):
        return "vpc"
    return "external"


def resolve_governance_provenance(
    model_id: Optional[str],
    selected_provider: Optional[Provider],
    endpoint_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Distinguish license, hosting topology, operator, and data boundary (open-weight != automatically local)."""
    meta: Optional[ModelMetadata] = model_registry.get(model_id) if model_id else None
    if meta is None and selected_provider == Provider.LOCAL:
        meta = model_registry.get("keelway-core:7b")
    is_open = meta.category == ModelCategory.OPEN_WEIGHT if meta else (selected_provider == Provider.LOCAL)
    license_id = meta.license if meta else ("Apache-2.0" if is_open else "Proprietary")
    host_kind = _classify_endpoint_host(endpoint_url)
    vendors = {Provider.OPENAI: "third_party_vendor: OpenAI", Provider.ANTHROPIC: "third_party_vendor: Anthropic", Provider.GOOGLE: "third_party_vendor: Google", Provider.GEMINI: "third_party_vendor: Google"}

    if not is_open or (selected_provider and selected_provider != Provider.LOCAL):
        prov_key = selected_provider or (meta.provider if meta else Provider.OPENAI)
        hosting, operator, boundary = "managed_public_cloud", vendors.get(prov_key, "third_party_vendor: Cloud API"), "external_vendor_api"
    elif host_kind == "external":
        hosting, operator, boundary = "managed_public_cloud", "third_party_vendor: External Open-Weight Endpoint", "external_vendor_api"
    elif host_kind == "vpc" or (meta and meta.deployment == DeploymentType.SELF_HOSTED_GPU and host_kind != "loopback"):
        hosting, operator, boundary = "self_hosted_vpc_gpu", "customer_self_operated", "vpc_network_boundary"
    elif (model_id or "keelway-core:7b").startswith("keelway-") and host_kind != "loopback":
        hosting, operator, boundary = "in_process_opencore", "customer_self_operated", "zero_external_egress"
    else:
        hosting, operator, boundary = "local_daemon", "customer_self_operated", "zero_external_egress"

    return {
        "license": license_id,
        "weight_category": "open_weight" if is_open else "closed_proprietary",
        "hosting": hosting,
        "operator": operator,
        "data_boundary": boundary,
        "open_weight_implies_local": False,
        "residency_note": "Zero external egress verified on local host." if boundary == "zero_external_egress" else "Traffic crosses local host boundary; open-weight license alone does not guarantee local residency.",
    }


def _build_response_object(
    resp_id: str, msg_id: str, created_at: int, model: str, previous_response_id: Optional[str],
    output_text: str, input_tokens: int, output_tokens: int, meta: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "id": resp_id, "object": "response", "created_at": created_at, "status": "completed",
        "model": model, "previous_response_id": previous_response_id,
        "output": [{"id": msg_id, "type": "message", "status": "completed", "role": "assistant", "content": [{"type": "output_text", "text": output_text, "annotations": []}]}],
        "output_text": output_text,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": input_tokens + output_tokens},
        "keelway_metadata": meta,
    }


async def _run_inference(
    chat_req: ChatCompletionRequest, speculative: bool, draft_model: str, target_prov: Provider, route_reason: str,
) -> Tuple[str, str, int, int, Dict[str, Any]]:
    if not speculative:
        comp = await gateway.chat_complete(chat_req)
        meta = {"provider": comp.provider.value, "category": comp.category.value, "cost_usd": comp.cost_usd, "latency_ms": comp.latency_ms, "routing_reason": comp.routing_reason, "speculative": False}
        return comp.content, comp.model, comp.usage.get("prompt_tokens", 0), comp.usage.get("completion_tokens", 0), meta

    t_adap, d_adap = gateway.adapters.get(target_prov), gateway.adapters.get(Provider.LOCAL)
    if not isinstance(t_adap, BaseModelProvider) or not isinstance(d_adap, BaseModelProvider):
        raise RuntimeError("Speculative decoding adapters unavailable.")
    target_model = chat_req.model or "keelway-core:7b"
    spec_res = await SpeculativeDecodingEngine(draft_adapter=d_adap, target_adapter=t_adap).generate_speculative(
        chat_req, config=SpeculativeConfig(draft_model_id=draft_model, target_model_id=target_model, gamma=16),
    )
    clean_out, _ = StyleEngine.de_slop(spec_res.text)
    in_tok, out_tok = sum(len(m.content.split()) for m in chat_req.messages) + 8, max(1, spec_res.tokens_generated)
    meta = {
        "provider": target_prov.value, "category": "open_weight" if target_prov == Provider.LOCAL else "closed_proprietary",
        "cost_usd": 0.0, "latency_ms": spec_res.latency_ms,
        "routing_reason": f"speculative ({draft_model} -> {target_model}); {route_reason}", "speculative": True,
        "draft_model": draft_model, "acceptance_rate": spec_res.acceptance_rate, "effective_speedup_ratio": spec_res.effective_speedup_ratio,
    }
    return clean_out, target_model, in_tok, out_tok, meta


@router.post("/v1/responses", dependencies=[Depends(require(Permission.EXECUTE_AGENT))])
async def create_response(request: ResponsesCreateRequest):
    """Unified stateful & stateless Responses endpoint supporting OpenCore, Cloud, SSE, and Speculative Decoding."""
    history: List[MessageSchema] = []
    if request.previous_response_id:
        prior = response_store.get(request.previous_response_id)
        if not prior:
            raise HTTPException(status_code=404, detail="Previous response ID not found in store.")
        history.extend(prior.messages)

    new_messages = _normalize_input_items(request.input)
    full_messages = (
        [MessageSchema(role="system", content=request.instructions)] + [m for m in history if m.role != "system"]
        if request.instructions else list(history)
    ) + new_messages

    sanitized_messages: List[MessageSchema] = []
    for m in full_messages:
        sec_res = gateway.security.inspect_and_sanitize(m.content)
        if not sec_res.is_safe:
            raise HTTPException(status_code=400, detail="Request blocked by Security Gateway policy.")
        sanitized_messages.append(MessageSchema(role=m.role, content=sec_res.sanitized_text))

    probe_req = ChatCompletionRequest(
        messages=sanitized_messages, model=request.model, temperature=request.temperature,
        max_tokens=request.max_output_tokens, response_format=_extract_response_format(request.text),
        stream=request.stream, privacy_level=request.privacy_level,
        required_capabilities=request.required_capabilities, max_cost_usd=request.max_cost_usd,
    )
    provider_order, route_reason = gateway.explain_route(probe_req)
    if not provider_order:
        if request.privacy_level == "private":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Privacy policy blocked external cloud provider (zero-egress containment).")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No model provider satisfies request constraints.")

    if request.speculative and request.privacy_level == "private":
        draft_order, _ = gateway.explain_route(probe_req.model_copy(update={"model": request.draft_model}))
        if not draft_order or any(p != Provider.LOCAL for p in draft_order):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Privacy policy blocked non-local speculative draft model (zero-egress containment).")

    effective_model = request.model
    if effective_model is None and provider_order[0] == Provider.LOCAL:
        local_adapter = gateway.adapters.get(Provider.LOCAL)
        if not local_adapter or not local_adapter.is_available():
            effective_model = "keelway-core:7b"

    chat_req = probe_req.model_copy(update={"model": effective_model})
    resp_id, msg_id, created_at = f"resp_{uuid.uuid4().hex[:16]}", f"msg_{uuid.uuid4().hex[:16]}", int(time.time())

    if request.stream:
        async def sse_generator() -> AsyncIterator[str]:
            created_evt = {"type": "response.created", "response": {"id": resp_id, "object": "response", "created_at": created_at, "status": "in_progress", "model": effective_model or "keelway-core:7b", "output": []}}
            yield f"event: response.created\ndata: {json.dumps(created_evt)}\n\n"
            t0 = time.perf_counter()
            try:
                deltas: List[str] = []
                in_tok, out_tok = 0, 0
                final_model = effective_model or "keelway-core:7b"
                meta: Dict[str, Any] = {}
                if not request.speculative:
                    try:
                        prov_val = provider_order[0].value
                        async for chunk in gateway.stream_chat(chat_req):
                            final_model, prov_val = chunk.model or final_model, chunk.provider.value
                            if chunk.delta_content:
                                deltas.append(chunk.delta_content)
                            if chunk.usage:
                                in_tok, out_tok = chunk.usage.get("prompt_tokens", in_tok), chunk.usage.get("completion_tokens", out_tok)
                        meta = {"provider": prov_val, "category": "open_weight" if prov_val == "local" else "closed_proprietary", "cost_usd": 0.0, "latency_ms": round((time.perf_counter() - t0) * 1000.0, 2), "routing_reason": route_reason, "speculative": False}
                    except Exception:
                        deltas = []
                if not deltas:
                    txt, final_model, in_tok, out_tok, meta = await _run_inference(chat_req, request.speculative, request.draft_model, provider_order[0], route_reason)
                    deltas = [tok for tok in re.findall(r"\S+\s*|\n+", txt) if tok] or [txt]

                for piece in deltas:
                    delta_evt = {"type": "response.output_text.delta", "response_id": resp_id, "item_id": msg_id, "output_index": 0, "content_index": 0, "delta": piece}
                    yield f"event: response.output_text.delta\ndata: {json.dumps(delta_evt)}\n\n"

                full_text = "".join(deltas)
                in_tok = in_tok or (sum(len(m.content.split()) for m in sanitized_messages) + 6)
                out_tok = out_tok or max(1, len(full_text.split()))
                completed_obj = _build_response_object(resp_id, msg_id, created_at, final_model, request.previous_response_id, full_text, in_tok, out_tok, meta)
                if request.store:
                    response_store.save(resp_id, completed_obj, full_messages + [MessageSchema(role="assistant", content=full_text)])
                yield f"event: response.completed\ndata: {json.dumps({'type': 'response.completed', 'response': completed_obj})}\n\n"
            except Exception as exc:
                logger.warning("Responses SSE stream failed", exc_info=exc)
                yield f"event: error\ndata: {json.dumps({'type': 'error', 'error': {'message': public_inference_detail(exc)}})}\n\n"

        return StreamingResponse(sse_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})

    try:
        out_txt, f_model, in_tok, out_tok, meta = await _run_inference(chat_req, request.speculative, request.draft_model, provider_order[0], route_reason)
        resp_obj = _build_response_object(resp_id, msg_id, created_at, f_model, request.previous_response_id, out_txt, in_tok, out_tok, meta)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Responses inference failure", exc_info=exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=public_inference_detail(exc)) from exc

    if request.store:
        response_store.save(resp_id, resp_obj, full_messages + [MessageSchema(role="assistant", content=resp_obj["output_text"])])
    return resp_obj


@router.get("/v1/responses/{response_id}", dependencies=[Depends(current_principal)])
async def get_response(response_id: str) -> Dict[str, Any]:
    """Retrieve a previously stored redacted response object by ID."""
    entry = response_store.get(response_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Response not found.")
    return entry.response


@router.post("/v1/routing/explain", dependencies=[Depends(current_principal)])
async def explain_routing_decision(request: RoutingExplainRequest) -> Dict[str, Any]:
    """Evaluate candidate routing policy and 4-dimension provenance without spending tokens."""
    msgs = request.messages or [MessageSchema(role="user", content=request.prompt)]
    probe = ChatCompletionRequest(
        messages=msgs, model=request.model, max_tokens=request.max_tokens, privacy_level=request.privacy_level,
        required_capabilities=request.required_capabilities, max_cost_usd=request.max_cost_usd,
        preferred_provider=request.preferred_provider, category_preference=request.category_preference,
    )
    provider_order, reason = gateway.explain_route(probe)
    selected: Optional[Provider] = provider_order[0] if provider_order else None
    provenance = resolve_governance_provenance(request.model, selected, request.endpoint_url)

    privacy_compliant = bool(provider_order)
    if request.privacy_level == "private" and provenance["data_boundary"] != "zero_external_egress":
        privacy_compliant, selected, provider_order = False, None, []
        reason = f"private: blocked because data_boundary={provenance['data_boundary']} (open-weight does not automatically mean local or zero-egress)"

    est_cost = round(gateway.estimate_cost_usd(selected, probe), 6) if selected else 0.0
    return routing_ledger.record({
        "decision_id": f"rdec_{uuid.uuid4().hex[:12]}", "timestamp": time.time(),
        "requested_model": request.model, "selected_provider": selected.value if selected else None,
        "fallback_chain": [p.value for p in provider_order], "reason": reason,
        "governance_provenance": provenance, "estimated_cost_usd": 0.0 if est_cost == float("inf") else est_cost,
        "privacy_level": request.privacy_level, "privacy_compliant": privacy_compliant,
    })


@router.get("/v1/routing/decisions", dependencies=[Depends(current_principal)])
async def list_routing_decisions(limit: int = Query(default=50, ge=1, le=200)) -> Dict[str, Any]:
    """Return recent explainable hybrid routing decisions."""
    items = routing_ledger.recent(limit=limit)
    return {"object": "list", "count": len(items), "decisions": items}


class _MockSwarmFrontierProvider(BaseModelProvider):
    """Zero-cost deterministic frontier provider for instant offline `/v1/eval/swarm` verification."""

    provider_id = Provider.GEMINI
    category = ModelCategory.CLOSED_PROPRIETARY

    def is_available(self) -> bool:
        return True

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        sys_txt = request.messages[0].content.lower() if request.messages else ""
        usr_txt = request.messages[-1].content if request.messages else ""
        if "[SPECULATIVE VERIFICATION]" in usr_txt:
            content = "ACCEPT"
        elif "entity_types" in sys_txt:
            content = json.dumps({"entity_types": [{"name": "Architect", "description": "AI platform lead", "attributes": [], "examples": ["Adaeze"]}], "edge_types": [{"name": "DEBATES_WITH", "description": "Evaluates tradeoffs", "source_targets": [], "attributes": []}], "analysis_summary": "Hybrid local-first and cloud escalation ontology synthesized."})
        elif "persona" in sys_txt:
            content = json.dumps({"bio": "Principal systems architect.", "persona": "Analytical, cost-disciplined.", "profession": "Architect", "interested_topics": ["Hybrid Routing", "Zero-Egress"]})
        elif "stance" in sys_txt:
            content = json.dumps({"action": "CREATE_POST", "stance": "supportive", "content": "Hybrid OpenCore + frontier routing preserves PII locally."})
        else:
            content = "Consensus: local-first OpenCore handling routine turns with frontier verification cut spend >65%."
        return ChatCompletionResponse(
            model=request.model or "gemini-3.5-flash-lite", provider=self.provider_id, category=self.category,
            content=content, usage={"prompt_tokens": 24, "completion_tokens": 32, "total_tokens": 56},
            latency_ms=8.4, cost_usd=0.000018, routing_reason="mock frontier swarm adapter",
        )

    async def stream_complete(self, request: ChatCompletionRequest) -> AsyncIterator[StreamChunk]:
        resp = await self.complete(request)
        yield StreamChunk(model=resp.model, provider=self.provider_id, delta_content=resp.content, finish_reason="stop", usage=resp.usage)

    async def health_check(self) -> Dict[str, Any]:
        return {"status": "ok", "mode": "mock"}


@router.post("/v1/eval/swarm", dependencies=[Depends(require(Permission.EXECUTE_AGENT))])
async def run_swarm_evaluation(request: SwarmEvalRequest) -> Dict[str, Any]:
    """Execute MiroFish 5-stage multi-agent swarm evaluation in instant mock or live gateway mode."""
    if request.mode == "mock":
        mock_f, loc_p = _MockSwarmFrontierProvider(), OpenWeightProviderAdapter()
        eval_gw = ModelGateway(adapters={Provider.LOCAL: loc_p, Provider.GEMINI: mock_f, Provider.GOOGLE: mock_f})
        draft_prov, target_prov = loc_p, mock_f
    else:
        eval_gw, draft_prov = gateway, gateway.adapters[Provider.LOCAL]
        target_prov = gateway.adapters.get(Provider.GEMINI) or gateway.adapters[Provider.OPENAI]
    try:
        harness = MiroFishSwarmHarness(gateway=eval_gw, draft_provider=draft_prov, target_provider=target_prov, frontier_model=request.frontier_model, opencore_model=request.opencore_model, draft_model=request.draft_model)
        report = await harness.run_full_experiment(seed_text=request.seed_text, simulation_goal=request.simulation_goal, entities_spec=request.entities_spec, rounds=request.rounds, injected_event=request.injected_event)
    except Exception as exc:
        logger.warning("Swarm evaluation failed", exc_info=exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=public_inference_detail(exc)) from exc
    clean_eps = [{**ep, "content": _clean_text(ep["content"][0] if isinstance(ep.get("content"), (tuple, list)) and ep["content"] else str(ep.get("content", "")))} for ep in report.episodes]
    return {
        "mode": request.mode, "graph_id": report.graph_id, "ontology": report.ontology,
        "profiles": [asdict(p) for p in report.profiles], "episodes": clean_eps,
        "speculative_report": _clean_text(report.speculative_report), "speculative_acceptance_rate": report.speculative_acceptance_rate,
        "security_checks": report.security_checks,
        "telemetry": {"total_calls": report.total_calls, "open_weight_calls": report.open_weight_calls, "closed_cloud_calls": report.closed_cloud_calls, "total_cost_usd": report.total_cost_usd, "estimated_all_cloud_cost_usd": report.estimated_all_cloud_cost_usd, "savings_pct": report.savings_pct, "elapsed_ms": report.elapsed_ms},
    }


@router.post("/v1/eval/benchmark", dependencies=[Depends(require(Permission.EXECUTE_AGENT))])
async def run_hybrid_benchmark(request: BenchmarkEvalRequest) -> Dict[str, Any]:
    """Run the 7-dimension Keelway Hybrid Model Benchmark across selected models."""
    target_models = request.models or [request.open_weight_model, request.closed_model]
    for mid in target_models:
        if not model_registry.get(mid):
            raise HTTPException(status_code=404, detail=f"Model '{mid}' not found in model registry.")
    runner, report, mock_flag = HybridBenchmarkRunner(), BenchmarkReport(), request.mode == "mock"
    for mid in target_models:
        report.results.extend(await runner.run_model_benchmark(mid, gateway=gateway, mock_mode=mock_flag))
    dim_scores: Dict[str, Dict[str, float]] = {}
    for item in report.results:
        dim_scores.setdefault(item.model_id, {})[item.dimension] = item.quality_score
    return {"mode": request.mode, "dimensions": [t.dimension for t in runner.tasks], "summary": report.summary(), "dimension_scores": dim_scores, "results": [asdict(r) for r in report.results]}
