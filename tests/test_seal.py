"""Offline Seal tests: declared fields, safety, exhaustive search, and live API."""
import importlib
from itertools import combinations
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from engine.blind_leak import utility as task_utility

seal = importlib.import_module("engine.blind_leak.cheapest_fix")


def test_task_utility_and_delegation():
    assert len(task_utility.OPERATIONAL_TASKS) == 6
    assert task_utility.utility([]) == 1
    assert task_utility.utility(["unblinded_pharmacist", "sham_titration"]) == 1
    assert task_utility.utility(["central_lab"]) == pytest.approx(5 / 6)
    assert task_utility.utility(["matched_kits"]) == pytest.approx(5 / 6)
    assert task_utility.utility(["central_lab", "matched_kits"]) == pytest.approx(4 / 6)
    assert task_utility.utility(["central_lab", "central_lab"]) == pytest.approx(5 / 6)


def test_utility_on_known_field_map(monkeypatch):
    monkeypatch.setattr(task_utility, "TASK_FIELDS", {
        "schedule": frozenset({"visit.date"}),
        "labs": frozenset({"lab.value", "lab.kind"}),
        "report_safety_events": frozenset({"investigator.adverse_events.detail"}),
    })
    monkeypatch.setattr(task_utility, "REMEDY_FIELD_EFFECTS", {
        "mask_lab": frozenset({"lab.value"}),
        "mask_visit": frozenset({"visit.date"}),
    })
    assert task_utility.utility([]) == 1
    assert task_utility.utility(["mask_lab"]) == pytest.approx(2 / 3)
    assert task_utility.utility(["mask_lab", "mask_visit"]) == pytest.approx(1 / 3)


def test_safety_rejects_investigator_ae_mask(monkeypatch):
    for size in range(5):
        for combo in combinations(seal.REMEDIES, size):
            assert task_utility.safety_accessible(list(combo))
    monkeypatch.setitem(task_utility.REMEDY_FIELD_EFFECTS, "hide_ae",
                        frozenset({"investigator.adverse_events.detail"}))
    assert task_utility.safety_accessible(["hide_ae"]) is False
    assert task_utility.safety_accessible(["matched_kits", "hide_ae"]) is False
    with pytest.raises(ValueError, match="unknown remedies"):
        task_utility.safety_accessible(["unknown"])


@pytest.fixture
def synthetic_search(monkeypatch):
    calls = []

    def export(trial_id, role, remedies):
        assert trial_id == "synthetic"
        assert role == "assessor"
        calls.append(tuple(remedies))
        return pd.DataFrame({"policy": [tuple(remedies)]})

    def blind(view, trial_id, **kwargs):
        assert kwargs["n_permutations"] == 0 and kwargs["top"] == 0
        combo = frozenset(view.iloc[0]["policy"])
        auc = {frozenset({"sham_titration"}): 0.54,
               frozenset({"unblinded_pharmacist"}): 0.52,
               frozenset({"matched_kits"}): 0.40,
               frozenset({"central_lab"}): 0.40}.get(combo, 0.8)
        return SimpleNamespace(auc=auc)

    monkeypatch.setattr(seal, "export_view", export)
    monkeypatch.setattr(seal, "run_blind", blind)
    return calls


def test_search_picks_lowest_cost_feasible_and_evaluates_all(synthetic_search):
    best, rows = seal.cheapest_fix("synthetic")
    assert len(rows) == len(set(synthetic_search)) == 16
    assert best["combo"] == ["sham_titration"]
    assert best["auc"] == 0.54 and best["utility"] == 1 and best["cost"] == 1
    # Lower-AUC candidates cannot win when they lose a required task.
    assert next(r for r in rows if r["combo"] == ["matched_kits"])["utility"] < 0.9


def test_search_rejects_unsafe_candidate(synthetic_search, monkeypatch):
    monkeypatch.setattr(seal, "safety_accessible", lambda combo: "sham_titration" not in combo)
    best, _ = seal.cheapest_fix("synthetic")
    assert best["combo"] == ["unblinded_pharmacist"]


def test_search_returns_none_without_feasible_combo(synthetic_search):
    best, rows = seal.cheapest_fix("synthetic", auc_ceiling=0.3)
    assert best is None and len(rows) == 16


def test_search_validates_thresholds_before_export(synthetic_search):
    with pytest.raises(ValueError):
        seal.cheapest_fix("synthetic", utility_floor=1.1)
    assert not synthetic_search


def test_live_route_preserves_shape(synthetic_search, monkeypatch):
    from backend.main import app
    monkeypatch.setenv("DEMO_MODE", "live")
    response = TestClient(app).post("/blind-leak/cheapest-fix", json={"trial_id": "synthetic"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["_mock"] is False and data["costs_are_assigned"] is True
    assert data["recommended"]["combo"] == ["sham_titration"]
    assert len(data["results"]) == 16
    assert set(data["results"][0]) == {"combo", "auc", "utility", "cost", "safety_ok"}
