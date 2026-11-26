import pytest
import tempfile
from pathlib import Path

from core.storage.database import init_db, AsyncSessionLocal
from core.storage.models import TaskRecord, TaskState
from research.datasets.pipeline import TraceDatasetExtractor, ExportFormat


@pytest.mark.asyncio
async def test_dataset_pipeline_extraction_and_export():
    await init_db()

    async with AsyncSessionLocal() as db:
        # Seed 2 completed tasks
        task1 = TaskRecord(
            title="PR Review Workflow",
            description="Engineering brief analysis",
            state=TaskState.COMPLETED,
            payload={
                "workflow_type": "engineering_brief",
                "input_query": "Analyze PR #42 with changes to gateway.py",
                "brief": "Summary: PR adds GeminiAdapter.\nRisks: High.\nActions: Run integration tests.",
            },
        )
        task2 = TaskRecord(
            title="ADR Review Workflow",
            description="Architecture decision record",
            state=TaskState.COMPLETED,
            payload={
                "workflow_type": "engineering_brief",
                "input_query": "Analyze ADR-001 with secret: sk-ant-123456789012345678901234567890",
                "brief": "Architecture decision establishes sovereign core.",
            },
        )
        db.add_all([task1, task2])
        await db.commit()

        extractor = TraceDatasetExtractor(db)
        samples = await extractor.extract_samples(workflow_type="engineering_brief")
        assert len(samples) >= 2

        # Verify DLP scrubbing occurred in extracted sample
        sample_with_secret = [s for s in samples if "sk-ant" in s["input"] or "[REDACTED_ANTHROPIC_KEY]" in s["input"]][0]
        assert "[REDACTED_ANTHROPIC_KEY]" in sample_with_secret["input"]

        # Test formatting
        sharegpt_sample = extractor.format_sample(samples[0], format_type=ExportFormat.SHAREGPT)
        assert "conversations" in sharegpt_sample
        assert len(sharegpt_sample["conversations"]) == 3

        openai_sample = extractor.format_sample(samples[0], format_type=ExportFormat.OPENAI)
        assert "messages" in openai_sample
        assert len(openai_sample["messages"]) == 3

        # Test export to temporary file
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "train.jsonl"
            manifest = await extractor.export_dataset(
                output_file=out_file,
                format_type=ExportFormat.SHAREGPT,
                workflow_type="engineering_brief",
            )
            assert out_file.exists()
            assert manifest["sample_count"] >= 2
            assert manifest["sha256"] is not None
            assert (Path(tmpdir) / "train_manifest.json").exists()
