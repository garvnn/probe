"""In-memory run registry for live mode (fake-data runs, test-attacker evals, blind-leak runs). Owner: Shreyas."""

from __future__ import annotations

from dataclasses import dataclass, field

OWNER = "Shreyas"


@dataclass
class RunRecord:
    run_id: str
    kind: str
    """"fake_data" | "test_attacker" | "blind_leak"."""
    status: str = "queued"
    events: list[dict] = field(default_factory=list)


class RunRegistry:
    """Tracks background runs so SSE endpoints can stream their events."""

    def create(self, kind: str) -> RunRecord:
        raise NotImplementedError(f"owner: {OWNER}")

    def get(self, run_id: str) -> RunRecord:
        raise NotImplementedError(f"owner: {OWNER}")

    def append_event(self, run_id: str, event: dict) -> None:
        raise NotImplementedError(f"owner: {OWNER}")


registry = RunRegistry()
