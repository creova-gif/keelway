"""
Keelway Interactive Chat Session & Stateful Agent REPL.
Integrates Hybrid RAG Memory, Security Gateway, Multi-Provider Routing,
and 4 Distinct Conversation Modes (Ask, Plan, Edit, Agent) per Section 6.1.
A completed local-model response is returned as that model sent it. Provider
failures stay unavailable and do not invent an offline completion.
"""

from __future__ import annotations

import re
import time
from enum import Enum
from typing import Any, Dict, List, Optional

from core.api.schemas import CompletionRequestSchema, MessageSchema, Provider
from core.models.gateway import ModelGateway, gateway as default_gateway
from core.storage.memory import MemoryService
from core.storage.database import AsyncSessionLocal
from core.security.firewall import SecurityGateway
from core.storage.workspace_fs import WorkspaceFilesystem
from core.storage.ast_index import CodebaseSemanticIndex


class ConversationMode(str, Enum):
    """Four distinct developer interaction modes (PRD Section 6.1)."""
    ASK = "ask"       # Read-only code explanations, repository queries, error diagnostics
    PLAN = "plan"     # Structured implementation plan grounded in code
    EDIT = "edit"     # Workspace-scoped code patch formulation with diff previews
    AGENT = "agent"   # Autonomous multi-step engineering loop with approval gating


def _provider_error_payload(exc: BaseException) -> Dict[str, str]:
    """Classify a provider failure without copying its text into the response.

    Adapter and gateway exceptions can carry request bodies, prompts, or
    credentials. Callers receive a fixed message instead of ``str(exc)``.
    """
    text = str(exc)
    if "No model provider allowed" in text:
        code = "routing_failure"
        message = "Model routing failed before a provider completed this request."
    elif text.startswith("All model providers failed or unavailable"):
        code = "model_unavailable"
        message = "No model is available to complete this request."
    else:
        code = "provider_error"
        message = "The model provider failed before completing this request."
    return {"code": code, "message": message}


def _keyword_plan(user_message: str) -> Dict[str, Any]:
    """Steps come from keyword matching, not from a model completion."""
    from core.orchestration.agent_loop import AutonomousAgentLoop

    return {
        "goal": user_message,
        "steps": AutonomousAgentLoop.formulate_plan(user_message),
        "required_permissions": ["read_file", "edit_file", "run_command"],
        "test_strategy": "Keyword template only. No test run is claimed.",
        "planning_source": "keyword_manual",
        "model_generated": False,
    }


def _unavailable_result(
    mode: ConversationMode,
    exc: BaseException,
    memory_citations: List[Dict[str, Any]],
    *,
    structured_plan: Optional[Dict[str, Any]] = None,
    workspace_observations: Optional[List[str]] = None,
) -> Dict[str, Any]:
    error = _provider_error_payload(exc)
    body: Dict[str, Any] = {
        "mode": mode.value,
        "status": "unavailable",
        "available": False,
        "error": error,
        "content": error["message"],
        "model": None,
        "latency_ms": None,
        "cost_usd": None,
        "usage": None,
        "memory_citations": memory_citations,
    }
    if structured_plan is not None:
        body["structured_plan"] = structured_plan
    if workspace_observations:
        body["workspace_observations"] = {
            "source": "workspace_index",
            "model_generated": False,
            "items": workspace_observations,
        }
    return body


