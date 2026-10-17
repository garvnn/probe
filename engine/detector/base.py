"""Site data container and the SiteCheck interface every check implements. Owner: Garv."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pandas as pd


@dataclass
class SiteData:
    """All tables for one site.

    Attributes:
        site_id: Site identifier, e.g. "S07".
        tables: Table name -> DataFrame, filtered to this site's patients.
    """

    site_id: str
    tables: dict[str, pd.DataFrame]


@runtime_checkable
class SiteCheck(Protocol):
    """One forensic check. Droid-written checks must implement this too."""

    name: str

    def score(self, site: SiteData, reference: list[SiteData]) -> float:
        """Return a z-like score for `site` against `reference` sites. Higher = more suspicious."""
        ...
