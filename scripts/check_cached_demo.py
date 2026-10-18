"""Exercise demo endpoints against a running cached backend; no attacker calls.

Usage: .venv/bin/python -m scripts.check_cached_demo --out cached-run-through.json
Start the backend with DEMO_MODE=cached CACHED_REPLAY_SPEED=0 first.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def check(base: str) -> list[dict]:
    rows = []
    tid = "tr_2026_B"

    def hit(name, method, path, body=None, stream=False):
        request = Request(base.rstrip("/") + path, method=method,
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=120) as response:
                text, status = response.read().decode(), response.status
            if stream:
                events = [json.loads(line[5:].strip()) for line in text.splitlines() if line.startswith("data:")]
                if not events or events[-1].get("run_id") is None:
                    raise ValueError("SSE missing done event")
                measured = all(event.get("_mock") is False for event in events)
                payload = {"events": len(events)}
            else:
                payload = json.loads(text)
                measured = payload.get("_mock") is False
            if name == "health" and payload.get("demo_mode") != "cached":
                raise ValueError("backend is not in cached mode")
            row = {"endpoint": name, "method": method, "path": path, "status": status,
                   "data": "real" if measured else ("metadata" if name == "health" else "sample"), "error": None}
            rows.append(row)
            print(f"{status} {name}: {row['data']}", flush=True)
            return payload
        except (HTTPError, OSError, ValueError) as error:
            rows.append({"endpoint": name, "method": method, "path": path,
                         "status": getattr(error, "code", None), "data": None, "error": str(error)})
            print(f"ERROR {name}: {error}", flush=True)
            return {}

    hit("health", "GET", "/health")
    hit("setup/create", "POST", "/trials", {"scenario": "B", "seed": 2026})
    hit("setup/detail", "GET", f"/trials/{tid}")
    hit("contract", "GET", f"/contract/{tid}")
    hit("contract/mixed", "GET", f"/contract/{tid}?fixture=mixed")
    run = hit("impostor/create", "POST", "/fake-data/runs", {"trial_id": tid})
    run_id = run.get("run_id", "missing")
    hit("impostor/detail", "GET", f"/fake-data/runs/{run_id}")
    hit("impostor/stream", "GET", f"/fake-data/runs/{run_id}/stream", stream=True)
    hit("patch", "POST", "/fraud-checks/patch", {"trial_id": tid, "run_id": run_id})
    hit("patch/held-out", "GET", f"/fraud-checks/held-out?trial_id={tid}")
    hit("stranger (current held-out UI)", "POST", "/test-attacker/eval", {"trial_id": tid, "suite_versions": [0, 1]})
    hit("tell/coordinator", "POST", "/blind-leak/runs", {"trial_id": tid})
    hit("tell/assessor", "POST", "/blind-leak/runs", {"trial_id": tid, "view": "assessor"})
    seal = hit("seal", "POST", "/blind-leak/cheapest-fix", {"trial_id": tid})
    combo = (seal.get("recommended") or {}).get("combo", [])
    hit("tell/policy", "POST", "/blind-leak/policy", {"trial_id": tid, "remedies": combo})
    hit("guess-who/cards", "GET", f"/blind-leak/guess-cards?trial_id={tid}")
    hit("guess-who/score", "POST", "/blind-leak/guess-cards/score", {"trial_id": tid, "guesses": {}})
    for version in (0, 1):
        hit(f"breaking-point/v{version}", "POST", "/breaking-point", {"trial_id": tid, "suite_version": version})
    hit("report", "GET", f"/report/{tid}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--out", type=Path, default=Path("data/demo_cache/precomputed/run_through.json"))
    args = parser.parse_args()
    rows = check(args.base)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"_mock": False, "demo_mode": "cached", "endpoints": rows}, indent=2) + "\n")
    raise SystemExit(1 if any(r["error"] for r in rows) else 0)


if __name__ == "__main__":
    main()
