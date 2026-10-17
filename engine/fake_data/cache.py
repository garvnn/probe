"""Saved fake-data runs in data/demo_cache/, for DEMO_MODE=cached replay. Owner: Shreyas.

One JSON file per run: `<run_id>.json`. Written after every round, so a crashed run still replays
the rounds it finished.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

RUN_PREFIX = "fd_"


def cache_dir() -> Path:
    """$DEMO_CACHE_DIR or data/demo_cache (read per call so tests can redirect it)."""
    return Path(os.environ.get("DEMO_CACHE_DIR", "data/demo_cache").split("#")[0].strip())


def run_path(run_id: str) -> Path:
    if not run_id.startswith(RUN_PREFIX) or "/" in run_id or ".." in run_id:
        raise FileNotFoundError(f"not a fake-data run id: {run_id!r}")
    return cache_dir() / f"{run_id}.json"


def save_run(run: dict) -> Path:
    path = run_path(run["run_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(run, indent=2, default=str))
    tmp.replace(path)
    return path


def load_run(run_id: str) -> dict:
    path = run_path(run_id)
    if not path.exists():
        raise FileNotFoundError(f"no saved run {run_id!r} in {cache_dir()}")
    return json.loads(path.read_text())


def latest_run_id(trial_id: str | None = None) -> str | None:
    """Newest saved run, preferring one for `trial_id` if any exist."""
    runs = sorted(cache_dir().glob(f"{RUN_PREFIX}*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if trial_id:
        for p in runs:
            try:
                if json.loads(p.read_text()).get("trial_id") == trial_id:
                    return p.stem
            except json.JSONDecodeError:
                continue
    return runs[0].stem if runs else None
