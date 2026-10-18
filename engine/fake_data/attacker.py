"""Attackers that write site-fabrication code: an LLM (Sparring / Stranger) or the scripted stand-in. Owner: Shreyas.

`make_attacker(role)` picks the LLM attacker when its provider key is in .env, else the
ScriptedAttacker. Either way the loop only calls `write_fake_site_code(context, feedback)`.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from integrations.llm import LLMCall, LLMClient, client_for, model_for

OWNER = "Shreyas"

PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_FOR_ROLE = {"training": PROMPTS_DIR / "training_attacker.md", "test": PROMPTS_DIR / "test_attacker.md"}
FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


def extract_code(text: str) -> str:
    """The first fenced code block if there is one, else the whole reply."""
    m = FENCE.search(text)
    return (m.group(1) if m else text).strip() + "\n"


def build_user_message(context: dict, feedback: dict | None) -> str:
    parts = ["PUBLIC CONTEXT (aggregate stats only):", json.dumps(context, indent=1)]
    if feedback is None:
        parts.append("This is round 1. Write your first generate_site(context).")
    else:
        previous = feedback.get("previous_code")
        if previous:
            parts += ["YOUR PREVIOUS CODE:", f"```python\n{previous}```"]
        shown = {k: v for k, v in feedback.items() if k != "previous_code"}
        if shown.get("why_checks_fired"):
            shown["why_checks_fired"] = [{k: v for k, v in d.items() if k != "summary"} for d in shown["why_checks_fired"]]
        parts += ["FEEDBACK FROM LAST ROUND:", json.dumps(shown, indent=1)]
        why = [d.get("summary") for d in feedback.get("why_checks_fired") or [] if d.get("summary")]
        if why:
            parts += ["WHY EACH CHECK FIRED (your site vs the typical 10th-90th percentile range on real sites):", "\n".join(f"- {w}" for w in why)]
        parts.append(
            "Revise YOUR PREVIOUS CODE with targeted edits that move each measure above into the real-site range. "
            "Keep everything that already passes unchanged; do not rewrite from scratch. Output the full revised code."
            if previous else "Write an improved generate_site(context)."
        )
    return "\n\n".join(parts)


@dataclass
class Attacker:
    """One LLM attacker strategy. The training attacker is used for patching; the test attacker is never seen during patching.

    Attributes:
        attacker_id: "training" or "test" (or a sweep label).
        model: LLM model ID (TRAINING_ATTACKER_MODEL / TEST_ATTACKER_MODEL). The two should differ.
        system_prompt_path: Path to the system prompt markdown in `prompts/`.
        seed: Sampling seed, logged per run.
        llm: The client that serves `model`.
    """

    attacker_id: str
    model: str
    system_prompt_path: Path
    seed: int
    llm: LLMClient | None = None
    kind: str = field(default="llm", init=False)

    def write_fake_site_code(self, context: dict, feedback: dict | None) -> str:
        """Ask the LLM for new fake-site code given the public context and last round's feedback.

        Returns Python source that defines `generate_site(context) -> dict[str, list[dict]]`
        using only numpy, pandas, and datetime. Output tables must match docs/schema.md.
        The source is untrusted: it is only ever executed through a SandboxRunner.
        """
        if self.llm is None:
            raise RuntimeError(f"no LLM client for {self.model}; set its API key in .env")
        system = self.system_prompt_path.read_text()
        reply = self.llm.complete(self.model, system, [{"role": "user", "content": build_user_message(context, feedback)}], seed=self.seed)
        return extract_code(reply)

    @property
    def last_call(self) -> LLMCall | None:
        return self.llm.calls[-1] if self.llm and self.llm.calls else None


def make_attacker(role: Literal["training", "test"] = "training", kind: Literal["auto", "llm", "scripted"] = "auto", seed: int = 2026):
    """The attacker for `role`. "auto" = LLM if its key is set, else ScriptedAttacker."""
    from engine.fake_data.scripted import ScriptedAttacker

    if kind == "scripted":
        return ScriptedAttacker(attacker_id=role, seed=seed)
    model = model_for(role)
    llm = client_for(model)
    if llm is None:
        if kind == "llm":
            raise RuntimeError(f"--attacker llm needs a key for {model}: set ANTHROPIC_API_KEY (claude-*), GEMINI_API_KEY (gemini-*), or OPENAI_API_KEY in .env")
        return ScriptedAttacker(attacker_id=role, seed=seed)
    return Attacker(attacker_id=role, model=model, system_prompt_path=PROMPT_FOR_ROLE[role], seed=seed, llm=llm)


def prompt_sha256(attacker) -> str | None:
    """SHA-256 of the attacker's system prompt file, so a run records exactly which prompt it used."""
    path = getattr(attacker, "system_prompt_path", None)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if path and Path(path).exists() else None
