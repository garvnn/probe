"""Where Tell's feature matrix comes from: Chalk when switched on, else built inline. Owner: Shreyas.

TELL_FEATURES=chalk   read features from Chalk (offline query against the branch in CHALK_TELL_BRANCH,
                      authenticated by the Chalk CLI login or CHALK_CLIENT_ID / CHALK_CLIENT_SECRET)
anything else         build_features(view_df) inline, exactly as before (the default)

Chalk is opt-in by an explicit switch, not by "credentials exist", so tests and the control test never
call out to Chalk by accident. Either way the arm label is never sent: it stays local, from ground_truth.
"""

from __future__ import annotations

import os

import pandas as pd

from engine.blind_leak.features import build_features

OWNER = "Shreyas"


def chalk_enabled() -> bool:
    return os.environ.get("TELL_FEATURES", "local").split("#")[0].strip().lower() == "chalk"


def tell_features(view_df: pd.DataFrame) -> pd.DataFrame:
    """The patient x feature matrix run_blind classifies, same columns and values from either source."""
    return chalk_features(view_df) if chalk_enabled() else build_features(view_df)


def chalk_features(view_df: pd.DataFrame, branch: str | None = None, client=None) -> pd.DataFrame:
    """Send each patient's view rows to Chalk, get per-patient vectors back, assemble locally."""
    import json

    from tell_chalk.vector import assemble, rows_to_json

    groups = list(view_df.groupby("patient_id", sort=True))
    ids = [pid for pid, _ in groups]
    sites = {pid: rows["site_id"].iloc[0] for pid, rows in groups}
    if client is None:
        from chalk.client import ChalkClient

        client = ChalkClient(branch=branch or os.environ.get("CHALK_TELL_BRANCH") or None)
    dataset = client.offline_query(
        input={"patient.id": ids, "patient.site_id": [sites[p] for p in ids], "patient.view_rows": [rows_to_json(r) for _, r in groups]},
        output=["patient.id", "patient.tell_vector"],
        recompute_features=True,
    )
    df = dataset.get_data_as_pandas()
    id_col = next(c for c in df.columns if c.endswith("patient.id") or c == "id")
    vec_col = next(c for c in df.columns if c.endswith("tell_vector"))
    vectors = {pid: json.loads(v) for pid, v in zip(df[id_col], df[vec_col])}
    missing = set(ids) - set(vectors)
    if missing:
        raise RuntimeError(f"Chalk returned no tell_vector for {len(missing)} patients, e.g. {sorted(missing)[:3]}")
    return assemble(vectors, sites)
