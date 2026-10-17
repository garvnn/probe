"""Training and held-out data for Patch: honest site pools and fake sites from Impostor runs. Owner: Garv.

Honest sites come from Trial Twin trials with seeds that v0 never saw. Fake sites come from saved
Impostor runs in data/demo_cache/ plus the hand-written scripted versions. LLM-written code is never
executed here: a fake is used only if its round saved the validated site (`fake_output`), or it is
a scripted version (repo code, regenerated in-process), or a SandboxRunner is passed to re-run it.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from engine.fraud_checks.base import SiteData

OWNER = "Garv"

FIT_SEEDS = range(201, 261)
"""Honest trials the learned check is fit on (1,200 sites)."""
HOLDOUT_SEEDS = range(301, 351)
"""Honest trials never used to fit or calibrate anything (1,000 sites)."""
SCRIPTED_SEEDS = range(8)
"""Seeds for regenerating each scripted version as training fakes."""

TRIAL_ID = re.compile(r"^tr_(\d+)_([AB])$")


@dataclass
class FakeRecord:
    """One fake site and where it came from.

    Attributes:
        site: The validated fake site (with the attacker's arms, if it sent them).
        reference: Real sites of the trial it attacked; features are computed against these.
        run_id / round: Saved run and round it came from ("scripted-local" for regenerated versions).
        group: The unit fakes are split by. Each LLM run is its own group; every scripted fake is in
            one "scripted" group, since all scripted runs share the same four templates.
        attacker_kind: "llm" or "scripted".
        source: "saved", "scripted-regenerated", or "sandbox-rerun".
    """

    site: SiteData
    reference: list[SiteData]
    run_id: str
    round: int
    group: str
    attacker_kind: str
    source: str


@contextmanager
def temp_db() -> Iterator[None]:
    """Point DB_PATH at a throwaway file so pool trials don't land in the team DB."""
    old = os.environ.get("DB_PATH")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DB_PATH"] = os.path.join(tmp, "patch.db")
        try:
            yield
        finally:
            if old is None:
                os.environ.pop("DB_PATH", None)
            else:
                os.environ["DB_PATH"] = old


def trial_sites(seed: int, scenario: str | None = None) -> list[SiteData]:
    """Real sites of the default (leaks-on) trial for `seed`. Scenarios alternate A/B unless given."""
    from engine.fake_data.sites import split_sites
    from engine.simulator.trial import TrialConfig, generate_trial

    return split_sites(generate_trial(TrialConfig(scenario or ("A" if seed % 2 else "B"), seed=seed)))


def honest_pool(seeds) -> list[tuple[SiteData, list[SiteData]]]:
    """(site, its trial's sites) for every real site of every seed."""
    pairs = []
    for seed in seeds:
        sites = trial_sites(seed)
        pairs.extend((s, sites) for s in sites)
    return pairs


def _scripted_output(version: int, context: dict, seed: int) -> dict:
    """Run a hand-written scripted generator (repo code, not LLM output) in-process."""
    from engine.fake_data.scripted import scripted_source

    ns: dict = {}
    exec(compile(scripted_source(version), f"scripted_v{version}.py", "exec"), ns)  # noqa: S102 - trusted repo template
    return ns["generate_site"]({**context, "seed": seed})


def scripted_fakes(trial_id: str = "tr_2026_B", seeds=SCRIPTED_SEEDS) -> list[FakeRecord]:
    """Every scripted version x `seeds`, made against `trial_id`'s public context."""
    from engine.fake_data.context import public_context
    from engine.fake_data.validate import validate_schema

    trial, real = _trial(trial_id)
    context = public_context(trial)
    site_id = context["your_site"]["site_id"]
    out = []
    for version in (1, 2, 3, 4):
        for seed in seeds:
            site = validate_schema(_scripted_output(version, context, seed), site_id)
            out.append(FakeRecord(site, real, "scripted-local", version, "scripted", "scripted", "scripted-regenerated"))
    return out


_TRIALS: dict[str, tuple] = {}


def _trial(trial_id: str):
    """(Trial, real sites) for a default-mechanisms trial ID like tr_2026_B."""
    from engine.fake_data.sites import split_sites
    from engine.simulator.trial import TrialConfig, generate_trial

    if trial_id not in _TRIALS:
        m = TRIAL_ID.match(trial_id)
        if not m:
            raise ValueError(f"can't rebuild trial {trial_id!r}: only default-mechanism IDs like tr_2026_B")
        trial = generate_trial(TrialConfig(m.group(2), seed=int(m.group(1))))
        _TRIALS[trial_id] = (trial, split_sites(trial))
    return _TRIALS[trial_id]


def load_fakes(cache_dir: Path | None = None, runner=None) -> tuple[list[FakeRecord], list[str]]:
    """Fake sites from every saved Impostor run. Returns (records, skipped-round notes)."""
    from engine.fake_data.cache import cache_dir as default_cache_dir
    from engine.fake_data.context import public_context
    from engine.fake_data.scripted import scripted_source
    from engine.fake_data.validate import SchemaError, validate_schema

    scripted_sources = {scripted_source(v): v for v in (1, 2, 3, 4)}
    records: list[FakeRecord] = []
    skipped: list[str] = []
    for path in sorted((cache_dir or default_cache_dir()).glob("fd_*.json")):
        run = json.loads(path.read_text())
        run_id, kind = run["run_id"], run.get("attacker", {}).get("kind", "llm")
        try:
            trial, real = _trial(run["trial_id"])
        except ValueError as e:
            skipped.append(f"{run_id}: {e}")
            continue
        context = public_context(trial)
        site_id = run.get("fake_site_id") or context["your_site"]["site_id"]
        group = "scripted" if kind == "scripted" else run_id
        for rnd in run["rounds"]:
            if not rnd.get("ok"):
                continue
            r, code = rnd["round"], rnd.get("code", "")
            seed = rnd.get("input_seed") if rnd.get("input_seed") is not None else 2026 * 100 + r
            if rnd.get("fake_output"):
                output, source = rnd["fake_output"], "saved"
            elif kind == "scripted" and code in scripted_sources:
                output, source = _scripted_output(scripted_sources[code], context, seed), "scripted-regenerated"
            elif runner is not None:
                result = runner.run(code, {**context, "seed": seed}, timeout=60)
                if not result.ok:
                    skipped.append(f"{run_id} round {r + 1}: sandbox re-run failed")
                    continue
                output, source = result.output, "sandbox-rerun"
            else:
                skipped.append(f"{run_id} round {r + 1}: no saved fake site; LLM code only re-runs in a sandbox (--runner daytona)")
                continue
            try:
                site = validate_schema(output, site_id)
            except SchemaError as e:
                skipped.append(f"{run_id} round {r + 1}: schema error on rebuild: {e}")
                continue
            records.append(FakeRecord(site, real, run_id, r, group, kind, source))
    return records, skipped


def split_groups(groups: list[str], holdout_fraction: float = 0.5) -> tuple[set[str], set[str]]:
    """Deterministic split of fake groups into (train, held-out). The scripted group always trains:
    it's four fixed templates, and every scripted fake is already caught by v0."""
    import hashlib

    llm = sorted({g for g in groups if g != "scripted"}, key=lambda g: hashlib.sha1(g.encode()).hexdigest())
    n_holdout = int(round(holdout_fraction * len(llm)))
    held = set(llm[:n_holdout])
    return {g for g in groups if g not in held}, held
