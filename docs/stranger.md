# Stranger: post-freeze test attacker

Stranger uses a different model, prompt, and generator seed from the training attacker.
It receives baseline v0 feedback only. After a fixed round budget finishes, the evaluator
scores the identical saved, schema-valid submissions against frozen v0 and v1. Neither
monitor nor the Stranger prompt is tuned after observing this evaluation.

`gemini-*` models use `GEMINI_API_KEY` and Google's OpenAI-compatible endpoint, independently
of `OPENAI_API_KEY` and `OPENAI_BASE_URL`. `TEST_ATTACKER_MODEL` defaults to
`gemini-3-flash-preview`; override it explicitly if Google changes availability.
The model API does not receive a sampling seed. Recorded seeds control the generated-site
randomness, and the stored source and output are the reproducibility artifacts.

Run these commands **inside Daytona**, from the repository root, with a `.venv` populated
using `uv pip install -r requirements.txt`. The orchestration sandbox needs provider and
Daytona access; each generated program executes in a separate network-blocked Daytona sandbox.
Never execute generated source on a laptop.

```sh
.venv/bin/python scripts/run_impostor.py --role test --attacker llm --seed 85301 --rounds 3
.venv/bin/python scripts/run_impostor.py --role test --attacker llm --seed 85302 --rounds 3
# Pass every completed run ID from the predeclared evaluation batch:
.venv/bin/python scripts/eval_stranger.py fd_stranger_<run1> fd_stranger_<run2>
```

Keep budgets identical; choose seeds and budgets before inspecting results. Test mode refuses
scripted fallback, mock execution, early stopping, non-v0 feedback, reused training seeds, and
an unfrozen Patch. Training run metadata in `data/demo_cache/fd_*.json` is checked for seed/model
reuse. Preserve the complete training cache when starting a new evaluation.

Stranger saves runs under `data/demo_cache/stranger/`, outside Patch's training scan and the
Impostor replay selection. Each run stores the prompt/context hashes, model, seed, source,
validated outputs, provider usage, sandbox identifiers, and hashes of v0, v1, and Patch's report.
The evaluator never executes saved source, and rejects incomplete runs, duplicates, mixed models,
mixed prompts, changed frozen artifacts, and provider failures with no sandbox execution.

The primary endpoint is **a run with at least one valid escaped fake within the fixed budget**.
API `attempted` and `escaped` count runs; `evasion_rate` is their ratio. Wilson intervals are
computed over runs, not adaptive rounds, and remain exploratory with small samples. The report
also retains valid/error/escaped round counts for every run and suite. `fp_rate` measures honest
sites in the requested trial, not Patch's held-out cohort. Do not present it as that cohort's rate.

`eval_stranger.py` atomically writes `data/demo_cache/stranger_report.json`.
`POST /test-attacker/eval` serves that measured report in cached and live modes, filtering the
requested suite versions and checking trial identity and frozen hashes. It never starts a paid
attack from an HTTP request. Missing measurements return 404; stale reports return 409.
Mock mode retains explicitly tagged sample fixtures.

The original Gemini 2.5 Pro availability probes failed at the provider with no code generated;
Gemini 3.1 Pro also had zero quota on this key. A connectivity check succeeded for Gemini 3 Flash.
They are infrastructure attempts, excluded from the measured batch. A successful evaluation
supports only the tested model, prompt, trial, and attack budget; it does not establish robustness
against arbitrary attackers or real trials.

## Measured pilot

The committed Gemini 3 Flash preview batch used seeds 87301–87304 and a fixed budget of
three rounds per run. Twelve rounds yielded seven schema-valid submissions and five code/schema
errors. Both frozen suites flagged all seven valid submissions; neither had a run with an escape
(0/4 runs for v0, 0/4 for v1). The run-level Wilson interval is 0–48.99% for each suite.
Each suite flagged one of the requested trial's twenty honest sites (5%). This is not the
1,000-site Patch holdout measurement.

**This pilot does not demonstrate improved escape detection by v1: there were no v0 escapes.**
It is a small-budget execution of the independent-attacker protocol, not a broad robustness claim.

The measured run files and [paired report](../data/demo_cache/stranger_report.json) are committed.
The orchestration sandbox could not reach Daytona's toolbox proxy, so this batch used native CLI
command/file transport to fresh, network-blocked sandboxes. Generated Python executed only in
Daytona. One completed third-round output was recovered after a partial transfer read; it was
not re-executed, and the missing call's token/latency records are explicitly marked unavailable.
The recovery note is retained in the run and report. Latency and total token/cost comparisons
should not be made from this pilot.
