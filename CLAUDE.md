# CLAUDE.md

Probe is a pentest harness for clinical trials (HackHarvard 2026). `README.md` explains the product, the pitch names and who owns what. This file covers what an agent needs that the README doesn't: **how the frontend is wired to the backend, how far along it is, and the rules for changing either side without breaking the other.**

## Layout and commands

| Path | What |
|---|---|
| `backend/` | FastAPI. `models.py` is the API contract; `routes/` serve `backend/mocks/*.json` when `DEMO_MODE=mock`, and raise 501 `owner: <name>` for anything not built yet |
| `engine/` | Simulator, Sentinel, Impostor, Patch, blind leak, analysis |
| `probe-frontend/` | Next.js 14 + TypeScript + Tailwind + Recharts. Owner: Akarsh |

```bash
make mock     # API on :8000 serving fixtures (needs .venv: python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt)
make web      # frontend on :3000 (first time: cd probe-frontend && npm install)
make types    # regenerate probe-frontend/lib/api-types.ts from the running API
make test     # backend pytest
cd probe-frontend && npm run typecheck && npm run build
```

## How the frontend talks to the backend

- **`probe-frontend/lib/api.ts` is the only HTTP client.** Each backend route has one method there (`api.patch`, `api.testAttacker`, …). Paths, request bodies and response types are checked at compile time against `lib/api-types.ts`.
- **`lib/api-types.ts` is generated, never hand-edited.** `npm run gen:api` reads `http://localhost:8000/openapi.json`. It is committed, so the frontend builds without a running backend.
- **SSE** goes through `lib/useForgerStream.ts`, reading `GET /fake-data/runs/{id}/stream`, which sends `round` events (`RoundEvent`) and then a `done` event. `RoundEvent` is not in the OpenAPI schema because SSE has no response model, so stream payloads are read loosely through `lib/utils.ts` helpers.
- **Cross-screen state** (trial id, fake-data run id, suite version, last escaped damage, contract) lives in `lib/demo-context.tsx`.
- **`_mock: true`** on any payload turns on the "SAMPLE DATA: NOT A LIVE RESULT" badge. Never strip `_mock` from a response or show mock numbers as measured results.
- **Errors:** a 501 renders "Not built yet (owner: X)", and an unreachable backend says to run `make mock`. Screens show N/A or an empty state rather than invented numbers.

### Screen ↔ endpoint map

Frontend routes still use the older names (`/forger`, `/harden`, `/blind`). The table gives the code name for each.

| Route | Screen (pitch name) | Calls |
|---|---|---|
| `/setup` | Setup + Contract | `POST /trials`, `GET /trials/{id}`, `GET /contract/{id}` |
| `/forger` | Impostor live | `POST /fake-data/runs`, SSE `/fake-data/runs/{id}/stream` |
| `/harden` | Patch + Stranger + Breaking Point | `POST /fraud-checks/patch`, `POST /test-attacker/eval` (suites `[0, vN]`), `POST /breaking-point` ×2 (v0, vN) |
| `/blind` | Guess Who → Tell → Seal | `GET /blind-leak/guess-cards`, `POST /blind-leak/guess-cards/score`, `POST /blind-leak/runs`, `POST /blind-leak/cheapest-fix`, `POST /blind-leak/policy` |
| `/report` | Probe Report | `GET /report/{id}` |
| `/demo` | All five, presenter mode (← → space, P pause, C code, R restart) | (the above) |
| `/` | Marketing homepage | none (illustrations only, no backend data) |

## Rules when changing the contract

1. **Backend owners:** if you change `backend/models.py`, a route path, or a fixture's shape, run `make mock` and `make types`, then `cd probe-frontend && npm run typecheck`. Fix what breaks, or tell Akarsh. Type errors in `lib/api.ts` or a screen mean the UI is reading a field that no longer exists.
2. **Frontend:** never handwrite response interfaces. Use `Schemas['X']` from `lib/api.ts`, and add new calls to the `api` object rather than calling `fetch` from components.
3. **Don't invent data in the UI.** No placeholder metrics, patient values or outcomes. Missing means N/A. The homepage's KYOTO HEART section is cited historical context, not a Probe result.
4. Fields with a server default (`seed`, `suite_version`, …) are optional in request types because `gen:api` runs with `--default-non-nullable false`. Keep that flag.

## Status (updated 2026-10-17, branch `ui/frontend-integration`)

**Done**
- All five screens are wired to the real backend routes and typed from the generated schema.
- Verified against `make mock`: typecheck and build pass, and headless Chrome clicks through the whole `/demo` flow with no console errors and no failed requests.
- Contract flips from NOT TESTED to PASSED/FAILED once the report loads. The test-attacker chart shows counts plus Wilson 95% error bars. The breaking-point chart compares v0 with vN. The cheapest-fix scatter highlights the recommended combo and flags `safety_ok: false` in red.

**Known gaps / next up**
- **Cached and live modes are untested from the UI.** Only `/fake-data/runs` and its stream implement `cached`; every other route returns 501 outside mock, so the UI shows "Not built yet (owner: …)" there.
- **Contract mid-demo:** in mock, `GET /contract/{id}` stays all-untested until the report loads, which also sets the contract from `/report`. The mock-only `?fixture=mixed` exists (`api.getContract(id, 'mixed')`) but isn't used.
- **"View test code" modal (Impostor screen) is empty:** it reads `code` from each round, but `RoundEvent` has no code field. It needs a backend field (Shreyas) before it can show the attacker's diff.
- Patch runs against suite v0 only (one patch round), and the test attacker evaluates `[0, new_version]`. Multi-round patching isn't surfaced yet.
- Mock `POST /breaking-point` returns the same curve for every version, so v0 and vN overlap on `/harden`. The report uses the distinct curves in `report.json`.
- Route and file names (`forger`, `harden`, `useForgerStream`) predate the README's naming table. Renaming them is cosmetic and was left out of this branch.
- `npm audit` reports advisories against `next@14.2.35`; not yet triaged.

When you finish a chunk of frontend or integration work, update this Status section (date, what moved, what's still open).
