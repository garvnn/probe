"""What the attacker is allowed to know. Owner: Shreyas."""

from __future__ import annotations

from engine.generator.trial import Trial

OWNER = "Shreyas"


def public_context(trial: Trial) -> dict:
    """Protocol plus aggregate stats a site investigator could plausibly know.

    Never patient-level rows from other sites, never ground truth.
    """
    raise NotImplementedError(f"owner: {OWNER}")
