# Seal

Seal searches all 16 subsets of the four documented remedies. It calls the public
`export_view(trial_id, "coordinator", remedies=combo)` boundary and measures Tell's
site-grouped cross-validation AUC. It never modifies patient records or tunes the
classifier. No simulator implementation is inspected.

The selected row minimizes assigned cost subject to AUC <= 0.55, utility >= 0.90,
and investigator safety access. Equal costs prefer fewer remedies, then registry
order. If no combination qualifies, the recommendation is null. Every evaluated
row is returned for the Pareto chart, including infeasible rows.

## Assigned operational model

Utility is the fraction of six equally weighted tasks whose required fields
remain available to the responsible role. This is a declared task model, not a
measurement of clinical productivity. Field requirements and remedy effects are
explicit in `engine/blind_leak/utility.py` and follow `docs/schema.md`.

| Task | Required access |
|---|---|
| Schedule visits | Coordinator visit identity, date, and name |
| Report adverse events | Investigator patient/site, onset, term, category, severity |
| Manage inventory | Pharmacist kit identity, movements, receipt date, storage condition and temperature |
| Track retention | Coordinator visit identity, date, and name |
| Query labs | Investigator local lab identity, date, test, and result |
| Dispense drug | Pharmacist patient, date, event type, and kit identity |

Delegating dispensing to an unblinded pharmacist preserves pharmacy tasks. Sham
titration removes no required fields. Central-lab restriction removes the local
lab-query task. Matched kits mask storage condition and temperature, losing the
inventory-monitoring task under this conservative model. Each lost task reduces
utility by 1/6: a 0.90 floor therefore requires all six tasks.

Investigator adverse-event identity, onset, term, category, and severity must all
remain accessible. None of the four documented remedies removes that access.
The search targets coordinator confidentiality. Investigator AE access is checked
separately; switching to an already restricted assessor view is not a remedy for
a coordinator leak.

Costs are **assigned by us**, in relative units: sham titration 1, matched kits 1,
central lab 2, unblinded pharmacist 3. They are not measured implementation costs.
The API retains `costs_are_assigned: true`; the UI must label them as assigned.

## Execution and API

`cheapest_fix(trial_id, utility_floor=0.90, auc_ceiling=0.55)` returns
`(recommended_or_none, all_16_rows)`. Each row retains the existing
`combo`, `auc`, `utility`, `cost`, and `safety_ok` fields.

In `DEMO_MODE=live`, `POST /blind-leak/cheapest-fix` runs this search and returns
`_mock: false`. Existing mock/cached behavior is retained. The search uses Tell's
same grouped-CV AUC with zero permutation-null refits and no reported top fields;
it makes no permutation-significance claim. AUC selection on this trial is not
independent held-out validation of the selected policy. Tell's separate full
coordinator analysis retains its default permutation test.

## Measured coordinator search: tr_2026_B

All 16 combinations were measured with the existing grouped-CV classifier and
seed 0. Baseline coordinator AUC was **0.8529375**, utility **1.0**. With AUC
ceiling 0.55 and utility floor 0.90, **no combination is feasible**; the returned
recommendation is null.

| Candidate | Coordinator AUC | Utility | Assigned cost | Outcome |
|---|---|---|---|---|
| unblinded_pharmacist | 0.63821875 | 1.0 | 3 | Best AUC retaining required utility; fails AUC ceiling |
| sham_titration + matched_kits | 0.51104375 | 5/6 | 2 | Cheapest reaching AUC ceiling; fails utility floor |

Investigator exports were compared directly for all 16 combinations: all
**493 AE rows** (including identity, dates, terms, categories, and severity) were
unchanged. Safety access passed every combination. No utility assumptions,
thresholds, classifier settings, or remedy effects were tuned to obtain a pass.

## Earlier assessor-only search (superseded)

On the existing trial database, all 16 combinations returned grouped-CV assessor
AUC **0.44760625**. The cheapest feasible row was the empty combination (`[]`),
with utility **1.0**, assigned cost **0.0**, and safety access true. This is a
baseline pass of the existing assessor policy, not evidence of improvement from
the four remedies or restoration of coordinator confidentiality.

Tell's full default coordinator run on the same `tr_2026_B` returned accuracy
**0.74875** and AUC **0.8529375**, with its default 200 within-site permutations
and seed 0. This coordinator result and the assessor search use different access
policies and must not be presented as a measured remedy effect on one view.
