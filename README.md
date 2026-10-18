# Probe

**Penetration testing for clinical trials.**

Probe attacks a clinical trial before a real attacker or a real accident does. Then it proves the fix works on an attack it has never seen.

> **Probe never touches, alters, or "fixes" patient data.** It patches the *monitoring system* and the *information boundary*. It tests fraud checks and access policies, not records.

Built at HackHarvard 2026 for the Regeneron track (Reinvent Clinical Trials), with Daytona, Chalk, and Factory.

---

## The idea: a trial's Integrity Contract

Every randomized trial makes promises it has to keep. Probe writes them down as an **Integrity Contract** and searches for counterexamples to it.

| Property | Rule | Tested by |
|---|---|---|
| **Data authenticity** | Fabricated site data must not be accepted as authentic | Impostor |
| **Treatment confidentiality** | Coordinator- and assessor-visible data must not predict who got the real drug | Tell |
| **Statistical integrity** | Undetected integrity failures must not materially change the trial's conclusion | Damage + Breaking Point analysis |
| **Safety accessibility** | Required safety information stays visible to the people who need it | Constraint on every fix |
| **Operational utility** | Defenses must keep required site tasks possible | Constraint on every fix |

Every property starts as **UNTESTED**. A run flips each one to **HELD** or **BROKEN**, and a broken property comes with the counterexample that broke it.

## Why

Every trial relies on two assumptions, and both are usually checked after the fact, if at all:

1. **The data is real.** Central statistical monitoring exists, but it's tuned against human fakers. Taloni et al. (2025, *JAMA Ophthalmology*) showed a custom GPT could refine fabricated datasets until some passed forensic checks as authentic.
2. **The blind holds.** In practice the drug leaves fingerprints in ordinary paperwork: side effects cause extra visits, and dose changes create pharmacy records. A review of 300 blinded trials found only 8% explicitly reported the risk of unblinding.

Probe attacks both before the first patient is enrolled, the same way a bank hires pentesters before real attackers show up.

## Names

The pitch uses short names; the code uses names that say what each piece does.

| Pitch name | Code |
|---|---|
| Trial Twin | `engine/simulator` |
| Sentinel | `engine/fraud_checks` |
| Impostor | `engine/fake_data` |
| Tell | `engine/blind_leak` (attack) |
| Seal | `engine/blind_leak/cheapest_fix.py` |
| Sparring | training attacker |
| Stranger | test attacker |
| Patch | `engine/patch` |
| Breaking Point | `engine/analysis/breaking_point.py` |
| Guess Who, Integrity Contract, Probe Report | unchanged |

## The two attack heads

### Impostor: fake data (the main attack)

