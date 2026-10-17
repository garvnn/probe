# Assumptions

Owner: Garv. Every leak mechanism in the simulator gets one row. No mechanism ships without a "why realistic" and a source. Strengths are config knobs; results are shown across a range, not one tuned value.

| Mechanism | Strength param | Default | Why realistic | Source |
|---|---|---|---|---|
| Nausea on drug → unscheduled visits, antiemetics, AE entries | `nausea_rr` | TODO | TODO | TODO |
| Dose titration on drug → pharmacy dispensing events | `titration` | TODO | TODO | TODO |
| Lower glucose on drug → local fingerstick values differ | `local_glucose` | TODO | TODO | TODO |
| Cold-chain drug → kit storage / temperature log entries | `cold_chain` | TODO | TODO | TODO |

## Simulation parameters (not claims about any real drug)

| Parameter | Value | Note |
|---|---|---|
| Scenario A effect | TODO | |
| Scenario B effect | TODO | Equal to placebo |
| Check-suite false-alarm budget | ≤5% of real sites | Frozen before any attack runs |
