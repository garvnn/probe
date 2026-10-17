"""Download the NHANES files the simulator needs into data/raw/, then build the processed base. Owner: Garv.

Files: DEMO, GHB, GLU, BMX, BPXO. Default cycle is 2017-March 2020 pre-pandemic (`P_` prefix),
the largest recent sample. URLs verified 2026-10-17 against the current CDC layout:
https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/<year>/DataFiles/<FILE>.xpt

The processed base (data/processed/nhanes_base.csv) is committed so every teammate generates
identical trials; rerun this only to rebuild it.

Usage:
    python -m scripts.download_nhanes --cycle 2017-2020 --out data/raw
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

OWNER = "Garv"

CYCLES: dict[str, tuple[str, dict[str, str]]] = {
    "2017-2020": ("2017", {"demo": "P_DEMO", "ghb": "P_GHB", "glu": "P_GLU", "bmx": "P_BMX", "bpx": "P_BPXO"}),
    "2017-2018": ("2017", {"demo": "DEMO_J", "ghb": "GHB_J", "glu": "GLU_J", "bmx": "BMX_J", "bpx": "BPX_J"}),
}
"""Cycle -> (URL year folder, role -> file name)."""

URL = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{name}.xpt"


def download(cycle: str, out: Path) -> dict[str, Path]:
    """Fetch each file for `cycle` into `out` (skipping ones already there). Returns role -> path."""
    year, files = CYCLES[cycle]
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for role, name in files.items():
        path = out / f"{name}.xpt"
        if not path.exists():
            with urllib.request.urlopen(URL.format(year=year, name=name), timeout=60) as resp:
                body = resp.read()
            if body[:6] != b"HEADER":  # CDC serves an HTML page for unknown files
                raise RuntimeError(f"{name}: not an XPT file; check the file name for cycle {cycle}")
            path.write_bytes(body)
        paths[role] = path
    return paths


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cycle", default="2017-2020", choices=sorted(CYCLES), help="NHANES cycle")
    parser.add_argument("--out", type=Path, default=Path("data/raw"))
    args = parser.parse_args(argv)

    from engine.simulator.nhanes import BASE_PATH, build_base

    download(args.cycle, args.out)
    base = build_base(args.cycle, args.out)
    BASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    base.to_csv(BASE_PATH, index=False)
    print(f"wrote {len(base)} participants to {BASE_PATH}")


if __name__ == "__main__":
    main()
