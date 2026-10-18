"""Shared mock/live switch for routes."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from backend.config import demo_mode
from backend.mocks import load_mock

M = TypeVar("M", bound=BaseModel)


def serve(fixture: str, model: type[M], owner: str, **overrides: object) -> M:
    """In mock mode, return fixture `fixture` validated as `model` (with `overrides` applied).

    Cached mode has no cache for this route yet, so it serves the same fixture (still `_mock: true`,
    so the UI badges it) and the cached demo can run end to end next to a real fake-data replay.
    In live mode, raise NotImplementedError naming the owner; main.py turns that into a 501.
    """
    mode = demo_mode()
    if mode in ("mock", "cached"):
        data = load_mock(fixture)
        assert isinstance(data, dict)
        data.update(overrides)
        return model.model_validate(data)
    raise NotImplementedError(f"owner: {owner} ({mode} mode)")
