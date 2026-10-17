"""Measure Daytona sandbox latency for the Impostor loop. Owner: Shreyas.

This is a measurement script, not a feature. It runs a canned fake-clinic generator
(numpy + pandas, ~40 patients x 9 visits) through DaytonaRunner in several modes and prints
per-run timings and totals. It also checks that a broken generator returns a clean error and
an infinite loop returns a clean timeout, and probes warm pools and VM forking.

Every sandbox it creates is deleted at the end, even on a crash: each mode cleans up in a
finally block, and a last sweep deletes anything still carrying the probe label.

Usage:
    .venv/bin/python scripts/daytona_benchmark.py                # all modes
    .venv/bin/python scripts/daytona_benchmark.py --modes fresh reuse --runs 5
    .venv/bin/python scripts/daytona_benchmark.py --json data/demo_cache/daytona_benchmark.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

from integrations.daytona import DaytonaRunner, SandboxResult  # noqa: E402

OWNER = "Shreyas"

FAKE_CLINIC = '''
import datetime as dt

import numpy as np
import pandas as pd


def generate_site(context):
    rng = np.random.default_rng(context["seed"])
    n = context["n_patients"]
    site = context["site_id"]
    visit_names = ["Screening", "Baseline", "Week 2", "Week 4", "Week 8", "Week 12", "Week 16", "Week 20", "Week 24"]
    offsets = [-14, 0, 14, 28, 56, 84, 112, 140, 168]
    start = dt.date(2026, 1, 5)

    patients = pd.DataFrame({
        "patient_id": [f"P{site}{i:03d}" for i in range(n)],
        "site_id": site,
        "age": rng.integers(30, 76, n),
        "sex": rng.choice(["F", "M"], n),
        "bmi": rng.normal(31, 4, n).round(1),
        "baseline_hba1c": rng.uniform(7.0, 10.5, n).round(1),
    })

    visits, labs, vitals = [], [], []
    for p in patients.itertuples():
        enrolled = start + dt.timedelta(days=int(rng.integers(0, 60)))
        hba1c = p.baseline_hba1c
        for name, off in zip(visit_names, offsets):
            vid = f"V{p.patient_id}-{name.replace(' ', '')}"
            day = enrolled + dt.timedelta(days=off + int(rng.integers(-3, 4)))
            visits.append({"visit_id": vid, "patient_id": p.patient_id, "visit_name": name, "date": day.isoformat(), "scheduled": True})
            hba1c = hba1c - 0.03 + rng.normal(0, 0.15)
            labs.append({"lab_id": f"L{vid}", "visit_id": vid, "test": "hba1c", "value": round(float(hba1c), 1), "source": "central"})
            sbp = int(rng.normal(132, 12))
            vitals.append({"visit_id": vid, "sbp": sbp, "dbp": int(sbp * 0.62 + rng.normal(0, 5)), "weight": round(float(p.bmi * 2.9 + rng.normal(0, 1)), 1)})

    n_ae = int(rng.poisson(0.4 * n))
    aes = pd.DataFrame({
        "ae_id": [f"AE{site}{i:03d}" for i in range(n_ae)],
        "patient_id": rng.choice(patients["patient_id"], n_ae),
        "term": rng.choice(["Nausea", "Headache", "Fatigue"], n_ae),
        "category": "GI",
        "onset_date": [(start + dt.timedelta(days=int(d))).isoformat() for d in rng.integers(0, 200, n_ae)],
        "severity": rng.choice(["mild", "moderate"], n_ae, p=[0.8, 0.2]),
    })

    return {
        "patients": patients.to_dict("records"),
        "visits": visits,
        "labs": labs,
        "vitals": vitals,
        "adverse_events": aes.to_dict("records"),
        "conmeds": [],
        "dispensing": [],
    }
'''

BROKEN = '''
import numpy as np


def generate_site(context):
    patients = np.zeros(context["n_patients"])
    return {"patients": patients_list}  # NameError: deliberately broken
'''

INFINITE_LOOP = '''
def generate_site(context):
    while True:
        pass
'''

INPUTS = {"seed": 2026, "n_patients": 40, "site_id": "S99"}


# ---------------------------------------------------------------------- stats / printing


def p90(xs: list[float]) -> float:
    """Nearest-rank 90th percentile."""
    s = sorted(xs)
    return s[max(0, math.ceil(0.9 * len(s)) - 1)]


def summarize(name: str, results: list[SandboxResult], setup_s: float = 0.0, close_s: float = 0.0) -> dict:
    totals = [r.timings.get("total_s", r.runtime_s) for r in results]
    errors = sum(not r.ok for r in results)
    wall = sum(totals) + setup_s + close_s
    print(f"\n  {name}: sum {sum(totals):.2f}s  mean {statistics.mean(totals):.2f}s  p90 {p90(totals):.2f}s  errors {errors}/{len(results)}")
    if setup_s or close_s:
        print(f"  {name}: + setup {setup_s:.2f}s + close {close_s:.2f}s = {wall:.2f}s wall")
    return {
        "mode": name,
        "runs": len(results),
        "sum_s": round(sum(totals), 3),
        "mean_s": round(statistics.mean(totals), 3),
        "p90_s": round(p90(totals), 3),
        "wall_s": round(wall, 3),
        "errors": errors,
        "per_run": [r.timings | {"ok": r.ok, "sandbox_id": r.sandbox_id} for r in results],
    }


def print_run(i: int, r: SandboxResult) -> None:
    t = r.timings
    status = "ok" if r.ok else f"ERROR {r.stderr.strip().splitlines()[-1][:80] if r.stderr.strip() else ''}"
    rows = len(r.output["visits"]) if r.ok and r.output else 0
    print(
        f"  run {i:2d}  create {t.get('create_s', 0):5.2f}s  exec {t.get('exec_s', 0):5.2f}s  "
        f"teardown {t.get('teardown_s', 0):5.2f}s  total {t.get('total_s', 0):5.2f}s  {status}"
        + (f"  ({rows} visits)" if rows else "")
    )


def run_series(runner: DaytonaRunner, runs: int) -> list[SandboxResult]:
    results = []
    for i in range(1, runs + 1):
        r = runner.run(FAKE_CLINIC, INPUTS, timeout=60)
        print_run(i, r)
        results.append(r)
    return results


# ---------------------------------------------------------------------- modes


def mode_fresh(runs: int) -> dict:
    print("\n(a) fresh sandbox per run")
    runner = DaytonaRunner(reuse=False)
    return summarize("fresh", run_series(runner, runs))


def mode_reuse(runs: int) -> dict:
    print("\n(b) one sandbox reused for every run")
    runner = DaytonaRunner(reuse=True)
    try:
        results = run_series(runner, runs)
    finally:
        t = time.perf_counter()
        runner.close()
        close_s = time.perf_counter() - t
    return summarize("reuse", results, close_s=close_s)


def mode_warm_pool(runs: int, snapshot: str) -> dict:
    print(f"\n(c) warm pool on snapshot {snapshot!r}")
    runner = DaytonaRunner(reuse=False, snapshot=snapshot)
    try:
        existing = runner.client.warm_pool.list()
    except Exception as e:
        print(f"  warm pools unavailable: {type(e).__name__}: {e}")
        return {"mode": "warm_pool", "available": False, "reason": f"{type(e).__name__}: {e}"}

    pool = None
    created_here = False
    try:
        pool = next((p for p in existing if p.snapshot == snapshot), None)
        if pool is None:
            try:
                pool = runner.client.warm_pool.create(snapshot, pool=2)
                created_here = True
            except Exception as e:
                print(f"  warm pool create failed: {type(e).__name__}: {e}")
                return {"mode": "warm_pool", "available": False, "reason": f"{type(e).__name__}: {e}"}
        t = time.perf_counter()
        while time.perf_counter() - t < 120:
            pool = next(p for p in runner.client.warm_pool.list() if p.id == pool.id)
            if pool.error_reason:
                print(f"  pool error: {pool.error_reason}")
                return {"mode": "warm_pool", "available": False, "reason": pool.error_reason}
            if (pool.current_size or 0) >= 1:
                break
            time.sleep(2)
        fill_s = time.perf_counter() - t
        print(f"  pool {pool.id} ready: {pool.current_size}/{pool.pool} warm after {fill_s:.1f}s")
        return summarize("warm_pool", run_series(runner, runs)) | {"available": True, "fill_s": round(fill_s, 2)}
    finally:
        if pool is not None and created_here:
            runner.client.warm_pool.delete(pool.id)
            print(f"  deleted warm pool {pool.id}")


def mode_errors() -> dict:
    print("\nerror handling (fresh sandbox each)")
    runner = DaytonaRunner(reuse=False)
    out = {}
    for name, code, timeout in [("broken", BROKEN, 30), ("infinite_loop", INFINITE_LOOP, 5)]:
        r = runner.run(code, INPUTS, timeout=timeout)
        print_run(0, r)
        print(f"    stderr: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else '(empty)'}")
        out[name] = {"ok": r.ok, "stderr_tail": r.stderr.strip()[-300:], "timings": r.timings}
    out["broken_clean_error"] = (not out["broken"]["ok"]) and "NameError" in out["broken"]["stderr_tail"]
    out["timeout_clean"] = (not out["infinite_loop"]["ok"]) and out["infinite_loop"]["stderr_tail"].startswith("TIMEOUT")
    return out


def mode_fork() -> dict:
    """Containers can't fork; try a Linux VM sandbox, start a process holding state, fork, check the copy."""
    print("\nfork: container sandbox")
    runner = DaytonaRunner(reuse=False)
    result: dict = {}
    sandboxes = []
    try:
        sb = runner.create_sandbox()
        sandboxes.append(sb)
        try:
            sb.fork()
            result["container_fork"] = "supported"
        except Exception as e:
            result["container_fork"] = f"{type(e).__name__}: {e}"
        print(f"  container fork: {result['container_fork'][:160]}")

        vm = None
        for target in ("us", "eu"):
            print(f"fork: Linux VM sandbox (daytona-vm-small, region {target})")
            vm_runner = DaytonaRunner(reuse=False, snapshot="daytona-vm-small", target=target)
            t = time.perf_counter()
            try:
                vm = vm_runner.create_sandbox()
                break
            except Exception as e:
                result[f"vm_create_{target}"] = f"{type(e).__name__}: {e}"
                print(f"  VM create failed: {result[f'vm_create_{target}'][:200]}")
        if vm is None:
            return result
        sandboxes.append(vm)
        result["vm_create_s"] = round(time.perf_counter() - t, 2)
        print(f"  VM created in {result['vm_create_s']}s")
        vm.process.exec("echo filesystem-state > /tmp/probe_marker && (nohup python3 -c 'import time; x=[42]*10**6; time.sleep(900)' >/dev/null 2>&1 &)", timeout=30)
        t = time.perf_counter()
        try:
            child = vm.fork()
        except Exception as e:
            result["vm_fork"] = f"{type(e).__name__}: {e}"
            print(f"  VM fork failed: {result['vm_fork'][:200]}")
            return result
        sandboxes.insert(0, child)  # children must be deleted before the parent
        result["vm_fork_s"] = round(time.perf_counter() - t, 2)
        check = child.process.exec("cat /tmp/probe_marker; pgrep -f 'time.sleep(900)' >/dev/null && echo process-alive || echo process-missing", timeout=30)
        result["fork_check"] = check.result.strip()
        print(f"  VM fork in {result['vm_fork_s']}s; child sees: {result['fork_check']!r}")
        return result
    finally:
        for s in sandboxes:
            try:
                runner.delete_sandbox(s)
            except Exception as e:
                print(f"  delete {s.id} failed: {e}")


