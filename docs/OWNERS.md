# Owners

One owner per module. Every stub raises `NotImplementedError("owner: <name>")` so a failing call tells you who to ask.

| Person | Role | Owns |
|---|---|---|
| **Garv** | Data | `engine/simulator/`, `engine/analysis/`, `engine/fraud_checks/` (base, suite, calibrate, `checks_core.py`), `evals/ground_truth.py`, `engine/fake_data/sites.py`, `engine/patch/` (gate, learned check, features, data, pipeline; not `droid_task.py`), `scripts/run_patch.py`, `scripts/download_nhanes.py`, `docs/schema.md`, `docs/assumptions.md` |
| **Shreyas** | Fake data | `engine/fake_data/`, `engine/patch/droid_task.py`, `integrations/daytona.py`, `integrations/factory.py`, `integrations/llm.py`, `scripts/precompute_demo.py` |
| **Ajay** | Blind leak + evals | `engine/blind_leak/`, `engine/fraud_checks/checks_rates.py`, `integrations/chalk.py`, `evals/` (metrics, scenarios, export), `scripts/run_full_eval.py` |
| **Akarsh** | Frontend + pitch | `frontend/`, Guess Who, report page, demo script, Devpost |

`backend/` (routes, mocks, state) is shared: whoever adds or changes an endpoint updates its Pydantic model and its fixture in `backend/mocks/`.

Branches: `data/*`, `fake_data/*`, `blind/*`, `ui/*`. `main` is always demoable.

## Rules

- **Bias firewall:** Ajay never opens `engine/simulator/`. They work only from `docs/schema.md` and `export_view(...)` output.
- **Ground truth:** only `evals/` and scoring code import `evals/ground_truth.py`.
- **Test attacker:** nobody touches `engine/fake_data/prompts/test_attacker.md` or runs the test attacker until patching is frozen.
- **No LLM-written code on a laptop:** attacker and Droid code runs only through a `SandboxRunner`.
