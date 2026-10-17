"""Sentinel: site splitting, the five core checks, scoring, and the frozen v0 calibration."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from engine.fake_data.sites import split_sites
from engine.fraud_checks.base import SCORE_CLIP, SiteData
from engine.fraud_checks.calibrate import FALSE_ALARM_BUDGET, threshold_for
from engine.fraud_checks.checks_core import CORE_CHECKS
from engine.fraud_checks.suite import FROZEN_DIR, CheckSuite, SiteScores, load_suite
from engine.simulator.mechanisms import DEFAULT_MECHANISMS
from engine.simulator.trial import TrialConfig, generate_trial


@pytest.fixture(scope="module")
def demo_sites(tmp_path_factory: pytest.TempPathFactory) -> list[SiteData]:
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DB_PATH", str(tmp_path_factory.mktemp("db") / "probe.db"))
        trial = generate_trial(TrialConfig("B", seed=2026, mechanisms=DEFAULT_MECHANISMS))
    return split_sites(trial)


@pytest.fixture(scope="module")
def suite() -> CheckSuite:
    return load_suite(0)


def test_split_sites_partitions_rows(demo_sites) -> None:
    assert [s.site_id for s in demo_sites] == [f"S{i:02d}" for i in range(1, 21)]
    for s in demo_sites:
        assert set(s.tables["patients"]["site_id"]) == {s.site_id}
        assert set(s.tables["visits"]["patient_id"]) <= set(s.tables["patients"]["patient_id"])
        assert set(s.tables["labs"]["visit_id"]) <= set(s.tables["visits"]["visit_id"])
    assert sum(len(s.tables["labs"]) for s in demo_sites) > 10_000
    assert sum(len(s.tables["patients"]) for s in demo_sites) == 800


def test_frozen_v0(suite) -> None:
    data = json.loads((FROZEN_DIR / "v0.json").read_text())
    assert suite.version == 0 and suite.threshold == data["threshold"]
    assert [c.name for c in suite.checks] == [c.name for c in CORE_CHECKS] == data["checks"][:5]
    assert data["budget"] == FALSE_ALARM_BUDGET
    assert data["verification"]["false_alarm_rate"] <= FALSE_ALARM_BUDGET + 0.02


def test_demo_false_alarms_match_frozen_file(suite, demo_sites) -> None:
    """Determinism: the demo trial flags exactly the real sites recorded when v0 was frozen."""
    flagged = [s.site_id for s in demo_sites if suite.flags(s, demo_sites)]
    assert flagged == json.loads((FROZEN_DIR / "v0.json").read_text())["verification"]["demo_sites_flagged"]


def test_real_site_scores_are_z_like(suite, demo_sites) -> None:
    scores = pd.DataFrame([suite.score_site(s, demo_sites).per_check for s in demo_sites])
    assert (scores.mean().abs() < 0.8).all(), scores.mean()
    assert (scores.std() < 2.0).all(), scores.std()


def test_threshold_for() -> None:
    scores = list(range(100))
    t = threshold_for(scores, 0.05)
    assert sum(s >= t for s in scores) == 5


def test_with_check_and_fired(suite) -> None:
    class Always:
        name = "always"

        def score(self, site, reference):
            return 99.0

    bigger = suite.with_check(Always())
    assert bigger.version == suite.version + 1 and bigger.threshold == suite.threshold
    assert len(suite.checks) == 5 and len(bigger.checks) == 6
    s = SiteScores(per_check={"a": 1.0, "b": 4.0, "c": 3.2}, combined=4.0)
    assert s.fired(3.118) == ["b", "c"]


# ---------------------------------------------------------------- crude fakes


def _copy(site: SiteData, site_id: str = "F01") -> SiteData:
    return SiteData(site_id, {k: v.copy() for k, v in site.tables.items()})


def _vitals_with_patient(site: SiteData) -> pd.DataFrame:
    return site.tables["vitals"].merge(site.tables["visits"][["visit_id", "patient_id", "date"]], on="visit_id")


def fake_digit_preference(site: SiteData) -> SiteData:
    """BP written down by hand, rounded to the nearest 5."""
    f = _copy(site)
    for col in ("sbp", "dbp"):
        f.tables["vitals"][col] = (np.round(f.tables["vitals"][col] / 5) * 5).astype(int)
    return f


def fake_too_tidy(site: SiteData) -> SiteData:
    """Every patient pulled halfway to the site average: plausible means, too little spread."""
    f = _copy(site)
    p = f.tables["patients"]
    for col in ("bmi", "baseline_hba1c"):
        p[col] = (p[col].mean() + 0.4 * (p[col] - p[col].mean())).round(1)
    v = _vitals_with_patient(f)
    pmean = v.groupby("patient_id")["sbp"].transform("mean")
    f.tables["vitals"]["sbp"] = np.round(v["sbp"].mean() + 0.4 * (pmean - v["sbp"].mean()) + 0.4 * (v["sbp"] - pmean)).astype(int).to_numpy()
    return f


def fake_broken_correlations(site: SiteData, rng=np.random.default_rng(0)) -> SiteData:
    """Each variable drawn on its own: weight unrelated to BMI, DBP unrelated to SBP."""
    f = _copy(site)
    v = _vitals_with_patient(f)
    pids = f.tables["patients"]["patient_id"].to_numpy()
    shuffled = dict(zip(pids, rng.permutation(pids)))
    pmean = v.groupby("patient_id")[["weight", "dbp"]].mean()
    donor = v["patient_id"].map(shuffled)
    for col in ("weight", "dbp"):
        own = v["patient_id"].map(pmean[col])
        f.tables["vitals"][col] = (v[col] - own + donor.map(pmean[col])).round(1 if col == "weight" else 0).to_numpy()
    f.tables["vitals"]["dbp"] = f.tables["vitals"]["dbp"].astype(int)
    return f


def fake_too_smooth(site: SiteData) -> SiteData:
    """Weight and BP trajectories drawn as clean straight lines from first to last visit."""
    f = _copy(site)
    v = _vitals_with_patient(f).sort_values(["patient_id", "date"])
    for col in ("weight", "sbp"):
        g = v.groupby("patient_id")[col]
        first, last, n, i = g.transform("first"), g.transform("last"), g.transform("size"), g.cumcount()
        v[col] = first + (last - first) * i / (n - 1).clip(lower=1)
    v = v.set_index("visit_id")
    f.tables["vitals"]["weight"] = v.loc[f.tables["vitals"]["visit_id"], "weight"].round(1).to_numpy()
    f.tables["vitals"]["sbp"] = v.loc[f.tables["vitals"]["visit_id"], "sbp"].round().astype(int).to_numpy()
    return f


@pytest.mark.parametrize(
    ("make_fake", "check"),
    [
        (fake_digit_preference, "digit_pref"),
        (fake_too_tidy, "variance"),
        (fake_too_tidy, "inlier"),
        (fake_broken_correlations, "corr_struct"),
        (fake_too_smooth, "autocorr"),
    ],
)
def test_crude_fake_caught_by_its_check(suite, demo_sites, make_fake, check: str) -> None:
    template = demo_sites[0]
    fake = make_fake(template)
    scores = suite.score_site(fake, demo_sites)
    assert check in scores.fired(suite.threshold), scores.per_check
    assert scores.combined >= suite.threshold
    assert suite.score_site(template, demo_sites).per_check[check] < suite.threshold


def test_degenerate_site_scores_max(suite, demo_sites) -> None:
    f = _copy(demo_sites[0])
    f.tables["vitals"][["sbp", "dbp"]] = 120
    f.tables["vitals"]["weight"] = 80.0
    scores = suite.score_site(f, demo_sites)
    assert scores.combined == SCORE_CLIP
