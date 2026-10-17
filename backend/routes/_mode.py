"""Shared mock/live switch for routes."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from backend.config import demo_mode
from backend.mocks import load_mock

M = TypeVar("M", bound=BaseModel)


def serve(fixture: str, model: type[M], owner: str, **overrides: object) -> M:
    """In mock mode, return fixture `fixture` validated as `model` (with `overrides` applied).

    In cached/live mode, raise NotImplementedError naming the owner; main.py turns that into a 501.
    """
    mode = demo_mode()
    if mode == "mock":
        data = load_mock(fixture)
        assert isinstance(data, dict)
        data.update(overrides)
        return model.model_validate(data)
    raise NotImplementedError(f"owner: {owner} ({mode} mode)")
