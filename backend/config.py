"""Runtime config read from the environment (.env via python-dotenv)."""

from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

DemoMode = Literal["mock", "cached", "live"]


def demo_mode() -> DemoMode:
    """mock: serve backend/mocks fixtures. cached: replay data/demo_cache. live: run the engine.

    Read per request so tests and `make mock` can switch it without a restart.
    """
    mode = os.environ.get("DEMO_MODE", "mock").split("#")[0].strip() or "mock"
    if mode not in ("mock", "cached", "live"):
        raise ValueError(f"DEMO_MODE must be mock | cached | live, got {mode!r}")
    return mode  # type: ignore[return-value]


def mock_stream_interval_s() -> float:
    """Delay between mock SSE rounds. 1s for the UI; tests set MOCK_STREAM_INTERVAL_S=0."""
    return float(os.environ.get("MOCK_STREAM_INTERVAL_S", "1.0"))


def cached_replay_speed() -> float:
    """Multiplier on recorded round durations when replaying a cached run. 1.0 = real speed, 0 = instant (tests)."""
    return float(os.environ.get("CACHED_REPLAY_SPEED", "1.0"))
