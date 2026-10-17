"""The test-scenario suite. Owner: Ajay."""

from __future__ import annotations

from engine.generator.trial import TrialConfig

OWNER = "Ajay"

SCENARIOS = (
    "A_mechanisms_on",   # drug works, leaks present
    "B_mechanisms_on",   # useless drug, damage test
    "strength_sweep",    # weak / medium / strong nausea effect
    "control_off",       # mechanisms off: Blind Breaker must be at chance
)


def build_scenario(name: str, seed: int = 2026) -> list[TrialConfig]:
    """TrialConfigs for scenario `name` (a sweep returns several)."""
    raise NotImplementedError(f"owner: {OWNER}")
