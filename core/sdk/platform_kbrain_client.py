"""
Keelway Client SDK — Phase 10 KBrain Hybrid Memory & KHub Air-Gapped Skill Mirror Mixins (`client.platform`).

Defines `AsyncPlatformKbrainMixin` and `SyncPlatformKbrainMixin` inherited by
`AsyncPlatformRuntimeMixin` and `SyncPlatformRuntimeMixin` for 100% sync + async parity across
`/v1/platform/kbrain/*` and `/v1/platform/khub/*`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from urllib.parse import quote

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient


def _kbrain_seg(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be non-empty.")
    return quote(clean, safe="")


def _kbrain_fact_body(
    key: str,
    statement: str,
    scope: str,
    provenance_uri: str,
    tags: Optional[List[str]],
    auto_approve: bool,
    workspace_id: str,
) -> Dict[str, Any]:
    clean_key = str(key or "").strip()
    if not clean_key:
        raise ValueError("key must be non-empty.")
    clean_statement = str(statement or "").strip()
    if not clean_statement:
        raise ValueError("statement must be non-empty.")
    return {
        "workspace_id": workspace_id,
        "key": clean_key,
        "statement": clean_statement,
        "scope": scope,
        "provenance_uri": provenance_uri,
        "tags": list(tags or []),
        "auto_approve": bool(auto_approve),
    }


def _kbrain_search_params(
    query: str,
    max_scope: str,
    include_conflicts: bool,
    limit: int,
    workspace_id: str,
) -> Dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "query": query,
        "max_scope": max_scope,
        "include_conflicts": bool(include_conflicts),
        "limit": int(limit),
    }


def _kbrain_resolve_body(resolution: str, workspace_id: str) -> Dict[str, Any]:
    clean_res = str(resolution or "").strip()
    if not clean_res:
        raise ValueError("resolution must be non-empty.")
    return {
        "workspace_id": workspace_id,
        "resolution": clean_res,
    }


class AsyncPlatformKbrainMixin:
    """Asynchronous Phase 10 KBrain Hybrid Memory & KHub Skill Mirror methods on `AsyncKeelwayClient.platform`."""

    _client: "AsyncKeelwayClient"

    async def record_kbrain_fact(
        self,
        key: str,
        statement: str,
        scope: str = "project",
        provenance_uri: str = "workspace",
        tags: Optional[List[str]] = None,
        auto_approve: bool = True,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/kbrain/facts",
            json=_kbrain_fact_body(
                key,
                statement,
                scope,
                provenance_uri,
                tags,
                auto_approve,
                workspace_id,
            ),
        )

    async def search_kbrain_facts(
        self,
        query: str = "",
        max_scope: str = "org",
        include_conflicts: bool = False,
        limit: int = 10,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "GET",
            "/v1/platform/kbrain/search",
            params=_kbrain_search_params(query, max_scope, include_conflicts, limit, workspace_id),
        )

    async def resolve_kbrain_fact(
        self,
        fact_id: str,
        resolution: str = "approve",
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            f"/v1/platform/kbrain/facts/{_kbrain_seg(fact_id, 'fact_id')}/resolve",
            json=_kbrain_resolve_body(resolution, workspace_id),
        )

    async def list_khub_skills(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req(
            "GET",
            "/v1/platform/khub/skills",
            params={"workspace_id": workspace_id},
        )

    async def verify_khub_mirror(
        self,
        skill_ids: Optional[List[str]] = None,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/khub/mirror/verify",
            json={"workspace_id": workspace_id, "skill_ids": list(skill_ids or [])},
        )


class SyncPlatformKbrainMixin:
    """Synchronous Phase 10 KBrain Hybrid Memory & KHub Skill Mirror methods on `KeelwayClient.platform`."""

    _client: "KeelwayClient"

    def record_kbrain_fact(
        self,
        key: str,
        statement: str,
        scope: str = "project",
        provenance_uri: str = "workspace",
        tags: Optional[List[str]] = None,
        auto_approve: bool = True,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/kbrain/facts",
            json=_kbrain_fact_body(
                key,
                statement,
                scope,
                provenance_uri,
                tags,
                auto_approve,
                workspace_id,
            ),
        )

    def search_kbrain_facts(
        self,
        query: str = "",
        max_scope: str = "org",
        include_conflicts: bool = False,
        limit: int = 10,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return self._client._req(
            "GET",
            "/v1/platform/kbrain/search",
            params=_kbrain_search_params(query, max_scope, include_conflicts, limit, workspace_id),
        )

    def resolve_kbrain_fact(
        self,
        fact_id: str,
        resolution: str = "approve",
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            f"/v1/platform/kbrain/facts/{_kbrain_seg(fact_id, 'fact_id')}/resolve",
            json=_kbrain_resolve_body(resolution, workspace_id),
        )

    def list_khub_skills(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req(
            "GET",
            "/v1/platform/khub/skills",
            params={"workspace_id": workspace_id},
        )

    def verify_khub_mirror(
        self,
        skill_ids: Optional[List[str]] = None,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/khub/mirror/verify",
            json={"workspace_id": workspace_id, "skill_ids": list(skill_ids or [])},
        )
