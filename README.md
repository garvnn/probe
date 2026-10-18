# Probe

**Penetration testing for clinical trials.**

Probe attacks a clinical trial before a real attacker or a real accident does. Then it checks whether the fix holds up against attacks it never trained on.

> **Probe never touches, alters, or "fixes" patient data.** It patches the *monitoring system* and the *information boundary*. It tests fraud checks and access policies, not records.

Built at HackHarvard 2026 for the Regeneron track (Reinvent Clinical Trials), with Daytona and Chalk.

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

| Name | What it is | Code |
|---|---|---|
| **Trial Twin** | The simulated trial | `engine/simulator` |
| **Sentinel** | The fraud-check suite (v0 = published checks, v1 = patched) | `engine/fraud_checks` |
| **Impostor** | The fake-data attack: an LLM writes code that fabricates a trial site | `engine/fake_data` |
| **Sparring** | The attacker Impostor runs against Sentinel | `engine/fake_data/prompts/training_attacker.md` |
| **Patch** | Learns a new check from Impostor's escapes and gates it before it ships | `engine/patch` |
| **Tell** | The blind-leak attack: predicts treatment arm from blinded views | `engine/blind_leak` |
| **Seal** | The cheapest set of remedies that closes Tell's leak | `engine/blind_leak/cheapest_fix.py` |
| **Breaking Point** | How many undetected fake sites it takes to flip the trial's conclusion | `engine/analysis/breaking_point.py` |

---

## Results

Every number below was measured on the simulated trial. Counts come with Wilson 95% intervals.

### Impostor vs. Sentinel

Sentinel v0 is the frozen suite of published central-statistical-monitoring checks. Patch fit a new check on the fakes from the training runs, and Sentinel v1 is v0 plus that check, recalibrated to the same false-alarm budget. Both suites were then scored on runs and honest sites that Patch never saw.

| | Sentinel v0 | Sentinel v1 |
|---|---|---|
| Held-out fakes that escaped v0, caught | 0 / 13 | **13 / 13** (95% CI 77–100%) |
| All held-out fakes caught | 38 / 51 = 75% | **51 / 51** (95% CI 93–100%) |
| False alarms on held-out honest sites | 39 / 1000 = 3.9% | **39 / 1000 = 3.9%** (95% CI 2.9–5.3%) |

- **Held-out fakes** come from 4 Impostor runs that were split off by run before fitting, so v1 never saw those runs. Rounds within a run are adaptive and not independent, so the 13 escapes are not 13 independent trials.
- **Held-out honest sites** are 1000 sites from Trial Twin seeds 301–350. None of them were used to fit the check or set its threshold.
- **False alarms:** at v0's threshold the new check pushed false alarms to 4.2% (42 / 1000). v1 was then recalibrated on separate seeds (1–50) to the 5% budget, and at that frozen threshold it flags the same 3.9% as v0.
- **Data authenticity:** BROKEN on v0, with 13 counterexamples. HELD on v1 against those 4 held-out runs. Source: `engine/fraud_checks/frozen/patch_report.json`.

### Tell: blind leak

Tell sees only the site coordinator's export of trial `tr_2026_B` (seed 2026). It uses 5-fold cross-validation with folds grouped by site (4 test sites per fold), and a null built from 200 within-site label shuffles.

| | Coordinator view, leaks on |
|---|---|
| Arm-prediction accuracy | **76%** (chance is 50%) |
| AUC | **0.85** |
| Permutation null, accuracy range | 45.6–53.9% |
| Permutation p-value | **0.005** (none of 200 shuffles matched it; 0.005 is the smallest p that 200 shuffles can give) |

- The strongest leak is the pharmacy titration-step field, which comes from the dose-titration mechanism.
- **Treatment confidentiality:** BROKEN for the coordinator view.

**Mechanisms-off control.** This is the same trial (seed 2026, scenario B) with every leak mechanism turned off, using the same Tell settings. Accuracy is **48.6%**, AUC 0.48, permutation p = 0.75, and the null range is 45.0–54.0%. Tell is at chance when there is nothing to find, so the 76% above is coming from the leaks.

### Seal: cheapest fix

Seal tried all 16 combinations of the four remedies. A combination qualifies if it gets AUC ≤ 0.55, keeps utility ≥ 0.90, and leaves investigators with access to safety data. **None of the 16 qualified.**

| Remedies | AUC | Utility | Assigned cost |
|---|---|---|---|
| None | 0.85 | 1.00 | 0 |
| Sham titration | 0.65 | 1.00 | 1 |
| Unblinded pharmacist | 0.64 | 1.00 | 3 |
| Sham titration + matched kits | **0.52** | 0.83 | 2 |
| Sham titration + central lab + matched kits | 0.48 | 0.67 | 4 |