1. An LLM attacker writes Python that fabricates an entire trial site.
2. That code runs in a **Daytona** sandbox. No LLM-written code ever runs on a laptop.
3. Sentinel, the fraud-check suite, scores the fake site. The attacker sees which checks fired and rewrites its code. This repeats for several rounds.
4. Every fake that escapes becomes a counterexample. **Factory Droid** acts as the defender and writes a new fraud check (the Patch). The check ships only if false alarms on real sites stay flat.
5. A **brand-new test attacker** (Stranger: different model, prompt, and seed, never seen during patching) receives baseline v0 feedback only. The same saved submissions are scored against frozen v0 and v1, without giving v1 feedback to the attacker. The training attacker (Sparring) is the one used for patching. See [Stranger's protocol and commands](docs/stranger.md).
6. **Damage:** how far the undetected fakes move the trial's treatment effect, and whether a drug with zero true effect could be made to look significant.
7. **Breaking Point:** how many undetected fake sites it takes to flip the trial's conclusion, before vs after patching.

### Tell: blind leak

1. A classifier sees **only** the site coordinator's view of the data and predicts each patient's treatment arm. It is cross-validated by site and compared against a permutation null.
2. SHAP and drop-column attribution name the fields that leak the arm.
3. Each leaking field maps to a real-world remedy: an unblinded pharmacist, routing efficacy labs through a central lab, sham titration in the placebo arm, or matched kits. Probe brute-forces every combination and picks the **cheapest** one (the Seal) that brings accuracy back to chance while operational tasks stay supported.
4. Adverse events are never hidden. When the leak comes from safety data, the remedy is a separate blinded outcome assessor.

> **We use AI where an attacker would.** Everything that judges the attack (the statistical checks, the classifier, the primary analysis, every metric) is plain, deterministic statistics you can audit.

### What Probe does not do

- It doesn't touch, alter, or "fix" patient data, and it doesn't use real trial data.
- It doesn't fix leaks that happen in the room, such as patients visibly feeling sick. It can only report how much leakage is left in the data.
- It doesn't hide safety information from anyone who needs it.
- It makes no claim of regulatory validity or real-world fraud detection. It's a pre-launch stress test.

---

## The simulated trial (Trial Twin)

The fictional drug **PRB-101** treats type 2 diabetes. The primary endpoint is the change in HbA1c from baseline to week 24. All effect sizes are simulation parameters we chose, not claims about any real drug.

```
NHANES adults with diabetes-range HbA1c        (real, public physiology)
  ↓ 1:1 block randomization within site        (seeded, logged)
  ↓ 20 sites × ~40 patients
  ↓ visits: screen, baseline, wk 2/4/8/12/16/20/24 (+ unscheduled)
  ↓ HbA1c trajectory = baseline + arm effect + patient noise + site effect
  ↓ documented mechanisms that leave operational traces:
      nausea on drug       → unscheduled visits, antiemetics, AE entries
      dose titration       → pharmacy dispensing events
      lower glucose        → local fingerstick values differ
      cold-chain drug      → kit storage / temperature log entries
  ↓ ground truth written to a separate, locked table
```

- **Scenario A:** the drug works (−0.6 HbA1c vs −0.1 on placebo).
- **Scenario B:** the drug is useless (its effect equals placebo). This is the scenario for the damage demo.
- **Control:** with all mechanisms turned off, the blind-leak attack must score at chance. If it doesn't, that's a bug, not a finding.

**Bias firewall:** whoever builds the blind-leak attack never reads the simulator code. They see only `docs/schema.md` and the exported views. Every leak mechanism and its strength is documented in `docs/assumptions.md`, and mechanism strengths are configurable so results can be shown across a range of settings.

### Sentinel v0: fraud checks (published central-statistical-monitoring methods)

| Check | What it catches |
|---|---|
| Terminal digit preference | Rounding to 0/5 in BP readings |
| Variance / inlier | Fakes that are too tidy or too average |
| Correlation structure | Broken relationships (SBP↔DBP, weight↔BMI, glucose↔HbA1c) |
| Within-patient autocorrelation | Trajectories that are too smooth or too random |
| Date anomalies | Weekend visits, perfect visit-window adherence |
| AE under-reporting | Fakers forgetting side effects |
| Missingness | Fakes with no missing data |

The check-suite threshold is calibrated so that no more than 5% of real sites get flagged, and it is frozen before any attack runs.

---

## Evaluation

**Primary Stranger metric:** the fraction of fixed-budget attack runs with at least one valid fake site that escapes detection, measured on identical submissions for frozen v0 and v1. Counts and Wilson intervals use runs because adaptive rounds within a run are not independent. The saved report also gives valid, error, and escaped round totals. False alarms in the Stranger report are measured on the requested trial's honest sites, separately from Patch's held-out cohort.

**Measured Stranger pilot:** Gemini 3 Flash preview, four runs with three rounds each: seven valid submissions and five code/schema errors. Neither v0 nor v1 had an escaping run (0/4 each). This pilot does **not** establish improved detection by v1, because no submission escaped v0. [Protocol, saved results, and limitations](docs/stranger.md#measured-pilot).

| Metric | Target direction |
|---|---|
| `fraud_evasion_rate` (training attacker) | down after patching |
| `generalization_to_held_out_attack` (test attacker) | down after patching (**the main claim**) |
| `legitimate_false_positive_rate` | flat (≤ +1 pt) |
| `damage_effect_shift` | reported honestly |
| `unblinding_accuracy` / AUC | well above 50% before, ≈50% after |
| `permutation_null` | shows that "above chance" is real |
| `operational_utility_retained` | high |
| `breaking_point` | higher after patching |
| `cheapest_fix_cost` | reported, labeled as an assigned cost |

Evasion is reported as counts with Wilson 95% intervals. Blind-leak accuracy uses cross-validation grouped by site, with a permutation p-value. **No number appears in this repo, the demo, or the pitch until it has been measured.** Chalk metric logging remains unfinished.

---

## Architecture

```
┌──────────────── Frontend (Next.js · Tailwind · Recharts) ────────────────┐
│   Setup + Contract · Impostor Live · Patch + Stranger · Tell · Report    │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ REST + SSE
┌────────────────────────────────▼──────── Backend (FastAPI) ──────────────┐
└───┬─────────────┬──────────────────┬───────────────────┬─────────────────┘
┌───▼──────┐ ┌────▼─────┐   ┌────────▼─────────┐   ┌─────▼──────┐
│simulator │ │fake_data │   │fraud_checks+patch│   │ blind_leak │
│ (NHANES) │ │   loop   │   │  (Factory Droid) │   │            │
└───┬──────┘ └────┬─────┘   └────────┬─────────┘   └─────┬──────┘
    │             └── Daytona sandboxes (all LLM-written code) ──┘
    ▼                                                    ▼
┌──────────────────────────────── SQLite ──────────────────────────────────┐
└────────────────────────────────┬─────────────────────────────────────────┘
                                 ▼
                    Chalk (features + eval metrics)
```

## Tech stack

| Layer | Choice | Fallback |
|---|---|---|
| Backend | Python 3.11, FastAPI + SSE | Flask |
| Frontend | Next.js 14, React, Tailwind, Recharts | Streamlit |
| Data / stats | pandas, NumPy, SciPy, statsmodels | n/a |
| ML / attribution | LightGBM, SHAP | sklearn, drop-column only |
| Storage | SQLite | Parquet |
| LLM attackers | Claude / GPT / Gemini (training and test attackers on different models) | Same model with a different prompt and seed |
| Sandbox | Daytona | Local Docker |
| Evals | Chalk | Local metrics table |
| Defender agent | Factory Droid | Fallback classifier check |
| Data source | NHANES (public, de-identified, CDC) | Published distributions |

## Repository layout

```
probe/
├── probe-frontend/ Next.js app: 5 screens, charts, SSE client (see CLAUDE.md for status)
├── backend/        FastAPI: routes, run state, background tasks, SSE
├── engine/
│   ├── simulator/     NHANES load, trial builder, mechanisms, views
│   ├── fraud_checks/  SiteCheck base, check suite, calibration, versions
│   ├── fake_data/     training + test attacker prompts, loop, schema validation
│   ├── patch/         Droid task builder, acceptance gate, fallback check
│   ├── blind_leak/    classifier, permutation, SHAP, remedies, utility, cheapest fix
│   └── analysis/      ANCOVA primary analysis, damage, breaking point
├── integrations/   daytona.py, chalk.py, factory.py (thin, mockable)
├── evals/          metric definitions, scenario suite, results export
├── scripts/        download_nhanes.py, precompute_demo.py, run_full_eval.py
├── data/           raw NHANES (gitignored), processed parquet, demo cache
├── tests/          imports, every route in mock mode, mechanisms-off control
└── docs/           schema.md, assumptions.md, pitch notes
```

## Getting started

```bash
git clone https://github.com/garvnn/probe.git && cd probe
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

```bash
make dev     # API on :8000 with autoreload
make test    # pytest
make mock    # API serving fixtures only (DEMO_MODE=mock), for frontend work
make web     # frontend on :3000 (first time: cd probe-frontend && npm install)
make types   # regenerate frontend API types after changing backend/models.py
```

```
ANTHROPIC_API_KEY=        # or OPENAI_API_KEY
TRAINING_ATTACKER_MODEL=
TEST_ATTACKER_MODEL=
DAYTONA_API_KEY=
CHALK_CLIENT_ID=
CHALK_CLIENT_SECRET=
FACTORY_API_KEY=
DEMO_MODE=mock            # mock | cached | live
DEMO_SEED=2026
DB_PATH=data/probe.db
```

`DEMO_MODE=mock` serves the JSON fixtures in `backend/mocks/` (every payload tagged `"_mock": true`) so the frontend can be built before the engine exists. `DEMO_MODE=cached` replays a precomputed run (`scripts/precompute_demo.py`) through the same UI at real speed, as a backup in case the APIs fail during the demo.

## Team

| Person | Owns |
|---|---|
| **Garv** (Data) | Simulator, NHANES pipeline, `schema.md`, `assumptions.md`, fraud-check core (base, suite, calibration, core checks), ground truth, primary analysis, damage, breaking point |
| **Shreyas** (Fake data) | Training + test attacker prompts, fake-data loop, acceptance gate, Droid task, Daytona, Factory, LLM integrations, demo precompute |
| **Ajay** (Blind leak + evals) | Blind leak (features, classifier, permutation, SHAP, remedies, utility, cheapest fix), rate checks, fallback check, Chalk, evals |
| **Akarsh** (Frontend + pitch) | Next.js frontend, Guess Who, report page, demo script, Devpost |

`main` should always be in a demoable state. Branch names: `data/*`, `fake_data/*`, `blind/*`, `ui/*`.

## Responsible use

Probe is a defensive stress-test harness. Its attackers exist only to find weaknesses in fraud monitoring and blinding controls before a real trial depends on them. It runs only on semi-synthetic data, and attacker code runs only in isolated sandboxes.
