"""Chalk: feature definitions + eval metric logging. Owner: Ajay."""

from __future__ import annotations

import os
from typing import Protocol

OWNER = "Ajay"


class MetricSink(Protocol):
    def log(self, name: str, value: float, context: dict) -> None:
        """Record one eval metric with its context (trial_id, suite_version, attacker_id, seed, ...)."""
        ...


class ChalkClient:
    """Real Chalk client."""

    # TODO: verify what counts as meaningful usage at chalk.ai/hackharvard

    def __init__(self, client_id: str | None = None, client_secret: str | None = None) -> None:
        self.client_id = client_id or os.environ.get("CHALK_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("CHALK_CLIENT_SECRET", "")

    def log(self, name: str, value: float, context: dict) -> None:
        raise NotImplementedError(f"owner: {OWNER}")


class LocalMockChalk:
    """Keeps metrics in memory."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def log(self, name: str, value: float, context: dict) -> None:
        self.records.append({"name": name, "value": value, "context": context})
