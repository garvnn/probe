# Probe

**Penetration testing for clinical trials.**

Probe attacks a clinical trial before a real attacker or a real accident does. Then it proves the fix works on an attack it has never seen.

> **Probe never touches, alters, or "fixes" patient data.** It hardens the *monitoring system* and the *information boundary*. It tests detectors and access policies, not records.

Built at HackHarvard 2026 for the Regeneron track (Reinvent Clinical Trials), with Daytona, Chalk, and Factory.

---

## The idea: a trial's Integrity Contract

Every randomized trial makes promises it has to keep. Probe writes them down as an **Integrity Contract** and searches for counterexamples to it.

| Property | Rule | Tested by |
|---|---|---|
| **Data authenticity** | Fabricated site data must not be accepted as authentic | Data Forger |
| **Treatment confidentiality** | Coordinator- and assessor-visible data must not predict who got the real drug | Blind Breaker |
| **Statistical integrity** | Undetected integrity failures must not materially change the trial's conclusion | Damage + integrity-margin analysis |
| **Safety accessibility** | Required safety information stays visible to the people who need it | Constraint on every fix |
| **Operational utility** | Defenses must keep required site tasks possible | Constraint on every fix |

Every property starts as **UNTESTED**. A run flips each one to **HELD** or **BROKEN**, and a broken property comes with the counterexample that broke it.

## Why

Every trial relies on two assumptions, and both are usually checked after the fact, if at all:

1. **The data is real.** Central statistical monitoring exists, but it's tuned against human fakers. Taloni et al. (2025, *JAMA Ophthalmology*) showed a custom GPT could refine fabricated datasets until some passed forensic checks as authentic.
2. **The blind holds.** In practice the drug leaves fingerprints in ordinary paperwork: side effects cause extra visits, and dose changes create pharmacy records. A review of 300 blinded trials found only 8% explicitly reported the risk of unblinding.

Probe attacks both before the first patient is enrolled, the same way a bank hires pentesters before real attackers show up.

## The two attack heads

### Data Forger (the main attack)

1. An LLM attacker writes Python that fabricates an entire trial site.
2. That code runs in a **Daytona** sandbox. No LLM-written code ever runs on a laptop.
3. The fraud detector scores the fake site. The attacker sees which checks fired and rewrites its code. This repeats for several rounds.
4. Every fake that escapes becomes a counterexample. **Factory Droid** acts as the defender and writes a new detector check. The check ships only if false alarms on real sites stay flat.
5. A **brand-new attacker B** (different model, prompt, and seed, never used during hardening) attacks the hardened detector. We report evasion before and after hardening against attacker B.
6. **Damage:** how far the undetected fakes move the trial's treatment effect, and whether a drug with zero true effect could be made to look significant.
7. **Integrity margin:** how many undetected fake sites it takes to flip the trial's conclusion, before vs after hardening.

### Blind Breaker

1. A classifier sees **only** the site coordinator's view of the data and predicts each patient's treatment arm. It is cross-validated by site and compared against a permutation null.
2. SHAP and drop-column attribution name the fields that leak the arm.
3. Each leaking field maps to a real-world remedy: an unblinded pharmacist, routing efficacy labs through a central lab, sham titration in the placebo arm, or matched kits. Probe brute-forces every combination and picks the **cheapest** one that brings accuracy back to chance while operational tasks stay supported.
4. Adverse events are never hidden. When the leak comes from safety data, the remedy is a separate blinded outcome assessor.

> **We use AI where an attacker would.** Everything that judges the attack (the statistical checks, the classifier, the primary analysis, every metric) is plain, deterministic statistics you can audit.

### What Probe does not do

- It doesn't touch, alter, or "fix" patient data, and it doesn't use real trial data.
- It doesn't fix leaks that happen in the room, such as patients visibly feeling sick. It can only report how much leakage is left in the data.
- It doesn't hide safety information from anyone who needs it.
- It makes no claim of regulatory validity or real-world fraud detection. It's a pre-launch stress test.

---

## The simulated trial

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
- **Control:** with all mechanisms turned off, the Blind Breaker must score at chance. If it doesn't, that's a bug, not a finding.

**Bias firewall:** whoever builds the Blind Breaker never reads the generator code. They see only `docs/schema.md` and the exported views. Every leak mechanism and its strength is documented in `docs/assumptions.md`, and mechanism strengths are configurable so results can be shown across a range of settings.

### Detector v0 (published central-statistical-monitoring methods)

