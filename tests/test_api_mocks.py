"""Every route returns 200 with a "_mock": true payload in mock mode."""

from __future__ import annotations

import json

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.main import app

TID = "tr_2026_B"

CASES: list[tuple[str, str, dict | None]] = [
    ("GET", "/health", None),
    ("POST", "/trials", {"scenario": "B"}),
    ("GET", f"/trials/{TID}", None),
    ("POST", "/forger/runs", {"trial_id": TID}),
    ("POST", "/detector/harden", {"trial_id": TID, "run_id": "fr_01"}),
    ("POST", "/heldout/eval", {"trial_id": TID, "detector_versions": [0, 1]}),
    ("POST", "/blind/runs", {"trial_id": TID}),
    ("POST", "/blind/policy", {"trial_id": TID, "remedies": ["central_lab"]}),
    ("POST", "/blind/minimum-fix", {"trial_id": TID}),
    ("GET", "/blind/guess-cards", None),
    ("POST", "/blind/guess-cards/score", {"trial_id": TID, "guesses": {"C1": "drug", "C2": "drug"}}),
    ("GET", "/contract/demo", None),
    ("POST", "/margin", {"trial_id": TID}),
    ("GET", f"/report/{TID}", None),
]


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "mock")
    monkeypatch.setenv("MOCK_STREAM_INTERVAL_S", "0")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize(("method", "path", "body"), CASES)
def test_route_returns_mock(client: TestClient, method: str, path: str, body: dict | None) -> None:
    r = client.request(method, path, json=body)
    assert r.status_code == 200, r.text
    if path != "/health":
        assert r.json()["_mock"] is True


def test_every_route_is_covered() -> None:
    tested = {(m, p.replace(TID, "{trial_id}").replace("/demo", "/{trial_id}")) for m, p, _ in CASES}
    tested.add(("GET", "/forger/runs/{run_id}/stream"))
    routes = {(m, r.path) for r in app.routes if isinstance(r, APIRoute) for m in r.methods}
    assert routes <= tested, f"untested routes: {routes - tested}"


def test_forger_stream(client: TestClient) -> None:
    with client.stream("GET", "/forger/runs/fr_01/stream") as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    events, current = [], None
    for line in body.splitlines():
        if line.startswith("event:"):
            current = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            events.append((current, json.loads(line.split(":", 1)[1])))
    rounds = [d for e, d in events if e == "round"]
    assert len(rounds) == 6
    assert all(r["_mock"] for r in rounds)
    assert [r["escaped"] for r in rounds] == [False] * 5 + [True]
    assert events[-1][0] == "done"


def test_contract_defaults_untested(client: TestClient) -> None:
    props = client.get("/contract/demo").json()["properties"]
    assert [p["name"] for p in props] == [
        "data_authenticity",
        "treatment_confidentiality",
        "statistical_integrity",
        "safety_accessibility",
        "operational_utility",
    ]
    assert {p["status"] for p in props} == {"untested"}

    mixed = client.get("/contract/demo", params={"fixture": "mixed"}).json()["properties"]
    assert {p["status"] for p in mixed} == {"held", "broken"}
    assert all(p["counterexample"] for p in mixed if p["status"] == "broken")


def test_minimum_fix_has_all_combos(client: TestClient) -> None:
    data = client.post("/blind/minimum-fix", json={"trial_id": TID}).json()
    assert len(data["results"]) == 16
    assert data["recommended"] in data["results"]


def test_guess_cards_have_no_labels(client: TestClient) -> None:
    text = client.get("/blind/guess-cards").text
    assert "truth" not in text and "arm" not in json.loads(text)["cards"][0]["visible"]


def test_live_mode_is_501_with_owner(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "live")
    r = client.post("/trials", json={"scenario": "B"})
    assert r.status_code == 501
    assert r.json()["detail"].startswith("owner: Garv")
