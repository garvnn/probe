"""Seal: remedies, utility, safety, and the 16-combo search on synthetic views."""

from __future__ import annotations

import pandas as pd
import pytest

from engine.blind_leak.cheapest_fix import all_combos, evaluate_combos, pick
from engine.blind_leak.remedies import REMEDIES, cost, validate
from engine.blind_leak.synthetic import Leak, make_trial
from engine.blind_leak.utility import OPERATIONAL_TASKS, safety_accessible, utility


@pytest.fixture(scope="module")
def trial():
    return make_trial(n_sites=8, patients_per_site=24, leaks=[Leak("dispensing", "titration_step", strength=1.2)], seed=1)


def _ae(view: pd.DataFrame) -> pd.DataFrame:
    return view.loc[view["source"] == "adverse_event"].sort_values(["patient_id", "date", "kind"]).reset_index(drop=True)


def test_sixteen_combos() -> None:
    combos = all_combos()
    assert len(combos) == 16
    assert len({tuple(c) for c in combos}) == 16


def test_every_combo_keeps_adverse_events_intact(trial) -> None:
    base = _ae(trial.view("coordinator"))
    assert len(base) > 0
    for combo in all_combos():
        pd.testing.assert_frame_equal(_ae(trial.view("coordinator", combo)), base)
        assert safety_accessible(combo)


def test_unknown_remedy_raises() -> None:
    with pytest.raises(ValueError):
        validate(["hide_adverse_events"])


def test_remedy_effects(trial) -> None:
    v = trial.view("coordinator", ["unblinded_pharmacist"])
    assert not (v["source"] == "dispensing").any()
    assert (trial.view("pharmacist", ["unblinded_pharmacist"])["source"] == "dispensing").any()
    v = trial.view("coordinator", ["central_lab"])
    assert not ((v["source"] == "lab") & (v["category"] == "local")).any()
    k = trial.view("coordinator", ["matched_kits"])
    k = k.loc[k["source"] == "kit_storage"]
    assert (k["category"] == "matched").all() and k["value"].isna().all()


def test_utility_rubric() -> None:
    assert utility([]) == 1.0
    assert utility(["unblinded_pharmacist", "sham_titration"]) == 1.0
    assert utility(["central_lab"]) == pytest.approx(1 - 1 / len(OPERATIONAL_TASKS))
    assert utility(REMEDIES) < 0.90
    assert cost(REMEDIES) == 7.0


def test_search_picks_cheapest_acceptable(trial) -> None:
    rec, rows = evaluate_combos(lambda c: trial.view("coordinator", c), trial.arms, n_permutations=5)
    assert len(rows) == 16
    none = rows[0]
    assert none["combo"] == [] and not none["blind_restored"]
    assert rec is not None and rec == pick(rows)
    cheaper = [r for r in rows if r["acceptable"] and r["cost"] < rec["cost"]]
    assert not cheaper
    assert "unblinded_pharmacist" in rec["combo"]


def test_no_acceptable_combo_is_reported() -> None:
    assert pick([{"acceptable": False, "cost": 1.0, "accuracy": 0.8}]) is None
