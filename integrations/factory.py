"""Factory Droid as the defender: writes a new SiteCheck from escaped fakes. Owner: Shreyas."""

from __future__ import annotations

import os
from typing import Protocol

OWNER = "Shreyas"


class DroidClient(Protocol):
    def write_check(self, task: dict) -> str:
        """Submit a task (see engine.patch.droid_task) and return the proposed check's Python source."""
        ...


class FactoryDroid:
    """Real Droid client."""

    # TODO: verify Droid API/CLI flow at docs.factory.ai

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("FACTORY_API_KEY", "")

    def write_check(self, task: dict) -> str:
        raise NotImplementedError(f"owner: {OWNER}")


CANNED_CHECK_SOURCE = '''\
class MockCheck:
    """Mock Droid output for wiring. Always scores 0."""

    name = "mock_droid_check"

    def score(self, site, reference):
        return 0.0
'''


class LocalMockDroid:
    """Returns a canned check source. The source still only ever runs in a sandbox."""

    def write_check(self, task: dict) -> str:
        return CANNED_CHECK_SOURCE
