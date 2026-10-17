from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from backend.config import cached_replay_speed, demo_mode, mock_stream_interval_s
from backend.mocks import load_mock
from backend.models import FakeDataRun, FakeDataRunCreate, RoundEvent
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
        damage={k: damage[k] for k in ("effect_real", "effect_with_fake", "p_with_fake")} if damage else None,
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


@router.get("/runs/{run_id}/stream")
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
