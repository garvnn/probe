# Owners

One owner per module. Every stub raises `NotImplementedError("owner: <name>")` so a failing call tells you who to ask.

| Person | Role | Owns |
|---|---|---|
| **Garv** | Data | `engine/generator/`, `engine/analysis/`, `engine/detector/` (base, detector, calibrate, `checks_core.py`), `evals/ground_truth.py`, `scripts/download_nhanes.py`, `docs/schema.md`, `docs/assumptions.md` |
| **Shreyas** | Forger | `engine/forger/`, `engine/harden/gate.py`, `engine/harden/droid_task.py`, `integrations/daytona.py`, `integrations/factory.py`, `integrations/llm.py`, `scripts/precompute_demo.py` |
| **Ajay** | Blind Breaker + evals | `engine/blind/`, `engine/detector/checks_rates.py`, `engine/harden/fallback_check.py`, `integrations/chalk.py`, `evals/` (metrics, scenarios, export), `scripts/run_full_eval.py` |
| **Akarsh** | Frontend + pitch | `frontend/`, Guess Who, report page, demo script, Devpost |

`backend/` (routes, mocks, state) is shared: whoever adds or changes an endpoint updates its Pydantic model and its fixture in `backend/mocks/`.

## Rules

- **Bias firewall:** Ajay never opens `engine/generator/`. He works only from `docs/schema.md` and `export_view(...)` output.
- **Ground truth:** only `evals/` and scoring code import `evals/ground_truth.py`.
- **Attacker B:** nobody touches `engine/forger/prompts/attacker_b.md` or runs attacker B until hardening is frozen.
- **No LLM-written code on a laptop:** attacker and Droid code runs only through a `SandboxRunner`.
