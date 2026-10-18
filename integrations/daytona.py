"""Sandboxed execution for all LLM-written code (attacker fake-site code, Droid checks). Owner: Shreyas.

Rule: no LLM-written code ever runs on a laptop. Every execution goes through a SandboxRunner.
"""

from __future__ import annotations

import base64
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Protocol

OWNER = "Shreyas"


@dataclass
class SandboxResult:
    """Result of one sandboxed run.

    Attributes:
        ok: True if the code ran to completion and produced output.
        stdout: Captured stdout.
        stderr: Captured stderr (the tail is fed back to the attacker on failure).
        output: Parsed return value of `generate_site(context)`, or None on failure.
        sandbox_id: Sandbox identifier, shown in the UI strip.
        runtime_s: Seconds spent executing the code (excludes sandbox create/teardown).
        timings: Phase breakdown when available: create_s, exec_s, teardown_s, total_s.
    """

    ok: bool
    stdout: str
    stderr: str
    output: dict | None
    sandbox_id: str
    runtime_s: float
    timings: dict[str, float] = field(default_factory=dict)


class SandboxRunner(Protocol):
    def run(self, code: str, inputs: dict, timeout: int = 60) -> SandboxResult:
        """Execute `code` in isolation, call `generate_site(inputs)`, return its output."""
        ...