| Check | What it catches |
|---|---|
| Terminal digit preference | Rounding to 0/5 in BP readings |
| Variance / inlier | Fakes that are too tidy or too average |
| Correlation structure | Broken relationships (SBP↔DBP, weight↔BMI, glucose↔HbA1c) |
| Within-patient autocorrelation | Trajectories that are too smooth or too random |
| Date anomalies | Weekend visits, perfect visit-window adherence |
| AE under-reporting | Fakers forgetting side effects |
| Missingness | Fakes with no missing data |

The detection threshold is calibrated so that no more than 5% of real sites get flagged, and it is frozen before any attack runs.

---

## Evaluation

**Primary metric:** held-out evasion rate. This is the fraction of attacker B's fake sites that escape detection, measured for detector v0 and for the hardened detector vN at the same false-alarm budget.

| Metric | Target direction |
|---|---|
| `fraud_evasion_rate` (attacker A) | down after hardening |
| `generalization_to_held_out_attack` (attacker B) | down after hardening (**the main claim**) |
| `legitimate_false_positive_rate` | flat (≤ +1 pt) |
| `damage_effect_shift` | reported honestly |
| `unblinding_accuracy` / AUC | well above 50% before, ≈50% after |
| `permutation_null` | shows that "above chance" is real |
| `operational_utility_retained` | high |
| `integrity_margin` | higher after hardening |
| `minimum_fix_cost` | reported, labeled as an assigned cost |

Evasion is reported as counts with Wilson 95% intervals. Blind accuracy uses cross-validation grouped by site, with a permutation p-value. **No number appears in this repo, the demo, or the pitch until it has been measured.** All metrics are logged to **Chalk**.

---

## Architecture

```
┌──────────────── Frontend (Next.js · Tailwind · Recharts) ────────────────┐
│   Setup + Contract · Forger Live · Harden + Held-Out · Blind · Report    │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ REST + SSE
┌────────────────────────────────▼──────── Backend (FastAPI) ──────────────┐
└───┬─────────────┬──────────────────┬───────────────────┬─────────────────┘
┌───▼──────┐ ┌────▼─────┐   ┌────────▼─────────┐   ┌─────▼──────┐
│generator │ │  forger  │   │ detector + harden│   │   blind    │
│ (NHANES) │ │   loop   │   │  (Factory Droid) │   │  breaker   │
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
| LLM attackers | Claude / GPT (attacker A and B on different models) | Same model with a different prompt and seed |
| Sandbox | Daytona | Local Docker |
| Evals | Chalk | Local metrics table |
| Defender agent | Factory Droid | Fallback classifier check |
| Data source | NHANES (public, de-identified, CDC) | Published distributions |

## Repository layout

```
probe/
├── frontend/       Next.js app: 5 screens, charts, SSE client
├── backend/        FastAPI: routes, run state, background tasks, SSE
├── engine/
│   ├── generator/  NHANES load, trial builder, mechanisms, ground truth
│   ├── detector/   SiteCheck base, check battery, calibration, versions
│   ├── forger/     attacker prompts, loop, schema validation
│   ├── harden/     Droid task builder, acceptance gate, fallback check
│   ├── blind/      views, classifier, permutation, SHAP, remedies, utility
│   └── analysis/   ANCOVA primary analysis, damage metric
├── integrations/   daytona.py, chalk.py, factory.py (thin, mockable)
├── evals/          metric definitions, scenario suite, results export
├── scripts/        download_nhanes.py, precompute_demo.py, run_full_eval.py
├── data/           raw NHANES (gitignored), processed parquet, demo cache
├── tests/          generator sanity, mechanisms-off control, schema tests
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
```

```
ANTHROPIC_API_KEY=        # or OPENAI_API_KEY
ATTACKER_A_MODEL=
ATTACKER_B_MODEL=
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
| **Garv** (Data) | Generator, NHANES pipeline, `schema.md`, `assumptions.md`, detector core (base, calibration, core checks), ground truth, primary analysis, damage, integrity margin |
| **Shreyas** (Forger) | Attacker prompts, forger loop, acceptance gate, Droid task, Daytona, Factory, LLM integrations, demo precompute |
| **Ajay** (Blind Breaker + evals) | Blind Breaker (features, classifier, permutation, SHAP, remedies, utility, minimum fix), rate checks, fallback check, Chalk, evals |
| **Akarsh** (Frontend + pitch) | Next.js frontend, Guess Who, report page, demo script, Devpost |

`main` should always be in a demoable state. Branch names: `data/*`, `forger/*`, `blind/*`, `ui/*`.

## Responsible use

Probe is a defensive stress-test harness. Its attackers exist only to find weaknesses in fraud monitoring and blinding controls before a real trial depends on them. It runs only on semi-synthetic data, and attacker code runs only in isolated sandboxes.
