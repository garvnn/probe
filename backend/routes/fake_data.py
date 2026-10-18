from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from backend.config import cached_replay_speed, demo_mode, mock_stream_interval_s
from backend.mocks import load_mock
from backend.models import FakeDataRun, FakeDataRunCreate, FakeDataRunDetail, RoundEvent
from backend.routes._mode import serve
from engine.fake_data import cache

router = APIRouter(prefix="/fake-data", tags=["fake-data"])
OWNER = "Shreyas"
MAX_REPLAY_GAP_S = 15.0


def round_event(rnd: dict, not_a_result: bool) -> RoundEvent:
    """A saved Round as the same RoundEvent the mock stream sends. `_mock` stays true for stand-in runs."""
    damage = rnd.get("damage")
    return RoundEvent(
        mock=not_a_result,
        round=rnd["round"],
        sandbox_id=rnd.get("sandbox_id") or "",
        runtime_s=rnd.get("sandbox_s") or 0.0,
        ok=rnd["ok"],
        scores=(rnd.get("scores") or {}).get("per_check"),
        combined=rnd.get("combined"),
        threshold=rnd["threshold"],
        escaped=rnd["escaped"],
        damage={k: damage.get(k) for k in ("effect_real", "effect_with_fake", "p_with_fake", "p_real")} if damage else None,
        code=rnd.get("code"),
        fired=rnd.get("fired") or [],
        diagnostics=rnd.get("diagnostics") or [],
        error=rnd.get("error"),
        attacker_model=rnd.get("attacker_model"),
        attacker_s=rnd.get("attacker_s"),
    )


def _load(run_id: str) -> dict:
    try:
        return cache.load_run(run_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


@router.post("/runs", response_model=FakeDataRun)
def start_run(body: FakeDataRunCreate) -> FakeDataRun:
    """Start an attack run (live), or point at the newest saved run (cached)."""
    if demo_mode() == "cached":
        run_id = cache.latest_run_id(body.trial_id)
        if run_id is None:
            raise HTTPException(status_code=404, detail=f"no saved runs in {cache.cache_dir()}; run scripts/run_impostor.py first")
        run = _load(run_id)
        return FakeDataRun(
            mock=run["not_a_result"],
            run_id=run_id,
            trial_id=run["trial_id"],
            attacker_id=run["attacker"]["id"],
            suite_version=run["suite"]["version"],
            status="done",
        )
    return serve("fake_data_run", FakeDataRun, OWNER, trial_id=body.trial_id, attacker_id=body.attacker_id)


@router.get("/runs/{run_id}", response_model=FakeDataRunDetail)
def get_run(run_id: str) -> FakeDataRunDetail:
    """Run header for the replay screen: attacker, suite, runner, token usage."""
    if demo_mode() != "cached":
        return serve("fake_data_run_detail", FakeDataRunDetail, OWNER, run_id=run_id)
    run = _load(run_id)
    usage = run.get("usage") or {}
    return FakeDataRunDetail(
        mock=run["not_a_result"],
        run_id=run["run_id"],
        trial_id=run["trial_id"],
        fake_site_id=run.get("fake_site_id"),
        attacker_id=run["attacker"]["id"],
        attacker_kind=run["attacker"].get("kind", ""),
        attacker_model=run["attacker"].get("model", ""),
        attacker_seed=run["attacker"].get("seed"),
        suite_version=run["suite"]["version"],
        threshold=run["suite"]["threshold"],
        runner=run.get("runner", ""),
        rounds_planned=run.get("rounds_planned", len(run["rounds"])),
        rounds_done=len(run["rounds"]),
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        label=run.get("label"),
    )


@router.get(
    "/runs/{run_id}/stream",
    responses={200: {"model": RoundEvent, "description": "text/event-stream: each `round` event's data is a RoundEvent; then one `done` event."}},
)
async def stream_run(run_id: str) -> EventSourceResponse:
    """SSE: one `round` event per fake-data round (RoundEvent shape), then a `done` event.

    mock: fixtures 1s apart. cached: a saved run replayed at its recorded pace (CACHED_REPLAY_SPEED).
    """
    mode = demo_mode()
    if mode == "mock":
        rounds = [RoundEvent.model_validate(r) for r in load_mock("fake_data_rounds")]
        gaps = [mock_stream_interval_s()] * len(rounds)
        done_mock = True
    elif mode == "cached":
        run = _load(run_id)
        rounds = [round_event(r, run["not_a_result"]) for r in run["rounds"]]
        speed = cached_replay_speed()
        gaps = [min((r.get("attacker_s", 0) + r.get("timings", {}).get("total_s", 0)) * speed, MAX_REPLAY_GAP_S) for r in run["rounds"]]
        done_mock = run["not_a_result"]
    else:
        raise NotImplementedError(f"owner: {OWNER} ({mode} mode)")

    async def events() -> AsyncIterator[dict]:
        for i, r in enumerate(rounds):
            if i and gaps[i]:
                await asyncio.sleep(gaps[i])
            yield {"event": "round", "data": r.model_dump_json(by_alias=True)}
        yield {"event": "done", "data": json.dumps({"run_id": run_id, "_mock": done_mock})}

    return EventSourceResponse(events())
