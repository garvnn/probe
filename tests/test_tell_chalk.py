"""Tell's Chalk feature path, offline: no Chalk account, no network.

The Chalk client is replaced by a fake that runs the same resolver function Chalk would
(tell_chalk.vector.vector_json) on the same JSON inputs, so these tests check everything except
Chalk's servers: the per-patient/cross-patient split, the JSON round trip, the client plumbing,
the local fallback, and that chalk_project/ is exactly the 9-file deploy unit, in sync with the repo.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pandas.testing as pdt
import pytest

from engine.blind_leak.feature_source import chalk_enabled, chalk_features, tell_features
from engine.blind_leak.features import build_features
from engine.blind_leak.synthetic import Leak, make_trial
from tell_chalk.features import named_features
from tell_chalk.vector import assemble, patient_vector, rows_from_json, rows_to_json, vector_json

LEAK = Leak(source="dispensing", kind="titration_step", mode="rate", strength=1.2)


class FakeDataset:
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df

    def get_data_as_pandas(self) -> pd.DataFrame:
        return self.df


class FakeChalk:
    """Runs the deployed resolver body locally on exactly the input Chalk would receive."""

    def __init__(self) -> None:
        self.queries: list[dict] = []

    def offline_query(self, input: dict, output: list, recompute_features: bool) -> FakeDataset:
        self.queries.append({"input": input, "output": output})
        assert "arm" not in " ".join(input) and not any("arm" in o for o in output)
        vecs = [vector_json(rows) for rows in input["patient.view_rows"]]
        return FakeDataset(pd.DataFrame({"patient.id": input["patient.id"], "patient.tell_vector": vecs}))


@pytest.fixture(scope="module")
def leaky_view() -> pd.DataFrame:
    return make_trial(leaks=[LEAK], seed=12).view("coordinator")


def test_chalk_path_matches_build_features_bit_for_bit(leaky_view) -> None:
    client = FakeChalk()
    pdt.assert_frame_equal(chalk_features(leaky_view, client=client), build_features(leaky_view), check_dtype=False, check_exact=True)
    sent = client.queries[0]["input"]
    assert set(sent) == {"patient.id", "patient.site_id", "patient.view_rows"}
    assert len(sent["patient.id"]) == leaky_view["patient_id"].nunique()


def test_local_fallback_is_the_default(leaky_view, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELL_FEATURES", raising=False)
    assert not chalk_enabled()
    pdt.assert_frame_equal(tell_features(leaky_view), build_features(leaky_view))
    monkeypatch.setenv("TELL_FEATURES", "chalk")
    assert chalk_enabled()


def test_json_round_trip_keeps_every_view_value(leaky_view) -> None:
    one = leaky_view[leaky_view["patient_id"] == leaky_view["patient_id"].iloc[0]].reset_index(drop=True)
    back = rows_from_json(rows_to_json(one))
    assert len(back) == len(one)
    pdt.assert_series_equal(back["value"], one["value"].astype(float), check_names=False)
    assert list(back["kind"]) == [str(k) for k in one["kind"]]


def test_vector_never_contains_an_arm(leaky_view) -> None:
    pid = leaky_view["patient_id"].iloc[0]
    cols = {col for _, col, _ in patient_vector(leaky_view[leaky_view["patient_id"] == pid])}
    assert not any("arm" in c.split("__") or c in ("drug", "placebo") for c in cols)


def test_named_features_read_the_same_vector() -> None:
    rows = pd.DataFrame(
        {
            "patient_id": ["P1"] * 6,
            "site_id": ["S01"] * 6,
            "source": ["visit", "visit", "visit", "adverse_event", "conmed", "dispensing"],
            "date": ["2026-01-01", "2026-01-15", "2026-01-20", "2026-01-16", "2026-01-16", "2026-01-15"],
            "kind": ["Baseline", "Week 2", "Unscheduled", "Nausea", "antiemetic", "return"],
            "category": ["scheduled", "scheduled", "unscheduled", "GI", "", ""],
            "value": [float("nan")] * 6,
            "detail": ["", "", "", "mild", "", "K-01-001"],
        }
    )
    import json

    nf = named_features(json.loads(vector_json(rows_to_json(rows))))
    assert nf["unscheduled_visit_count"] == 1 and nf["ae_count_gi"] == 1 and nf["ae_count_general"] == 0
    assert nf["antiemetic_flag"] is True and nf["dispensing_count"] == 1 and nf["kit_returns"] == 1
    assert nf["visit_gap_mean"] == pytest.approx((14 + 5) / 2)


def test_assemble_applies_min_support_across_patients() -> None:
    def vec(n_rare: int) -> list:
        # Like patient_vector: a count entry appears only for values the patient actually has.
        rows = [[[1, "conmeds", "conmed", 0, ""], "conmeds__rows_n", 1 + n_rare]]
        return rows + ([[[1, "conmeds", "conmed", 1, "rare"], "conmeds__rare_n", n_rare]] if n_rare else [])

    four_have_it = {f"P{i}": vec(1 if i < 4 else 0) for i in range(10)}
    feats = assemble(four_have_it, {p: "S01" for p in four_have_it})
    assert "conmeds__rare_n" not in feats.columns  # 4 < MIN_SUPPORT patients
    five_have_it = {f"P{i}": vec(1 if i < 5 else 0) for i in range(10)}
    assert "conmeds__rare_n" in assemble(five_have_it, {p: "S01" for p in five_have_it}).columns


CHALK_PROJECT_FILES = {
    "chalk.yaml": None,
    "chalk_requirements.txt": None,
    "engine/__init__.py": None,
    "engine/blind_leak/__init__.py": "engine/blind_leak/__init__.py",
    "engine/blind_leak/contract.py": "engine/blind_leak/contract.py",
    "engine/blind_leak/features.py": "engine/blind_leak/features.py",
    "tell_chalk/__init__.py": "tell_chalk/__init__.py",
    "tell_chalk/features.py": "tell_chalk/features.py",
    "tell_chalk/vector.py": "tell_chalk/vector.py",
}
"""chalk_project/ is the deploy unit: these 9 files and nothing else. Code files are copies of the repo's."""


def test_chalk_project_is_exactly_the_nine_files_and_in_sync() -> None:
    root = Path(__file__).resolve().parents[1]
    project = root / "chalk_project"
    files = {str(p.relative_to(project)) for p in project.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    assert files == set(CHALK_PROJECT_FILES), "chalk_project/ must contain exactly the files Chalk needs"
    for copy, source in CHALK_PROJECT_FILES.items():
        if source:
            assert (project / copy).read_bytes() == (root / source).read_bytes(), f"chalk_project/{copy} is out of date; re-copy {source}"
    reqs = (project / "chalk_requirements.txt").read_text()
    assert "pandas==2.3.3" in reqs and "numpy==2.4.6" in reqs


def test_no_repo_root_chalk_config() -> None:
    """A chalk.yaml at the repo root would let `chalk apply` upload the whole repository."""
    root = Path(__file__).resolve().parents[1]
    assert not (root / "chalk.yaml").exists() and not (root / ".chalkignore").exists()
