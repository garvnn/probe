"""Cached mode: /blind-leak/* serve saved Tell/Seal results, never the fixture."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.main import app

TELL = {
    "_mock": False, "trial_id": "tr_A", "view": "coordinator", "remedies": [], "accuracy": 0.7, "auc": 0.8,
    "null_lo": 0.45, "null_hi": 0.55, "utility": 1.0, "p_value": 0.005, "top_leaks": [],
    "control": {"_mock": False, "trial_id": "tr_A_off", "view": "coordinator", "remedies": [], "accuracy": 0.5,
                "auc": 0.5, "null_lo": 0.45, "null_hi": 0.55, "utility": 1.0, "p_value": 0.6, "top_leaks": []},
}
ROW = {"combo": ["unblinded_pharmacist"], "accuracy": 0.5, "auc": 0.5, "null_lo": 0.45, "null_hi": 0.55,
       "p_value": 0.4, "utility": 1.0, "cost": 3.0, "safety_ok": True, "blind_restored": True, "acceptable": True}
SEAL = {"_mock": False, "trial_id": "tr_A", "view": "coordinator", "utility_floor": 0.9, "auc_ceiling": 0.55,
        "n_permutations": 200, "recommended": ROW, "results": [ROW]}


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEMO_MODE", "cached")
    monkeypatch.setenv("DEMO_CACHE_DIR", str(tmp_path))
    return TestClient(app)


def test_cached_without_saved_results_is_404_not_mock(client: TestClient) -> None:
    for path in ("/blind-leak/runs", "/blind-leak/cheapest-fix"):
        r = client.post(path, json={"trial_id": "tr_2026_B"})
        assert r.status_code == 404


def test_cached_serves_saved_results(client: TestClient, tmp_path) -> None:
    (tmp_path / "tell_tr_A.json").write_text(json.dumps(TELL))
    (tmp_path / "seal_tr_A.json").write_text(json.dumps(SEAL))
    run = client.post("/blind-leak/runs", json={"trial_id": "tr_2026_B"}).json()
    assert run["_mock"] is False and run["trial_id"] == "tr_A" and run["control"]["accuracy"] == 0.5
    fix = client.post("/blind-leak/cheapest-fix", json={"trial_id": "tr_2026_B"}).json()
    assert fix["_mock"] is False and fix["recommended"]["combo"] == ["unblinded_pharmacist"]
    pol = client.post("/blind-leak/policy", json={"trial_id": "x", "remedies": ["unblinded_pharmacist"]}).json()
    assert pol["_mock"] is False and pol["view"] == "coordinator" and pol["p_value"] == 0.4
    assert client.post("/blind-leak/policy", json={"trial_id": "x", "remedies": ["central_lab"]}).status_code == 404
