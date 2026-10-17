"""Threshold calibration against the false-alarm budget, and freezing suite v0. Owner: Garv.

Twenty real sites can't calibrate a 5% budget on their own (one site is 5%), so the threshold is set
on real sites pooled from many simulated trials, each site scored against the other sites in its own
trial. The demo seed is never used for calibration.

Usage:
    python -m engine.fraud_checks.calibrate                 # calibrate + verify, write frozen/v0.json
    python -m engine.fraud_checks.calibrate --dry-run       # print, don't write
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import date

import numpy as np

from engine.fraud_checks.base import SiteCheck, SiteData
from engine.fraud_checks.suite import FROZEN_DIR, CheckSuite

OWNER = "Garv"

FALSE_ALARM_BUDGET = 0.05
"""At most 5% of real sites may be flagged. Fixed before any attack runs."""

CALIBRATION_SEEDS = range(1, 51)
VERIFY_SEEDS = range(101, 201)
DEMO_SEED = 2026


def site_scores(checks: list[SiteCheck], real_sites: list[SiteData]) -> list[float]:
    """Combined score of each real site, scored against the other real sites."""
    suite = CheckSuite(checks=list(checks), threshold=np.inf)
    return [suite.score_site(site, real_sites).combined for site in real_sites]


def threshold_for(scores: list[float], budget: float = FALSE_ALARM_BUDGET) -> float:
    """Smallest threshold that flags (score >= threshold) at most `budget` of `scores`."""
    ranked = np.sort(np.asarray(scores, dtype=float))[::-1]
    allowed = int(np.floor(budget * len(ranked)))
    return float(np.nextafter(ranked[allowed], np.inf))


def calibrate_threshold(checks: list[SiteCheck], real_sites: list[SiteData], budget: float = FALSE_ALARM_BUDGET) -> float:
    """Return the combined-score threshold that flags at most `budget` of `real_sites`."""
    return threshold_for(site_scores(checks, real_sites), budget)


def calibrate_on_trials(checks: list[SiteCheck], trials: list[list[SiteData]], budget: float = FALSE_ALARM_BUDGET) -> float:
    """Like calibrate_threshold, pooling real sites from several trials (each scored within its own trial)."""
    return threshold_for([s for sites in trials for s in site_scores(checks, sites)], budget)


def _trial_sites(seeds) -> list[list[SiteData]]:
    """Real sites of the demo-configuration trial for each seed (scenarios alternate A/B)."""
    from engine.fraud_checks.base import split_sites
    from engine.simulator.mechanisms import DEFAULT_MECHANISMS
    from engine.simulator.trial import TrialConfig, generate_trial

    return [
        split_sites(generate_trial(TrialConfig("A" if seed % 2 else "B", seed=seed, mechanisms=DEFAULT_MECHANISMS)).tables)
        for seed in seeds
    ]


def freeze_v0(checks: list[SiteCheck], budget: float = FALSE_ALARM_BUDGET, write: bool = True) -> dict:
    """Calibrate on CALIBRATION_SEEDS, verify on VERIFY_SEEDS and the demo seed, and write frozen/v0.json."""
    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("DB_PATH")
        os.environ["DB_PATH"] = os.path.join(tmp, "calibration.db")
        try:
            calibration = _trial_sites(CALIBRATION_SEEDS)
            verify = _trial_sites(VERIFY_SEEDS)
            demo = _trial_sites([DEMO_SEED])[0]
        finally:
            if old is None:
                os.environ.pop("DB_PATH")
            else:
                os.environ["DB_PATH"] = old

    threshold = calibrate_on_trials(checks, calibration, budget)
    suite = CheckSuite(checks=list(checks), threshold=threshold)
    n_cal = sum(len(t) for t in calibration)
    fp_cal = sum(suite.false_alarm_rate(t) * len(t) for t in calibration) / n_cal
    fp_verify = sum(suite.false_alarm_rate(t) * len(t) for t in verify) / sum(len(t) for t in verify)
    flagged_demo = [s.site_id for s in demo if suite.flags(s, demo)]
    data = {
        "version": 0,
        "checks": [c.name for c in checks],
        "threshold": round(threshold, 6),
        "combined": "max",
        "flag_rule": "combined >= threshold",
        "budget": budget,
        "calibration": {
            "trial_config": "DEFAULT_MECHANISMS, 20 sites x 40 patients, scenarios alternate A/B",
            "seeds": f"{CALIBRATION_SEEDS.start}-{CALIBRATION_SEEDS.stop - 1}",
            "n_sites": n_cal,
            "false_alarm_rate": round(fp_cal, 4),
        },
        "verification": {
            "seeds": f"{VERIFY_SEEDS.start}-{VERIFY_SEEDS.stop - 1}",
            "n_sites": sum(len(t) for t in verify),
            "false_alarm_rate": round(fp_verify, 4),
            "demo_seed": DEMO_SEED,
            "demo_sites_flagged": flagged_demo,
        },
        "frozen_on": date.today().isoformat(),
    }
    if write:
        FROZEN_DIR.mkdir(parents=True, exist_ok=True)
        (FROZEN_DIR / "v0.json").write_text(json.dumps(data, indent=2) + "\n")
    return data


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--budget", type=float, default=FALSE_ALARM_BUDGET)
    parser.add_argument("--dry-run", action="store_true", help="print the result without writing frozen/v0.json")
    args = parser.parse_args(argv)

    from engine.fraud_checks.suite import check_registry

    checks = []
    for cls in check_registry().values():
        check = cls()
        try:
            check.score(SiteData("probe", {}), [])
        except NotImplementedError:
            print(f"skipping {check.name}: not implemented yet")
            continue
        except Exception:  # noqa: BLE001 - implemented, just not happy with an empty site
            pass
        checks.append(check)
    print(json.dumps(freeze_v0(checks, args.budget, write=not args.dry_run), indent=2))


if __name__ == "__main__":
    main()
