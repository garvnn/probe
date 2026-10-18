# Probe

**Penetration testing for clinical trials.**

A trial makes promises. Probe writes them down as an **Integrity Contract** and searches for counterexamples: fabricated sites that pass monitoring, or operational records that reveal treatment assignment. It then evaluates changes to the monitoring system and access policies.

> **Probe never touches, alters, or “fixes” patient data.** We patch the monitoring system and the information boundary, never patient records.

Built at HackHarvard 2026 for the Regeneron Reinvent Clinical Trials track, with **Daytona** and **Chalk**. All trial data is semi-synthetic: public NHANES physiology plus a simulated trial layer. Probe does not operate on real clinical-trial patient records.

## Integrity Contract

| Property | Promise | How Probe tests it |
|---|---|---|
| **Data authenticity** | Fabricated site data must not be accepted as authentic | Impostor attacks Sentinel; Patch evaluates a learned monitoring check |
| **Treatment confidentiality** | Role-visible records must not reveal treatment assignment | Tell predicts treatment arm; Seal evaluates access-policy remedies |
| **Statistical integrity** | Undetected integrity failures must not materially change the trial’s conclusion | ANCOVA damage analysis and Breaking Point |
| **Safety accessibility** | Required safety information stays visible to those who need it | Investigator adverse-event access is a hard constraint |
| **Operational utility** | Defenses must preserve required site tasks | Explicit task requirements constrain remedy selection |

Properties begin **UNTESTED**. Measurements can produce a counterexample (**BROKEN**) or support a property within the tested scope (**HELD**). Missing evidence stays UNTESTED.

## Measured results

These are measurements, not demo targets or claims of clinical validation.

### Impostor, Sentinel, and Patch

**Impostor** writes a fabricated trial site, runs its code in a Daytona sandbox, and receives feedback from **Sentinel**. Saved rounds preserve the code, check scores, and fabricated outputs for replay and evaluation.

**Patch** adds a learned monitoring check behind an acceptance gate. Sentinel v0 and v1 are frozen; v1 is locked and is not tuned again.

- **Sentinel v1 caught every v0 escape across four held-out runs: 13 fabricated sites that v0 missed.** Adaptive rounds within a run are not independent trials.
- **False alarms stayed at 3.9% on 1,000 held-out honest sites** for both frozen versions.
- The accepted monitoring check is the learned fallback classifier check.

The final frozen comparison is in [patch_report.json](engine/fraud_checks/frozen/patch_report.json). Its final v1 table reflects recalibration; the earlier gate section records the pre-recalibration result.

### Tell: can the coordinator infer treatment?

On `tr_2026_B`, the Linux measurement gives **74.9% accuracy and 0.853 AUC** from the coordinator view. The mechanisms-off control is **approximately 50% accuracy**, at chance.

Tell builds features only from a role’s exported view, uses cross-validation grouped by site, and compares the observed accuracy against a within-site permutation null. SHAP and drop-column attribution identify leaking fields. Ground-truth treatment labels enter scoring only, after features are built.

The headline uses the Linux seed-0 measurement documented in [Seal’s results](docs/seal.md). The [cached demo](docs/precompute-demo.md) uses seed 2026 for classifier/permutation randomness; its exact replay values differ. The trial seed is 2026 in both cases.

**Bias firewall:** Tell’s implementation is developed from [docs/schema.md](docs/schema.md) and `export_view()` output, without inspecting simulator implementation.

### Seal: confidentiality has an operational cost

Seal measures all 16 subsets of four remedies on the **coordinator view**. It minimizes assigned relative cost, subject to AUC ≤0.55, utility ≥0.90, and investigator safety access.

| Policy | Coordinator AUC | Tasks retained | Assigned cost |
|---|---:|---:|---:|
| No remedies | 0.853 | 6/6 | 0 |
| `unblinded_pharmacist` | 0.638 | 6/6 | 3 |
| `sham_titration` + `matched_kits` | 0.511 | 5/6 | 2 |

One remedy cuts leakage from **0.85 to 0.64 AUC with zero disruption under the task model**. Closure to approximately chance costs **one operational task**: the cheapest combination reaching the AUC ceiling masks storage condition and temperature, losing the inventory-monitoring task.

Utility is an **assigned model** of six equally weighted tasks, not measured staff productivity. Costs are **assigned relative units**, not monetary estimates. With six binary tasks, retaining five gives utility 0.833; therefore **no combination meets both the current AUC and utility thresholds**, and Seal returns no recommendation. All **493 investigator adverse-event rows remained unchanged across all 16 combinations**.