- **No remedy set reaches chance without giving up a site task.** The best set that keeps all six tasks (unblinded pharmacist) still leaves AUC at 0.64.
- **Matched kits are the reason.** Every set that reaches chance includes them. Matched kits hide kit storage temperature, and under our task model that removes inventory monitoring (utility drops by 1/6).
- **This depends on an assumption we made.** If inventory monitoring could be handed to someone unblinded, sham titration + matched kits would qualify at cost 2. The task model is in `docs/seal.md`.
- **Source:** Seal and the control were measured on the seed-2026 trial rebuilt from the simulator, because the original locked database isn't in the repo. That rebuild matches the original's damage numbers to floating-point precision. Its coordinator Tell result is 75.9% accuracy and AUC 0.854, against 76.0% and 0.851 for the original.

---

## How it works

### Impostor: fake data

1. An LLM attacker (Sparring) writes Python that fabricates an entire trial site.
2. That code runs in a **Daytona** sandbox. No LLM-written code ever runs on a laptop.
3. Sentinel scores the fake site. The attacker is shown which checks fired, along with the ranges real sites fall in, and rewrites its code. This repeats for several rounds. Sparring's only goal is to pass the checks.
4. Every fake that escapes becomes a counterexample.
5. **Patch** fits a regularized logistic-regression check on site-level features (visit dates, kit temperatures, glucose and BP variability, and the v0 check scores), using honest sites and the escaped fakes from the training runs. The acceptance gate admits the check only if it catches the held-out escapes and keeps false alarms on held-out honest sites flat. After that, the suite is recalibrated to the 5% budget and frozen as v1.
6. **Damage:** how far the undetected fakes move the trial's treatment effect, and whether a drug with zero true effect could be made to look significant.
7. **Breaking Point:** how many undetected fake sites it takes to flip the trial's conclusion, before and after patching.

### Tell: blind leak

1. A classifier sees **only** the site coordinator's view of the data and predicts each patient's treatment arm. It is cross-validated with folds grouped by site and compared against a permutation null.
2. SHAP and drop-column attribution name the fields that leak the arm.
3. Each leaking field maps to a real-world remedy: an unblinded pharmacist, routing efficacy labs through a central lab, sham titration in the placebo arm, or matched kits. Probe tries every combination and picks the **cheapest** one (the Seal) that brings accuracy back to chance while keeping operational tasks possible, or reports that no combination qualifies. Remedy costs are assigned by us, not measured.
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
- **Scenario B:** the drug is useless (its effect equals placebo). This is the scenario for the damage analysis.
- **Control:** with all mechanisms turned off, Tell must score at chance. If it doesn't, that's a bug, not a finding.

**Bias firewall:** whoever builds Tell never reads the simulator code. They see only `docs/schema.md` and the exported views. Every leak mechanism and its strength is documented in `docs/assumptions.md`, and mechanism strengths are configurable so results can be shown across a range of settings.

### Sentinel v0: published central-statistical-monitoring checks

| Check | What it catches |
|---|---|
| Terminal digit preference | Rounding to 0/5 in BP readings |
| Variance | Fakes that are too tidy |
| Inlier | Patients that are too average |
| Correlation structure | Broken relationships (SBP↔DBP, weight↔BMI, glucose↔HbA1c) |
| Within-patient autocorrelation | Trajectories that are too smooth or too random |

The suite threshold is calibrated on Trial Twin seeds 1–50 so that no more than 5% of honest sites get flagged, and it was frozen (`engine/fraud_checks/frozen/v0.json`) before any attack ran.

---

## Evaluation

