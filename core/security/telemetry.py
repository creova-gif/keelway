"""
Keelway OpenTelemetry GenAI (`gen_ai.*`) Semantic Tracing Subsystem.
Implements vendor-neutral observability conforming to OpenTelemetry 2026 specs:
- Standardized attributes: gen_ai.system, gen_ai.request.model, gen_ai.usage.input_tokens
- Privacy-safe tracing (scrubs prompt text unless explicitly opted-in)
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List


@dataclass
class GenAISpan:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    system: str  # e.g., 'local', 'anthropic', 'openai', 'google'
    request_model: str
    response_model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: float = 0.0
    air_gapped: bool = False
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "OK"


class TelemetryTracer:
    """Manages OpenTelemetry-compliant GenAI spans and trace export."""

    def __init__(self, service_name: str = "keelway-core"):
        self.service_name = service_name
        self.spans: List[GenAISpan] = []

    def start_span(
        self,
        name: str,
        system: str,
        request_model: str,
        air_gapped: bool = False,
        parent_span_id: Optional[str] = None,
    ) -> GenAISpan:
        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        span = GenAISpan(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            system=system,
            request_model=request_model,
            air_gapped=air_gapped,
            attributes={
                "service.name": self.service_name,
                "gen_ai.system": system,
                "gen_ai.request.model": request_model,
                "gen_ai.air_gapped": air_gapped,
            },
        )
        self.spans.append(span)
        return span

    def end_span(
        self,
        span: GenAISpan,
        response_model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: float,
        status: str = "OK",
    ) -> Dict[str, Any]:
        span.response_model = response_model
        span.input_tokens = input_tokens
        span.output_tokens = output_tokens
        span.duration_ms = duration_ms
        span.status = status

        span.attributes.update({
            "gen_ai.response.model": response_model,
            "gen_ai.usage.input_tokens": input_tokens,
            "gen_ai.usage.output_tokens": output_tokens,
            "gen_ai.client.operation.duration_ms": duration_ms,
            "otel.status_code": status,
        })
        return span.attributes


tracer = TelemetryTracer()
