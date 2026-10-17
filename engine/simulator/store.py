"""SQLite persistence for generated trials. Owner: Garv.

Every table is stored with an extra `trial_id` column so one DB holds many trials. Ground truth and
hidden tables (protocol-variant rows only a remedy may reveal) are stored here too, but only
`evals.ground_truth` and `engine.simulator.views` read them.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

from engine.simulator.schema import GROUND_TRUTH_SCHEMA, SCHEMA, ColumnType, coerce

GROUND_TRUTH_TABLE = "ground_truth"
HIDDEN_TABLES: dict[str, dict[str, ColumnType]] = {
    "sham_dispensing": SCHEMA["dispensing"],
}
"""Hidden table -> columns. `sham_dispensing` holds the placebo-arm events the sham_titration remedy adds."""


def db_path() -> Path:
    """The DB file, from $DB_PATH (read per call so tests can point it at a temp dir)."""
    return Path(os.environ.get("DB_PATH", "data/probe.db").split("#")[0].strip())


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None


def _write(conn: sqlite3.Connection, name: str, trial_id: str, df: pd.DataFrame) -> None:
    if _table_exists(conn, name):
        conn.execute(f'DELETE FROM "{name}" WHERE trial_id = ?', (trial_id,))
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    if "trial_id" not in out.columns:  # sites already carries it
        out.insert(0, "trial_id", trial_id)
    out.to_sql(name, conn, if_exists="append", index=False)


def _read(conn: sqlite3.Connection, name: str, trial_id: str, columns: dict[str, ColumnType]) -> pd.DataFrame:
    df = pd.read_sql_query(f'SELECT * FROM "{name}" WHERE trial_id = ?', conn, params=(trial_id,))
    if "trial_id" in columns:
        return coerce(columns, df)
    return coerce(columns, df.drop(columns="trial_id"))


def save_trial(
    trial_id: str,
    config: dict,
    tables: dict[str, pd.DataFrame],
    ground_truth: pd.DataFrame,
    hidden: dict[str, pd.DataFrame],
) -> None:
    """Write (or overwrite) one trial: its config, tables, ground truth, and hidden tables."""
    with closing(_connect()) as conn, conn:
        conn.execute("CREATE TABLE IF NOT EXISTS trials (trial_id TEXT PRIMARY KEY, config_json TEXT, created_at TEXT)")
        conn.execute(
            "INSERT OR REPLACE INTO trials VALUES (?, ?, datetime('now'))",
            (trial_id, json.dumps(config, sort_keys=True)),
        )
        for name, df in tables.items():
            _write(conn, name, trial_id, df)
        _write(conn, GROUND_TRUTH_TABLE, trial_id, ground_truth)
        for name, df in hidden.items():
            _write(conn, name, trial_id, df)


def load_config(trial_id: str) -> dict:
    """The config dict a trial was generated with. Raises KeyError if the trial isn't in the DB."""
    with closing(_connect()) as conn:
        row = None
        if _table_exists(conn, "trials"):
            row = conn.execute("SELECT config_json FROM trials WHERE trial_id = ?", (trial_id,)).fetchone()
    if row is None:
        raise KeyError(f"unknown trial_id {trial_id!r} in {db_path()}; run generate_trial first")
    return json.loads(row[0])


def load_tables(trial_id: str) -> dict[str, pd.DataFrame]:
    """Every table in SCHEMA for `trial_id`."""
    load_config(trial_id)
    with closing(_connect()) as conn:
        return {name: _read(conn, name, trial_id, cols) for name, cols in SCHEMA.items()}


def load_ground_truth(trial_id: str) -> pd.DataFrame:
    """The locked arm table. Only evals.ground_truth may call this."""
    load_config(trial_id)
    with closing(_connect()) as conn:
        return _read(conn, GROUND_TRUTH_TABLE, trial_id, GROUND_TRUTH_SCHEMA)


def load_hidden(trial_id: str, name: str) -> pd.DataFrame:
    """A hidden table. Only engine.simulator.views may call this, to apply a remedy."""
    load_config(trial_id)
    with closing(_connect()) as conn:
        return _read(conn, name, trial_id, HIDDEN_TABLES[name])
