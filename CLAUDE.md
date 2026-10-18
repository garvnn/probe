# CLAUDE.md

Probe is a pentest harness for clinical trials (HackHarvard 2026). `README.md` explains the product, the pitch names and who owns what. This file covers what an agent needs that the README doesn't: **how the frontend is wired to the backend, how far along it is, and the rules for changing either side without breaking the other.**

## Layout and commands

| Path | What |
|---|---|
| `backend/` | FastAPI. `models.py` is the API contract. `DEMO_MODE=mock` serves `backend/mocks/*.json`. `cached` replays saved Impostor runs from `data/demo_cache/` and serves fixtures (`_mock: true`) for every other route. `live` raises 501 `owner: <name>` for anything not built yet |
| `engine/` | Simulator, Sentinel, Impostor, Patch, blind leak, analysis |
| `probe-frontend/` | Next.js 14 + TypeScript + Tailwind + Recharts. Owner: Akarsh |

```bash
make mock     # API on :8000 serving fixtures (needs .venv: python3.11 -m venv .venv && uv pip install -r requirements.txt)
make web      # frontend on :3000 (first time: cd probe-frontend && npm install)
make types    # regenerate probe-frontend/lib/api-types.ts from the running API
make test     # backend pytest
cd probe-frontend && npm run typecheck && npm run build
```

## How the frontend talks to the backend

- **`probe-frontend/lib/api.ts` is the only HTTP client.** Each backend route has one method there (`api.patch`, `api.testAttacker`, …). Paths, request bodies and response types are checked at compile time against `lib/api-types.ts`.
- **`lib/api-types.ts` is generated, never hand-edited.** `npm run gen:api` reads `http://localhost:8000/openapi.json`. It is committed, so the frontend builds without a running backend.
- **SSE** goes through `lib/useForgerStream.ts`, reading `GET /fake-data/runs/{id}/stream`, which sends `round` events (`RoundEvent`) and then a `done` event. `RoundEvent` is published in OpenAPI through the route's `responses=`, so stream rounds are typed too. Each round carries the attacker's `code`, the checks that `fired`, and the `diagnostics` (what Sentinel told the attacker).
- **Cross-screen state** (trial id, fake-data run id, suite version, last escaped damage, contract) lives in `lib/demo-context.tsx`.
- **`_mock: true`** on any payload turns on the "SAMPLE DATA: NOT A LIVE RESULT" badge **for that screen only** (`MockScope` in `demo-context.tsx`, mounted by `ScreenShell`). A real run (`not_a_result: false` → `_mock: false`) shows no badge. The contract panel carries its own SAMPLE tag. Never strip `_mock` from a response or show mock numbers as measured results.
- **Measured contract changes:** a non-mock escaped Impostor round sets Data authenticity to BROKEN (`observe()` in the context, tagged MEASURED). Observed rows win over any fetched or mock contract.
- **Errors:** a 501 renders "Not built yet (owner: X)", and an unreachable backend says to run `make mock`. Screens show N/A or an empty state rather than invented numbers.

### Screen ↔ endpoint map

Frontend routes still use the older names (`/forger`, `/harden`, `/blind`). The table gives the code name for each.

| Route | Screen (pitch name) | Calls |
|---|---|---|
| `/setup` | Setup + Contract | `POST /trials`, `GET /trials/{id}`, `GET /contract/{id}` |
| `/forger` | Impostor replay (**hero screen**) | `POST /fake-data/runs` (cached: newest saved run), `GET /fake-data/runs/{id}` (run header), SSE `/fake-data/runs/{id}/stream` |
| `/harden` | Patch + Stranger + Breaking Point | `POST /fraud-checks/patch`, `POST /test-attacker/eval` (suites `[0, vN]`), `POST /breaking-point` ×2 (v0, vN) |
| `/blind` | Guess Who → Tell → Seal | `GET /blind-leak/guess-cards`, `POST /blind-leak/guess-cards/score`, `POST /blind-leak/runs`, `POST /blind-leak/cheapest-fix`, `POST /blind-leak/policy` |
| `/report` | Probe Report | `GET /report/{id}` |
| `/demo` | All five, presenter mode. ← → and space work on every stage route; P pause, C code, R restart, Esc close | (the above) |
| `/` | Marketing homepage | none (illustrations only, no backend data) |

