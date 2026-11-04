"""
Pydantic v2 schemas for Keelway Core API.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Provider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    NVIDIA = "nvidia"
    LOCAL = "local"
    OPEN_WEIGHT = "open_weight"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"
    VLLM = "vllm"


from core.orchestration.state import TaskState


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    environment: str
    database_connected: bool
    timestamp: datetime


class MessageSchema(BaseModel):
    role: str = Field(..., description="Role: system | user | assistant | tool")
    content: str = Field(..., description="Message text content")
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


class ToolDefinitionSchema(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]


class CompletionRequestSchema(BaseModel):
    messages: List[MessageSchema] = Field(..., min_length=1, description="Conversation messages")
    tools: Optional[List[ToolDefinitionSchema]] = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    preferred_provider: Optional[Provider] = None
    required_capabilities: List[str] = Field(default_factory=list)
    max_cost_usd: Optional[float] = None
    max_latency_ms: Optional[int] = None
    privacy_level: str = Field(default="standard", description="standard | sensitive | private")


class CompletionResponseSchema(BaseModel):
    content: str
    provider: Provider
    model: str
    usage: Dict[str, int] = Field(..., description="prompt_tokens, completion_tokens, total_tokens")
    latency_ms: float
    cost_usd: Optional[float] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    routing_reason: Optional[str] = None


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    owner: str = Field(default="anonymous", max_length=100)
    budget_usd: float = Field(default=0.50, gt=0.0)
    payload: Dict[str, Any] = Field(default_factory=dict)


class TaskTransitionRequest(BaseModel):
    target_state: TaskState


class TaskResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    state: TaskState
    owner: str
    budget_usd: float
    cost_usd: float
    created_at: datetime
    updated_at: datetime
    payload: Dict[str, Any]

    model_config = {"from_attributes": True}


class EvidenceSchema(BaseModel):
    source_uri: str
    commit_sha: Optional[str] = None
    classification: str = "UNVERIFIED"
    content_hash: Optional[str] = None
    excerpt: Optional[str] = None


class EngineeringBriefRequest(BaseModel):
    pr_title: str = Field(..., min_length=3, max_length=255)
    pr_description: str
    files_touched: List[str] = Field(default_factory=list)
    failing_tests: List[str] = Field(default_factory=list)
    preferred_provider: Optional[Provider] = None


class EngineeringBriefResponse(BaseModel):
    task_id: Optional[str] = None
    brief_content: str
    provider: str
    model: str
    latency_ms: float
    cost_usd: Optional[float] = None
    usage: Dict[str, int]
    state: str
    citations: List[str]


class ResearchSummaryRequest(BaseModel):
    document_title: str = Field(..., min_length=2, max_length=255)
    document_content: str = Field(..., min_length=10)
    source_uri: str = Field(..., min_length=3)
    store_in_memory: bool = False
    memory_key: Optional[str] = None
    preferred_provider: Optional[Provider] = None


class ResearchSummaryResponse(BaseModel):
    task_id: Optional[str] = None
    memory_id: Optional[str] = None
    summary_content: str
    provider: str
    model: str
    latency_ms: float
    cost_usd: Optional[float] = None
    usage: Dict[str, int]
    source_uri: str


class SandboxTestRequest(BaseModel):
    test_command: str = Field(..., min_length=3, max_length=512)
    human_approved: bool = Field(default=False, description="Explicit approval gate for Tier 3 container execution")
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    preferred_provider: Optional[Provider] = None


class SandboxTestResponse(BaseModel):
    task_id: Optional[str] = None
    test_command: str
    passed: bool
    exit_code: int
    duration_ms: float
    stdout: str
    stderr: str
    failure_analysis: Optional[str] = None
    state: str


class MemoryCreateRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    scope: str = Field(default="project", max_length=100)
    provenance_uri: Optional[str] = None


class MemoryResponse(BaseModel):
    id: str
    scope: str
    key: str
    content: str
    provenance_uri: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
