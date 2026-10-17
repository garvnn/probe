"""Trial math: the primary ANCOVA, damage from fake sites, and the breaking point."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.analysis.breaking_point import breaking_point, concludes_drug_works
from engine.analysis.damage import effect_shift
from engine.analysis.primary import analysis_frame, primary_analysis, primary_result
from engine.fake_data.sites import split_sites
from engine.fraud_checks.base import SiteData
from engine.simulator.trial import TrialConfig, generate_trial
from evals.ground_truth import ground_truth


@pytest.fixture(scope="module", autouse=True)
def temp_db(tmp_path_factory: pytest.TempPathFactory):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DB_PATH", str(tmp_path_factory.mktemp("db") / "probe.db"))
        yield


@pytest.fixture(scope="module")
def trial_a():
    return generate_trial(TrialConfig("A"))


@pytest.fixture(scope="module")
def trial_b():
    return generate_trial(TrialConfig("B"))


def inflated_fake(trial, template_index: int, drug_shift: float = -1.2, with_arms: bool = True) -> SiteData:
    """A copy of a real site, renamed to S21, whose drug patients' Week 24 HbA1c is pushed down by
    `drug_shift`. Carries its arms the way a validated attacker site does."""
    real = split_sites(trial)[template_index]
    tables = {k: v.copy() for k, v in real.tables.items()}
    arms = ground_truth(trial.trial_id).reindex(tables["patients"]["patient_id"])
    labs = tables["labs"].merge(tables["visits"][["visit_id", "patient_id", "visit_name"]], on="visit_id", how="left")
    target = (labs["test"] == "hba1c") & (labs["visit_name"] == "Week 24") & (labs["patient_id"].map(arms) == "drug")
    tables["labs"].loc[target.to_numpy(), "value"] += drug_shift
    tables["patients"]["site_id"] = "S21"
    return SiteData("S21", tables, arms=arms if with_arms else None)


def test_scenario_a_drug_works(trial_a) -> None:
    r = primary_result(trial_a)
    assert r.effect == pytest.approx(-0.5, abs=0.12)
    assert r.p < 1e-6 and r.ci95[0] < r.effect < r.ci95[1] < 0
    assert concludes_drug_works(r.effect, r.p)


def test_scenario_b_drug_does_nothing(trial_b) -> None:
    effect, p = primary_analysis(trial_b)
    assert abs(effect) < 0.15 and p > 0.05
    assert not concludes_drug_works(effect, p)


def test_analysis_frame_is_complete_cases(trial_b) -> None:
    df = analysis_frame(trial_b)
    assert df["patient_id"].is_unique and not df["fake"].any()
    assert 0.85 * 800 < len(df) <= 800  # dropouts and missed Week 24 visits are left out
    assert set(df["arm"]) == {"drug", "placebo"} and df["site"].nunique() == 20


def test_effect_shift_moves_toward_the_fakes_claim(trial_b) -> None:
    d = effect_shift(trial_b, [inflated_fake(trial_b, 0)])
    assert d.effect_real == pytest.approx(primary_analysis(trial_b)[0])
    assert d.effect_with_fake < d.effect_real - 0.03
    assert d.p_with_fake < d.p_real
    assert d.fake_patients_analyzed > 30


def test_fake_without_arms_cannot_do_damage(trial_b) -> None:
    d = effect_shift(trial_b, [inflated_fake(trial_b, 0, with_arms=False)])
    assert d.fake_patients_analyzed == 0
    assert d.effect_with_fake == pytest.approx(d.effect_real) and d.p_with_fake == pytest.approx(d.p_real)


def test_fakes_sharing_a_site_id_are_separate_sites(trial_b) -> None:
    fakes = [inflated_fake(trial_b, i) for i in range(3)]
    df = analysis_frame(trial_b, fakes)
    assert df.loc[df["fake"], "site"].nunique() == 3
    assert primary_result(trial_b, fakes).n_fake == int(df["fake"].sum())


def test_breaking_point_scenario_b(trial_b) -> None:
    fakes = [inflated_fake(trial_b, i) for i in range(6)]
    curve, break_k = breaking_point(trial_b, fakes)
    assert [c["k"] for c in curve] == list(range(7))
    effects = [c["effect"] for c in curve]
    assert all(b < a for a, b in zip(effects, effects[1:])), "each inflated fake pushes the effect further"
    assert break_k is not None and 1 <= break_k <= 6
    assert concludes_drug_works(curve[break_k]["effect"], curve[break_k]["p"])
    assert not any(concludes_drug_works(c["effect"], c["p"]) for c in curve[:break_k])


def test_breaking_point_no_flip_and_short_list(trial_a, trial_b) -> None:
    curve, break_k = breaking_point(trial_a, [inflated_fake(trial_a, 0)], max_k=6)
    assert len(curve) == 2 and break_k is None  # a working drug that looks better still "works"
    curve, break_k = breaking_point(trial_b, [])
    assert len(curve) == 1 and break_k is None


def test_honest_copies_barely_move_scenario_b(trial_b) -> None:
    fakes = [inflated_fake(trial_b, i, drug_shift=0.0) for i in range(3)]
    curve, break_k = breaking_point(trial_b, fakes)
    assert break_k is None
    assert np.ptp([c["effect"] for c in curve]) < 0.1
