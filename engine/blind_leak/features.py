"""Patient-level features from a role's view. Owner: Ajay.

Features are generated mechanically from whatever the view contains, the same way for every source:
row counts per kind and per category, numeric summaries per (kind, category), and timing relative to
the patient's Baseline. No feature is picked by hand for a suspected leak. Column names are
`<group>__<description>`, where <group> is the docs/schema.md field group (or `patient`), so
attribution can roll features up to the field that would need a remedy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.blind_leak.contract import field_group

OWNER = "Ajay"

MIN_SUPPORT = 5
"""A kind or category value becomes its own count column only if at least this many patients have it."""


def build_features(view_df: pd.DataFrame) -> pd.DataFrame:
    """One row per patient, indexed by patient_id. Keeps site_id as a column for grouped CV; every other
    column is a numeric feature."""
    df = view_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["category"] = df["category"].fillna("")
    df["group"] = [field_group(s, c) for s, c in zip(df["source"], df["category"])]

    site = df.groupby("patient_id")["site_id"].first()
    out = pd.DataFrame(index=site.index)
    out.index.name = "patient_id"

    baseline = _baseline_dates(df)
    df["day"] = (df["date"] - df["patient_id"].map(baseline)).dt.days

    parts = [_patient(df)]
    for (group, source), g in df.loc[df["source"] != "patient"].groupby(["group", "source"]):
        prefix = f"{group}__{source}" if group == "visits" else group
        parts.append(_source_features(g, prefix))
    feats = out.join(pd.concat(parts, axis=1)) if parts else out
    feats = feats.fillna({c: 0.0 for c in feats.columns if c.endswith(("_n", "_any"))})
    feats = feats.loc[:, feats.nunique(dropna=False) > 1]
    feats.insert(0, "site_id", site)
    return feats.sort_index()


def feature_columns(features: pd.DataFrame) -> list[str]:
    return [c for c in features.columns if c != "site_id"]


def group_of(feature: str) -> str:
    return feature.split("__", 1)[0]


def label_of(feature: str) -> str:
    """Plain-English label built from the column name, for the UI."""
    group, _, rest = feature.partition("__")
    return f"{group.replace('_', ' ')}: {rest.replace('__', ' / ').replace('_', ' ')}"


def _baseline_dates(df: pd.DataFrame) -> pd.Series:
    visits = df.loc[df["source"] == "visit"]
    bl = visits.loc[visits["kind"] == "Baseline"].groupby("patient_id")["date"].min()
    first = df.loc[df["date"].notna()].groupby("patient_id")["date"].min()
    return bl.reindex(first.index).fillna(first)


def _patient(df: pd.DataFrame) -> pd.DataFrame:
    p = df.loc[df["source"] == "patient"]
    num = p.loc[p["value"].notna()].pivot_table(index="patient_id", columns="kind", values="value", aggfunc="first")
    num.columns = [f"patient__{c}" for c in num.columns]
    cat = p.loc[p["category"] != ""]
    dummies = pd.crosstab(cat["patient_id"], cat["kind"] + "_" + cat["category"]).clip(upper=1)
    dummies.columns = [f"patient__{c}_any" for c in dummies.columns]
    return num.join(dummies, how="outer")


def _counts(g: pd.DataFrame, key: pd.Series, prefix: str) -> pd.DataFrame:
    support = g.assign(k=key).groupby("k")["patient_id"].nunique()
    keep = support.index[support >= MIN_SUPPORT]
    sub = g.loc[key.isin(keep)]
    if sub.empty:
        return pd.DataFrame()
    c = pd.crosstab(sub["patient_id"], key.loc[sub.index])
    c.columns = [f"{prefix}__{_slug(k)}_n" for k in c.columns]
    return c


def _source_features(g: pd.DataFrame, prefix: str) -> pd.DataFrame:
    pieces = [g.groupby("patient_id").size().rename(f"{prefix}__rows_n").to_frame()]
    pieces.append(_counts(g, g["kind"], prefix))
    if (g["category"] != "").any():
        pieces.append(_counts(g, g["category"], f"{prefix}__cat"))
        pieces.append(_counts(g, g["kind"] + "|" + g["category"], f"{prefix}__kindcat"))

    dated = g.loc[g["day"].notna()]
    if not dated.empty:
        t = dated.groupby("patient_id")["day"]
        pieces.append(pd.DataFrame({f"{prefix}__day_mean": t.mean(), f"{prefix}__day_min": t.min()}))
        dd = dated.sort_values(["patient_id", "date"])
        gaps = dd.groupby("patient_id")["date"].diff().dt.days
        pieces.append(gaps.groupby(dd["patient_id"]).agg(["mean", "std"]).add_prefix(f"{prefix}__gap_"))

    numeric = g.loc[g["value"].notna()]
    if not numeric.empty:
        for k, kg in numeric.groupby(numeric["kind"] + "|" + numeric["category"]):
            pieces.append(_numeric(kg, f"{prefix}__{_slug(k)}"))

    if g["source"].iloc[0] == "lab":
        hours = pd.to_datetime(g["detail"], format="%H:%M", errors="coerce")
        h = (hours.dt.hour + hours.dt.minute / 60).groupby(g["patient_id"]).mean()
        if h.notna().any():
            pieces.append(h.rename(f"{prefix}__draw_hour_mean").to_frame())
    return pd.concat([p for p in pieces if not p.empty], axis=1)


def _numeric(kg: pd.DataFrame, prefix: str) -> pd.DataFrame:
    kg = kg.sort_values(["patient_id", "date"])
    v = kg.groupby("patient_id")["value"]
    out = pd.DataFrame({f"{prefix}__mean": v.mean(), f"{prefix}__std": v.std(), f"{prefix}__first": v.first()})
    out[f"{prefix}__change"] = v.last() - v.first()
    if kg["day"].notna().any():
        out[f"{prefix}__slope"] = kg.groupby("patient_id")[["day", "value"]].apply(_slope)
    return out


def _slope(g: pd.DataFrame) -> float:
    g = g.dropna()
    if len(g) < 2 or g["day"].nunique() < 2:
        return np.nan
    return float(np.polyfit(g["day"].to_numpy(float), g["value"].to_numpy(float), 1)[0])


def _slug(s: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(s).lower()).strip("_")
