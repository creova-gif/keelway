"""
Keelway Interactive Chat Session & Stateful Agent REPL.
Integrates Hybrid RAG Memory, Security Gateway, and Multi-Provider Routing.
"""

import sys
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from core.api.schemas import CompletionRequestSchema, MessageSchema, Provider
from core.models.gateway import ModelGateway, gateway as default_gateway
from core.storage.memory import MemoryService
from core.storage.database import AsyncSessionLocal
from core.security.firewall import SecurityGateway


class InteractiveChatSession:
    """Manages multi-turn stateful agent chat with dynamic memory recall and safety checks."""

    DEFAULT_SYSTEM_PROMPT = (
        "You are Keelway, a sovereign, deterministic AI engineering assistant. "
        "You provide precise, evidence-grounded responses, cite source files when available, "
        "and prioritize reliability, safety, and infrastructure economics."
    )

    def __init__(
        self,
        gateway: Optional[ModelGateway] = None,
        provider: Provider = Provider.LOCAL,
        system_prompt: Optional[str] = None,
    ):
        self.gateway = gateway or default_gateway
        self.provider = provider
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self.history: List[MessageSchema] = [
            MessageSchema(role="system", content=self.system_prompt)
        ]
        self.security = SecurityGateway(block_on_injection=True, redact_secrets=True)

    def reset(self) -> None:
        """Clear conversation history while preserving system prompt."""
        self.history = [MessageSchema(role="system", content=self.system_prompt)]

    async def step(self, user_message: str, use_memory: bool = True) -> Dict[str, Any]:
        """
        Processes one turn of dialogue:
        1. DLP / Prompt Injection audit
        2. Dynamic hybrid memory lookup
        3. Augmentation of context
        4. Model Gateway completion
        """
        # Security scan
        sec_result = self.security.inspect_and_sanitize(user_message)
        if not sec_result.is_safe:
            return {
                "content": f"[SECURITY ALERT] Message blocked: {sec_result.blocked_reason}",
                "model": "security-firewall",
                "latency_ms": 0.0,
                "cost_usd": 0.0,
                "memory_citations": [],
            }

        sanitized_input = sec_result.sanitized_text
        memory_citations = []

        # Retrieve relevant context from hybrid memory
        context_block = ""
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
                        context_parts = []
                        for rec, score in results:
                            citation = rec.provenance_uri or f"memory://{rec.scope}/{rec.key}"
                            memory_citations.append({"key": rec.key, "score": score, "citation": citation})
                            context_parts.append(f"[{citation}]\n{rec.content}")
                        context_block = "\n\nRelevant Project Context:\n" + "\n---\n".join(context_parts)
            except Exception:
                pass  # Graceful fallback if database is unavailable

        # Formulate turn prompt
        turn_content = sanitized_input
        if context_block:
            turn_content = f"{sanitized_input}\n\n{context_block}"

        # Append user turn
        self.history.append(MessageSchema(role="user", content=turn_content))

        # Request completion
        request = CompletionRequestSchema(
            messages=self.history,
            preferred_provider=self.provider,
            temperature=0.2,
            max_tokens=1500,
        )

        response = await self.gateway.complete(request)

        # Append assistant turn (store only the clean answer)
        self.history.append(MessageSchema(role="assistant", content=response.content))

        return {
            "content": response.content,
            "model": response.model,
            "latency_ms": response.latency_ms,
            "cost_usd": response.cost_usd,
            "usage": response.usage,
            "memory_citations": memory_citations,
        }
