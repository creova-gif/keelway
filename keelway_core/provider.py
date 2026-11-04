"""Simple provider contract, with explicit optional loopback-only Ollama integration."""
from __future__ import annotations
from dataclasses import dataclass
import json
from urllib.request import Request, urlopen

@dataclass(frozen=True)
class Generation:
    text: str
    provider: str
    offline: bool
    reported_tokens: int | None = None

class OllamaLocal:
    def __init__(self, model: str, endpoint: str = 'http://127.0.0.1:11434/api/chat'):
        if endpoint != 'http://127.0.0.1:11434/api/chat':
            raise ValueError('Only the explicitly vetted loopback Ollama endpoint is supported in this reference.')
        if not model.strip():
            raise ValueError('model required')
        self.model, self.endpoint = model, endpoint

    def complete(self, user_text: str) -> Generation:
        payload = json.dumps({'model': self.model, 'messages': [{'role': 'user', 'content': user_text}], 'stream': False}).encode()
        req = Request(self.endpoint, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
        with urlopen(req, timeout=60) as r:
            data = json.loads(r.read(2_000_000))
        return Generation(text=str(data['message']['content']), provider=f'ollama:{self.model}', offline=True, reported_tokens=data.get('eval_count'))

class FixtureProvider:
    """Only for deterministic local tests; not a real AI model."""
    def complete(self, user_text: str) -> Generation:
        return Generation(text='FIXTURE: '+user_text, provider='fixture', offline=True)
