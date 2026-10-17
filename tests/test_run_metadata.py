"""run_impostor flags, saved-run metadata, and the cost estimate. Offline: no keys, no network.

Uses LocalMockRunner, which never executes the attacker's code.
"""

from __future__ import annotations

import hashlib

import pytest

from engine.fake_data.attacker import Attacker, prompt_sha256
from engine.fake_data.cache import load_run
from engine.fake_data.loop import fake_data_loop
from engine.fake_data.scripted import ScriptedAttacker
from engine.fake_data.sites import split_sites
from engine.fraud_checks.suite import load_suite
from engine.simulator.mechanisms import DEFAULT_MECHANISMS
from engine.simulator.trial import TrialConfig, generate_trial
from integrations.daytona import LocalMockRunner
from integrations.llm import LocalMockLLM, estimate_cost_usd
from scripts import run_impostor


@pytest.fixture(scope="module", autouse=True)
def isolated(tmp_path_factory: pytest.TempPathFactory):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DB_PATH", str(tmp_path_factory.mktemp("db") / "probe.db"))
        mp.setenv("DEMO_CACHE_DIR", str(tmp_path_factory.mktemp("cache")))
        yield


@pytest.fixture(scope="module")
def trial():
    return generate_trial(TrialConfig(scenario="B", mechanisms=DEFAULT_MECHANISMS))


def test_defaults_are_ten_rounds_and_no_fixed_seed() -> None:
    args = run_impostor.build_parser().parse_args([])
    assert args.rounds == 10 and args.seed is None and args.trial_seed == 2026 and args.suite_version == 0


def test_seed_flag_and_time_derived_default(monkeypatch: pytest.MonkeyPatch) -> None:
    assert run_impostor.build_parser().parse_args(["--seed", "41"]).seed == 41
    monkeypatch.setattr(run_impostor.time, "time", lambda: 1000.123)
    a = run_impostor.default_seed()
    monkeypatch.setattr(run_impostor.time, "time", lambda: 1000.456)
    assert a != run_impostor.default_seed()


def test_saved_run_records_seed_model_prompt_hash_suite_and_fake_output(trial, tmp_path) -> None:
    prompt = tmp_path / "training_attacker.md"
    prompt.write_text("prompt v1")
    attacker = Attacker("training", "mock-model", prompt, seed=41, llm=LocalMockLLM())
    suite = load_suite(0)
    fake_data_loop(trial, suite, attacker, 2, runner=LocalMockRunner(), real_sites=split_sites(trial), run_id="fd_test_meta")
    run = load_run("fd_test_meta")
    assert run["attacker"]["seed"] == 41 and run["attacker"]["model"] == "mock-model"
    assert run["attacker"]["prompt_file"] == "training_attacker.md"
    assert run["attacker"]["prompt_sha256"] == hashlib.sha256(b"prompt v1").hexdigest()
    assert run["suite"]["name"] == "sentinel" and run["suite"]["version"] == 0
    assert run["usage"] == {"input_tokens": 0, "output_tokens": 0}
    for r in run["rounds"]:
        assert r["ok"] and r["fake_output"] and r["fake_output"]["patients"] and r["input_seed"] == 41 * 100 + r["round"]


def test_scripted_attacker_has_no_prompt_hash() -> None:
    assert prompt_sha256(ScriptedAttacker()) is None


def test_cost_estimate_reads_prices_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATTACKER_PRICE_IN_PER_1M", raising=False)
    monkeypatch.delenv("ATTACKER_PRICE_OUT_PER_1M", raising=False)
    assert estimate_cost_usd(1_000_000, 1_000_000) == 0.0
    monkeypatch.setenv("ATTACKER_PRICE_IN_PER_1M", "0.25")
    monkeypatch.setenv("ATTACKER_PRICE_OUT_PER_1M", "2.0  # comment")
    assert estimate_cost_usd(2_000_000, 500_000) == pytest.approx(0.5 + 1.0)


def test_usage_summary_sums_llm_rounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATTACKER_PRICE_IN_PER_1M", "1")
    monkeypatch.setenv("ATTACKER_PRICE_OUT_PER_1M", "10")

    class R:
        def __init__(self, llm):
            self.llm = llm

    rounds = [R({"input_tokens": 1000, "output_tokens": 200}), R(None), R({"input_tokens": 3000, "output_tokens": 800})]
    assert run_impostor.usage_summary(rounds) == (4000, 1000, pytest.approx(0.004 + 0.01))


def test_training_prompt_goal_is_only_passing_the_checks() -> None:
    from engine.fake_data.attacker import PROMPT_FOR_ROLE

    text = PROMPT_FOR_ROLE["training"].read_text()
    assert "That is the only goal." in text and "strong drug effect" not in text
