"""
Kora AI Personal Agent — Workflow 1: Engineering Brief Generator.
Permission Level: READ ONLY
Generates source-grounded engineering briefs from PRs/git changes and verifies against KORA.md.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from core.api.schemas import (
    CompletionRequestSchema,
    MessageSchema,
    Provider,
)
from core.models.gateway import gateway as default_gateway, ModelGateway
from core.orchestration.state import TaskState
from core.storage.models import TaskRecord, EvidenceRecord


class EngineeringBriefWorkflow:
    def __init__(self, gateway: Optional[ModelGateway] = None, docs_dir: Optional[Path] = None):
        self.gateway = gateway or default_gateway
        self.docs_dir = docs_dir or Path("kora-ai")

    def load_governance_context(self) -> str:
        """Load KORA.md and ADR-001 principles as grounded context."""
        context_parts = []
        kora_candidates = [
            self.docs_dir / "docs" / "architecture" / "KORA.md",
            self.docs_dir / "KORA.md",
            Path("docs/architecture/KORA.md"),
            Path("KORA.md"),
        ]
        for k_path in kora_candidates:
            if k_path.exists():
                context_parts.append(f"=== KORA.md Principles ===\n{k_path.read_text()[:2000]}")
                break

        adr_candidates = [
            self.docs_dir / "docs" / "architecture" / "ADR-001-AI-Core-Architecture.md",
            self.docs_dir / "ADR-001-AI-Core-Architecture.md",
            Path("docs/architecture/ADR-001-AI-Core-Architecture.md"),
            Path("ADR-001-AI-Core-Architecture.md"),
        ]
        for a_path in adr_candidates:
            if a_path.exists():
                context_parts.append(f"=== ADR-001 Architecture Principles ===\n{a_path.read_text()[:2000]}")
                break

        return "\n\n".join(context_parts)

    async def execute(
        self,
        pr_title: str,
        pr_description: str,
        files_touched: List[str],
        failing_tests: List[str],
        db: Optional[AsyncSession] = None,
        owner: str = "founder",
        preferred_provider: Optional[Provider] = None,
    ) -> Dict[str, Any]:
        """Execute Workflow 1: Generate prioritized brief with citations and persist task."""

        governance_context = self.load_governance_context()

        system_prompt = (
            "You are the Kora Technical Lead & DevSecOps Lead. "
            "Your job is to produce a rigorous, source-grounded engineering brief for a proposed pull request. "
            "You MUST:\n"
            "1. Summarize the changes (2-3 sentences)\n"
            "2. Identify risky or failing tests and evaluate their severity\n"
            "3. Assess alignment with KORA.md and ADR-001 principles\n"
            "4. Provide ranked risks with concrete mitigations\n"
            "5. Provide ordered next actions for the developer\n"
            "6. Cite exact files mentioned\n"
            "Do NOT hallucinate file contents or external claims."
        )

        user_content = (
            f"Pull Request: {pr_title}\n"
            f"Description: {pr_description}\n"
            f"Files Touched: {', '.join(files_touched)}\n"
            f"Failing Tests: {', '.join(failing_tests) if failing_tests else 'None reported'}\n\n"
            f"Repository Governance Context:\n{governance_context}\n"
        )

        request = CompletionRequestSchema(
            messages=[
                MessageSchema(role="system", content=system_prompt),
                MessageSchema(role="user", content=user_content),
            ],
            temperature=0.2,
            max_tokens=2048,
            preferred_provider=preferred_provider,
        )

        completion = await self.gateway.complete(request)

        # Create task record if database session is provided
        task_id = None
        if db:
            task = TaskRecord(
                title=f"Engineering Brief: {pr_title}",
                description=f"Generated brief for PR touching {len(files_touched)} files.",
                owner=owner,
                state=TaskState.AWAITING_APPROVAL,
                budget_usd=0.50,
                cost_usd=completion.cost_usd or 0.0,
                payload={
                    "pr_title": pr_title,
                    "provider": completion.provider.value,
                    "model": completion.model,
                    "latency_ms": completion.latency_ms,
                },
            )
            db.add(task)
            await db.flush()
            await db.refresh(task)
            task_id = task.id

            # Save file citations as evidence records
            for f in files_touched:
                evidence = EvidenceRecord(
                    task_id=task.id,
                    source_uri=f"file://{f}",
                    classification="SOURCE-VERIFIED",
                    excerpt=f"File touched in PR: {pr_title}",
                )
                db.add(evidence)
            await db.flush()

        return {
            "task_id": task_id,
            "brief_content": completion.content,
            "provider": completion.provider.value,
            "model": completion.model,
            "latency_ms": completion.latency_ms,
            "cost_usd": completion.cost_usd,
            "usage": completion.usage,
            "state": TaskState.AWAITING_APPROVAL.value,
            "citations": files_touched,
        }
