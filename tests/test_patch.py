"""Patch: site features, the learned check, the gate, and the pipeline's honest reporting."""

from __future__ import annotations

import json

import numpy as np
import pytest

from engine.fraud_checks.suite import FROZEN_DIR, load_suite
from engine.patch import data
from engine.patch.fallback_check import FallbackClassifierCheck
from engine.patch.features import FEATURES, feature_frame
from engine.patch.gate import MIN_HELDOUT_ESCAPES, evaluate_gate, wilson
from engine.patch.pipeline import run_patch


@pytest.fixture(scope="module")
def pools():
    with data.temp_db():
        fit = data.honest_pool(range(201, 206))
        hold = data.honest_pool(range(301, 304))
        fakes = data.scripted_fakes(seeds=range(3))
        yield fit, hold, fakes


@pytest.fixture(scope="module")
def frames(pools):
    fit, hold, fakes = pools
    return feature_frame(fit), feature_frame(hold), feature_frame([(f.site, f.reference) for f in fakes])


@pytest.fixture(scope="module")
def learned(frames):
    X_fit, _, X_fake = frames
    return FallbackClassifierCheck().fit_frames(X_fit, X_fake)


# ---------------------------------------------------------------- features


def test_features_are_z_like_on_honest_sites(frames) -> None:
    X_fit, X_hold, _ = frames
    assert list(X_fit.columns) == list(FEATURES)
    X = np.clip(X_hold, -10, 10)
    assert (X.mean().abs() < 1.0).all(), X.mean()[X.mean().abs() >= 1.0]
    assert (X.std() < 2.5).all(), X.std()[X.std() >= 2.5]


def test_scripted_fakes_stand_out(frames) -> None:
    _, X_hold, X_fake = frames
    assert X_fake["check_corr_struct"].median() > X_hold["check_corr_struct"].quantile(0.95)


def test_scripted_fakes_are_one_group(pools) -> None:
    _, _, fakes = pools
    assert {f.group for f in fakes} == {"scripted"} and {f.source for f in fakes} == {"scripted-regenerated"}
    assert all(f.site.arms is not None for f in fakes)


# ---------------------------------------------------------------- learned check


def test_learned_score_is_z_like_on_held_out_real(learned, frames) -> None:
    _, X_hold, X_fake = frames
    real = learned.score_frame(X_hold)
    assert abs(np.median(real)) < 0.6
    assert np.median(learned.score_frame(X_fake)) > np.quantile(real, 0.95)


def test_learned_params_round_trip(learned, pools) -> None:
    _, hold, _ = pools
    again = FallbackClassifierCheck.from_params(json.loads(json.dumps(learned.to_params())))
    site, ref = hold[0]
    assert again.score(site, ref) == pytest.approx(learned.score(site, ref))


def test_learned_explain_format(learned, pools) -> None:
    _, _, fakes = pools
    out = learned.explain(fakes[0].site, fakes[0].reference)
    assert out["check"] == "learned" and out["summary"].startswith("learned check:")
    assert all({"measure", "your_site", "real_sites_typical", "position"} <= set(r) for r in out["measures"])


def test_unfitted_learned_check_refuses_to_score(pools) -> None:
    _, hold, _ = pools
    with pytest.raises(RuntimeError, match="not fitted"):
        FallbackClassifierCheck().score(*hold[0])


def test_load_suite_rebuilds_learned_check(learned, tmp_path) -> None:
    v0 = json.loads((FROZEN_DIR / "v0.json").read_text())
    v1 = {**v0, "version": 1, "checks": [*v0["checks"], "learned"], "check_params": {"learned": learned.to_params()}, "threshold": 3.5}
    (tmp_path / "v1.json").write_text(json.dumps(v1))
    suite = load_suite(1, frozen_dir=tmp_path)
    assert [c.name for c in suite.checks][-1] == "learned" and suite.version == 1 and suite.threshold == 3.5
    assert suite.checks[-1].to_params()["coef"] == learned.to_params()["coef"]


# ---------------------------------------------------------------- gate


def test_wilson() -> None:
    assert wilson(0, 0) == (0.0, 1.0)
    lo, hi = wilson(9, 10)
    assert 0.59 < lo < 0.6 and 0.98 < hi <= 1.0


def _gate(real_after_flags: int, caught: int, n_escaped: int, n_real: int = 1000, real_before_flags: int = 40):
    t = 3.0
    real_before = np.r_[np.full(real_before_flags, 5.0), np.zeros(n_real - real_before_flags)]
    real_after = np.r_[np.full(real_after_flags, 5.0), np.zeros(n_real - real_after_flags)]
    fake_before = np.r_[np.zeros(n_escaped), np.full(4, 9.0)]  # 4 fakes v0 already caught don't count
    fake_after = np.r_[np.full(caught, 5.0), np.zeros(n_escaped - caught), np.full(4, 9.0)]
    return evaluate_gate(t, real_before, real_after, fake_before, fake_after)


def test_gate_accepts_clear_majority_with_flat_false_alarms() -> None:
    g = _gate(real_after_flags=48, caught=15, n_escaped=18)
    assert g.accepted and g.status == "accepted" and g.n_escaped == 18 and g.caught == 15


def test_gate_rejects_rising_false_alarms() -> None:
    g = _gate(real_after_flags=52, caught=18, n_escaped=18)
    assert not g.accepted and "rose 1.2 points" in g.status


def test_gate_rejects_unclear_majority() -> None:
    g = _gate(real_after_flags=40, caught=10, n_escaped=18)
    assert not g.accepted and "lower bound" in g.status


def test_gate_insufficient_escapes_is_never_a_pass() -> None:
    g = _gate(real_after_flags=40, caught=MIN_HELDOUT_ESCAPES - 1, n_escaped=MIN_HELDOUT_ESCAPES - 1)
    assert not g.accepted and g.status.startswith("insufficient")


def test_split_groups_keeps_runs_whole_and_scripted_in_train() -> None:
    groups = ["scripted"] * 5 + [f"fd_run{i}" for i in range(6) for _ in range(3)]
    train, held = data.split_groups(groups)
    assert "scripted" in train and "scripted" not in held
    assert len(held) == 3 and not (train & held)
    assert data.split_groups(groups) == (train, held)


# ---------------------------------------------------------------- pipeline


def test_pipeline_reports_insufficient_without_llm_runs(tmp_path) -> None:
    report = run_patch(
        cache_dir=tmp_path, write=False, fit_seeds=range(201, 204), holdout_seeds=range(301, 303), calibration_seeds=range(1, 3), scripted_seeds=range(2)
    )
    assert report["frozen"] is False and report["status"].startswith("insufficient")
    assert report["data"]["n_heldout_fakes"] == 0 and report["data"]["heldout_groups"] == []
    assert [r["suite"] for r in report["table"]] == ["v0", "candidate (not frozen)"]
    assert report["table"][0]["heldout_real_flagged"]["n"] == 40


def test_old_llm_rounds_without_saved_sites_are_skipped_not_run(tmp_path) -> None:
    run = {
        "run_id": "fd_old_llm", "trial_id": "tr_2026_B", "fake_site_id": "S21", "attacker": {"kind": "llm"},
        "rounds": [{"round": 0, "ok": True, "code": "def generate_site(c):\n    raise SystemExit('must never run locally')\n"}],
    }
    (tmp_path / "fd_old_llm.json").write_text(json.dumps(run))
    with data.temp_db():
        records, skipped = data.load_fakes(tmp_path)
    assert records == [] and len(skipped) == 1 and "sandbox" in skipped[0]
