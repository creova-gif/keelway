# Keelway Model Provider Specification

## 1. Provider Adapter Interface Contract

All inference integrations in Keelway implement the `BaseModelProvider` abstract base class located in `core/models/provider.py`.

```python
class BaseModelProvider(ABC):
    provider_id: Provider
    category: ModelCategory

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if local server is responsive or cloud credentials are valid."""
        ...

    @abstractmethod
    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Execute non-streaming completion."""
        ...

    @abstractmethod
    async def stream_complete(self, request: ChatCompletionRequest) -> AsyncIterator[StreamChunk]:
        """Execute streaming completion yielding normalized chunks."""
        ...
```

---

## 2. Normalized Schemas

### Request Schema (`ChatCompletionRequest`)
- `messages`: List of role/content items (`user`, `assistant`, `system`).
- `model`: Optional explicit model identifier (e.g. `qwen2.5-coder:7b`, `gpt-4o`).
- `temperature`: Float between `0.0` and `2.0`.
- `max_tokens`: Upper bound on completion tokens (1 to 128,000).
- `stream`: Boolean indicating whether SSE streaming is requested.
- `privacy_level`: `standard` | `sensitive` | `private`.
- `required_capabilities`: List of capability tags (`code`, `reasoning`, `vision`, `tools`).
- `max_cost_usd`: Maximum allowed inference cost in USD.

### Response Schema (`ChatCompletionResponse`)
- `id`: Unique completion identifier (`chatcmpl-...`).
- `model`: Exact model identifier executing the request.
- `provider`: Provider enum (`local`, `openai`, `anthropic`, `gemini`).
- `category`: `open_weight` or `closed_proprietary`.
- `content`: Generated text response.
- `finish_reason`: Stop indicator (`stop`, `length`, `tool_calls`).
- `usage`: Dictionary containing `prompt_tokens`, `completion_tokens`, and `total_tokens`.
- `latency_ms`: Total execution time in milliseconds.
- `cost_usd`: Attributed inference cost ($0.00 for open-weight local inference).
- `routing_reason`: Transparent audit explanation detailing why this model was selected.

### Stream Chunk Schema (`StreamChunk`)
- `id`: Event chunk identifier.
- `object`: Always `"chat.completion.chunk"`.
- `model`: Model identifier.
- `provider`: Provider identifier.
- `delta_content`: Incremental token string.
- `finish_reason`: Optional termination reason.
- `to_sse()`: Method serializing chunk to compliant Server-Sent Event wire format (`data: {...}\n\n`).

---

## 3. Normalized Error Hierarchy

To prevent provider-specific exceptions from leaking through the API gateway, all adapters map native HTTP responses into a structured error hierarchy:

- `ProviderError`: Root exception capturing message, provider enum, and HTTP status code.
- `ProviderAuthenticationError`: Raised on HTTP 401 / missing or invalid API keys.
- `ProviderRateLimitError`: Raised on HTTP 429 / quota exhaustion.
- `ModelNotFoundError`: Raised on HTTP 404 / uninstalled local models.
- `ContextLengthExceededError`: Raised when prompt tokens exceed model context limit.
- `ProviderTimeoutError`: Raised when inference exceeds configured timeout thresholds.
