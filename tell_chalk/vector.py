"""Tell's feature matrix split into a per-patient half (runs in Chalk) and a cross-patient half (local).

`engine.blind_leak.features.build_features` mixes two kinds of work:

* per-patient transforms: row counts, timing, gaps, numeric summaries, slopes, draw hours;
* cross-patient decisions: a count column exists only if MIN_SUPPORT patients have that value, category
  counts exist only if some patient in that source has a category, constant columns are dropped.

A Chalk resolver sees one patient, so `patient_vector` computes every per-patient value for one
patient's view rows (reusing features.py's own helpers), keyed so that `assemble` can apply the
cross-patient decisions and reproduce build_features' exact columns, order, and values.
`tests/test_tell_chalk.py` checks assemble(...) == build_features(...) on real and synthetic views.

Inputs are export_view() rows only. No arm label is ever an input or an output here.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from engine.blind_leak import features as F
from engine.blind_leak.contract import VIEW_COLUMNS, field_group

# Ranks that order a source's columns exactly as features._source_features emits them.
ROWS, KIND, CAT, KINDCAT, DAY, GAP, NUMERIC, DRAW = range(8)
NUMERIC_STATS = ("mean", "std", "first", "change", "slope")
CATEGORY_FLAG = "__has_category__"


def _plain(x):
    """JSON-safe scalar: numpy -> Python, NaN -> None."""
    if x is None:
        return None
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if math.isnan(float(x)) else float(x)
    return x


def rows_to_json(rows: pd.DataFrame) -> str:
    """One patient's view rows as JSON, the Chalk input. Dates as ISO strings, NaN as null."""
    out = []
    for r in rows[VIEW_COLUMNS].itertuples(index=False):
        rec = dict(zip(VIEW_COLUMNS, r))
        rec["date"] = None if pd.isna(rec["date"]) else pd.Timestamp(rec["date"]).isoformat()
        rec["value"] = _plain(rec["value"])
        for k in ("category", "detail", "kind"):
            rec[k] = None if (rec[k] is None or (isinstance(rec[k], float) and math.isnan(rec[k]))) else str(rec[k])
        out.append(rec)
    return json.dumps(out)


