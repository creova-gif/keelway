"""
Keelway Client SDK — Phase 4 Workspace & Phase 5 Runtime Mixins (`client.platform`).

Defines `AsyncPlatformRuntimeMixin` and `SyncPlatformRuntimeMixin` inherited by
`AsyncPlatformClient` and `SyncPlatformClient` for 100% sync + async parity across
Phase 4 Workspace endpoints and Phase 5 Multi-Workspace, RBAC, Vault, Webhooks, and SSE Execution.
"""

from __future__ import annotations

import codecs
import json as _json
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, Iterator, List, Optional
from urllib.parse import quote

import httpx

from core.sdk.errors import ConnectionError
from core.sdk.platform_enterprise_client import (
    AsyncPlatformEnterpriseMixin,
    SyncPlatformEnterpriseMixin,
)
from core.sdk.platform_kbrain_client import (
    AsyncPlatformKbrainMixin,
    SyncPlatformKbrainMixin,
)
from core.sdk.platform_kflow_client import (
    AsyncPlatformKflowMixin,
    SyncPlatformKflowMixin,
)
from core.sdk.platform_mcp_eval_client import (
    AsyncPlatformMcpEvalMixin,
    SyncPlatformMcpEvalMixin,
)

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient


def _seg(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be non-empty.")
    return quote(clean, safe="")


def _http_client(keelway_client: Any) -> Any:
    http = getattr(keelway_client, "_http", None)
    return http if http is not None else getattr(keelway_client, "_client")


def _raise_stream_error(res: httpx.Response) -> None:
    from core.sdk.client import _handle_response_error

    _handle_response_error(res)


def _doc_body(title: str, diataxis_kind: str, summary: str, body: str, linked_prd_id: Optional[str], workspace_id: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"title": title, "diataxis_kind": diataxis_kind, "summary": summary, "body": body, "workspace_id": workspace_id}
    if linked_prd_id is not None:
        out["linked_prd_id"] = linked_prd_id
    return out


def _filter_docs_by_kind(res: Dict[str, Any], diataxis_kind: Optional[str]) -> Dict[str, Any]:
    if diataxis_kind is None or not isinstance(res, dict) or not isinstance(res.get("docs"), list):
        return res
    filtered = [doc for doc in res["docs"] if doc.get("diataxis_kind") == diataxis_kind]
    out: Dict[str, Any] = {**res, "docs": filtered, "count": len(filtered)}
    if "total" in out:
        out["total"] = len(filtered)
    return out


def _feedback_body(persona: str, quote_text: str, impact_score: float, linked_prd_id: Optional[str], workspace_id: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"persona": persona, "quote": quote_text, "impact_score": impact_score, "workspace_id": workspace_id}
    if linked_prd_id is not None:
        out["linked_prd_id"] = linked_prd_id
    return out


def _scan_body(snippet: str, target_path: str, write_paths: Optional[List[str]], workspace_id: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "snippet": snippet, "content": snippet, "target_path": target_path, "target_name": target_path, "workspace_id": workspace_id
    }
    if write_paths is not None:
        out["write_paths"] = list(write_paths)
    return out


def _webhook_body(url: str, events: List[str], description: str, secret: Optional[str], workspace_id: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"url": url, "events": list(events), "description": description, "workspace_id": workspace_id}
    if secret is not None:
        out["secret"] = secret
    return out


class _SseChunkDecoder:
    """Chunk-boundary-safe UTF-8 and line-buffered SSE frame parser (`data: {...}` / `data: [DONE]`)."""

    def __init__(self) -> None:
        self._utf8 = codecs.getincrementaldecoder("utf-8")()
        self._buf = ""
        self.done = False

    def feed(self, chunk: bytes, *, final: bool = False) -> List[Dict[str, Any]]:
        if self.done:
            return []
        self._buf += self._utf8.decode(chunk, final=final)
        events: List[Dict[str, Any]] = []
        while True:
            nl_idx = self._buf.find("\n")
            if nl_idx == -1:
                if final and self._buf:
                    line, self._buf = self._buf.rstrip("\r"), ""
                    parsed = self._parse_line(line)
                    if parsed is not None:
                        events.append(parsed)
                break
            line, self._buf = self._buf[:nl_idx].rstrip("\r"), self._buf[nl_idx + 1 :]
            parsed = self._parse_line(line)
            if parsed is not None:
                events.append(parsed)
            if self.done:
                break
        return events

    def _parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        stripped = line.strip()
        if not stripped or stripped.startswith(":") or not stripped.startswith("data:"):
            return None
        data_str = stripped[5:].strip()
        if not data_str:
            return None
        if data_str == "[DONE]":
            self.done = True
            return None
        decoded = _json.loads(data_str)
        return decoded if isinstance(decoded, dict) else {"data": decoded}


class AsyncPlatformRuntimeMixin(
    AsyncPlatformMcpEvalMixin,
    AsyncPlatformKflowMixin,
    AsyncPlatformEnterpriseMixin,
    AsyncPlatformKbrainMixin,
):
    """Asynchronous Phase 4 & Phase 5 `/v1/platform/*` runtime methods."""

    _client: "AsyncKeelwayClient"

    async def list_docs(self, workspace_id: str = "default", diataxis_kind: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"workspace_id": workspace_id, **({"diataxis_kind": diataxis_kind} if diataxis_kind is not None else {})}
        return _filter_docs_by_kind(await self._client._req("GET", "/v1/platform/docs", params=params), diataxis_kind)

    async def create_doc(
        self, title: str, diataxis_kind: str = "reference", summary: str = "", body: str = "", linked_prd_id: Optional[str] = None, workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/platform/docs", json=_doc_body(title, diataxis_kind, summary, body, linked_prd_id, workspace_id))

    async def update_doc(
        self, doc_id: str, title: str, diataxis_kind: str = "reference", summary: str = "", body: str = "", linked_prd_id: Optional[str] = None, workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return await self._client._req("PUT", f"/v1/platform/docs/{_seg(doc_id, 'doc_id')}", json=_doc_body(title, diataxis_kind, summary, body, linked_prd_id, workspace_id))

    async def update_issue(self, issue_id: str, workspace_id: str = "default", **patch: Any) -> Dict[str, Any]:
        return await self._client._req("PATCH", f"/v1/platform/pm/issues/{_seg(issue_id, 'issue_id')}", json={"workspace_id": workspace_id, **patch})

    async def list_feedback(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/product/feedback", params={"workspace_id": workspace_id})

    async def create_feedback(
        self, persona: str, quote: str, impact_score: float = 8.5, linked_prd_id: Optional[str] = "PRD-01", workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/platform/product/feedback", json=_feedback_body(persona, quote, impact_score, linked_prd_id, workspace_id))

    async def scan_workspace_security(
        self, snippet: str, target_path: str = "manifest.json", write_paths: Optional[List[str]] = None, workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/platform/security/scan", json=_scan_body(snippet, target_path, write_paths, workspace_id))

    async def list_workspaces(self) -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/workspaces")

    async def create_workspace(self, workspace_id: str, name: str, branch: str = "main", isolation_mode: str = "seatbelt_local") -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/platform/workspaces", json={"id": workspace_id, "name": name, "branch": branch, "isolation_mode": isolation_mode})

    async def list_rbac_members(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/rbac/members", params={"workspace_id": workspace_id})

    async def upsert_rbac_member(self, actor_id: str, role: str, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/platform/rbac/members", json={"actor_id": actor_id, "role": role, "workspace_id": workspace_id})

    async def check_rbac(self, actor_id: str, permission: str, role: Optional[str] = None, workspace_id: str = "default") -> Dict[str, Any]:
        body: Dict[str, Any] = {"actor_id": actor_id, "permission": permission, "workspace_id": workspace_id, **({"role": role} if role is not None else {})}
        return await self._client._req("POST", "/v1/platform/rbac/check", json=body)

    async def list_secrets(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/vault/secrets", params={"workspace_id": workspace_id})

    async def put_secret(self, name: str, secret_value: str, namespace: str = "byom", workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/platform/vault/secrets", json={"name": name, "secret_value": secret_value, "namespace": namespace, "workspace_id": workspace_id})

    async def rotate_secret(self, name: str, secret_value: str, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("POST", f"/v1/platform/vault/secrets/{_seg(name, 'name')}/rotate", json={"secret_value": secret_value, "workspace_id": workspace_id})

    async def delete_secret(self, name: str, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("DELETE", f"/v1/platform/vault/secrets/{_seg(name, 'name')}", params={"workspace_id": workspace_id})

    async def list_webhooks(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/webhooks", params={"workspace_id": workspace_id})

    async def create_webhook(
        self, url: str, events: List[str], description: str = "", secret: Optional[str] = None, workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/platform/webhooks", json=_webhook_body(url, events, description, secret, workspace_id))

    async def delete_webhook(self, webhook_id: str, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("DELETE", f"/v1/platform/webhooks/{_seg(webhook_id, 'webhook_id')}", params={"workspace_id": workspace_id})

    async def test_webhook(
        self, webhook_id: str, event_type: str = "agent.run.completed", payload: Optional[Dict[str, Any]] = None, workspace_id: str = "default"
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"event_type": event_type, "workspace_id": workspace_id, **({"payload": dict(payload)} if payload is not None else {})}
        return await self._client._req("POST", f"/v1/platform/webhooks/{_seg(webhook_id, 'webhook_id')}/test", json=body)

    async def verify_webhook(self, payload: Any, signature: str, secret: str, timestamp: int, tolerance_seconds: int = 300) -> Dict[str, Any]:
        return await self._client._req(
            "POST", "/v1/platform/webhooks/verify", json={"payload": payload, "signature": signature, "secret": secret, "timestamp": timestamp, "tolerance_seconds": tolerance_seconds}
        )

    async def start_execution_run(
        self, kind: str, target_id: str, objective: str, requires_p10: bool = True, workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST", "/v1/platform/execution/runs", json={"kind": kind, "target_id": target_id, "objective": objective, "requires_p10": requires_p10, "workspace_id": workspace_id, "stream": False}
        )

    async def stream_execution_events(self, run_id: str) -> AsyncIterator[Dict[str, Any]]:
        path, decoder = f"/v1/platform/execution/runs/{_seg(run_id, 'run_id')}/events", _SseChunkDecoder()
        try:
            async with _http_client(self._client).stream("GET", path) as res:
                if not res.is_success:
                    await res.aread()
                    _raise_stream_error(res)
                async for chunk in res.aiter_bytes():
                    for event in decoder.feed(chunk):
                        yield event
                    if decoder.done:
                        return
                for event in decoder.feed(b"", final=True):
                    yield event
        except httpx.ConnectError as exc:
            raise ConnectionError(f"Failed to connect to Keelway daemon at {self._client.base_url}: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise ConnectionError(f"Keelway daemon request timed out: {exc}") from exc

    async def resolve_execution_p10(self, run_id: str, decision: str, approver: str = "local-operator", reason: str = "") -> Dict[str, Any]:
        return await self._client._req("POST", f"/v1/platform/execution/runs/{_seg(run_id, 'run_id')}/p10", json={"decision": decision, "approver": approver, "reason": reason})

    async def simulate_pricing(
        self, schedule: str = "compare", seats: int = 8, monthly_api_spend_usd: float = 1200.0, run_swarm: bool = True
    ) -> Dict[str, Any]:
        body = {"schedule": schedule, "seats": seats, "monthly_api_spend_usd": monthly_api_spend_usd, "run_swarm": run_swarm}
        return await self._client._req("POST", "/v1/platform/pricing/simulate", json=body)


class SyncPlatformRuntimeMixin(
    SyncPlatformMcpEvalMixin,
    SyncPlatformKflowMixin,
    SyncPlatformEnterpriseMixin,
    SyncPlatformKbrainMixin,
):
    """Synchronous Phase 4 & Phase 5 `/v1/platform/*` runtime methods."""

    _client: "KeelwayClient"

    def list_docs(self, workspace_id: str = "default", diataxis_kind: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"workspace_id": workspace_id, **({"diataxis_kind": diataxis_kind} if diataxis_kind is not None else {})}
        return _filter_docs_by_kind(self._client._req("GET", "/v1/platform/docs", params=params), diataxis_kind)

    def create_doc(
        self, title: str, diataxis_kind: str = "reference", summary: str = "", body: str = "", linked_prd_id: Optional[str] = None, workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return self._client._req("POST", "/v1/platform/docs", json=_doc_body(title, diataxis_kind, summary, body, linked_prd_id, workspace_id))

    def update_doc(
        self, doc_id: str, title: str, diataxis_kind: str = "reference", summary: str = "", body: str = "", linked_prd_id: Optional[str] = None, workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return self._client._req("PUT", f"/v1/platform/docs/{_seg(doc_id, 'doc_id')}", json=_doc_body(title, diataxis_kind, summary, body, linked_prd_id, workspace_id))

    def update_issue(self, issue_id: str, workspace_id: str = "default", **patch: Any) -> Dict[str, Any]:
        return self._client._req("PATCH", f"/v1/platform/pm/issues/{_seg(issue_id, 'issue_id')}", json={"workspace_id": workspace_id, **patch})

    def list_feedback(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/product/feedback", params={"workspace_id": workspace_id})

    def create_feedback(
        self, persona: str, quote: str, impact_score: float = 8.5, linked_prd_id: Optional[str] = "PRD-01", workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return self._client._req("POST", "/v1/platform/product/feedback", json=_feedback_body(persona, quote, impact_score, linked_prd_id, workspace_id))

    def scan_workspace_security(
        self, snippet: str, target_path: str = "manifest.json", write_paths: Optional[List[str]] = None, workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return self._client._req("POST", "/v1/platform/security/scan", json=_scan_body(snippet, target_path, write_paths, workspace_id))

    def list_workspaces(self) -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/workspaces")

    def create_workspace(self, workspace_id: str, name: str, branch: str = "main", isolation_mode: str = "seatbelt_local") -> Dict[str, Any]:
        return self._client._req("POST", "/v1/platform/workspaces", json={"id": workspace_id, "name": name, "branch": branch, "isolation_mode": isolation_mode})

    def list_rbac_members(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/rbac/members", params={"workspace_id": workspace_id})

    def upsert_rbac_member(self, actor_id: str, role: str, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("POST", "/v1/platform/rbac/members", json={"actor_id": actor_id, "role": role, "workspace_id": workspace_id})

    def check_rbac(self, actor_id: str, permission: str, role: Optional[str] = None, workspace_id: str = "default") -> Dict[str, Any]:
        body: Dict[str, Any] = {"actor_id": actor_id, "permission": permission, "workspace_id": workspace_id, **({"role": role} if role is not None else {})}
        return self._client._req("POST", "/v1/platform/rbac/check", json=body)

    def list_secrets(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/vault/secrets", params={"workspace_id": workspace_id})

    def put_secret(self, name: str, secret_value: str, namespace: str = "byom", workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("POST", "/v1/platform/vault/secrets", json={"name": name, "secret_value": secret_value, "namespace": namespace, "workspace_id": workspace_id})

    def rotate_secret(self, name: str, secret_value: str, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("POST", f"/v1/platform/vault/secrets/{_seg(name, 'name')}/rotate", json={"secret_value": secret_value, "workspace_id": workspace_id})

    def delete_secret(self, name: str, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("DELETE", f"/v1/platform/vault/secrets/{_seg(name, 'name')}", params={"workspace_id": workspace_id})

    def list_webhooks(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/webhooks", params={"workspace_id": workspace_id})

    def create_webhook(
        self, url: str, events: List[str], description: str = "", secret: Optional[str] = None, workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return self._client._req("POST", "/v1/platform/webhooks", json=_webhook_body(url, events, description, secret, workspace_id))

    def delete_webhook(self, webhook_id: str, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("DELETE", f"/v1/platform/webhooks/{_seg(webhook_id, 'webhook_id')}", params={"workspace_id": workspace_id})

    def test_webhook(
        self, webhook_id: str, event_type: str = "agent.run.completed", payload: Optional[Dict[str, Any]] = None, workspace_id: str = "default"
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"event_type": event_type, "workspace_id": workspace_id, **({"payload": dict(payload)} if payload is not None else {})}
        return self._client._req("POST", f"/v1/platform/webhooks/{_seg(webhook_id, 'webhook_id')}/test", json=body)

    def verify_webhook(self, payload: Any, signature: str, secret: str, timestamp: int, tolerance_seconds: int = 300) -> Dict[str, Any]:
        return self._client._req(
            "POST", "/v1/platform/webhooks/verify", json={"payload": payload, "signature": signature, "secret": secret, "timestamp": timestamp, "tolerance_seconds": tolerance_seconds}
        )

    def start_execution_run(
        self, kind: str, target_id: str, objective: str, requires_p10: bool = True, workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST", "/v1/platform/execution/runs", json={"kind": kind, "target_id": target_id, "objective": objective, "requires_p10": requires_p10, "workspace_id": workspace_id, "stream": False}
        )

    def stream_execution_events(self, run_id: str) -> Iterator[Dict[str, Any]]:
        path, decoder = f"/v1/platform/execution/runs/{_seg(run_id, 'run_id')}/events", _SseChunkDecoder()
        try:
            with _http_client(self._client).stream("GET", path) as res:
                if not res.is_success:
                    res.read()
                    _raise_stream_error(res)
                for chunk in res.iter_bytes():
                    for event in decoder.feed(chunk):
                        yield event
                    if decoder.done:
                        return
                for event in decoder.feed(b"", final=True):
                    yield event
        except httpx.ConnectError as exc:
            raise ConnectionError(f"Failed to connect to Keelway daemon at {self._client.base_url}: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise ConnectionError(f"Keelway daemon request timed out: {exc}") from exc

    def resolve_execution_p10(self, run_id: str, decision: str, approver: str = "local-operator", reason: str = "") -> Dict[str, Any]:
        return self._client._req("POST", f"/v1/platform/execution/runs/{_seg(run_id, 'run_id')}/p10", json={"decision": decision, "approver": approver, "reason": reason})

    def simulate_pricing(
        self, schedule: str = "compare", seats: int = 8, monthly_api_spend_usd: float = 1200.0, run_swarm: bool = True
    ) -> Dict[str, Any]:
        body = {"schedule": schedule, "seats": seats, "monthly_api_spend_usd": monthly_api_spend_usd, "run_swarm": run_swarm}
        return self._client._req("POST", "/v1/platform/pricing/simulate", json=body)
