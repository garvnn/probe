"""LLM access for the attackers (Claude, or any OpenAI-compatible provider). Owner: Shreyas.

Switching from the scripted attacker to a real LLM is configuration only: put a key in .env.

    TRAINING_ATTACKER_MODEL   model id; "claude-*" -> Anthropic, anything else -> OpenAI-compatible
    TEST_ATTACKER_MODEL       same, for the held-out test attacker (should differ from training)
    ANTHROPIC_API_KEY         used for claude-* models
    GEMINI_API_KEY            used for gemini-* models (Google's OpenAI-compatible endpoint)
    OPENAI_API_KEY            used for other non-Claude models
    OPENAI_BASE_URL           optional, for OpenAI-compatible providers other than OpenAI
    ATTACKER_EFFORT           optional Claude effort: low | medium | high (default medium)
    ATTACKER_PRICE_IN_PER_1M  optional USD per 1M input tokens, for the cost estimate (default 0)
    ATTACKER_PRICE_OUT_PER_1M optional USD per 1M output tokens (default 0)

Every call is recorded as an LLMCall (model, tokens, latency) on the client's `calls` list.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Protocol

OWNER = "Shreyas"

DEFAULT_MODELS = {"training": "claude-sonnet-5-5", "test": "gemini-3-flash-preview"}
"""Used when a key is set but the model env var is empty. Set TEST_ATTACKER_MODEL to a different model
than training so the test attacker really is a stranger."""
MODEL_ENV = {"training": "TRAINING_ATTACKER_MODEL", "test": "TEST_ATTACKER_MODEL"}
MAX_TOKENS = 16000


def _env(name: str) -> str:
    """Env var with any inline `# comment` stripped (the .env.example style)."""
    return os.environ.get(name, "").split("#")[0].strip()


@dataclass
class LLMCall:
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    stop_reason: str | None = None


class LLMRefusal(RuntimeError):
    """The model declined. The loop records the round as an error and feeds this back."""


class LLMClient(Protocol):
    calls: list[LLMCall]

    def complete(self, model: str, system: str, messages: list[dict], seed: int | None = None) -> str:
        """Return the assistant's text response."""
        ...


@dataclass
class AnthropicLLM:
    """Real client backed by the Anthropic SDK."""

    api_key: str = ""
    effort: str = ""
    calls: list[LLMCall] = field(default_factory=list)

    def __post_init__(self) -> None:
        import anthropic

        self.api_key = self.api_key or _env("ANTHROPIC_API_KEY")
        self.effort = self.effort or _env("ATTACKER_EFFORT") or "medium"
        self._client = anthropic.Anthropic(api_key=self.api_key)

    def complete(self, model: str, system: str, messages: list[dict], seed: int | None = None) -> str:
        t = time.perf_counter()
        response = self._client.beta.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            output_config={"effort": self.effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        self.calls.append(
            LLMCall(
                model=response.model,
                provider="anthropic",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                latency_s=round(time.perf_counter() - t, 3),
                stop_reason=response.stop_reason,
            )
        )
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise LLMRefusal(f"model declined ({getattr(details, 'category', None)}): {getattr(details, 'explanation', '')}")
        return "".join(b.text for b in response.content if b.type == "text")


@dataclass
class OpenAILLM:
    """Real client for OpenAI or any OpenAI-compatible endpoint (set OPENAI_BASE_URL)."""

    api_key: str = ""
    base_url: str = ""
    provider: str = "openai_compatible"
    calls: list[LLMCall] = field(default_factory=list)

    def __post_init__(self) -> None:
        import openai

        self.api_key = self.api_key or _env("OPENAI_API_KEY")
        self.base_url = self.base_url or _env("OPENAI_BASE_URL")
        self._client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url or None)

    def complete(self, model: str, system: str, messages: list[dict], seed: int | None = None) -> str:
        t = time.perf_counter()
        response = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, *messages],
            **({"seed": seed} if self.provider != "gemini" else {}),
        )
        usage = response.usage
        choice = response.choices[0]
        self.calls.append(
            LLMCall(
                model=response.model,
                provider=self.provider,
                input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                latency_s=round(time.perf_counter() - t, 3),
                stop_reason=choice.finish_reason,
            )
        )
        if getattr(choice.message, "refusal", None):
            raise LLMRefusal(f"model declined: {choice.message.refusal}")
        return choice.message.content or ""


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Estimated spend from ATTACKER_PRICE_IN_PER_1M / ATTACKER_PRICE_OUT_PER_1M (0 if unset)."""
    price_in = float(_env("ATTACKER_PRICE_IN_PER_1M") or 0)
    price_out = float(_env("ATTACKER_PRICE_OUT_PER_1M") or 0)
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def model_for(role: str) -> str:
    """The configured model for "training" or "test", falling back to DEFAULT_MODELS."""
    return _env(MODEL_ENV[role]) or DEFAULT_MODELS[role]


def provider_for(model: str) -> str:
    if model.startswith("gemini-"):
        return "gemini"
    return "anthropic" if model.startswith("claude") else "openai_compatible"


def client_for(model: str) -> LLMClient | None:
    """A real client for `model` if its provider's key is set, else None (caller falls back to scripted)."""
    if provider_for(model) == "anthropic":
        return AnthropicLLM() if _env("ANTHROPIC_API_KEY") else None
    if provider_for(model) == "gemini":
        return OpenAILLM(
            api_key=_env("GEMINI_API_KEY"),
            base_url=_env("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai/",
            provider="gemini",
        ) if _env("GEMINI_API_KEY") else None
    return OpenAILLM() if _env("OPENAI_API_KEY") else None


CANNED_FAKE_SITE_SOURCE = '''\
def generate_site(context):
    """Mock attacker output for wiring. Never executed outside a sandbox."""
    return {"patients": [], "visits": [], "labs": [], "vitals": [],
            "adverse_events": [], "conmeds": [], "dispensing": [], "kit_storage": []}
'''


class LocalMockLLM:
    """Returns a canned fake-site source."""

    def __init__(self) -> None:
        self.calls: list[LLMCall] = []

    def complete(self, model: str, system: str, messages: list[dict], seed: int | None = None) -> str:
        self.calls.append(LLMCall(model=model, provider="mock", input_tokens=0, output_tokens=0, latency_s=0.0))
        return CANNED_FAKE_SITE_SOURCE
