# Trial schema

Owner: Garv. This file is the contract between the simulator and everyone else; Ajay builds the blind-leak attack from this file only. It is also the output contract for fake-data attackers: a fake site must produce these tables and columns.

The same schema lives in code at `engine/simulator/schema.py` (`SCHEMA`, `VIEW_COLUMNS`, `coerce`). Import it rather than hard-coding columns. A test keeps this file and the code in sync.

Columns with a fixed set of values (`sex`, `visit_name`, lab `test` and `source`, AE `category` and `severity`, dispensing and kit `event_type`, kit `storage`, `arm`) accept only the values listed below; the list lives in code as `schema.ALLOWED_VALUES`.

Conventions: IDs are strings (`P0412`, `S07`, `V0412-W08`), dates are ISO `YYYY-MM-DD` (pandas `datetime64` in memory), units are noted per column. Trial IDs look like `tr_2026_B`.

## Entry points

| Call | Returns | Who uses it |
|---|---|---|
| `engine.simulator.trial.generate_trial(TrialConfig(...))` | `Trial`, also written to the DB at `$DB_PATH` (default `data/probe.db`) | backend, scripts |
| `engine.simulator.trial.load_trial(trial_id)` | `Trial` (tables below; never ground truth) | everyone |
| `engine.simulator.views.export_view(trial_id, role, remedies=[])` | long-format `DataFrame` (see Views) | blind leak |
| `evals.ground_truth.ground_truth(trial_id)` | `Series` of `drug` \| `placebo` indexed by `patient_id` | evals and scoring only |

## Trial design (fixed per config)

- Fictional drug PRB-101 for type 2 diabetes. Primary endpoint: change in central HbA1c from Baseline to Week 24.
- `n_sites` sites (default 20) × `patients_per_site` patients (default 40). 1:1 randomization within each site.
- Visit schedule (target study day relative to Baseline, window ±3 days): Screening (−14), Baseline (0), Week 2 (14), Week 4 (28), Week 8 (56), Week 12 (84), Week 16 (112), Week 20 (140), Week 24 (168), plus any number of Unscheduled visits.
- Some scheduled visits are missed and some patients drop out early, so not every patient has every visit.
- Study drug kits are dispensed at Baseline, Week 4, 8, 12, 16, 20 and returned at the next dispensing visit (last return at Week 24).

## patients

One row per randomized patient.

| Column | Type | Unit | Description |
|---|---|---|---|
| patient_id | str | | `P0001`… unique within a trial |
| site_id | str | | Site the patient is enrolled at, `S01`… |
| age | int | years | Age at Screening, 30–75 |
| sex | str | | `F` \| `M` |
| bmi | float | kg/m² | BMI at Screening, 1 decimal |
| baseline_hba1c | float | % | Central HbA1c at Baseline, 1 decimal |

## sites

| Column | Type | Unit | Description |
|---|---|---|---|
| site_id | str | | `S01`… |
| trial_id | str | | Trial this site belongs to |
| is_fake | bool | | Evals only. Never exported in a view. |
| source | str | | `simulator` \| `fake_data:training` \| `fake_data:test` |

## visits

| Column | Type | Unit | Description |
|---|---|---|---|
| visit_id | str | | `V<patient number>-<code>`: `SCR`, `BL`, `W02`…`W24`, or `U1`, `U2`… for unscheduled |
| patient_id | str | | |
| visit_name | str | | `Screening`, `Baseline`, `Week 2` … `Week 24`, or `Unscheduled` |
| date | date | | Date the visit happened |
| scheduled | bool | | False for Unscheduled visits |

## labs

| Column | Type | Unit | Description |
|---|---|---|---|
| lab_id | str | | `L000001`… |
| visit_id | str | | Visit the sample was drawn at |
| test | str | | `hba1c` (%), `glucose_fasting` (mg/dL), `glucose_fingerstick` (mg/dL) |
| value | float | see `test` | Result, 1 decimal for HbA1c, integer-valued for glucose |
| source | str | | `central` (HbA1c and fasting glucose at Screening, Baseline, Week 12, Week 24) \| `local` (fingerstick glucose at every scheduled visit from Baseline on) |
| draw_time | str | HH:MM | Local clock time of the draw |

## vitals

One row per attended scheduled visit.

| Column | Type | Unit | Description |
|---|---|---|---|
| visit_id | str | | |
| sbp | int | mmHg | Systolic blood pressure |
| dbp | int | mmHg | Diastolic blood pressure |
| weight | float | kg | 1 decimal |