class DaytonaRunner:
    """Real runner backed by Daytona sandboxes.

    Modes:
        reuse=False (default): a fresh sandbox per run, deleted right after. Strongest isolation.
        reuse=True: one sandbox for every run until close(). Faster; rounds share a filesystem.

    Use as a context manager (or call close()) so a reused sandbox is always deleted.
    Sandboxes are created with no network access, a label for cleanup sweeps, and
    ephemeral + auto-stop, so a crashed process can't leave one running for long.

    Forking (sandbox.fork) is only supported for Linux VM sandboxes, not the default container
    class; see scripts/daytona_benchmark.py for the measured status.
    """

    LABELS = {"app": "probe", "component": "integrations.daytona"}
    CREATE_ATTEMPTS = 2
    """Sandbox creation is tried twice (one retry) before the round is recorded as an error."""
    create_retry_delay_s: float = 2.0

    def __init__(
        self,
        api_key: str | None = None,
        *,
        reuse: bool = False,
        snapshot: str | None = None,
        target: str | None = None,
        auto_stop_minutes: int = 5,
    ) -> None:
        from daytona import Daytona, DaytonaConfig

        self.api_key = api_key or os.environ.get("DAYTONA_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("DAYTONA_API_KEY is not set (put it in .env)")
        self.reuse = reuse
        self.snapshot = snapshot
        self.auto_stop_minutes = auto_stop_minutes
        self.client = Daytona(DaytonaConfig(api_key=self.api_key, target=target))
        self._sandbox = None

    # ------------------------------------------------------------- lifecycle

    def create_sandbox(self):
        """Create one locked-down sandbox. Callers own deleting it."""
        from daytona import CreateSandboxFromSnapshotParams

        params = CreateSandboxFromSnapshotParams(
            language="python",
            snapshot=self.snapshot,
            labels=self.LABELS,
            network_block_all=True,
            ephemeral=True,
            auto_stop_interval=self.auto_stop_minutes,
        )
        return self.client.create(params)

    def delete_sandbox(self, sandbox) -> None:
        self.client.delete(sandbox)

    def close(self) -> None:
        """Delete the reused sandbox, if any. Safe to call twice."""
        if self._sandbox is not None:
            sandbox, self._sandbox = self._sandbox, None
            self.delete_sandbox(sandbox)

    def __enter__(self) -> DaytonaRunner:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------- execution

    def run(self, code: str, inputs: dict, timeout: int = 60) -> SandboxResult:
        """Run `code` in a sandbox, call `generate_site(inputs)`, and return its output.

        The timeout is enforced inside the sandbox with `timeout -s KILL`, so a runaway
        generator is killed there; the SDK call gets a few extra seconds of slack.
        """
        timings: dict[str, float] = {"create_s": 0.0, "exec_s": 0.0, "teardown_s": 0.0}
        t0 = time.perf_counter()
        sandbox = self._sandbox
        if sandbox is None:
            sandbox, create_error = self._create_with_retry()
            timings["create_s"] = time.perf_counter() - t0
            if sandbox is None:
                timings["total_s"] = time.perf_counter() - t0
                return SandboxResult(False, "", create_error, None, "", 0.0, timings)
            if self.reuse:
                self._sandbox = sandbox
        try:
            t1 = time.perf_counter()
            result = execute_in_sandbox(sandbox, code, inputs, timeout)
            timings["exec_s"] = time.perf_counter() - t1
        finally:
            if not self.reuse:
                t2 = time.perf_counter()
                try:
                    self.delete_sandbox(sandbox)
                except Exception as e:  # ephemeral + auto-stop: an undeleted sandbox still expires on its own
                    timings["teardown_error"] = f"{type(e).__name__}: {e}"[:300]
                timings["teardown_s"] = time.perf_counter() - t2
        timings["total_s"] = time.perf_counter() - t0
        result.runtime_s = timings["exec_s"]
        result.timings = timings
        return result

    def _create_with_retry(self):
        """(sandbox, None) on success, or (None, error message) after CREATE_ATTEMPTS failures.

        A Daytona outage or timeout must become one error round, never a crash of the whole loop.
        The message says plainly that it is infrastructure, not the attacker's code.
        """
        errors = []
        for attempt in range(1, self.CREATE_ATTEMPTS + 1):
            try:
                return self.create_sandbox(), None
            except Exception as e:
                errors.append(f"attempt {attempt}: {type(e).__name__}: {str(e)[:300]}")
                if attempt < self.CREATE_ATTEMPTS:
                    time.sleep(self.create_retry_delay_s)
        return None, (
            f"SANDBOX_CREATE_FAILED: infrastructure error, not caused by your code; resubmit it unchanged. "
            f"({'; '.join(errors)})"
        )

    def fork(self, sandbox_id: str) -> str:
        """Fork a running sandbox (filesystem + memory) and return the new sandbox's id.

        Only Linux VM sandboxes support this; container sandboxes raise.
        """
        return self.client.get(sandbox_id).fork().id


RESULT_SENTINEL = "__PROBE_RESULT__"
TIMEOUT_EXIT_CODES = (124, 137)

HARNESS = '''\
import base64, json, sys, traceback

SENTINEL = {sentinel!r}


def _default(o):
    if hasattr(o, "item"):
        return o.item()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    if hasattr(o, "tolist"):
        return o.tolist()
    raise TypeError(f"not JSON serializable: {{type(o).__name__}}")


def _main():
    code = base64.b64decode({code_b64!r}).decode()
    context = json.loads(base64.b64decode({inputs_b64!r}))
    ns = {{"__name__": "attacker"}}
    try:
        exec(compile(code, "attacker.py", "exec"), ns)
        fn = ns.get("generate_site")
        if not callable(fn):
            raise NameError("generate_site(context) is not defined")
        out = fn(context)
        if not isinstance(out, dict):
            raise TypeError(f"generate_site must return dict, got {{type(out).__name__}}")
        payload = {{"ok": True, "output": out}}
    except BaseException:
        payload = {{"ok": False, "error": traceback.format_exc(limit=8)}}
    sys.stdout.flush()
    sys.stdout.write("\\n" + SENTINEL + json.dumps(payload, default=_default) + "\\n")


_main()
'''


def build_command(code: str, inputs: dict, timeout: int, nonce: str) -> str:
    """One shell command: write the harness (code + inputs embedded as base64) and run it under `timeout`."""
    harness = HARNESS.format(
        sentinel=f"{RESULT_SENTINEL}{nonce}:",
        code_b64=base64.b64encode(code.encode()).decode(),
        inputs_b64=base64.b64encode(json.dumps(inputs).encode()).decode(),
    )
    harness_b64 = base64.b64encode(harness.encode()).decode()
    path = f"/tmp/probe_run_{nonce}.py"
    return f"printf %s '{harness_b64}' | base64 -d > {path} && timeout -s KILL {int(timeout)} python3 {path}; rc=$?; rm -f {path}; exit $rc"


def parse_result(raw: str, exit_code: int, nonce: str, timeout: int, sandbox_id: str) -> SandboxResult:
    """Turn the harness's stdout into a SandboxResult. Attacker prints come back as stdout."""
    marker = f"{RESULT_SENTINEL}{nonce}:"
    before, sep, after = raw.rpartition(marker)
    if exit_code in TIMEOUT_EXIT_CODES and not sep:
        return SandboxResult(False, raw, f"TIMEOUT: killed after {timeout}s", None, sandbox_id, 0.0)
    if not sep:
        return SandboxResult(False, raw, f"harness produced no result (exit {exit_code})", None, sandbox_id, 0.0)
    try:
        payload = json.loads(after.strip().splitlines()[0])
    except (json.JSONDecodeError, IndexError) as e:
        return SandboxResult(False, before, f"unparseable result: {e}", None, sandbox_id, 0.0)
    if payload.get("ok"):
        return SandboxResult(True, before, "", payload["output"], sandbox_id, 0.0)
    return SandboxResult(False, before, payload.get("error", "unknown error"), None, sandbox_id, 0.0)


def execute_in_sandbox(sandbox, code: str, inputs: dict, timeout: int) -> SandboxResult:
    nonce = uuid.uuid4().hex[:12]
    command = build_command(code, inputs, timeout, nonce)
    try:
        resp = sandbox.process.exec(command, timeout=int(timeout) + 15)
    except Exception as e:  # SDK-side timeout or transport error
        msg = f"{type(e).__name__}: {e}"
        kind = "TIMEOUT" if "timeout" in msg.lower() else "SANDBOX_ERROR"
        return SandboxResult(False, "", f"{kind}: {msg}", None, sandbox.id, 0.0)
    return parse_result(resp.result or "", resp.exit_code, nonce, timeout, sandbox.id)


CANNED_FAKE_SITE: dict[str, list[dict]] = {
    "patients": [
        {"patient_id": "P9901", "site_id": "S21", "age": 58, "sex": "F", "bmi": 31.2, "baseline_hba1c": 8.4},
        {"patient_id": "P9902", "site_id": "S21", "age": 63, "sex": "M", "bmi": 29.8, "baseline_hba1c": 8.1},
    ],
    "visits": [
        {"visit_id": "V9901-BL", "patient_id": "P9901", "visit_name": "Baseline", "date": "2026-03-12", "scheduled": True},
        {"visit_id": "V9902-BL", "patient_id": "P9902", "visit_name": "Baseline", "date": "2026-03-13", "scheduled": True},
    ],
    "labs": [
        {"lab_id": "LM00001", "visit_id": "V9901-BL", "test": "hba1c", "value": 8.4, "source": "central", "draw_time": "08:15"},
        {"lab_id": "LM00002", "visit_id": "V9902-BL", "test": "hba1c", "value": 8.1, "source": "central", "draw_time": "09:40"},
    ],
    "vitals": [
        {"visit_id": "V9901-BL", "sbp": 131, "dbp": 79, "weight": 84.2},
        {"visit_id": "V9902-BL", "sbp": 138, "dbp": 86, "weight": 92.7},
    ],
    "adverse_events": [],
    "conmeds": [],
    "dispensing": [],
    "kit_storage": [],
}
"""Mock fake site for wiring and tests. Not a measured or generated result."""


class LocalMockRunner:
    """Returns a canned fake site. It never executes `code`, so it's safe for local development."""

    def __init__(self) -> None:
        self._n = 0

    def run(self, code: str, inputs: dict, timeout: int = 60) -> SandboxResult:
        self._n += 1
        return SandboxResult(
            ok=True,
            stdout="",
            stderr="",
            output=CANNED_FAKE_SITE,
            sandbox_id=f"mock_{self._n:03d}",
            runtime_s=0.0,
        )
