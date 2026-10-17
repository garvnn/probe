"""LLM attacker that writes site-fabrication code. Owner: Shreyas."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

OWNER = "Shreyas"

PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass
class Attacker:
    """One attacker strategy. Attacker A is used for hardening; attacker B is held out.

    Attributes:
        attacker_id: "A" or "B" (or a sweep label).
        model: LLM model ID (ATTACKER_A_MODEL / ATTACKER_B_MODEL). A and B should differ.
        system_prompt_path: Path to the system prompt markdown in `prompts/`.
        seed: Sampling seed, logged per run.
    """

    attacker_id: str
    model: str
    system_prompt_path: Path
    seed: int

    def write_generator(self, context: dict, feedback: dict | None) -> str:
        """Ask the LLM for a new site generator given the public context and last round's feedback.

        Returns Python source that defines `generate_site(context) -> dict[str, list[dict]]`
        using only numpy, pandas, and datetime. Output tables must match docs/schema.md.
        The source is untrusted: it is only ever executed through a SandboxRunner.
        """
        raise NotImplementedError(f"owner: {OWNER}")
