"""Stranger provenance, isolation, and cached API regression coverage."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from engine.fake_data.cache import run_path
from engine.fake_data.stranger import frozen_hashes, score_runs, wilson
from integrations.llm import client_for, provider_for


def test_gemini_has_dedicated_credentials(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    assert provider_for("gemini-2.5-pro") == "gemini"
    assert client_for("gemini-2.5-pro") is None
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    client = client_for("gemini-2.5-pro")
    assert client.api_key == "gemini-test-key"
    assert client.base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert client.provider == "gemini"


def test_stranger_is_excluded_from_patch_corpus(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_CACHE_DIR", str(tmp_path))
    assert run_path("fd_stranger_example").parent == tmp_path / "stranger"
    assert run_path("fd_training_example").parent == tmp_path


def test_wilson_uses_run_count():
    assert wilson(0, 0) == (0, 1)
    lo, hi = wilson(1, 1)
    assert 0.20 < lo < 0.21 and hi == pytest.approx(1)


def test_scorer_rejects_mock_before_scoring(monkeypatch):
    monkeypatch.setattr("engine.fake_data.sites.split_sites", lambda _: [])
    with pytest.raises(ValueError, match="measured Stranger"):
        score_runs([{"attacker": {"id": "training", "model": "test-model", "prompt_sha256": "test"}, "rounds_planned": 3}], SimpleNamespace(trial_id="trial"))


def test_cached_report_requires_trial_and_frozen_provenance(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_MODE", "cached")
    monkeypatch.setenv("DEMO_CACHE_DIR", str(tmp_path))
    client = TestClient(app)
    body = {"trial_id": "tr_2026_B", "suite_versions": [0, 1]}
    assert client.post("/test-attacker/eval", json=body).status_code == 404
    report = {"_mock": False, "trial_id": body["trial_id"], "attacker_id": "test",
              "never_seen_during_patching": True, "frozen_sha256": frozen_hashes(),
              "rows": [{"suite_version": v, "attacker_id": "test", "attempted": 1,
                        "escaped": 0, "evasion_rate": 0, "ci95": [0, 0.8], "fp_rate": 0}
                       for v in (0, 1)]}
    path = tmp_path / "stranger_report.json"
    path.write_text(json.dumps(report))
    result = client.post("/test-attacker/eval", json=body)
    assert result.status_code == 200
    assert result.json()["_mock"] is False
    assert client.post("/test-attacker/eval", json={**body, "trial_id": "wrong"}).status_code == 404
    report["frozen_sha256"] = {}
    path.write_text(json.dumps(report))
    assert client.post("/test-attacker/eval", json=body).status_code == 409


def test_paired_scoring_counts_runs_and_retains_errors(monkeypatch):
    monkeypatch.setattr("engine.fake_data.sites.split_sites", lambda _: [])
    monkeypatch.setattr("engine.fake_data.validate.validate_schema", lambda output, _: output)

    class Suite:
        threshold = 1

        def __init__(self, version):
            self.version = version

        def score_site(self, site, _):
            return SimpleNamespace(combined=site["score"] + self.version)

        def false_alarm_rate(self, _):
            return 0.05

    monkeypatch.setattr("engine.fraud_checks.suite.load_suite", Suite)
    run = {"run_id": "fd_stranger_example", "trial_id": "trial", "fake_site_id": "S21",
           "attacker": {"id": "test", "kind": "llm", "model": "gemini-test", "seed": 99,
                        "prompt_sha256": "frozen-test-prompt"},
           "not_a_result": False, "runner": "DaytonaRunner", "suite": {"version": 0},
           "frozen_sha256": frozen_hashes(), "rounds_planned": 3,
           "rounds": [{"ok": True, "sandbox_id": "sandbox", "fake_output": {"score": 0.5}},
                      {"ok": True, "sandbox_id": "sandbox2", "fake_output": {"score": 0.1}},
                      {"ok": False, "error": "schema"}]}
    report = score_runs([run], SimpleNamespace(trial_id="trial"))
    assert [(r["attempted"], r["escaped"]) for r in report["rows"]] == [(1, 1), (1, 0)]
    assert report["per_run"][0]["escaped_rounds"] == 2
    assert report["per_run"][1]["error_rounds"] == 1
    with pytest.raises(ValueError, match="Duplicate"):
        score_runs([run, run], SimpleNamespace(trial_id="trial"))
    run["frozen_sha256"] = {}
    with pytest.raises(ValueError, match="Frozen artifacts"):
        score_runs([run], SimpleNamespace(trial_id="trial"))


def test_readiness_rejects_unfrozen_patch_and_training_reuse(monkeypatch, tmp_path):
    from engine.fake_data import stranger
    monkeypatch.setenv("TRAINING_ATTACKER_MODEL", "training-model")
    monkeypatch.setenv("TEST_ATTACKER_MODEL", "gemini-test-model")
    monkeypatch.setattr(stranger, "cache_dir", lambda: tmp_path)
    (tmp_path / "fd_training.json").write_text(json.dumps({
        "not_a_result": False,
        "attacker": {"id": "training", "model": "training-model", "seed": 41}}))
    with pytest.raises(ValueError, match="seed 41"):
        stranger.assert_test_ready(41)
    stranger.assert_test_ready(99)
    monkeypatch.setenv("TEST_ATTACKER_MODEL", "training-model")
    with pytest.raises(ValueError, match="different model"):
        stranger.assert_test_ready(99)
    monkeypatch.setattr(stranger, "FROZEN", tmp_path)
    (tmp_path / "patch_report.json").write_text('{"frozen":false}')
    with pytest.raises(ValueError, match="accepted and frozen"):
        stranger.assert_test_ready(99)
