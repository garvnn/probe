"""Every module in the repo imports cleanly."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

PACKAGES = ["engine", "integrations", "evals", "backend", "scripts"]


def _modules() -> list[str]:
    names: list[str] = []
    for pkg_name in PACKAGES:
        pkg = importlib.import_module(pkg_name)
        names.append(pkg_name)
        for info in pkgutil.walk_packages(pkg.__path__, prefix=f"{pkg_name}."):
            names.append(info.name)
    return names


@pytest.mark.parametrize("name", _modules())
def test_import(name: str) -> None:
    importlib.import_module(name)


def test_stub_names_owner() -> None:
    from engine.simulator.nhanes import load_nhanes

    with pytest.raises(NotImplementedError, match="owner: Garv"):
        load_nhanes()