MODE_SYSTEM_PROMPTS: Dict[ConversationMode, str] = {
    ConversationMode.ASK: (
        "You are Keelway in ASK Mode (Read-Only). "
        "Your role is to explain code, answer repository architecture questions, find symbols, "
        "and diagnose errors. You never modify files or run commands. Ground your answers in inspected files."
    ),
    ConversationMode.PLAN: (
        "You are Keelway in PLAN Mode. "
        "Your role is to produce a structured, actionable implementation plan grounded in inspected repository context. "
        "Always outline: 1. Goal, 2. Relevant Files, 3. Proposed Modifications, 4. Dependencies & Risks, "
        "5. Required Permissions, 6. Test Strategy, and 7. Expected Outcome."
    ),
    ConversationMode.EDIT: (
        "You are Keelway in EDIT Mode. "
        "Your role is to generate precise, workspace-scoped code modifications in structured patch format. "
        "Identify the file path, exact target substring to replace, and the replacement code. "
        "Never apply changes without explicit human authorization."
    ),
    ConversationMode.AGENT: (
        "You are Keelway in AGENT Mode. "
        "You orchestrate multi-step software engineering tasks using deterministic tools, "
        "recording flight tapes, and pausing for human authorization on all mutating actions."
    ),
}


class InteractiveChatSession:
    """Manages multi-turn stateful agent chat across the 4 conversation modes."""

    def __init__(
        self,
        gateway: Optional[ModelGateway] = None,
        provider: Provider = Provider.LOCAL,
        mode: ConversationMode = ConversationMode.ASK,
        system_prompt: Optional[str] = None,
        workspace_fs: Optional[WorkspaceFilesystem] = None,
    ):
        self.gateway = gateway or default_gateway
        self.provider = provider
        self.mode = mode
        self.fs = workspace_fs or WorkspaceFilesystem()
        self.semantic_index = CodebaseSemanticIndex(workspace_fs=self.fs)
        self.system_prompt = system_prompt or MODE_SYSTEM_PROMPTS.get(self.mode, MODE_SYSTEM_PROMPTS[ConversationMode.ASK])
        self.history: List[MessageSchema] = [
            MessageSchema(role="system", content=self.system_prompt)
        ]
        self.security = SecurityGateway(block_on_injection=True, redact_secrets=True)

    def set_mode(self, new_mode: ConversationMode) -> None:
        """Switch conversation mode and update system instructions."""
        self.mode = new_mode
        self.system_prompt = MODE_SYSTEM_PROMPTS.get(new_mode, MODE_SYSTEM_PROMPTS[ConversationMode.ASK])
        self.history = [MessageSchema(role="system", content=self.system_prompt)]

    def reset(self) -> None:
        """Clear conversation history while preserving system prompt."""
        self.history = [MessageSchema(role="system", content=self.system_prompt)]

    async def step(
        self,
        user_message: str,
        use_memory: bool = True,
        mode: Optional[ConversationMode] = None,
        target_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Processes one turn of dialogue according to the active mode:
        1. DLP / Prompt Injection audit
        2. Repository context & memory lookup
        3. Mode-specific prompt augmentation & model completion
        4. Structured payload assembly (explanation, plan, diff preview, or agent state)
        """
        active_mode = mode or self.mode

        # 1. Security scan
        sec_result = self.security.inspect_and_sanitize(user_message)
        if not sec_result.is_safe:
            return {
                "mode": active_mode.value,
                "status": "blocked",
                "available": False,
                "content": f"[SECURITY ALERT] Message blocked: {sec_result.blocked_reason}",
                "error": {
                    "code": "security_blocked",
                    "message": "The message was blocked before a model was called.",
                },
                "model": None,
                "latency_ms": None,
                "cost_usd": None,
                "usage": None,
                "memory_citations": [],
            }

        sanitized_input = sec_result.sanitized_text
        memory_citations: List[Dict[str, Any]] = []

        # 2. Dynamic hybrid memory lookup
        context_parts: List[str] = []
        if use_memory:
            try:
                async with AsyncSessionLocal() as db:
                    mem_service = MemoryService(db)
                    results = await mem_service.search_hybrid(
                        query_text=sanitized_input,
                        limit=3,
                        threshold=0.15,
                    )
                    if results:
                        for rec, score in results:
                            citation = rec.provenance_uri or f"memory://{rec.scope}/{rec.key}"
                            memory_citations.append({"key": rec.key, "score": score, "citation": citation})
                            context_parts.append(f"[{citation}]\n{rec.content}")
            except Exception:
                pass

        # 3. Codebase semantic symbol lookup
        if active_mode in (ConversationMode.ASK, ConversationMode.PLAN, ConversationMode.EDIT):
            try:
                symbols = self.semantic_index.search_symbols(sanitized_input, top_k=4)
                if symbols:
                    sym_lines = [f"{s.get('kind', 'symbol')} {s.get('name')} in {s.get('file_path')}:{s.get('line_number')}" for s in symbols]
                    context_parts.append("Workspace Symbols:\n" + "\n".join(sym_lines))
            except Exception:
                pass

        # 4. Mode-specific handling
        if active_mode == ConversationMode.PLAN:
            return await self._step_plan_mode(sanitized_input, context_parts, memory_citations)
        elif active_mode == ConversationMode.EDIT:
            return await self._step_edit_mode(sanitized_input, target_file, context_parts, memory_citations)
        elif active_mode == ConversationMode.AGENT:
            return await self._step_agent_mode(sanitized_input, context_parts, memory_citations)
        else:
            return await self._step_ask_mode(sanitized_input, context_parts, memory_citations)

    async def _step_ask_mode(
        self,
        user_message: str,
        context_parts: List[str],
        memory_citations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Read-only developer query mode with citations."""
        turn_prompt = user_message
        if context_parts:
            turn_prompt += "\n\nRelevant Workspace Context:\n" + "\n---\n".join(context_parts)

        self.history.append(MessageSchema(role="user", content=turn_prompt))
        request = CompletionRequestSchema(
            messages=self.history,
            preferred_provider=self.provider,
            temperature=0.2,
            max_tokens=1500,
        )

        try:
            response = await self.gateway.complete(request)
        except Exception as exc:
            self.history.pop()
            return _unavailable_result(
                ConversationMode.ASK,
                exc,
                memory_citations,
                workspace_observations=list(context_parts),
            )

        self.history.append(MessageSchema(role="assistant", content=response.content))
        return {
            "mode": ConversationMode.ASK.value,
            "status": "ok",
            "available": True,
            "content": response.content,
            "model": response.model,
            "latency_ms": response.latency_ms,
            "cost_usd": response.cost_usd,
            "usage": response.usage,
            "memory_citations": memory_citations,
        }

    async def _step_plan_mode(
        self,
        user_message: str,
        context_parts: List[str],
        memory_citations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generates a structured, editable implementation plan."""
        plan_instructions = (
            "Formulate an implementation plan in structured format with:\n"
            "- Goal: Single sentence objective\n"
            "- Relevant Files: List of file paths\n"
            "- Proposed Modifications: What lines/functions to edit\n"
            "- Dependencies & Risks: Potential side-effects\n"
            "- Required Permissions: Tools required (e.g. edit_file, run_command)\n"
            "- Test Strategy: Test command and validation steps\n"
            "- Expected Outcome: How success will be confirmed\n"
        )
        turn_prompt = f"{user_message}\n\n{plan_instructions}"
        if context_parts:
            turn_prompt += "\nRelevant Workspace Context:\n" + "\n---\n".join(context_parts)

        self.history.append(MessageSchema(role="user", content=turn_prompt))
        request = CompletionRequestSchema(
            messages=self.history,
            preferred_provider=self.provider,
            temperature=0.1,
            max_tokens=1500,
        )

        keyword_plan = _keyword_plan(user_message)
        try:
            response = await self.gateway.complete(request)
        except Exception as exc:
            self.history.pop()
            return _unavailable_result(
                ConversationMode.PLAN,
                exc,
                memory_citations,
                structured_plan=keyword_plan,
                workspace_observations=list(context_parts),
            )

        self.history.append(MessageSchema(role="assistant", content=response.content))
        return {
            "mode": ConversationMode.PLAN.value,
            "status": "ok",
            "available": True,
            "content": response.content,
            "structured_plan": keyword_plan,
            "model": response.model,
            "latency_ms": response.latency_ms,
            "cost_usd": response.cost_usd,
            "memory_citations": memory_citations,
        }

    async def _step_edit_mode(
        self,
        user_message: str,
        target_file: Optional[str],
        context_parts: List[str],
        memory_citations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Asks a model for an edit. A missing model is an error, not a patch."""
        file_path = target_file
        if not file_path:
            match = re.search(r"[\w\./-]+\.(?:py|ts|js|tsx|json|md|html|css)", user_message)
            file_path = match.group(0) if match else None

        original_content = ""
        exists = False
        if file_path:
            try:
                file_data = self.fs.read_file(file_path)
                original_content = file_data.get("content", "")
                exists = True
            except Exception:
                pass

        turn_prompt = (
            f"Propose code changes for '{file_path or 'unspecified file'}'. User request: {user_message}\n"
            f"Original file content:\n```\n{original_content[:2000]}\n```\n"
            "Specify the exact target string to replace and the replacement string."
        )
        if context_parts:
            turn_prompt += "\nContext:\n" + "\n---\n".join(context_parts)

        self.history.append(MessageSchema(role="user", content=turn_prompt))
        request = CompletionRequestSchema(
            messages=self.history,
            preferred_provider=self.provider,
            temperature=0.1,
            max_tokens=1500,
        )

        try:
            response = await self.gateway.complete(request)
        except Exception as exc:
            self.history.pop()
            return _unavailable_result(
                ConversationMode.EDIT,
                exc,
                memory_citations,
                workspace_observations=list(context_parts),
            )

        self.history.append(MessageSchema(role="assistant", content=response.content))
        return {
            "mode": ConversationMode.EDIT.value,
            "status": "ok",
            "available": True,
            "content": response.content,
            "edit_proposal": {
                "file_path": file_path,
                "file_exists": exists,
                "target": "",
                "replacement": "",
                "diff": "",
                "conflict_detected": False,
                "authorized": False,
                "patch_source": "none",
                "note": "No structured patch was extracted from the model reply. Nothing was applied.",
            },
            "model": response.model,
            "latency_ms": response.latency_ms,
            "cost_usd": response.cost_usd,
            "memory_citations": memory_citations,
        }

    async def _step_agent_mode(
        self,
        user_message: str,
        context_parts: List[str],
        memory_citations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Builds a keyword plan. This mode does not call a model."""
        from core.orchestration.agent_loop import AutonomousAgentLoop, AutonomyPolicy

        try:
            task_id = f"task_{int(time.time())}"
            agent = AutonomousAgentLoop(
                task_id=task_id,
                workspace_fs=self.fs,
                policy=AutonomyPolicy.CONFIRM_MUTATION,
                record_flight=True,
            )
            plan_steps = AutonomousAgentLoop.formulate_plan(user_message)
            agent.initialize_plan(goal=user_message, steps=plan_steps)
        except Exception:
            message = "The keyword planner could not build a plan."
            return {
                "mode": ConversationMode.AGENT.value,
                "status": "error",
                "available": False,
                "planning_source": "keyword_manual",
                "model_generated": False,
                "error": {"code": "planner_error", "message": message},
                "content": message,
                "model": None,
                "latency_ms": None,
                "cost_usd": None,
                "usage": None,
                "memory_citations": memory_citations,
            }

        return {
            "mode": ConversationMode.AGENT.value,
            "status": "keyword_manual",
            "available": False,
            "planning_source": "keyword_manual",
            "model_generated": False,
            "content": (
                f"Keyword/manual plan only. No model was called. "
                f"Task {task_id} has {len(plan_steps)} steps from keyword matching, not model-driven planning."
            ),
            "agent_task": {
                "task_id": task_id,
                "goal": user_message,
                "policy": agent.policy.value,
                "planning_source": "keyword_manual",
                "model_generated": False,
                "plan": [
                    {"id": s.id, "description": s.description, "status": s.status}
                    for s in agent.plan
                ],
            },
            "model": None,
            "latency_ms": None,
            "cost_usd": None,
            "usage": None,
            "memory_citations": memory_citations,
        }
