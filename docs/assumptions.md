# Assumptions

Owner: Garv. Every leak mechanism in the simulator gets one row. No mechanism ships without a "why realistic" and a source. Strengths are config knobs; results are shown across a range, not one tuned value.

> **Bias firewall: Ajay, don't read this file until Tell's results are locked.** It describes every leak the simulator plants. Tell must find them from `docs/schema.md` and `export_view(...)` alone.

Anything marked **[VERIFY]** needs a check against the source before it goes on a slide.

## Leak mechanisms

Set in `TrialConfig.mechanisms` (code: `engine/simulator/mechanisms.py`). `true` means the default strength; `false` or a missing key means off; `{}` is the control trial (every mechanism off). The demo trial uses all four at their defaults (`DEFAULT_MECHANISMS`, trial IDs like `tr_2026_B`).

| Mechanism | Strength param | Range | Default | What it does in the data | Why realistic | Source |
|---|---|---|---|---|---|---|
| Nausea on drug → unscheduled visits, antiemetics, AE entries | `nausea_rr` | 1.0–10.0 | 2.5 | Drug patients get extra nausea AEs (onset in the first 9 weeks) so their nausea rate is ~`nausea_rr` × placebo's (placebo ≈ 5.8% of patients). Each nausea episode, from any cause in either arm, brings an unscheduled visit with p = 0.30 and an antiemetic with p = 0.35. | GI side effects, mostly early and around dose escalation, are the most common adverse events for incretin-class diabetes drugs; nausea rates several times placebo are typical. Symptomatic patients call or come in, and some get antiemetics. | Bettge et al. 2017, *Diabetes Obes Metab* 19(3):336–347 (systematic analysis of GI AEs in GLP-1 RA trials). **[VERIFY rate ratios.]** Visit and antiemetic probabilities are our parameters (clinical rationale, no source). |
| Dose titration on drug → pharmacy dispensing events | `titration` | 0.0–1.0 | 0.6 (`true`) | Chance a patient escalates at Week 4, and again at Week 8 if they escalated at Week 4. Drug patients' steps appear as `titration_step` dispensing events. Placebo patients get the same draw, but their steps are only written to the hidden `sham_dispensing` table. | Incretin-class drugs are started low and stepped up every ~4 weeks for tolerability; not everyone escalates. If only the active arm has titration paperwork, the pharmacy log gives the arm away. Sham titration in the placebo arm is the standard fix. | Semaglutide label: 0.25 mg weekly for 4 weeks, then 0.5 mg, with optional further increase after ≥4 weeks. **[VERIFY against current label.]** |
| Lower glucose on drug → local fingerstick values differ | `local_glucose` | 0.0–1.0 | 1.0 (`true`) | Site fingersticks pick up this share of each patient's on-treatment HbA1c change (×28.7 mg/dL per HbA1c point). It applies to both arms, so it only separates the arms when the drug works: **in Scenario B it leaks nothing.** With the mechanism off, fingersticks track each patient's baseline only. | A drug that lowers HbA1c lowers day-to-day glucose too, and sites measuring glucose locally see it. Routing efficacy labs centrally with results masked is the standard fix. | ADAG: Nathan et al. 2008, *Diabetes Care* 31(8):1473–1478 (eAG = 28.7 × A1C − 46.7). |
| Cold-chain drug → kit storage / temperature log entries | `cold_chain` | 0.0–1.0 | 0.3 (`true`) | At this share of sites (chosen at random), placebo kits are logged as `ambient` at ~21 °C; drug kits are always `refrigerated` at ~5 °C. Other sites refrigerate both. | Peptide drugs need 2–8 °C storage; placebo without the active ingredient doesn't, and when a depot or site handles them differently, the storage log reveals the arm. Unblinding through perceptible physical differences is the most commonly reported mechanism. Matched packaging and identical storage is the fix. | Unblinding mechanisms: "The risk of unblinding was infrequently and incompletely reported in 300 randomized clinical trial publications," *J Clin Epidemiol* (see master doc §2, source 2). Refrigerated storage: GLP-1 RA pen labels (2–8 °C before first use). **[VERIFY.]** The 30% of sites is our parameter. |

What a coordinator can't be shielded from: adverse events have to reach the investigator, so the nausea leak is never removed from the coordinator view. The remedy for it is a separate blinded outcome assessor (the `assessor` view), and Probe re-tests that view.

## Trial design parameters (not claims about any real drug)

| Parameter | Value | Note |
|---|---|---|
| Drug | PRB-101 (fictional) | Type 2 diabetes |
| Sites × patients | 20 × 40 | 1:1 permuted blocks of 4 within each site |
| Primary endpoint | Central HbA1c change, Baseline → Week 24 | ANCOVA adjusted for baseline, site as a factor |
| Scenario A effect | −0.6 points on drug vs −0.1 on placebo at Week 24 | Approached with a 6-week time constant |
| Scenario B effect | −0.1 on both arms | Equal to placebo (useless drug) |
| Between-patient response SD | 0.8 points | Site effect SD 0.1; central assay SD 0.15 |
| Visit-to-visit vitals | SBP ±8 mmHg (lag-1 autocorrelation 0.3), DBP follows 0.4 × SBP deviation ±5, weight ±1.5 kg (lag-1 autocorrelation 0.8) | Around each patient's NHANES baseline |
| Missed visits / dropout | 3% of post-baseline visits / 5% of patients | Same in both arms |
| Background unscheduled visits | 0.25 per patient | Same in both arms |
| Background AEs | 0.6 per patient (headache, nasopharyngitis, back pain, arthralgia, dizziness, fatigue, nausea, diarrhoea) | Same in both arms |
| Background conmeds | metformin 90%, statin 60%, ACE inhibitor 40% | Started before screening |
| Check-suite false-alarm budget | ≤5% of real sites | Frozen before any attack runs |

## Physiology base

| Item | Value |
|---|---|
| Source | NHANES 2017–March 2020 pre-pandemic (`P_DEMO`, `P_GHB`, `P_BMX`, `P_BPXO`, `P_GLU`), public domain, de-identified |
| Filter | Age 30–75, HbA1c 7.0–10.5%, complete age/sex/BMI/weight/height/BP/HbA1c → 495 participants |
| Committed as | `data/processed/nhanes_base.csv` (rebuild with `python -m scripts.download_nhanes`) |
| Sampling | 800 draws with replacement, jitter (age ±1 y, BMI ±0.4, HbA1c ±0.1, SBP ±3, DBP ±2 SD) so no NHANES row maps 1:1 to a patient |
| Real | Baseline age, sex, BMI, weight, blood pressure, HbA1c and how they co-vary |
| Simulated | Everything about the trial: assignment, outcomes, visits, AEs, conmeds, dispensing, storage |