| Metric | How it's measured |
|---|---|
| Held-out escapes caught | Fakes from held-out Impostor runs that v0 missed, scored by v1. Counts with Wilson 95% CI |
| False alarms | Share of 1000 held-out honest sites flagged, at each suite's frozen threshold |
| Damage | Shift in the ANCOVA treatment effect when undetected fakes are included |
| Breaking Point | Fewest undetected fake sites that flip the trial's conclusion, v0 vs v1 |
| Tell accuracy / AUC | Cross-validation with folds grouped by site, so no site appears in both train and test |
| Permutation null | Arm labels shuffled within site and the whole CV pipeline rerun; p = (1 + #null ≥ observed) / (1 + #perms) |
| Mechanisms-off control | Tell's accuracy with every leak mechanism off; it must be ≈50% |
| Seal cost | Reported, labeled as an assigned cost |

**No number appears in this repo, the demo, or the pitch until it has been measured.**

---

## Limitations and next steps

- **Different-model attacker (Stranger).** The held-out runs above were produced by the same attacker setup that Patch trained against, just from different runs. The stronger test is a different model with a different prompt and seed, never seen during patching. Wiring for this exists (`TEST_ATTACKER_MODEL`, `engine/fake_data/prompts/test_attacker.md`), but we have not run it yet, so it is not a result.
- **Small held-out set.** 13 escapes from 4 runs. A perfect 13/13 still has a 95% lower bound of 77%.
- **Simulated data only.** Results describe Trial Twin, not any real trial's fraud or leak risk.
- **Defender.** Patch currently uses a learned logistic-regression check. An LLM defender that writes checks as code is stubbed (`integrations/factory.py`) but not used.

---

## Architecture

```
┌──────────────── Frontend (Next.js · Tailwind · Recharts) ────────────────┐
│   Setup + Contract · Impostor Live · Patch · Tell · Report               │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ REST + SSE
┌────────────────────────────────▼──────── Backend (FastAPI) ──────────────┐
└───┬─────────────┬──────────────────┬───────────────────┬─────────────────┘
┌───▼──────┐ ┌────▼─────┐   ┌────────▼─────────┐   ┌─────▼──────┐
│simulator │ │fake_data │   │fraud_checks+patch│   │ blind_leak │
│ (NHANES) │ │ (Impostor│   │ (Sentinel, Patch)│   │   (Tell)   │
└───┬──────┘ └────┬─────┘   └──────────────────┘   └─────┬──────┘
    │             └── Daytona sandboxes (all LLM-written code)
    ▼                                                    ▼
┌──────────────────────────────── SQLite ──────────────────────────────────┐
└──────────────────────────────────────────────────────────────────────────┘
```

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI + SSE |
| Frontend | Next.js 14, React, Tailwind, Recharts |
| Data / stats | pandas, NumPy, SciPy, statsmodels |
| ML / attribution | scikit-learn, LightGBM, SHAP |
| Storage | SQLite |
| LLM attacker | Claude |
| Sandbox | Daytona |
| Evals | Chalk (integration stubbed; metrics are local for now) |
| Data source | NHANES (public, de-identified, CDC) |

## Repository layout

```
probe/
├── engine/
│   ├── simulator/     Trial Twin: NHANES base, trial builder, leak mechanisms, blinded views
│   ├── fraud_checks/  Sentinel: SiteCheck base, core checks, suite, calibration, frozen/ (v0, v1, patch report)
│   ├── fake_data/     Impostor: attacker prompts, loop, fired-check explanations, schema validation, run cache
│   ├── patch/         Patch: site features, learned check, acceptance gate, end-to-end pipeline
│   ├── blind_leak/    Tell + Seal: features, classifier, permutation test, attribution, remedies, cheapest fix
│   └── analysis/      ANCOVA primary analysis, damage, breaking point
├── backend/        FastAPI routes, run state, mock fixtures
├── probe-frontend/ Next.js app (see CLAUDE.md for status)
├── integrations/   daytona.py, llm.py, chalk.py, factory.py (thin, mockable)
├── evals/          metric definitions, scenarios, ground truth, export
├── scripts/        download_nhanes.py, run_impostor.py, run_patch.py, run_full_eval.py, precompute_demo.py
├── data/           raw NHANES (gitignored), processed base, demo_cache/ (saved Impostor runs)
├── tests/          simulator, Sentinel, Impostor, Patch, analysis, mechanisms-off control, API mocks
└── docs/           schema.md, assumptions.md, OWNERS.md
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

```bash
.venv/bin/python scripts/run_impostor.py   # run Impostor against Sentinel v0 (needs Daytona + LLM keys)
.venv/bin/python scripts/run_patch.py      # fit, gate, and freeze Sentinel v1 from saved runs in data/demo_cache/
```

`DEMO_MODE=mock` serves the JSON fixtures in `backend/mocks/`, where every payload is tagged `"_mock": true` so it's never mistaken for a result. `DEMO_MODE=cached` replays saved Impostor runs through the same UI.

## Team

| Person | Owns |
|---|---|
| **Garv** | Trial Twin, NHANES pipeline, `schema.md`, `assumptions.md`, Sentinel, Patch, primary analysis, damage, Breaking Point |
| **Shreyas** | Impostor (attacker prompts, loop), Daytona, LLM integrations, demo precompute |
| **Ajay** | Tell and Seal (features, classifier, permutation, attribution, remedies, utility, cheapest fix), rate checks, evals |
| **Akarsh** | Frontend, Guess Who, report page, demo script, Devpost |

## Responsible use

Probe is a defensive stress-test harness. Its attackers exist only to find weaknesses in fraud monitoring and blinding controls before a real trial depends on them. It runs only on semi-synthetic data, and attacker code runs only in isolated sandboxes.
