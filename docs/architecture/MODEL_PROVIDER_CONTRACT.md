# Keelway — Model Provider Adapter Contract

> **Version**: 1.0  
> **Status**: Approved Specification  
> **Location**: `core/models/provider.py` & `core/models/adapters/`

---

## 1. Provider Adapter Interface

All model provider integrations—whether local daemon, self-hosted GPU endpoint, or proprietary cloud API—must implement the abstract base contract defined in `core/models/provider.py`:

```python
class BaseModelProviderAdapter(ABC):
    """Abstract interface governing all Keelway AI model provider adapters."""

    @abstractmethod
    async def chat_complete(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Execute a non-streaming chat completion."""
        pass

    @abstractmethod
    async def stream_chat(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[StreamChunk]:
        """Execute a streaming chat completion yielding normalized SSE chunks."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Probe provider health and availability."""
        pass
```

---

## 2. Request & Response Normalization Data Models

### ChatCompletionRequest
```python
class ChatCompletionRequest(BaseModel):
    messages: List[MessageSchema]
    model: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    stream: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    response_format: Optional[Dict[str, Any]] = None  # JSON Schema
    is_private: bool = False                          # Enforces local-only execution
    air_gap: bool = False                             # Fail-closed air-gap enforcement
```

### ChatCompletionResponse
```python
class ChatCompletionResponse(BaseModel):
    id: str
    model: str
    provider: Provider
    category: ModelCategory
    content: str
    role: str = "assistant"
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: Dict[str, int]  # prompt_tokens, completion_tokens, total_tokens
    latency_ms: float
    cost_usd: float
    routing_reason: str
```

### StreamChunk
```python
class StreamChunk(BaseModel):
    id: str
    model: str
    delta_content: str = ""
    delta_tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None

    def to_sse(self) -> str:
        """Format chunk as OpenAI-compatible Server-Sent Event."""
        payload = {
            "id": self.id,
            "object": "chat.completion.chunk",
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": {"content": self.delta_content, "role": "assistant"},
                "finish_reason": self.finish_reason
            }]
        }
        return f"data: {json.dumps(payload)}\n\n"
```

---

## 3. Normalized Exception Hierarchy

Under no circumstances may raw provider HTTP exceptions (e.g. `httpx.HTTPStatusError`, `aiohttp.ClientResponseError`) leak to outer caller layers. All provider adapters must map external errors into Keelway's canonical hierarchy:

```
ProviderError (Base)
  ├── ProviderAuthenticationError  --> HTTP 401 Unauthorized (Invalid API key)
  ├── ProviderRateLimitError        --> HTTP 429 Too Many Requests (Backoff/Retry)
  ├── ModelNotFoundError           --> HTTP 404 Not Found (Unrecognized model tag)
  ├── ContextLengthExceededError   --> HTTP 400 / 413 Context Overflow
  ├── ProviderTimeoutError         --> HTTP 504 Gateway Timeout (Network hang)
  └── AirGapViolationError         --> HTTP 403 Forbidden (Privacy policy blocked cloud)
```

---

## 4. Contract Testing Requirements

Every provider adapter must supply automated contract tests validating:
1. **Request payload serialization**: Correct translation of system prompts, tool schemas, and temperature.
2. **Response body parsing**: Standard token usage extraction, latency calculation, and content mapping.
3. **SSE streaming**: Generation of formatted `data: {...}\n\n` chunks ending cleanly with `data: [DONE]\n\n`.
4. **Error handling**: Verification that 401, 404, 429, and 500 status codes map accurately to Keelway exceptions.