## Rules when changing the contract

1. **Backend owners:** if you change `backend/models.py`, a route path, or a fixture's shape, run `make mock` and `make types`, then `cd probe-frontend && npm run typecheck`. Fix what breaks, or tell Akarsh. Type errors in `lib/api.ts` or a screen mean the UI is reading a field that no longer exists.
2. **Frontend:** never handwrite response interfaces. Use `Schemas['X']` from `lib/api.ts`, and add new calls to the `api` object rather than calling `fetch` from components.
3. **Don't invent data in the UI.** No placeholder metrics, patient values or outcomes. Missing means N/A. The homepage's KYOTO HEART section is cited historical context, not a Probe result.
4. Fields with a server default (`seed`, `suite_version`, …) are optional in request types because `gen:api` runs with `--default-non-nullable false`. Keep that flag.

## Status (updated 2026-10-17, branch `ui/frontend-integration`)

**Demo setup:** `DEMO_MODE=cached make dev`, with `CACHED_REPLAY_SPEED=0.3` or so to speed up a real run (each round's gap is capped at 15 s), plus `make web`. `/forger` replays the newest run in `data/demo_cache/`. **Saved runs are gitignored** (`data/demo_cache/*`), so a run to share has to be force-added: `git add -f data/demo_cache/fd_<id>.json`.

**Done**
- **Impostor replay (hero):** run header (attacker model and seed, Sentinel version and threshold, fake site, tokens, REAL RUN vs STAND-IN tag) and a clickable 10-round timeline. Also a score-vs-flag-line chart, per-check bars against the threshold, and "what Sentinel told the attacker" (fake value vs real-site 10th–90th percentile). There's a round-to-round code diff (C), sandbox id and timings, and an escape banner with damage (effect and p, real vs with the fake). It works standalone at `/forger` without Setup, using the demo trial `tr_2026_B`.
- Integrity Contract panel on every screen. Stepper plus arrow keys between screens.
- Guess Who → Tell → Seal, and Patch + Stranger + Breaking Point, run on fixtures with the MOCK badge on (in mock and cached modes).
- Verified with headless Chrome: (a) the cached stand-in run shows STAND-IN plus the badge; (b) a not-mock escaped run shows no badge, the escape banner, and Data authenticity MEASURED/BROKEN; (c) arrow keys move /forger → /harden → /blind and back with the badge correct on each screen. Typecheck, build and pytest pass.

**Known gaps / next up**
- **Not yet replayed against the real committed run:** it wasn't on any branch as of this update (see the gitignore note above). Verify `/forger` on it once it lands.
- Tell (Ajay) and Patch (Garv/Shreyas, not frozen yet) are fixture-backed. When their routes get real data, the screens are already typed against `models.py`; only `routes/_mode.serve` callers change.
- Mock `POST /breaking-point` returns the same curve for every version, so v0 and vN overlap on `/harden`. The report uses the distinct curves in `report.json`.
- Route and file names (`forger`, `harden`, `useForgerStream`) predate the README's naming table; renaming them is cosmetic.
- `npm audit` reports advisories against `next@14.2.35`; not yet triaged.

When you finish a chunk of frontend or integration work, update this Status section (date, what moved, what's still open).

### Stranger integration (2026-10-17, `fake_data/stranger`)

- Gemini has dedicated credentials and endpoint selection. `run_impostor.py --role test` enforces
  a frozen Patch, different model/seed, a fixed budget, Daytona execution, and v0-only feedback.
- `scripts/eval_stranger.py` scores identical saved outputs against v0/v1. Stranger runs live in
  `data/demo_cache/stranger/`, outside Patch's training scan and the Impostor replay selector.
- `/test-attacker/eval` serves measured reports in cached/live modes, returns 404 for missing
  measurements and 409 for changed frozen artifacts. Mock mode remains explicitly tagged.
- `/harden` labels measured success per run, shows round errors and counts, and identifies the
  trial false-alarm population. API types were regenerated and typechecked in Daytona.
- Patch and Breaking Point retain their existing integration status. See `docs/stranger.md` for
  the fixed-budget protocol, availability constraints, and measured-batch caveats.
