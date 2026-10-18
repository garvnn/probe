"""Impostor loop, offline: no API keys, no network, no Daytona.

LLM-written code never runs locally. The only code these tests execute in-process is the
hand-written ScriptedAttacker source, through TrustedScriptedRunner, which refuses anything else.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from engine.fake_data.attacker import Attacker, build_user_message, extract_code, make_attacker
from engine.fake_data.cache import load_run
from engine.fake_data.context import public_context
from engine.fake_data.loop import fake_data_loop
from engine.fake_data.scripted import ScriptedAttacker, scripted_source
from engine.fake_data.sites import split_sites
from engine.fake_data.validate import SchemaError, validate_schema
from engine.fraud_checks.base import SCORE_CLIP
from engine.fraud_checks.checks_core import CORE_CHECKS
from engine.fraud_checks.suite import CheckSuite, load_suite
from engine.simulator.mechanisms import DEFAULT_MECHANISMS
from engine.simulator.trial import TrialConfig, generate_trial
from integrations.daytona import LocalMockRunner, SandboxResult
from integrations.llm import LocalMockLLM

SCRIPTED_SOURCES = {scripted_source(v) for v in (1, 2, 3, 4)}


class TrustedScriptedRunner:
    """Test-only: runs the hand-written scripted generators in-process. Refuses any other code."""

    def __init__(self) -> None:
        self.n = 0

    def run(self, code: str, inputs: dict, timeout: int = 60) -> SandboxResult:
        assert code in SCRIPTED_SOURCES, "TrustedScriptedRunner only runs ScriptedAttacker source"
        self.n += 1
        ns: dict = {}
        exec(compile(code, "scripted.py", "exec"), ns)
        return SandboxResult(True, "", "", ns["generate_site"](inputs), f"trusted_{self.n:03d}", 0.0)


class FixedRunner:
    """Returns a fixed SandboxResult without executing anything."""

    def __init__(self, result: SandboxResult) -> None:
        self.result = result

    def run(self, code: str, inputs: dict, timeout: int = 60) -> SandboxResult:
        return self.result


@dataclass
class RecordingAttacker(ScriptedAttacker):
    feedback_seen: list[dict | None] = field(default_factory=list)

    def write_fake_site_code(self, context: dict, feedback: dict | None) -> str:
        self.feedback_seen.append(feedback)
        return super().write_fake_site_code(context, feedback)


@pytest.fixture(scope="module", autouse=True)
def isolated(tmp_path_factory: pytest.TempPathFactory):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DB_PATH", str(tmp_path_factory.mktemp("db") / "probe.db"))
        mp.setenv("DEMO_CACHE_DIR", str(tmp_path_factory.mktemp("cache")))
        yield


@pytest.fixture(scope="module")
def trial():
    return generate_trial(TrialConfig(scenario="B", mechanisms=DEFAULT_MECHANISMS))


@pytest.fixture(scope="module")
def real_sites(trial):
    return split_sites(trial)


@pytest.fixture(scope="module")
def suite():
    return load_suite(0)


@pytest.fixture(scope="module")
def scripted_run(trial, suite, real_sites):
    return fake_data_loop(trial, suite, ScriptedAttacker(), 4, runner=TrustedScriptedRunner(), real_sites=real_sites, run_id="fd_test_scripted")


# ---------------------------------------------------------------- the loop


def test_sentinel_detects_every_scripted_version(scripted_run) -> None:
    """The stand-in let v4 escape; real Sentinel still catches it (weight not tied to BMI, vitals with
    no visit-to-visit drift)."""
    assert [r.status for r in scripted_run] == ["detected"] * 4


def test_each_version_is_caught_for_the_flaw_it_has(scripted_run) -> None:
    v1, v2, v3, v4 = (set(r.fired) for r in scripted_run)
    assert {"digit_pref", "inlier"} <= v1  # rounded readings; patients bunched at the center
    for v in (v2, v3, v4):
        assert "digit_pref" not in v and "variance" not in v
        assert {"corr_struct", "autocorr"} <= v


def test_round_records_everything(scripted_run, suite) -> None:
    r = scripted_run[-1]
    assert r.ok and r.n_patients == 40 and r.threshold == suite.threshold
    assert set(r.scores.per_check) == {c.name for c in CORE_CHECKS}
    assert r.attacker_kind == "scripted" and r.attacker_model == "scripted-v4"
    assert r.claimed_arms == {"drug": 20, "placebo": 20}
    assert r.damage["fake_patients_analyzed"] > 0
    assert r.damage["effect_with_fake"] < r.damage["effect_real"]  # the scripted fake claims a big drug effect


def test_run_is_saved_and_labeled_not_a_result(scripted_run, suite) -> None:
    run = load_run("fd_test_scripted")
    assert run["not_a_result"] is True and "TEMPORARY" in run["label"]
    assert run["suite"]["standin"] is False and run["suite"]["threshold"] == suite.threshold
    assert run["suite"]["name"] == "sentinel" and run["suite"]["version"] == 0
    assert [r["escaped"] for r in run["rounds"]] == [False] * 4
    assert all(r["code"] for r in run["rounds"])
    assert all(r["fake_output"]["patients"] and r["input_seed"] is not None for r in run["rounds"])  # Patch trains on these


def test_feedback_carries_scores_and_previous_code(trial, suite, real_sites) -> None:
    attacker = RecordingAttacker()
    fake_data_loop(trial, suite, attacker, 2, runner=TrustedScriptedRunner(), real_sites=real_sites, save=False)
    first, second = attacker.feedback_seen
    assert first is None
    assert second["result"] == "detected" and "digit_pref" in second["checks_fired"]
    assert second["threshold"] == suite.threshold and second["previous_code"] == scripted_source(1)


def test_feedback_explains_each_fired_check_with_real_site_ranges(trial, suite, real_sites) -> None:
    attacker = RecordingAttacker()
    fake_data_loop(trial, suite, attacker, 3, runner=TrustedScriptedRunner(), real_sites=real_sites, save=False)
    v2_feedback = attacker.feedback_seen[2]  # feedback on scripted v2: SBP and DBP drawn independently
    why = {d["check"]: d for d in v2_feedback["why_checks_fired"]}
    assert set(why) == set(v2_feedback["checks_fired"]) and "corr_struct" in why
    assert all(d["measures"] for d in why.values()), "every Sentinel core check has an explanation"
    sbp_dbp = next(m for m in why["corr_struct"]["measures"] if "SBP and mean DBP" in m["measure"])
    lo, hi = sbp_dbp["real_sites_typical"]
    assert sbp_dbp["your_site"] < lo < hi and sbp_dbp["position"] == "below"
    assert f"on your site: {sbp_dbp['your_site']}, real sites: " in why["corr_struct"]["summary"]
    assert not re.search(r"\bP\d{4}\b|\bS\d{2}\b", json.dumps(v2_feedback["why_checks_fired"])), "aggregates only, no ids"

    msg = build_user_message(public_context(trial), v2_feedback)
    assert "WHY EACH CHECK FIRED" in msg and why["corr_struct"]["summary"] in msg
    assert "targeted edits" in msg and v2_feedback["previous_code"] in msg


def test_sandbox_error_and_timeout_are_rounds_with_feedback(trial, suite, real_sites) -> None:
    for stderr in ("Traceback ...\nNameError: name 'x' is not defined", "TIMEOUT: killed after 60s"):
        attacker = RecordingAttacker()
        runner = FixedRunner(SandboxResult(False, "", stderr, None, "dt_err", 1.0))
        rounds = fake_data_loop(trial, suite, attacker, 2, runner=runner, real_sites=real_sites, save=False)
        assert [r.status for r in rounds] == ["error", "error"]
        assert attacker.feedback_seen[1]["result"] == "error" and stderr.splitlines()[-1] in attacker.feedback_seen[1]["error"]


def test_schema_error_is_fed_back_verbatim(trial, suite, real_sites) -> None:
    attacker = RecordingAttacker()
    runner = FixedRunner(SandboxResult(True, "", "", {"patients": []}, "dt_bad", 1.0))
    rounds = fake_data_loop(trial, suite, attacker, 2, runner=runner, real_sites=real_sites, save=False)
    assert rounds[0].status == "error" and rounds[0].error.startswith("schema: missing tables")
    assert attacker.feedback_seen[1]["error"] == rounds[0].error


def test_local_mock_runner_never_executes_and_tiny_site_is_detected(trial, suite, real_sites) -> None:
    rounds = fake_data_loop(trial, suite, ScriptedAttacker(), 1, runner=LocalMockRunner(), real_sites=real_sites, save=False)
    assert rounds[0].ok and rounds[0].status == "detected"


def test_attacker_exception_counts_as_a_round(trial, suite, real_sites) -> None:
    class Broken(ScriptedAttacker):
        def write_fake_site_code(self, context, feedback):
            raise RuntimeError("model declined")

    rounds = fake_data_loop(trial, suite, Broken(), 2, runner=LocalMockRunner(), real_sites=real_sites, save=False)
    assert [r.status for r in rounds] == ["error", "error"] and "model declined" in rounds[0].error


# ---------------------------------------------------------------- Sentinel, context, validation


def test_sentinel_false_alarms_on_demo_trial(suite, real_sites) -> None:
    assert suite.false_alarm_rate(real_sites) <= 0.05  # frozen v0 flags 1 of 20 real sites (S14)


def test_escape_path(trial, real_sites) -> None:
    """A fake under the threshold escapes with nothing fired (permissive test-only threshold)."""
    lax = CheckSuite(checks=[c() for c in CORE_CHECKS], threshold=SCORE_CLIP + 1)
    attacker = RecordingAttacker()
    rounds = fake_data_loop(trial, lax, attacker, 2, runner=TrustedScriptedRunner(), real_sites=real_sites, save=False)
    assert [r.status for r in rounds] == ["escaped", "escaped"] and rounds[0].fired == []
    assert attacker.feedback_seen[1]["result"] == "escaped" and attacker.feedback_seen[1]["checks_fired"] == []


def test_context_is_aggregate_only(trial) -> None:
    ctx = public_context(trial)
    text = json.dumps(ctx)
    assert not re.search(r"\bP\d{4}\b", text), "no patient ids"
    assert not re.search(r"\bV\d{4}-", text), "no visit ids"
    assert set(ctx) == {"protocol", "your_site", "schema", "aggregate_stats", "rates"}
    for section in ("aggregate_stats", "rates"):
        assert not re.search(r"drug|placebo|arm", json.dumps(ctx[section]).replace("drug_class", "")), section


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda o: o.pop("kit_storage"), "missing tables ['kit_storage']"),
        (lambda o: [v.pop("dbp") for v in o["vitals"]], "table 'vitals': missing columns ['dbp']"),
        (lambda o: o["patients"][0].update(site_id="S01"), "patients.site_id must be 'S21'"),
        (lambda o: o["labs"][0].update(visit_id="V0000-BL"), "table 'labs': visit_id not in visits ['V0000-BL']"),
        (lambda o: o["visits"][0].update(visit_name="Week 99"), "column 'visit_name': invalid values ['Week 99']"),
    ],
)
def test_validation_names_the_exact_problem(trial, mutate, message) -> None:
    ns: dict = {}
    exec(scripted_source(4), ns)
    output = ns["generate_site"](public_context(trial) | {"seed": 1})
    validate_schema(output, "S21")
    mutate(output)
    with pytest.raises(SchemaError, match=re.escape(message)):
        validate_schema(output, "S21")


# ---------------------------------------------------------------- attackers


def test_make_attacker_without_keys_is_scripted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert make_attacker("training").kind == "scripted"
    with pytest.raises(RuntimeError, match="needs a key"):
        make_attacker("training", kind="llm")


def test_make_attacker_with_key_is_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("TRAINING_ATTACKER_MODEL", "claude-opus-5-5")
    a = make_attacker("training")
    assert a.kind == "llm" and a.model == "claude-opus-5-5" and a.system_prompt_path.name == "training_attacker.md"


def test_llm_attacker_sends_context_and_feedback(trial, tmp_path) -> None:
    prompt = tmp_path / "p.md"
    prompt.write_text("system prompt")
    llm = LocalMockLLM()
    a = Attacker("training", "mock-model", prompt, seed=1, llm=llm)
    code = a.write_fake_site_code(public_context(trial), {"result": "detected", "checks_fired": ["variance"], "previous_code": "x = 1\n"})
    assert "def generate_site" in code and a.last_call.model == "mock-model"
    msg = build_user_message(public_context(trial), {"result": "detected", "checks_fired": ["variance"], "previous_code": "x = 1\n"})
    assert "FEEDBACK FROM LAST ROUND" in msg and "variance" in msg and "x = 1" in msg


def test_extract_code_strips_fences() -> None:
    assert extract_code("Here:\n```python\ndef generate_site(c):\n    return {}\n```\nDone") == "def generate_site(c):\n    return {}\n"
    assert extract_code("def generate_site(c): ...") == "def generate_site(c): ...\n"


# ---------------------------------------------------------------- cached replay through the API


def test_cached_mode_replays_saved_run_in_mock_event_shape(scripted_run, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.main import app
    from backend.mocks import load_mock

    monkeypatch.setenv("DEMO_MODE", "cached")
    monkeypatch.setenv("CACHED_REPLAY_SPEED", "0")
    client = TestClient(app)
    run = client.post("/fake-data/runs", json={"trial_id": "tr_2026_B"}).json()
    assert run["run_id"].startswith("fd_") and run["_mock"] is True and run["status"] == "done"

    with client.stream("GET", f"/fake-data/runs/{run['run_id']}/stream") as r:
        body = "".join(r.iter_text())
    rounds = [json.loads(line[5:]) for line in body.splitlines() if line.startswith("data:") and '"round"' in line]
    assert len(rounds) == len(load_run(run["run_id"])["rounds"])
    assert set(rounds[0]) == set(load_mock("fake_data_rounds")[0])
    assert [r["escaped"] for r in rounds] == [r["escaped"] for r in load_run(run["run_id"])["rounds"]]
    assert all(r["_mock"] for r in rounds)


def test_cached_mode_404_for_unknown_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.main import app

    monkeypatch.setenv("DEMO_MODE", "cached")
    assert TestClient(app).get("/fake-data/runs/fd_does_not_exist/stream").status_code == 404


def test_cached_run_detail_and_round_code(scripted_run, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.main import app

    monkeypatch.setenv("DEMO_MODE", "cached")
    monkeypatch.setenv("CACHED_REPLAY_SPEED", "0")
    client = TestClient(app)
    run_id = client.post("/fake-data/runs", json={"trial_id": "tr_2026_B"}).json()["run_id"]
    saved = load_run(run_id)
    detail = client.get(f"/fake-data/runs/{run_id}").json()
    assert detail["run_id"] == run_id and detail["_mock"] is saved["not_a_result"]
    assert detail["rounds_done"] == len(saved["rounds"]) and detail["threshold"] == saved["suite"]["threshold"]
    with client.stream("GET", f"/fake-data/runs/{run_id}/stream") as r:
        body = "".join(r.iter_text())
    rounds = [json.loads(line[5:]) for line in body.splitlines() if line.startswith("data:") and '"round"' in line]
    assert [r["code"] for r in rounds] == [r["code"] for r in saved["rounds"]]
    assert [r["fired"] for r in rounds] == [r["fired"] for r in saved["rounds"]]


def test_cached_mode_serves_fixtures_for_uncached_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.main import app

    monkeypatch.setenv("DEMO_MODE", "cached")
    r = TestClient(app).post("/test-attacker/eval", json={"trial_id": "tr_2026_B"})
    assert r.status_code == 200 and r.json()["_mock"] is True
