"""The fake-data loop: write -> sandbox -> score -> feedback -> rewrite. Owner: Shreyas."""

from __future__ import annotations

from dataclasses import dataclass

from engine.fraud_checks.suite import CheckSuite, SiteScores
from engine.fake_data.attacker import Attacker
from engine.simulator.trial import Trial

OWNER = "Shreyas"


@dataclass
class Round:
    """One attack round. Persisted to fake_data_rounds and streamed to the UI.

    Attributes:
        round: 0-based round index.
        code: The attacker's fake-site source for this round.
        sandbox_id: Daytona sandbox ID the code ran in.
        ok: False if the code errored, timed out, or failed schema validation.
        scores: Check-suite scores for the fake site (None if not ok).
        combined: Combined risk score (None if not ok).
        escaped: True if combined < the check-suite threshold.
        damage: Effect shift from including the fake site (see engine.analysis.damage).
    """

    round: int
    code: str
    sandbox_id: str
    ok: bool
    scores: SiteScores | None
    combined: float | None
    escaped: bool
    damage: dict | None


def fake_data_loop(trial: Trial, suite: CheckSuite, attacker: Attacker, rounds: int = 8) -> list[Round]:
    """Run `rounds` attack rounds. Sandbox errors and schema errors become feedback, not crashes."""
    raise NotImplementedError(f"owner: {OWNER}")
