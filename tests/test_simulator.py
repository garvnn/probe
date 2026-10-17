"""Trial Twin: shape, determinism, the arm firewall, role views, and remedies."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from engine.blind_leak.remedies import REMEDIES
from engine.simulator.schema import GROUND_TRUTH_SCHEMA, SCHEMA, VIEW_COLUMNS
from engine.simulator.trial import TABLES, TrialConfig, generate_trial, load_trial
from engine.simulator.views import ROLE_GROUPS, export_view
from evals.ground_truth import ground_truth

ROLES = list(ROLE_GROUPS)


@pytest.fixture(scope="module", autouse=True)
def temp_db(tmp_path_factory: pytest.TempPathFactory):
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DB_PATH", str(tmp_path_factory.mktemp("db") / "probe.db"))
        yield


@pytest.fixture(scope="module")
def trial_a():
    return generate_trial(TrialConfig(scenario="A"))


@pytest.fixture(scope="module")
def trial_b():
    return generate_trial(TrialConfig(scenario="B"))


def _schema_md() -> dict[str, dict[str, str]]:
    """Table -> column -> type, parsed from the per-table sections of docs/schema.md."""
    text = Path("docs/schema.md").read_text()
    out: dict[str, dict[str, str]] = {}
    for section in re.split(r"^## ", text, flags=re.M)[1:]:
        name, body = section.split("\n", 1)
        name = name.strip()
        if name not in SCHEMA and name != "ground_truth":
            continue
        out[name] = dict(re.findall(r"^\| (\w+) \| (str|int|float|bool|date) \|", body, flags=re.M))
    return out


def test_schema_md_matches_code() -> None:
    md = _schema_md()
    assert {k: v for k, v in md.items() if k != "ground_truth"} == SCHEMA
    assert md["ground_truth"] == GROUND_TRUTH_SCHEMA


def test_tables_match_schema(trial_a) -> None:
    assert set(trial_a.tables) == set(TABLES) == set(SCHEMA)
    for name, cols in SCHEMA.items():
        df = trial_a.tables[name]
        assert list(df.columns) == list(cols), name
        assert len(df) > 0, name
        for col, kind in cols.items():
            if kind == "date":
                assert pd.api.types.is_datetime64_any_dtype(df[col]), (name, col)
            elif kind in ("int", "float", "bool"):
                assert df[col].dtype == {"int": "int64", "float": "float64", "bool": "bool"}[kind], (name, col)


def test_shape(trial_a) -> None:
    t = trial_a.tables
    assert trial_a.trial_id == "tr_2026_A_off"
    assert len(t["patients"]) == 800 and t["patients"]["patient_id"].is_unique
    assert len(t["sites"]) == 20 and not t["sites"]["is_fake"].any()
    assert t["patients"]["age"].between(30, 75).all()
    assert t["patients"]["baseline_hba1c"].between(7.0, 10.5).all()
    assert set(t["labs"]["source"]) == {"central", "local"}


def test_referential_integrity(trial_a) -> None:
    t = trial_a.tables
    pids, vids = set(t["patients"]["patient_id"]), set(t["visits"]["visit_id"])
    assert t["visits"]["visit_id"].is_unique
    for name in ("visits", "adverse_events", "conmeds", "dispensing", "kit_storage"):
        assert set(t[name]["patient_id"]) <= pids, name
    assert set(t["labs"]["visit_id"]) <= vids
    assert set(t["vitals"]["visit_id"]) <= vids
    dispensed = set(t["dispensing"].query("event_type == 'dispense'")["kit_id"])
    assert dispensed == set(t["kit_storage"]["kit_id"])
    assert t["kit_storage"]["kit_id"].is_unique


def test_baseline_lab_equals_patient_baseline(trial_a) -> None:
    t = trial_a.tables
    bl = t["labs"].query("test == 'hba1c'").merge(t["visits"], on="visit_id").query("visit_name == 'Baseline'")
    merged = bl.merge(t["patients"], on="patient_id")
    assert np.allclose(merged["value"], merged["baseline_hba1c"])


def test_deterministic(trial_a) -> None:
    again = generate_trial(TrialConfig(scenario="A"))
    for name in TABLES:
        pdt.assert_frame_equal(trial_a.tables[name], again.tables[name])


def test_load_roundtrip(trial_a) -> None:
    loaded = load_trial(trial_a.trial_id)
    assert loaded.config == trial_a.config
    for name in TABLES:
        pdt.assert_frame_equal(trial_a.tables[name], loaded.tables[name])


def test_load_unknown_trial() -> None:
    with pytest.raises(KeyError, match="unknown trial_id"):
        load_trial("tr_nope")


def test_randomization_1_to_1_per_site(trial_a) -> None:
    arm = ground_truth(trial_a.trial_id)
    assert set(arm) == {"drug", "placebo"}
    site = trial_a.tables["patients"].set_index("patient_id")["site_id"]
    counts = pd.crosstab(site, arm.reindex(site.index))
    assert (counts["drug"] == counts["placebo"]).all()


def test_arm_never_in_trial_or_views(trial_a) -> None:
    for name, df in trial_a.tables.items():
        assert "arm" not in df.columns, name
    for role in ROLES:
        view = export_view(trial_a.trial_id, role, list(REMEDIES))
        assert "arm" not in view.columns
        text_cols = view[["source", "kind", "category", "detail"]].astype(str)
        assert not text_cols.isin(["drug", "placebo"]).any().any(), role


@pytest.mark.parametrize("role", ROLES)
def test_view_columns_and_groups(trial_a, role: str) -> None:
    view = export_view(trial_a.trial_id, role)
    assert list(view.columns) == list(VIEW_COLUMNS)
    assert set(view["patient_id"]) == set(trial_a.tables["patients"]["patient_id"])
    groups = ROLE_GROUPS[role]
    sources = set(view["source"])
    assert ("dispensing" in sources) == ("dispensing" in groups)
    assert ("kit_storage" in sources) == ("kit_storage" in groups)
    assert ("adverse_event" in sources) == ("adverse_events" in groups)
    labs = set(view.loc[view["source"] == "lab", "category"])
    assert ("local" in labs) == ("local_labs" in groups)
    assert ("central" in labs) == ("central_labs" in groups)


def test_remedies(trial_a) -> None:
    tid = trial_a.trial_id
    base = export_view(tid, "coordinator")
    assert "dispensing" not in set(export_view(tid, "coordinator", ["unblinded_pharmacist"])["source"])
    assert "dispensing" in set(export_view(tid, "pharmacist", ["unblinded_pharmacist"])["source"])
    no_local = export_view(tid, "coordinator", ["central_lab"])
    assert not ((no_local["source"] == "lab") & (no_local["category"] == "local")).any()
    kits = export_view(tid, "coordinator", ["matched_kits"]).query("source == 'kit_storage'")
    assert (kits["category"] == "matched").all() and kits["value"].isna().all()
    sham = export_view(tid, "coordinator", ["sham_titration"])
    assert len(sham) >= len(base)
    with pytest.raises(ValueError, match="unknown remedies"):
        export_view(tid, "coordinator", ["hide_everything"])
    with pytest.raises(ValueError, match="unknown role"):
        export_view(tid, "janitor")  # type: ignore[arg-type]


def _week24_change(trial) -> pd.DataFrame:
    t = trial.tables
    hb = t["labs"].query("test == 'hba1c'").merge(t["visits"], on="visit_id").query("visit_name == 'Week 24'")
    df = hb.merge(t["patients"], on="patient_id")
    df["change"] = df["value"] - df["baseline_hba1c"]
    df["arm"] = df["patient_id"].map(ground_truth(trial.trial_id))
    return df


def test_scenario_effects(trial_a, trial_b) -> None:
    a = _week24_change(trial_a).groupby("arm")["change"].mean()
    b = _week24_change(trial_b).groupby("arm")["change"].mean()
    assert a["drug"] - a["placebo"] == pytest.approx(-0.5, abs=0.2)
    assert b["drug"] - b["placebo"] == pytest.approx(0.0, abs=0.2)


def test_mechanisms_off_coordinator_view_at_chance(trial_a) -> None:
    """Simulator-side guard until the Tell control test is live: with no mechanisms, what the
    coordinator sees must not predict the arm."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold, cross_val_score

    view = export_view(trial_a.trial_id, "coordinator")
    view = view.assign(feature=view["source"] + ":" + view["kind"])
    counts = view.pivot_table(index="patient_id", columns="feature", values="site_id", aggfunc="count", fill_value=0)
    means = view.dropna(subset=["value"]).pivot_table(index="patient_id", columns="kind", values="value", aggfunc="mean")
    X = counts.join(means).fillna(0.0)
    X = (X - X.mean()) / X.std().replace(0, 1)
    y = ground_truth(trial_a.trial_id).reindex(X.index)
    groups = view.groupby("patient_id")["site_id"].first().reindex(X.index)
    acc = cross_val_score(LogisticRegression(max_iter=2000), X, y, groups=groups, cv=GroupKFold(5)).mean()
    assert acc == pytest.approx(0.5, abs=0.07)
