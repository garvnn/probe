"""Offline regression checks for measured cache identity and truthful fallback."""

import pytest
from fastapi.testclient import TestClient

from backend.cached import load_response
from backend.main import app
from scripts.precompute_demo import ResponseCache, assemble_contract, main, saved_escapes, write


@pytest.fixture
def cache_root(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("DEMO_MODE", "cached")
    return tmp_path


def install_index(root, cache):
    write(root / "precomputed/manifest.json", {"_mock": False, "trial_id": "tr_2026_B",
          "run_id": "fd_locked", "responses": cache.responses})


def test_exact_request_cache_never_relabels_measurement(cache_root):
    cache = ResponseCache(cache_root)
    cache.save("blind_leak_run", {"trial_id": "tr_2026_B", "view": "coordinator"},
               {"trial_id": "tr_2026_B", "view": "coordinator"})
    install_index(cache_root, cache)
    assert load_response("blind_leak_run", {"trial_id": "tr_2026_B", "view": "coordinator"})["_mock"] is False
    assert load_response("blind_leak_run", {"trial_id": "other", "view": "coordinator"}) is None
    assert load_response("blind_leak_run", {"trial_id": "tr_2026_B", "view": "assessor"}) is None


def test_cache_rejects_stand_in(cache_root):
    cache = ResponseCache(cache_root)
    cache.save("report", {}, {})
    install_index(cache_root, cache)
    write(cache_root / "precomputed/report.json", {"_mock": True})
    with pytest.raises(ValueError, match="not marked measured"):
        load_response("report", {})


def test_cache_prevents_path_escape(cache_root):
    write(cache_root / "precomputed/manifest.json", {"responses": {"report": [{"path": "../secret.json", "request": {}}]}})
    with pytest.raises(ValueError, match="outside"):
        load_response("report", {})


def test_live_unchanged_and_cached_missing_stays_badged(cache_root, monkeypatch):
    with TestClient(app) as client:
        response = client.post("/blind-leak/runs", json={"trial_id": "tr_2026_B"})
        assert response.status_code == 200 and response.json()["_mock"] is True
        monkeypatch.setenv("DEMO_MODE", "live")
        assert client.post("/blind-leak/runs", json={"trial_id": "tr_2026_B"}).status_code == 501


def test_route_serves_cached_p_value_and_matches_view(cache_root):
    cache = ResponseCache(cache_root)
    cache.save("blind_leak_run", {"trial_id": "tr_2026_B", "view": "coordinator", "accuracy": .75,
          "auc": .85, "null_lo": .45, "null_hi": .55, "utility": 1, "top_leaks": [],
          "p_value": .01, "n_permutations": 200}, {"trial_id": "tr_2026_B", "view": "coordinator"})
    install_index(cache_root, cache)
    with TestClient(app) as client:
        data = client.post("/blind-leak/runs", json={"trial_id": "tr_2026_B"}).json()
        assert data["_mock"] is False and data["p_value"] == .01
        other = client.post("/blind-leak/runs", json={"trial_id": "tr_2026_B", "view": "assessor"}).json()
        assert other["_mock"] is True


def test_saved_escapes_requires_saved_rows_never_executes_code():
    run = {"rounds": [{"round": 7, "ok": True, "escaped": True, "code": "raise AssertionError('never execute')"}]}
    with pytest.raises(ValueError, match="no saved site"):
        saved_escapes(run)


def test_contract_does_not_claim_unmeasured_safety_or_utility():
    rows = assemble_contract({"run_id": "saved", "rounds": [{"ok": True, "escaped": True}]},
        {"accuracy": .75, "auc": .85, "null_hi": .55, "p_value": .01},
        [{"effect_with_fake": -.1, "effect_real": -.02}])
    assert [r["status"] for r in rows] == ["broken", "broken", "broken", "untested", "untested"]
    assert "conclusion flip" in rows[2]["counterexample"]


def test_cli_rejects_nonlocked_seed_before_measurement():
    with pytest.raises(SystemExit):
        main(["--seed", "43"])


def test_pinned_run_cannot_be_replaced_by_newer_stand_in(cache_root):
    locked = {"run_id": "fd_locked", "trial_id": "tr_2026_B", "not_a_result": False,
              "attacker": {"id": "training"}, "suite": {"version": 0}}
    newer = {**locked, "run_id": "fd_newer", "not_a_result": True}
    write(cache_root / "fd_locked.json", locked)
    write(cache_root / "fd_newer.json", newer)
    install_index(cache_root, ResponseCache(cache_root))
    with TestClient(app) as client:
        data = client.post("/fake-data/runs", json={"trial_id": "tr_2026_B"}).json()
    assert data["run_id"] == "fd_locked" and data["_mock"] is False


def test_patch_held_out_has_its_own_measured_route(cache_root):
    cache = ResponseCache(cache_root)
    cache.save("patch_held_out", {"trial_id": "tr_2026_B", "table": [{"suite": "v1"}]}, {"trial_id": "tr_2026_B"})
    install_index(cache_root, cache)
    with TestClient(app) as client:
        data = client.get("/fraud-checks/held-out", params={"trial_id": "tr_2026_B"}).json()
        stranger = client.post("/test-attacker/eval", json={"trial_id": "tr_2026_B"}).json()
    assert data["_mock"] is False and stranger["_mock"] is True
