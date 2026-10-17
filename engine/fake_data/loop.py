"""The fake-data loop (Impostor): write -> sandbox -> validate -> score -> feedback -> rewrite. Owner: Shreyas."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from engine.fake_data.attacker import Attacker
from engine.fake_data.cache import save_run
from engine.fake_data.context import public_context
from engine.fake_data.sites import split_sites
from engine.fake_data.validate import SchemaError, fake_arms, validate_schema
from engine.fraud_checks.base import SiteData
from engine.fraud_checks.suite import CheckSuite, SiteScores
from engine.simulator.trial import Trial
from integrations.daytona import LocalMockRunner, SandboxRunner

OWNER = "Shreyas"

SANDBOX_TIMEOUT_S = 60
ERROR_FEEDBACK_CHARS = 2000


@dataclass
class Round:
    """One attack round. Persisted to data/demo_cache and streamed to the UI.

    Attributes:
        round: 0-based round index.
        code: The attacker's fake-site source for this round.
        sandbox_id: Daytona sandbox ID the code ran in.
        ok: False if the code errored, timed out, or failed schema validation.
        scores: Check-suite scores for the fake site (None if not ok).
        combined: Combined risk score (None if not ok).
        escaped: True if combined < the check-suite threshold.
        damage: Effect shift from including the fake site (see engine.analysis.damage); None until
            that lands.
        threshold: The check-suite threshold the round was scored against.
        fired: Checks at or above the threshold (what the attacker is told).
        error: Why the round failed, if it did (sandbox error, timeout, schema error, refusal).
        attacker_id / attacker_kind / attacker_model: Who wrote the code ("scripted" or "llm").
        attacker_s: Seconds the attacker took to write the code.
        sandbox_s: Seconds the code ran in the sandbox (excludes create/teardown).
        timings: Sandbox phase breakdown (create_s, exec_s, teardown_s, total_s).
        llm: Token and latency record for the attacker call, if an LLM wrote the code.
        n_patients: Fake patients produced (0 if not ok).
        claimed_arms: The attacker's own drug/placebo split, if it sent one. Never scored.
        diagnostics: For each check that fired, what it measured on the fake site vs the typical
            range on real sites (aggregates only). Sent to the attacker as feedback.
        fake_output: The validated fake site exactly as the sandbox returned it (tables as row
            lists, plus the optional ground_truth). Saved so Patch can train on it without re-running
            attacker code. Never sent to the attacker or the UI.
        input_seed: The seed the attacker's generate_site() was called with this round.
    """

    round: int
    code: str
    sandbox_id: str
    ok: bool
    scores: SiteScores | None
    combined: float | None
    escaped: bool
    damage: dict | None
    threshold: float | None = None
    fired: list[str] = field(default_factory=list)
    error: str | None = None
    attacker_id: str = ""
    attacker_kind: str = ""
    attacker_model: str = ""
    attacker_s: float = 0.0
    sandbox_s: float = 0.0
    timings: dict = field(default_factory=dict)
    llm: dict | None = None
    n_patients: int = 0
    claimed_arms: dict | None = None
    diagnostics: list[dict] = field(default_factory=list)
    fake_output: dict | None = field(default=None, repr=False)
    input_seed: int | None = None

    @property
    def status(self) -> str:
        return "escaped" if self.escaped else ("detected" if self.ok else "error")


def _damage(trial: Trial, fake: SiteData) -> dict | None:
    """Effect shift once engine.analysis.damage is implemented; None until then."""
    from engine.analysis.damage import effect_shift

    try:
        return asdict(effect_shift(trial, [fake]))
    except NotImplementedError:
        return None


def explain_fired(suite: CheckSuite, fake: SiteData, real_sites: list[SiteData], fired: list[str]) -> list[dict]:
    """For each fired check: what it measured on the fake site vs the typical range on real sites.

    Uses the check's own `explain(site, reference)` if it has one, else engine.fake_data.explain,
    else just the check's name. Aggregates only.
    """
    from engine.fake_data.explain import explain

    out = []
    for check in suite.checks:
        if check.name not in fired:
            continue
        own = getattr(check, "explain", None)
        detail = own(fake, real_sites) if callable(own) else explain(check.name, fake, real_sites)
        out.append(detail or {"check": check.name, "measures": [], "summary": f"{check.name} fired (no detail available)"})
    return out


def _is_standin(suite: CheckSuite) -> bool:
    return type(suite).__module__.endswith("_standin")


def fake_data_loop(
    trial: Trial,
    suite: CheckSuite,
    attacker: Attacker,
    rounds: int = 8,
    *,
    runner: SandboxRunner | None = None,
    real_sites: list[SiteData] | None = None,
    run_id: str | None = None,
    timeout: int = SANDBOX_TIMEOUT_S,
    stop_on_escape: bool = False,
    save: bool = True,
    on_round: Callable[[Round], None] | None = None,
) -> list[Round]:
    """Run `rounds` attack rounds. Sandbox errors and schema errors become feedback, not crashes.

    Each round: the attacker writes code, `runner` executes it (a fresh Daytona sandbox by
    default), the output is validated against the schema, `suite` scores it against the real
    sites, and the result goes back to the attacker as the next round's feedback. Every round is
    saved to data/demo_cache/<run_id>.json as it finishes.
    """
    if runner is None:
        from integrations.daytona import DaytonaRunner

        runner = DaytonaRunner(reuse=False)
    real_sites = real_sites if real_sites is not None else split_sites(trial)
    context = public_context(trial)
    site_id = context["your_site"]["site_id"]
    kind = getattr(attacker, "kind", "llm")
    run_id = run_id or f"fd_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{kind}"
    standin = _is_standin(suite)
    run = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trial_id": trial.trial_id,
        "scenario": trial.config.scenario,
        "fake_site_id": site_id,
        "suite": {"name": getattr(suite, "name", type(suite).__name__), "version": suite.version, "threshold": suite.threshold, "standin": standin},
        "attacker": {"id": attacker.attacker_id, "kind": kind, "model": attacker.model},
        "runner": type(runner).__name__,
        "rounds_planned": rounds,
        "not_a_result": standin or kind == "scripted" or isinstance(runner, LocalMockRunner),
        "rounds": [],
    }
    if run["not_a_result"]:
        run["label"] = "TEMPORARY: stand-in checks and/or scripted attacker. Not a result."

    history: list[Round] = []
    feedback: dict | None = None
    for r in range(rounds):
        t = time.perf_counter()
        code, error = "", None
        try:
            code = attacker.write_fake_site_code(context, feedback)
        except Exception as e:  # refusal, API error: the round still counts
            error = f"attacker failed: {type(e).__name__}: {e}"
        attacker_s = round(time.perf_counter() - t, 3)
        call = getattr(attacker, "last_call", None)
        base = {
            "round": r,
            "threshold": suite.threshold,
            "attacker_id": attacker.attacker_id,
            "attacker_kind": kind,
            "attacker_model": call.model if call else attacker.model,
            "attacker_s": attacker_s,
            "llm": asdict(call) if call and kind == "llm" else None,
        }

        if error is not None:
            rnd = Round(code="", sandbox_id="", ok=False, scores=None, combined=None, escaped=False, damage=None, error=error, **base)
            feedback = {"round": r + 1, "result": "error", "error": error}
        else:
            input_seed = attacker.seed * 100 + r
            result = runner.run(code, {**context, "seed": input_seed}, timeout=timeout)
            sandbox = {"sandbox_id": result.sandbox_id, "sandbox_s": round(result.runtime_s, 3), "timings": result.timings}
            if not result.ok:
                error = result.stderr.strip()[-ERROR_FEEDBACK_CHARS:] or "sandbox run failed with no output"
                rnd = Round(code=code, ok=False, scores=None, combined=None, escaped=False, damage=None, error=error, **sandbox, **base)
                feedback = {"round": r + 1, "result": "error", "error": error, "stdout_tail": result.stdout[-500:]}
            else:
                try:
                    fake = validate_schema(result.output, site_id)
                    arms = fake_arms(result.output)
                except SchemaError as e:
                    rnd = Round(code=code, ok=False, scores=None, combined=None, escaped=False, damage=None, error=f"schema: {e}", **sandbox, **base)
                    feedback = {"round": r + 1, "result": "error", "error": f"schema: {e}"}
                else:
                    scores = suite.score_site(fake, real_sites)
                    escaped = scores.combined < suite.threshold
                    fired = scores.fired(suite.threshold)
                    diagnostics = explain_fired(suite, fake, real_sites, fired)
                    rnd = Round(
                        code=code, ok=True, scores=scores, combined=scores.combined, escaped=escaped, damage=_damage(trial, fake),
                        fired=fired, diagnostics=diagnostics, n_patients=len(fake.tables["patients"]),
                        fake_output=result.output, input_seed=input_seed,
                        claimed_arms=arms.value_counts().to_dict() if arms is not None else None, **sandbox, **base,
                    )
                    feedback = {
                        "round": r + 1,
                        "result": "escaped" if escaped else "detected",
                        "checks_fired": fired,
                        "why_checks_fired": diagnostics,
                        "scores": scores.per_check,
                        "combined": scores.combined,
                        "threshold": suite.threshold,
                    }
        feedback["previous_code"] = code
        history.append(rnd)
        if save:
            run["rounds"].append(asdict(rnd))
            save_run(run)
        if on_round:
            on_round(rnd)
        if stop_on_escape and rnd.escaped:
            break
    return history