def rows_from_json(text: str) -> pd.DataFrame:
    df = pd.DataFrame(json.loads(text), columns=VIEW_COLUMNS)
    df["value"] = pd.to_numeric(df["value"], errors="coerce").astype(float)
    return df


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    """The same preparation build_features applies to the whole view, on one patient's rows."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["category"] = df["category"].fillna("")
    df["group"] = [field_group(s, c) for s, c in zip(df["source"], df["category"])]
    baseline = F._baseline_dates(df)
    df["day"] = (df["date"] - df["patient_id"].map(baseline)).dt.days
    return df


def patient_vector(rows: pd.DataFrame) -> list[list]:
    """Every per-patient value build_features would compute for this patient, before any cross-patient step.

    Returns entries [order_key, column_name, value]. order_key is a list that sorts into build_features'
    column order; count entries carry the raw value so `assemble` can apply MIN_SUPPORT.
    """
    df = _prepare(rows)
    entries: list[list] = []

    pat = F._patient(df)
    for col in pat.columns:
        v = pat[col].iloc[0] if len(pat) else np.nan
        part = 1 if col.endswith("_any") else 0
        entries.append([[0, part, col], col, _plain(v)])

    for (group, source), g in df.loc[df["source"] != "patient"].groupby(["group", "source"]):
        prefix = f"{group}__{source}" if group == "visits" else group
        base = [1, group, source]
        entries.append([base + [ROWS, ""], f"{prefix}__rows_n", len(g)])
        for k, n in g["kind"].value_counts().items():
            entries.append([base + [KIND, str(k)], f"{prefix}__{F._slug(k)}_n", int(n)])
        if (g["category"] != "").any():
            entries.append([base + [-1, CATEGORY_FLAG], CATEGORY_FLAG, 1])
        for k, n in g["category"].value_counts().items():
            entries.append([base + [CAT, str(k)], f"{prefix}__cat__{F._slug(k)}_n", int(n)])
        for k, n in (g["kind"] + "|" + g["category"]).value_counts().items():
            entries.append([base + [KINDCAT, str(k)], f"{prefix}__kindcat__{F._slug(k)}_n", int(n)])

        # Same grouped pandas calls as features._source_features, so floating-point sums are bit-identical.
        dated = g.loc[g["day"].notna()]
        if not dated.empty:
            t = dated.groupby("patient_id")["day"]
            entries.append([base + [DAY, "0"], f"{prefix}__day_mean", _plain(t.mean().iloc[0])])
            entries.append([base + [DAY, "1"], f"{prefix}__day_min", _plain(t.min().iloc[0])])
            dd = dated.sort_values(["patient_id", "date"])
            gaps = dd.groupby("patient_id")["date"].diff().dt.days
            agg = gaps.groupby(dd["patient_id"]).agg(["mean", "std"]).iloc[0]
            entries.append([base + [GAP, "0"], f"{prefix}__gap_mean", _plain(agg["mean"])])
            entries.append([base + [GAP, "1"], f"{prefix}__gap_std", _plain(agg["std"])])

        numeric = g.loc[g["value"].notna()]
        for k, kg in numeric.groupby(numeric["kind"] + "|" + numeric["category"]):
            block = F._numeric(kg, f"{prefix}__{F._slug(k)}")
            for col in block.columns:
                stat = NUMERIC_STATS.index(col.rsplit("__", 1)[1])
                entries.append([base + [NUMERIC, str(k), stat], col, _plain(block[col].iloc[0])])

        if source == "lab":
            hours = pd.to_datetime(g["detail"], format="%H:%M", errors="coerce")
            h = float((hours.dt.hour + hours.dt.minute / 60).groupby(g["patient_id"]).mean().iloc[0])
            if not math.isnan(h):
                entries.append([base + [DRAW, ""], f"{prefix}__draw_hour_mean", float(h)])
    return entries


def vector_json(rows_json: str) -> str:
    """The Chalk resolver body: one patient's view rows in, that patient's vector out."""
    return json.dumps(patient_vector(rows_from_json(rows_json)))


def assemble(vectors: dict[str, list], sites: dict[str, str]) -> pd.DataFrame:
    """Apply build_features' cross-patient steps to per-patient vectors. Same columns, order, values."""
    count_support: dict[tuple, int] = {}
    has_category: set[tuple] = set()
    for entries in vectors.values():
        for key, col, _ in entries:
            if key[0] == 1 and key[3] == -1:
                has_category.add(tuple(key[1:3]))
            elif key[0] == 1 and key[3] in (KIND, CAT, KINDCAT):
                count_support[tuple(key)] = count_support.get(tuple(key), 0) + 1

    def keep(key: list) -> bool:
        if key[0] != 1:
            return True
        rank = key[3]
        if rank == -1:
            return False
        if rank in (CAT, KINDCAT) and tuple(key[1:3]) not in has_category:
            return False
        if rank in (KIND, CAT, KINDCAT):
            return count_support[tuple(key)] >= F.MIN_SUPPORT
        return True

    columns: dict[tuple, str] = {}
    cells: dict[tuple, dict[str, float]] = {}
    for pid, entries in vectors.items():
        for key, col, value in entries:
            if not keep(key):
                continue
            k = _orderable(key)
            columns[k] = col
            cells.setdefault(k, {})[pid] = np.nan if value is None else value

    index = pd.Index(sorted(vectors), name="patient_id")
    ordered = sorted(columns)
    feats = pd.DataFrame({i: pd.Series(cells[k], dtype=float).reindex(index) for i, k in enumerate(ordered)}, index=index)
    feats.columns = [columns[k] for k in ordered]
    feats = feats.fillna({c: 0.0 for c in feats.columns if c.endswith(("_n", "_any"))})
    feats = feats.loc[:, feats.nunique(dropna=False) > 1]
    feats.insert(0, "site_id", pd.Series(sites).reindex(index))
    return feats.sort_index()


def _orderable(key: list) -> tuple:
    """Sort key: patient block first (numeric columns, then dummies), then sources in groupby order."""
    return tuple((0, x) if isinstance(x, (int, float)) else (1, str(x)) for x in key)
