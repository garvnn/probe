"""LLM access for the attackers (Claude / GPT). Owner: Shreyas."""

from __future__ import annotations

import os
from typing import Protocol

OWNER = "Shreyas"


class LLMClient(Protocol):
    def complete(self, model: str, system: str, messages: list[dict], seed: int | None = None) -> str:
        """Return the assistant's text response."""
        ...


class AnthropicLLM:
    """Real client backed by the Anthropic SDK."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def complete(self, model: str, system: str, messages: list[dict], seed: int | None = None) -> str:
        raise NotImplementedError(f"owner: {OWNER}")


class OpenAILLM:
    """Real client backed by the OpenAI SDK (e.g. for attacker B on a different model family)."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    def complete(self, model: str, system: str, messages: list[dict], seed: int | None = None) -> str:
        raise NotImplementedError(f"owner: {OWNER}")


CANNED_GENERATOR_SOURCE = '''\
def generate_site(context):
    """Mock attacker output for wiring. Never executed outside a sandbox."""
    return {"patients": [], "visits": [], "labs": [], "vitals": [],
            "adverse_events": [], "conmeds": [], "dispensing": []}
'''


class LocalMockLLM:
    """Returns a canned generator source."""

    def complete(self, model: str, system: str, messages: list[dict], seed: int | None = None) -> str:
        return CANNED_GENERATOR_SOURCE
