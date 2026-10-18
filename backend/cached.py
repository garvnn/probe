"""Measured response cache. Missing entries remain explicitly badged fixtures."""
from __future__ import annotations

import json
from pathlib import Path

from engine.fake_data.cache import cache_dir


def manifest() -> dict | None:
    path = cache_dir() / "precomputed" / "manifest.json"
    return json.loads(path.read_text()) if path.exists() else None


def load_response(fixture: str, request: dict) -> dict | None:
    index = manifest()
    if index is None:
        return None
    for entry in index["responses"].get(fixture, []):
        if entry["request"] != request:
            continue
        root = (cache_dir() / "precomputed").resolve()
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root):
            raise ValueError("cache response path outside precomputed directory")
        data = json.loads(path.read_text())
        if data.get("_mock") is not False:
            raise ValueError(f"cached response {path.name} is not marked measured")
        return data
    return None


def pinned_run_id(trial_id: str) -> str | None:
    index = manifest()
    return index["run_id"] if index and index["trial_id"] == trial_id else None
