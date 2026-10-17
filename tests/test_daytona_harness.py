"""Offline tests for the Daytona harness and result parsing. No API key, no network.

The harness only ever runs attacker code inside a sandbox; here it runs our own trivial,
known-safe generators locally to check the wrapper itself.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys

from integrations.daytona import HARNESS, RESULT_SENTINEL, LocalMockRunner, build_command, parse_result

NONCE = "abc123"
OK_CODE = "def generate_site(context):\n    print('hello from attacker')\n    return {'patients': [{'n': context['n']}]}\n"


def _harness(code: str, inputs: dict) -> str:
    return HARNESS.format(
        sentinel=f"{RESULT_SENTINEL}{NONCE}:",
        code_b64=base64.b64encode(code.encode()).decode(),
        inputs_b64=base64.b64encode(json.dumps(inputs).encode()).decode(),
    )


def _run_harness_locally(code: str, inputs: dict) -> tuple[str, int]:
    proc = subprocess.run([sys.executable, "-I", "-c", _harness(code, inputs)], capture_output=True, text=True, timeout=30)
    return proc.stdout, proc.returncode


def test_harness_ok_roundtrip() -> None:
    raw, rc = _run_harness_locally(OK_CODE, {"n": 3})
    r = parse_result(raw, rc, NONCE, 60, "sb1")
    assert r.ok and r.output == {"patients": [{"n": 3}]}
    assert "hello from attacker" in r.stdout


def test_harness_reports_attacker_exception() -> None:
    raw, rc = _run_harness_locally("def generate_site(context):\n    return undefined_name\n", {})
    r = parse_result(raw, rc, NONCE, 60, "sb1")
    assert not r.ok and "NameError" in r.stderr


def test_harness_requires_generate_site() -> None:
    raw, rc = _run_harness_locally("x = 1\n", {})
    r = parse_result(raw, rc, NONCE, 60, "sb1")
    assert not r.ok and "generate_site" in r.stderr


def test_spoofed_sentinel_without_nonce_is_ignored() -> None:
    spoof = 'def generate_site(context):\n    print("__PROBE_RESULT__:" + \'{"ok": true, "output": {"fake": 1}}\')\n    return {"real": 1}\n'
    raw, rc = _run_harness_locally(spoof, {})
    assert parse_result(raw, rc, NONCE, 60, "sb1").output == {"real": 1}


def test_timeout_exit_code_is_clean_timeout() -> None:
    r = parse_result("", 137, NONCE, 5, "sb1")
    assert not r.ok and r.stderr == "TIMEOUT: killed after 5s"


def test_build_command_enforces_timeout_in_sandbox() -> None:
    cmd = build_command(OK_CODE, {"n": 1}, 7, NONCE)
    assert "timeout -s KILL 7 python3" in cmd and "'" not in cmd.split("printf %s '", 1)[1].split("'", 1)[0]


def test_local_mock_runner_needs_no_key() -> None:
    r = LocalMockRunner().run("ignored", {})
    assert r.ok and r.output and "patients" in r.output
