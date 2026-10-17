# Trial schema

Owner: Garv. This file is the contract between the simulator and everyone else; Ajay builds the blind-leak attack from this file only.

Conventions: IDs are strings (`P0412`, `S07`, `V0412-W08`), dates are ISO `YYYY-MM-DD`, units are noted per column.

## patients

| Column | Type | Unit | Description |
|---|---|---|---|
| patient_id | str | | TODO |
| site_id | str | | TODO |
| age | int | years | TODO |
| sex | str | | TODO |
| bmi | float | kg/m² | TODO |
| baseline_hba1c | float | % | TODO |

## sites

| Column | Type | Unit | Description |
|---|---|---|---|
| site_id | str | | TODO |
| trial_id | str | | TODO |
| is_fake | bool | | Evals only. Never exported in a view. |
| source | str | | `simulator` \| `fake_data:training` \| `fake_data:test` |

## visits

| Column | Type | Unit | Description |
|---|---|---|---|
| visit_id | str | | TODO |
| patient_id | str | | TODO |
| visit_name | str | | TODO |
| date | date | | TODO |
| scheduled | bool | | TODO |

## labs

| Column | Type | Unit | Description |
|---|---|---|---|
| lab_id | str | | TODO |
| visit_id | str | | TODO |
| test | str | | TODO |
| value | float | | TODO |
| source | str | | `central` \| `local` |

## vitals

| Column | Type | Unit | Description |
|---|---|---|---|
| visit_id | str | | TODO |
| sbp | int | mmHg | TODO |
| dbp | int | mmHg | TODO |
| weight | float | kg | TODO |

## adverse_events

| Column | Type | Unit | Description |
|---|---|---|---|
| ae_id | str | | TODO |
| patient_id | str | | TODO |
| term | str | | TODO |
| category | str | | TODO |
| onset_date | date | | TODO |
| severity | str | | TODO |

## conmeds

| Column | Type | Unit | Description |
|---|---|---|---|
| patient_id | str | | TODO |
| drug_class | str | | TODO |
| start_date | date | | TODO |

## dispensing

| Column | Type | Unit | Description |
|---|---|---|---|
| event_id | str | | TODO |
| patient_id | str | | TODO |
| date | date | | TODO |
| kit_id | str | | TODO |
| event_type | str | | TODO |

## ground_truth

Locked. Never joined into any view. Read only via `evals.ground_truth.ground_truth(trial_id)`.

| Column | Type | Unit | Description |
|---|---|---|---|
| patient_id | str | | TODO |
| arm | str | | `drug` \| `placebo` |
