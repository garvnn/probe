"""Sandboxed execution for all LLM-written code (attacker fake-site code, Droid checks). Owner: Shreyas.

Rule: no LLM-written code ever runs on a laptop. Every execution goes through a SandboxRunner.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
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
        runtime_s: Wall-clock runtime in seconds.
    """

    ok: bool
    stdout: str
    stderr: str
    output: dict | None
    sandbox_id: str
    runtime_s: float


class SandboxRunner(Protocol):
    def run(self, code: str, inputs: dict, timeout: int = 60) -> SandboxResult:
        """Execute `code` in isolation, call `generate_site(inputs)`, return its output."""
        ...


class DaytonaRunner:
    """Real runner backed by Daytona sandboxes."""

    # TODO: verify SDK calls + fork/snapshot support with Daytona at the booth

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("DAYTONA_API_KEY", "")

    def run(self, code: str, inputs: dict, timeout: int = 60) -> SandboxResult:
        raise NotImplementedError(f"owner: {OWNER}")

    def fork(self, sandbox_id: str) -> str:
        """Snapshot a sandbox so the same episode can be replayed with and without the defense."""
        raise NotImplementedError(f"owner: {OWNER}")


CANNED_FAKE_SITE: dict[str, list[dict]] = {
    "patients": [
        {"patient_id": "PMOCK01", "site_id": "SFAKE", "age": 58, "sex": "F", "bmi": 31.2, "baseline_hba1c": 8.4},
        {"patient_id": "PMOCK02", "site_id": "SFAKE", "age": 63, "sex": "M", "bmi": 29.8, "baseline_hba1c": 8.1},
    ],
    "visits": [
        {"visit_id": "VMOCK01-W08", "patient_id": "PMOCK01", "visit_name": "Week 8", "date": "2026-03-12", "scheduled": True},
        {"visit_id": "VMOCK02-W08", "patient_id": "PMOCK02", "visit_name": "Week 8", "date": "2026-03-13", "scheduled": True},
    ],
    "labs": [],
    "vitals": [],
    "adverse_events": [],
    "conmeds": [],
    "dispensing": [],
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
