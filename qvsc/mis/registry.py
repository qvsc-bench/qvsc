"""The MIS instance registry: problems/mis/instances/index.csv."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repository root
PROBLEM_DIR = ROOT / "problems" / "mis"             # instances, baselines, submissions
INDEX = PROBLEM_DIR / "instances" / "index.csv"
FIELDS = ["name", "family", "tracks", "n", "m", "best_known", "status", "upper_bound",
          "record_source", "sha256", "origin", "license"]


def load_index(path: Path = INDEX) -> dict[str, dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for r in rows:
        for k in ("n", "m", "best_known"):
            r[k] = int(r[k])
        r["upper_bound"] = int(r["upper_bound"]) if r["upper_bound"] else None
        r["tracks"] = r["tracks"].split(";") if r["tracks"] else []
        out[r["name"]] = r
    return out


def save_index(rows: dict[str, dict], path: Path = INDEX) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for name in sorted(rows, key=lambda s: (rows[s]["family"], s.lower())):
            r = dict(rows[name])
            r["tracks"] = ";".join(r["tracks"])
            r["upper_bound"] = "" if r["upper_bound"] is None else r["upper_bound"]
            w.writerow(r)


def instance_path(row: dict, root: Path = PROBLEM_DIR) -> Path:
    return root / "instances" / row["family"] / f"{row['name']}.gph.gz"
