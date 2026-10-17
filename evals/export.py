"""Results export for the report page and Devpost. Owner: Ajay."""

from __future__ import annotations

from pathlib import Path

OWNER = "Ajay"


def export_results(trial_id: str, out_dir: Path = Path("data/demo_cache")) -> Path:
    """Write the metrics table (counts + Wilson 95% intervals) for `trial_id`. Returns the file path."""
    raise NotImplementedError(f"owner: {OWNER}")
