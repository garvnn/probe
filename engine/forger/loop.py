"""The forger loop: write -> sandbox -> score -> feedback -> rewrite. Owner: Shreyas."""

from __future__ import annotations

from dataclasses import dataclass

from engine.detector.detector import Detector, SiteScores
from engine.forger.attacker import Attacker
from engine.generator.trial import Trial

OWNER = "Shreyas"


@dataclass
class Round:
    """One attack round. Persisted to forger_rounds and streamed to the UI.

    Attributes:
        round: 0-based round index.
        code: The attacker's generator source for this round.
        sandbox_id: Daytona sandbox ID the code ran in.
        ok: False if the code errored, timed out, or failed schema validation.
        scores: Detector scores for the fake site (None if not ok).
        combined: Combined risk score (None if not ok).
        escaped: True if combined < detector threshold.
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


def forger_loop(trial: Trial, detector: Detector, attacker: Attacker, rounds: int = 8) -> list[Round]:
    """Run `rounds` attack rounds. Sandbox errors and schema errors become feedback, not crashes."""
    raise NotImplementedError(f"owner: {OWNER}")
