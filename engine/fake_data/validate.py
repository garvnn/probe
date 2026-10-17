"""Schema validation for attacker output. Owner: Shreyas."""

from __future__ import annotations

from engine.fraud_checks.base import SiteData

OWNER = "Shreyas"


class SchemaError(ValueError):
    """Raised when a fake site doesn't match docs/schema.md. The message is fed back to the attacker verbatim."""


def validate_schema(output: dict[str, list[dict]], site_id: str) -> SiteData:
    """Check every table and column against docs/schema.md and return the fake site as SiteData.

    Raises SchemaError naming exactly which tables/columns are wrong.
    """
    raise NotImplementedError(f"owner: {OWNER}")
