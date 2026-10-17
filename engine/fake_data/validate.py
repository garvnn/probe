"""Schema validation for attacker output. Owner: Shreyas.

Every SchemaError message is fed back to the attacker verbatim as next round's feedback, so it
names the exact table, column, and rows that are wrong.
"""

from __future__ import annotations

import pandas as pd

from engine.fake_data.sites import PATIENT_KEYED, SITE_TABLES, VISIT_KEYED
from engine.fraud_checks.base import SiteData
from engine.simulator.schema import ALLOWED_VALUES, GROUND_TRUTH_SCHEMA, SCHEMA, coerce

OWNER = "Shreyas"

REQUIRED_NONEMPTY = ("patients", "visits", "labs", "vitals")
OPTIONAL_TABLES = ("ground_truth",)
"""The attacker may say which of its fake patients are on drug; it is never scored by the checks."""
UNIQUE_KEYS = {"patients": "patient_id", "visits": "visit_id", "labs": "lab_id", "adverse_events": "ae_id", "dispensing": "event_id", "kit_storage": "event_id"}
MAX_LISTED = 5


class SchemaError(ValueError):
    """Raised when a fake site doesn't match docs/schema.md. The message is fed back to the attacker verbatim."""


def _few(values) -> str:
    values = sorted({str(v) for v in values})
    more = f" (+{len(values) - MAX_LISTED} more)" if len(values) > MAX_LISTED else ""
    return f"{values[:MAX_LISTED]}{more}"


def _frame(name: str, rows: object, columns: dict[str, str]) -> pd.DataFrame:
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise SchemaError(f"table '{name}' must be a list of row dicts, got {type(rows).__name__}")
    df = pd.DataFrame(rows, columns=None if rows else list(columns))
    missing = [c for c in columns if c not in df.columns]
    extra = [c for c in df.columns if c not in columns]
    if missing:
        raise SchemaError(f"table '{name}': missing columns {missing}; expected exactly {list(columns)}")
    if extra:
        raise SchemaError(f"table '{name}': unexpected columns {extra}; expected exactly {list(columns)}")
    for col, kind in columns.items():
        if kind != "float" and df[col].isna().any():
            bad = df.index[df[col].isna()].tolist()
            raise SchemaError(f"table '{name}' column '{col}' ({kind}): empty values in rows {bad[:MAX_LISTED]}")
    try:
        return coerce(columns, df)
    except (ValueError, TypeError) as e:
        for col, kind in columns.items():
            try:
                coerce({col: kind}, df[[col]])
            except (ValueError, TypeError) as col_err:
                raise SchemaError(f"table '{name}' column '{col}': expected {kind}, could not convert ({col_err})") from None
        raise SchemaError(f"table '{name}': {e}") from None


def validate_schema(output: dict[str, list[dict]], site_id: str) -> SiteData:
    """Check every table and column against docs/schema.md and return the fake site as SiteData.

    Raises SchemaError naming exactly which tables/columns are wrong.
    """
    if not isinstance(output, dict):
        raise SchemaError(f"generate_site must return a dict of table name -> list of row dicts, got {type(output).__name__}")
    missing = [t for t in SITE_TABLES if t not in output]
    extra = [t for t in output if t not in SITE_TABLES and t not in OPTIONAL_TABLES]
    if missing:
        raise SchemaError(f"missing tables {missing}; return all of {list(SITE_TABLES)} (empty lists are fine except {list(REQUIRED_NONEMPTY)})")
    if extra:
        raise SchemaError(f"unexpected tables {extra}; allowed: {list(SITE_TABLES)} plus optional {list(OPTIONAL_TABLES)}")

    tables = {name: _frame(name, output[name], SCHEMA[name]) for name in SITE_TABLES}
    for name in REQUIRED_NONEMPTY:
        if tables[name].empty:
            raise SchemaError(f"table '{name}' is empty; a site needs at least one row")

    wrong_site = set(tables["patients"]["site_id"]) - {site_id}
    if wrong_site:
        raise SchemaError(f"patients.site_id must be '{site_id}' for every row; found {_few(wrong_site)}")

    for name, key in UNIQUE_KEYS.items():
        dupes = tables[name][key][tables[name][key].duplicated()]
        if len(dupes):
            raise SchemaError(f"table '{name}': duplicate {key} values {_few(dupes)}")

    for (name, col), allowed in ALLOWED_VALUES.items():
        if name in tables:
            bad = set(tables[name][col]) - allowed
            if bad:
                raise SchemaError(f"table '{name}' column '{col}': invalid values {_few(bad)}; allowed {sorted(allowed)}")

    pids, vids = set(tables["patients"]["patient_id"]), set(tables["visits"]["visit_id"])
    unknown = set(tables["visits"]["patient_id"]) - pids
    if unknown:
        raise SchemaError(f"table 'visits': patient_id not in patients {_few(unknown)}")
    for name in VISIT_KEYED:
        unknown = set(tables[name]["visit_id"]) - vids
        if unknown:
            raise SchemaError(f"table '{name}': visit_id not in visits {_few(unknown)}")
    for name in PATIENT_KEYED:
        unknown = set(tables[name]["patient_id"]) - pids
        if unknown:
            raise SchemaError(f"table '{name}': patient_id not in patients {_few(unknown)}")

    arms = None
    if "ground_truth" in output:
        arms = fake_arms(output)
        unknown = set(arms.index) - pids
        if unknown:
            raise SchemaError(f"table 'ground_truth': patient_id not in patients {_few(unknown)}")

    return SiteData(site_id=site_id, tables=tables, arms=arms)


def fake_arms(output: dict) -> pd.Series | None:
    """The attacker's claimed arm per fake patient, if it sent a ground_truth table. Never scored."""
    if "ground_truth" not in output:
        return None
    gt = _frame("ground_truth", output["ground_truth"], GROUND_TRUTH_SCHEMA)
    bad = set(gt["arm"]) - ALLOWED_VALUES[("ground_truth", "arm")]
    if bad:
        raise SchemaError(f"table 'ground_truth' column 'arm': invalid values {_few(bad)}; allowed ['drug', 'placebo']")
    return gt.set_index("patient_id")["arm"]
