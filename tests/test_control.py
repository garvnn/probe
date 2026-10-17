"""Control: with every leak mechanism off, the blind-leak attack must be at chance.

If it isn't, that's a bug in the simulator or the view export, not a finding. Skips itself until
Tell's run_blind is implemented, then runs automatically.
"""

from __future__ import annotations

import pytest

from engine.blind_leak.result import run_blind
from engine.simulator.trial import TrialConfig, generate_trial
from engine.simulator.views import export_view


@pytest.fixture
def control_trial_id(tmp_path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "probe.db"))
    return generate_trial(TrialConfig(scenario="A", mechanisms={})).trial_id


def test_mechanisms_off_blind_at_chance(control_trial_id: str) -> None:
    view = export_view(control_trial_id, "coordinator")
    try:
        result = run_blind(view, control_trial_id)
    except NotImplementedError:
        pytest.skip("Tell's run_blind not implemented yet (owner: Ajay)")
    assert result.null_lo <= result.accuracy <= result.null_hi, (
        f"accuracy {result.accuracy:.3f} outside permutation null [{result.null_lo:.3f}, {result.null_hi:.3f}] with mechanisms off"
    )
