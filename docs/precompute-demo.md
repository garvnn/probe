# Measured cached demo

Start from the existing locked trial database (`DB_PATH`, default `data/probe.db`).
The command does not generate a replacement trial, run a new attacker, or refit
frozen Sentinel versions. It requires the committed seed-43 Impostor run and
`engine/fraud_checks/frozen/patch_report.json`.

```sh
DEMO_SEED=2026 .venv/bin/python -m scripts.precompute_demo
DEMO_MODE=cached CACHED_REPLAY_SPEED=0 .venv/bin/python -m uvicorn backend.main:app
# In a second terminal:
.venv/bin/python -m scripts.check_cached_demo
```

Install missing dependencies with `uv pip install -r requirements.txt`. Direct
execution of `scripts/precompute_demo.py` also works. Seed/scenario overrides
other than 2026/B are rejected. `--out` changes the output directory; set
`DEMO_CACHE_DIR` to the same directory when serving it.

## Cache layout and provenance

The existing `fd_20261017T202527_llm_s43.json` is reused, adding `_mock: false`.
The saved attacker source is replayed as text only. Saved fake tables and their
own arm assignments are deserialized; source is never executed.

Measured route payloads live in `data/demo_cache/precomputed/`. The manifest maps
exact request parameters to response files, records source hashes, pins the
Impostor run so a newer local run cannot silently replace it, and lists skipped
measurements. Every generated payload is `_mock: false`. An unsupported request
or missing cache keeps the existing `_mock: true` fixture rather than relabeling
it as measured. A malformed measured cache produces an error.

Tell uses the coordinator export and the existing grouped-by-site classifier,
200 within-site permutations, and seed 2026. Its p-values, null range, folds,
and leak attributions are saved; the API exposes the p-values and permutation
settings alongside the existing fields.

Patch uses the final frozen v0/v1 table, including the final recalibrated v1
false-alarm rate, rather than the earlier pre-recalibration gate rate. The new
`GET /fraud-checks/held-out` serves the frozen report. Its 13 escapes belong to
four held-out runs; adaptive rounds are not independent. This is not Stranger's
different-model evaluation, and the existing frontend calls Stranger separately.

Trial math calls the existing `damage.effect_shift` and
`breaking_point.breaking_point`. Each saved escaped fake is used once, in saved
round order, and checked against each frozen suite. Curves stop at the number of
available accepted saved sites (at most six); no repeated sites or extrapolated
points are invented. A null `break_k` only covers that observed range.

Contract and report payloads are assembled from these results. A measured effect
shift is reported without claiming a conclusion flip. Safety accessibility and
operational utility remain UNTESTED unless separately evaluated; `_mock: false`
does not imply all properties held.

## Intentional gaps on this branch

Seal is still a stub on the `main` base of this branch. It is skipped, so its
cheapest-fix/policy endpoints retain sample badges. If Seal is present on the
base of a future run, the same command includes its search and selected policy.
Guess Who and setup summary/detail are not precomputed. Stranger has no measured
result here; v1 has not been tested against a different-model attacker. These
endpoints retain sample badges. The run-through reports them explicitly.

No frontend files are changed. Consequently, the current held-out UI remains
sample data even though the separate frozen Patch held-out endpoint is real.

## Measured run-through on this branch

Tell (seed 2026): accuracy **0.76**, AUC **0.8509125**, permutation-null accuracy
range **0.45625–0.53875**, p-value **0.004975124378109453** (200 shuffles).
Frozen Patch: **13/13** v0 escapes caught across **4** held-out runs; final
honest-site false alarms **3.9%** for both v0 and v1.

The committed Impostor run contains four saved v0 escape sites (zero-based rounds
7, 8, 13, 14; displayed round 8 is zero-based 7). Re-scoring those saved sites
admits four under v0 and none under v1. The v0 curve covers k=0..4, with no
conclusion flip; the v1 curve contains only k=0. Neither establishes a threshold
beyond the observed range.

All 20 HTTP checks returned 200, including all 15 round events plus the SSE done
event. `precomputed/run_through.json` contains the per-endpoint record.

| Endpoint group | Result |
|---|---|
| Contract, including mixed query | Measured |
| Impostor create/detail/stream | Measured |
| Patch | Measured |
| `/fraud-checks/held-out` | Measured frozen Patch report |
| `/test-attacker/eval` (current held-out UI) | Sample |
| Tell coordinator | Measured |
| Tell assessor, policy, Seal | Sample (Seal stub on base) |
| Breaking point v0 and v1 | Measured, within observed range only |
| Report | Measured |
| Setup/create/detail and Guess Who cards/score | Sample |

These endpoint checks do not claim browser rendering or interaction testing.