def sweep(runner: DaytonaRunner, wait_s: float = 60.0) -> list[str]:
    """Delete every sandbox still carrying the probe label, waiting out in-flight deletes.

    Returns the ids still present after `wait_s` (should be empty).
    """
    from daytona import ListSandboxesQuery

    deadline = time.perf_counter() + wait_s
    while True:
        left = list(runner.client.list(ListSandboxesQuery(labels=DaytonaRunner.LABELS)))
        if not left or time.perf_counter() > deadline:
            return [s.id for s in left]
        for s in left:
            try:
                runner.client.delete(s)
            except Exception:
                pass  # usually "state change in progress": an earlier delete is still finishing
        time.sleep(3)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--modes", nargs="+", default=["fresh", "reuse", "warm_pool", "errors", "fork"])
    parser.add_argument("--json", type=Path, default=None, help="Also write results here")
    args = parser.parse_args(argv)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    report: dict = {}
    base = DaytonaRunner()
    try:
        probe = base.create_sandbox()
        try:
            env = probe.process.exec("python3 -c 'import sys,numpy,pandas;print(sys.version.split()[0],numpy.__version__,pandas.__version__)'", timeout=30)
            report["default_snapshot"] = probe.snapshot
            report["python_numpy_pandas"] = env.result.strip()
            print(f"default snapshot {probe.snapshot!r}; python/numpy/pandas: {env.result.strip()}")
        finally:
            base.delete_sandbox(probe)

        for mode in args.modes:
            try:
                if mode == "fresh":
                    report["fresh"] = mode_fresh(args.runs)
                elif mode == "reuse":
                    report["reuse"] = mode_reuse(args.runs)
                elif mode == "warm_pool":
                    report["warm_pool"] = mode_warm_pool(args.runs, report["default_snapshot"])
                elif mode == "errors":
                    report["errors"] = mode_errors()
                elif mode == "fork":
                    report["fork"] = mode_fork()
            except Exception:
                traceback.print_exc()
                report[mode] = {"crashed": traceback.format_exc(limit=3)}
    finally:
        left = sweep(base)
        print(f"\ncleanup: {len(left)} probe sandbox(es) left after sweep" + (f": {left}" if left else " (all deleted)"))
        report["left_after_sweep"] = left

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, default=str))
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
