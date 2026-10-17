from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from backend.config import demo_mode, mock_stream_interval_s
from backend.mocks import load_mock
from backend.models import ForgerRun, ForgerRunCreate, RoundEvent
from backend.routes._mode import serve

router = APIRouter(prefix="/forger", tags=["forger"])
OWNER = "Shreyas"


@router.post("/runs", response_model=ForgerRun)
def start_run(body: ForgerRunCreate) -> ForgerRun:
    """Start an attack run in the background (engine.forger.loop.forger_loop)."""
    return serve("forger_run", ForgerRun, OWNER, trial_id=body.trial_id, attacker_id=body.attacker_id)


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str) -> EventSourceResponse:
    """SSE: one `round` event per forger round (RoundEvent shape), then a `done` event."""
    mode = demo_mode()
    if mode != "mock":
        raise NotImplementedError(f"owner: {OWNER} ({mode} mode)")

    rounds = [RoundEvent.model_validate(r) for r in load_mock("forger_rounds")]
    interval = mock_stream_interval_s()

    async def events() -> AsyncIterator[dict]:
        for i, r in enumerate(rounds):
            if i:
                await asyncio.sleep(interval)
            yield {"event": "round", "data": r.model_dump_json(by_alias=True)}
        yield {"event": "done", "data": json.dumps({"run_id": run_id, "_mock": True})}

    return EventSourceResponse(events())