See [the task model and measured tradeoff](docs/seal.md). No thresholds or utility assumptions were changed to manufacture a feasible result.

### Damage and Breaking Point

The primary analysis is ANCOVA on week-24 HbA1c change, with baseline HbA1c and site as covariates. Damage analysis uses saved escaped fakes’ own arm assignments; it never runs a new attacker.

The committed seed-43 run contains four saved v0 escapes. Adding those sites shifts the estimated effect, but **does not flip the conclusion through four sites**. Frozen v1 rejects all four, so its accepted-fake curve contains only the baseline. A missing breaking point does not establish resilience beyond the observed range.

## Daytona and Chalk

- **Daytona:** all attacker code runs in isolated sandboxes. Saved attacker source is replayed as text; cache generation deserializes saved outputs without executing that source.
- **Chalk:** Tell’s features are defined in Chalk, deployed, and represented in a populated feature catalog. The treatment-arm label is kept out of the feature catalog and feature inputs; it is used only for scoring. Feature deployment is distinct from the generic metric-logging adapter in `integrations/chalk.py`, which remains a stub.

## Run the demo

Use Python 3.11 and `uv`:

```sh
git clone https://github.com/garvnn/probe.git
cd probe
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env
```

Keep keys in the gitignored `.env`. Daytona and the configured model provider are needed for live attacker execution; replaying committed caches does not require a new attacker call.

```sh
# API: explicit sample fixtures
make mock

# Frontend, in another terminal
cd probe-frontend
npm install
npm run dev
```

For measured cached responses:

```sh
DEMO_MODE=cached CACHED_REPLAY_SPEED=0 .venv/bin/python -m uvicorn backend.main:app

# Endpoint and SSE audit, in another terminal
.venv/bin/python -m scripts.check_cached_demo
```

To regenerate caches from the existing locked `tr_2026_B` database:

```sh
DEMO_SEED=2026 .venv/bin/python -m scripts.precompute_demo
```

The precompute command reuses the committed seed-43 Impostor run and frozen Patch report. It does not generate a replacement trial or a new attacker run. See [cache generation, provenance, and remaining sample endpoints](docs/precompute-demo.md).

`DEMO_MODE` selects `mock`, `cached`, or `live`. Missing cached measurements retain their **`_mock: true`** sample badges. A measured payload is **`_mock: false`**; that does not mean every Integrity Contract property has been tested or held. Live mode is implemented per route, not a promise that every screen is complete.

```sh
.venv/bin/python -m pytest -q  # tests
make dev                     # API with autoreload
make types                   # regenerate frontend types from a running API
```

## Repository layout

```text
probe-frontend/             Next.js UI, charts, and SSE replay
backend/                    FastAPI routes, response models, mocks, and cache lookup
engine/
  simulator/                Trial Twin: NHANES-based trial generation and role exports
  fraud_checks/             Sentinel: checks, calibration, frozen v0/v1, Patch report
  fake_data/                Impostor: attacker loop, saved outputs, and replay cache
  patch/                    Patch: learned check, acceptance gate, frozen-suite pipeline
  blind_leak/               Tell and Seal: features, classifier, null, attribution, remedies
  analysis/                 ANCOVA, damage, and Breaking Point
integrations/               Sandbox, model-provider, and integration adapters
scripts/                    Precompute, cached endpoint audit, and run commands
evals/                      Ground-truth scoring and evaluation interfaces
data/                       NHANES base and saved demo artifacts
  demo_cache/precomputed/   Measured response payloads, provenance, endpoint audit
docs/                       Public schema, assumptions, ownership, and measured results
tests/                      Statistical, engine, API, and cache regression tests
```

See [docs/OWNERS.md](docs/OWNERS.md) for team ownership.

## Limitations and next steps

- **Sentinel v1 has not been tested against a different-model attacker.** That evaluation belongs to future work, not the measured results above. Held-out runs are not evidence of different-model generalization.
- All findings concern this semi-synthetic trial and these frozen checks. They do not establish regulatory validity, clinical safety, or real-world fraud-detection performance.
- Seal currently finds no policy satisfying both confidentiality and the declared utility floor. Policy selection on the same trial is not independent validation of the chosen policy.
- Tell tests information in exported records. It cannot test clues outside the data, such as what a participant visibly experiences.
- Existing caches were generated before Seal was merged; their Seal/policy and other missing measurements remain badged samples until regenerated. The current held-out UI calls the separate test-attacker endpoint; the frozen Patch evidence is served at `/fraud-checks/held-out`.
- Complete generic metric logging, extend independently held-out evaluation, and measure additional policies without hiding investigator safety information.

Probe is a defensive stress-test harness. **We never touch patient data.**
