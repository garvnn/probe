"""Build the Factory Droid task that writes a new SiteCheck. Owner: Shreyas."""

from __future__ import annotations

from engine.fraud_checks.base import SiteData

OWNER = "Shreyas"

CHECK_INTERFACE = "engine/fraud_checks/base.py:SiteCheck"


def build_droid_task(escaped_fakes: list[SiteData]) -> dict:
    """Task payload: 'write a new site-level check that flags these escaped fakes', with examples
    and the SiteCheck interface. Droid's code is loaded only inside a sandbox."""
    raise NotImplementedError(f"owner: {OWNER}")
