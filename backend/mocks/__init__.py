"""JSON fixtures served when DEMO_MODE=mock. Every payload carries "_mock": true.

These numbers are invented for frontend development. They are not measured results and must
never appear in the pitch, the README, or a screenshot presented as real.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

MOCKS_DIR = Path(__file__).parent


@lru_cache
def _read(name: str) -> str:
    return (MOCKS_DIR / f"{name}.json").read_text()


def load_mock(name: str) -> dict | list:
    """Return a fresh copy of fixture `name` (backend/mocks/<name>.json)."""
    return json.loads(_read(name))