## adverse_events

| Column | Type | Unit | Description |
|---|---|---|---|
| ae_id | str | | `AE00001`… |
| patient_id | str | | |
| term | str | | Reported term, e.g. `Headache`, `Nausea`, `Back pain` |
| category | str | | Body-system group: `GI` \| `Nervous system` \| `Infection` \| `Musculoskeletal` \| `General` |
| onset_date | date | | |
| severity | str | | `mild` \| `moderate` \| `severe` |

## conmeds

Concomitant medications, including background diabetes therapy started before the trial.

| Column | Type | Unit | Description |
|---|---|---|---|
| patient_id | str | | |
| drug_class | str | | e.g. `metformin`, `statin`, `ace_inhibitor`, `analgesic`, `antiemetic` |
| start_date | date | | May be before Screening for background therapy |

## dispensing

Study-drug kit movements at the site pharmacy.

| Column | Type | Unit | Description |
|---|---|---|---|
| event_id | str | | `D00001`… |
| patient_id | str | | |
| date | date | | |
| kit_id | str | | `K-<site number>-<seq>`; kit numbers carry no treatment information |
| event_type | str | | `dispense` \| `return` \| `titration_step` |

## kit_storage

Kit receipt and storage log at the site, before dispensing.

| Column | Type | Unit | Description |
|---|---|---|---|
| event_id | str | | `KS00001`… |
| patient_id | str | | Patient the kit is assigned to |
| kit_id | str | | Matches `dispensing.kit_id` |
| date | date | | |
| event_type | str | | `received` |
| storage | str | | Storage condition recorded at receipt: `refrigerated` \| `ambient` |
| temp_c | float | °C | Temperature recorded at receipt, 1 decimal |

## ground_truth

Locked. Never joined into any view. Read only via `evals.ground_truth.ground_truth(trial_id)`.

| Column | Type | Unit | Description |
|---|---|---|---|
| patient_id | str | | |
| arm | str | | `drug` \| `placebo` |

## Views

`export_view(trial_id, role, remedies=[])` returns one long-format DataFrame: one row per thing that role can see, sorted by `patient_id`, `date`. It never contains the arm or anything derived from it. Build features from it however you like.

| Column | Type | Description |
|---|---|---|
| patient_id | str | |
| site_id | str | Keep for grouped CV |
| source | str | Which record the row came from (table below) |
| date | date | Visit date, onset date, start date, or event date; empty for demographics |
| kind | str | What the row is (table below) |
| category | str | Secondary label (table below), else empty |
| value | float | Numeric value, else NaN |
| detail | str | Extra text (table below), else empty |

| source | kind | category | value | detail | Field group |
|---|---|---|---|---|---|
| `patient` | `age`, `sex`, `bmi` | sex (`F`/`M`) for `sex` | age, BMI | | always visible |
| `visit` | visit_name | `scheduled` \| `unscheduled` | | visit_id | visits |
| `vital` | `sbp`, `dbp`, `weight` | | reading | visit_id | visits |
| `lab` | test | `local` | result | draw_time | local_labs |
| `lab` | test | `central` | result | draw_time | central_labs |
| `adverse_event` | term | AE category | | severity | adverse_events |
| `conmed` | drug_class | | | | conmeds |
| `dispensing` | event_type | | | kit_id | dispensing |
| `kit_storage` | event_type | storage | temp_c | kit_id | kit_storage |

### Who sees which field group

Same matrix the UI shows (`backend/mocks/trial_detail.json`).

| Field group | coordinator | investigator | pharmacist | assessor |
|---|---|---|---|---|
| visits | ✓ | ✓ | | ✓ |
| adverse_events | ✓ | ✓ | | |
| conmeds | ✓ | ✓ | | |
| dispensing | ✓ | | ✓ | |
| local_labs | ✓ | ✓ | | |
| central_labs | | | | ✓ |
| kit_storage | ✓ | | ✓ | |

### Remedies

Names come from `engine.blind_leak.remedies.REMEDIES`. Unknown names raise `ValueError`.

| Remedy | Effect on the view |
|---|---|
| `unblinded_pharmacist` | `dispensing` rows removed for every role except pharmacist |
| `sham_titration` | Placebo patients get matching `titration_step` dispensing rows |
| `central_lab` | `local_labs` rows removed |
| `matched_kits` | `kit_storage` rows: `category` set to `matched`, `value` set to NaN |
