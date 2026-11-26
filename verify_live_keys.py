#!/usr/bin/env python3
"""
Live Verification Script for Keelway Model Provider Keys.
Tests active credentials against Anthropic, Google Gemini, and OpenAI endpoints.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from core.config import settings
from core.api.schemas import (
    CompletionRequestSchema,
    MessageSchema,
)
from core.models.adapters.anthropic import AnthropicAdapter
from core.models.adapters.gemini import GeminiAdapter
from core.models.adapters.openai import OpenAIAdapter


async def test_provider(name: str, adapter, key_present: bool):
    print(f"\n[*] Testing {name} Provider API Key...", flush=True)
    if not key_present:
        print(f"    [-] Skipped: No key configured for {name}.", flush=True)
        return False

    request = CompletionRequestSchema(
        messages=[
            MessageSchema(role="user", content="Respond with exactly 'KEELWAY_OK' and nothing else.")
        ],
        temperature=0.0,
        max_tokens=20,
    )

    try:
        resp = await asyncio.wait_for(adapter.complete(request), timeout=10.0)
        print(f"    [+] {name} SUCCESS!", flush=True)
        print(f"        Model:   {resp.model}", flush=True)
        print(f"        Latency: {resp.latency_ms:.1f}ms", flush=True)
        print(f"        Tokens:  {resp.usage['prompt_tokens']} in / {resp.usage['completion_tokens']} out", flush=True)
        print(f"        Cost:    ${resp.cost_usd:.6f}", flush=True)
        print(f"        Output:  {resp.content.strip()[:60]}", flush=True)
        return True
    except asyncio.TimeoutError:
        print(f"    [!] {name} FAILED: Timeout after 10.0s", flush=True)
        return False
    except Exception as e:
        print(f"    [!] {name} FAILED: {e}", flush=True)
        return False


async def main():
    print("============================================================", flush=True)
    print("  Keelway — Live Provider Credentials Verification          ", flush=True)
    print("============================================================", flush=True)
    print(f"Loaded .env from: {Path(__file__).parent / '.env'}", flush=True)
    print(f"Anthropic Key Present: {bool(settings.anthropic_api_key)}", flush=True)
    print(f"OpenAI Key Present:    {bool(settings.openai_api_key)}", flush=True)
    print(f"Gemini Key Present:    {bool(settings.gemini_api_key)}", flush=True)

    results = {}

    # 1. Anthropic
    anthropic_adapter = AnthropicAdapter(api_key=settings.anthropic_api_key)
    results["Anthropic"] = await test_provider("Anthropic", anthropic_adapter, bool(settings.anthropic_api_key))

    # 2. OpenAI
    openai_adapter = OpenAIAdapter(api_key=settings.openai_api_key)
    results["OpenAI"] = await test_provider("OpenAI", openai_adapter, bool(settings.openai_api_key))

    # 3. Gemini
    gemini_adapter = GeminiAdapter(api_key=settings.gemini_api_key)
    results["Gemini"] = await test_provider("Gemini", gemini_adapter, bool(settings.gemini_api_key))

    print("\n============================================================", flush=True)
    print("  Summary Verification Results                              ", flush=True)
    print("============================================================", flush=True)
    for prov, status in results.items():
        tag = "VALID [OK]" if status else "FAILED / INVALID [!]"
        print(f"  • {prov:<12}: {tag}", flush=True)
    print("============================================================\n", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
