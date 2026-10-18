"""Tell on synthetic views: chance on noise, detects and localizes an injected leak, site-grouped CV."""

from __future__ import annotations

import numpy as np
import pytest

from engine.blind_leak.attribution import leak_table
from engine.blind_leak.classifier import cross_validate, site_folds
from engine.blind_leak.features import build_features
from engine.blind_leak.permutation import FAST_N, run_permutation, shuffle_within
from engine.blind_leak.result import align, run_blind
from engine.blind_leak.synthetic import Leak, make_trial

pytest.importorskip("lightgbm")

LEAK = Leak(source="dispensing", kind="titration_step", mode="rate", strength=1.2)


@pytest.fixture(scope="module")
def noise():
    t = make_trial(seed=11)
    return t, *align(build_features(t.view("coordinator")), t.arms)


@pytest.fixture(scope="module")
def leaky():
    t = make_trial(leaks=[LEAK], seed=12)
    return t, *align(build_features(t.view("coordinator")), t.arms)


def test_features_one_row_per_patient_and_no_arm(noise) -> None:
    t, X, y, groups = noise
    assert len(X) == len(t.arms) == 800
    assert not any("arm" in c or "drug" == c for c in X.columns)
    assert groups.nunique() == 20


def test_noise_is_at_chance(noise) -> None:
    _, X, y, groups = noise
    r = run_permutation(X, y, groups, n=FAST_N, seed=0)
    assert abs(r.observed.accuracy - 0.5) < 0.06
    assert r.p_value > 0.05
    assert r.accuracy_in_null


def test_injected_leak_detected_and_ranked_first(leaky) -> None:
    _, X, y, groups = leaky
    r = run_permutation(X, y, groups, n=FAST_N, seed=0)
    assert r.observed.accuracy > r.null_hi
    assert r.p_value < 0.05
    table = leak_table(X, y, groups, seed=0, top=5)
    assert table.iloc[0]["field"] == "dispensing__titration_step_n"
    assert table.iloc[0]["drop_auc"] > 0


def test_no_site_in_both_train_and_test(leaky) -> None:
    _, X, y, groups = leaky
    folds = site_folds(groups)
    pid = X.index.to_numpy()
    g = groups.to_numpy()
    tested = set()
    for tr, te in folds:
        assert not set(g[tr]) & set(g[te])
        assert not set(pid[tr]) & set(pid[te])
        tested |= set(g[te])
    assert tested == set(g)
    for f in cross_validate(X, y, groups).folds:
        assert not set(f.train_sites) & set(f.test_sites)


def test_shuffle_keeps_site_balance(leaky) -> None:
    _, X, y, groups = leaky
    s = shuffle_within(y, groups, np.random.default_rng(0))
    before = y.groupby(groups).value_counts().sort_index()
    after = s.groupby(groups).value_counts().sort_index()
    assert before.equals(after)
    assert (s != y).any()


def test_deterministic(leaky) -> None:
    _, X, y, groups = leaky
    a = run_permutation(X, y, groups, n=5, seed=3)
    b = run_permutation(X, y, groups, n=5, seed=3)
    assert a.observed.accuracy == b.observed.accuracy
    assert np.array_equal(a.null_accuracy, b.null_accuracy)


def test_run_blind_with_labels(leaky) -> None:
    t, *_ = leaky
    r = run_blind(t.view("coordinator"), "synthetic", labels=t.arms, n_permutations=FAST_N)
    assert r.top_leaks[0]["field"] == "dispensing__titration_step_n"
    assert not r.blind_holds
