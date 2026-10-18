"""Saved Tell and Seal results for the cached demo. Owner: Ajay.

Files live next to the saved Impostor runs (data/demo_cache, or $DEMO_CACHE_DIR):
  tell_<trial_id>.json   BlindLeakResultModel shape, `_mock: false`, with the control run under `control`
  seal_<trial_id>.json   CheapestFixResult shape, `_mock: false`
Written by scripts/run_tell.py. data/demo_cache/* is gitignored, so commit these with `git add -f`.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.fake_data.cache import cache_dir

OWNER = "Ajay"


def path(kind: str, trial_id: str) -> Path:
    return cache_dir() / f"{kind}_{trial_id}.json"


def save(kind: str, trial_id: str, payload: dict) -> Path:
    p = path(kind, trial_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2) + "\n")
    return p


def latest(kind: str) -> dict | None:
    """Newest saved `kind` ("tell" | "seal") file, or None."""
    files = sorted(cache_dir().glob(f"{kind}_*.json"), key=lambda f: f.stat().st_mtime)
    return json.loads(files[-1].read_text()) if files else None
