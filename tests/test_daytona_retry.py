"""DaytonaRunner create/teardown failures, offline: a fake client, no key, no network."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.fake_data.loop import fake_data_loop
from engine.fake_data.scripted import ScriptedAttacker
from engine.fake_data.sites import split_sites
from engine.fraud_checks.suite import load_suite
from engine.simulator.mechanisms import DEFAULT_MECHANISMS
from engine.simulator.trial import TrialConfig, generate_trial
from integrations import daytona as dt


class FakeClient:
    """Stands in for daytona.Daytona: create fails `fail_creates` times, then returns a sandbox."""

    def __init__(self, fail_creates: int = 0, fail_delete: bool = False) -> None:
        self.fail_creates, self.fail_delete = fail_creates, fail_delete
        self.creates = self.deletes = 0

    def create(self, params):
        self.creates += 1
        if self.creates <= self.fail_creates:
            raise TimeoutError("Read timed out. (read timeout=60)")
        return SimpleNamespace(id=f"sb_{self.creates}")

    def delete(self, sandbox):
        self.deletes += 1
        if self.fail_delete:
            raise ConnectionError("delete failed")


def runner_with(client: FakeClient) -> dt.DaytonaRunner:
    r = dt.DaytonaRunner.__new__(dt.DaytonaRunner)  # skip __init__: no key, no SDK client
    r.api_key, r.reuse, r.snapshot, r.auto_stop_minutes, r._sandbox = "test", False, None, 5, None
    r.client, r.create_retry_delay_s = client, 0.0
    r.create_sandbox = lambda: client.create(None)
    return r


@pytest.fixture
def ok_exec(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dt, "execute_in_sandbox", lambda sb, code, inputs, timeout: dt.SandboxResult(True, "", "", {"x": 1}, sb.id, 0.0))


def test_create_retries_once_then_succeeds(ok_exec) -> None:
    client = FakeClient(fail_creates=1)
    result = runner_with(client).run("code", {})
    assert result.ok and result.sandbox_id == "sb_2" and client.creates == 2 and client.deletes == 1


def test_create_failing_twice_is_an_error_result_not_an_exception(ok_exec) -> None:
    client = FakeClient(fail_creates=5)
    result = runner_with(client).run("code", {})
    assert not result.ok and result.output is None and client.creates == 2 and client.deletes == 0
    assert result.stderr.startswith("SANDBOX_CREATE_FAILED: infrastructure error, not caused by your code")
    assert "attempt 1: TimeoutError" in result.stderr and "attempt 2: TimeoutError" in result.stderr


def test_teardown_failure_does_not_lose_the_result(ok_exec) -> None:
    result = runner_with(FakeClient(fail_delete=True)).run("code", {})
    assert result.ok and result.output == {"x": 1} and "ConnectionError" in result.timings["teardown_error"]


def test_loop_records_create_failure_as_an_error_round_and_continues(tmp_path, monkeypatch: pytest.MonkeyPatch, ok_exec) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "probe.db"))
    trial = generate_trial(TrialConfig(scenario="B", mechanisms=DEFAULT_MECHANISMS))
    rounds = fake_data_loop(
        trial, load_suite(0), ScriptedAttacker(), 2, runner=runner_with(FakeClient(fail_creates=99)),
        real_sites=split_sites(trial), save=False,
    )
    assert [r.status for r in rounds] == ["error", "error"]
    assert all(r.error.startswith("SANDBOX_CREATE_FAILED") for r in rounds)
