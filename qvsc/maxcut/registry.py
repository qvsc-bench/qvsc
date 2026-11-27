"""The Max-Cut instance registry: problems/maxcut/instances/index.csv.

Columns
    best_known        best cut value backed by a solution file in this repository (verified by CI)
    reference_value   best value reported in the literature, not (yet) backed by a solution file here
    upper_bound       proven upper bound (exact solver, or optimum known by construction)
    status            optimal | best-known | below-reference | open
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repository root
PROBLEM_DIR = ROOT / "problems" / "maxcut"          # instances, baselines, submissions
INDEX = PROBLEM_DIR / "instances" / "index.csv"
FIELDS = ["name", "family", "tracks", "n", "m", "weights", "best_known", "status", "upper_bound",
          "reference_value", "reference_source", "record_source", "sha256", "origin", "license"]
INT_FIELDS = ("best_known", "upper_bound", "reference_value")


def load_index(path: Path = INDEX) -> dict[str, dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for r in rows:
        r["n"], r["m"] = int(r["n"]), int(r["m"])
        for k in INT_FIELDS:
            r[k] = int(r[k]) if r[k] not in ("", None) else None
        r["tracks"] = r["tracks"].split(";") if r["tracks"] else []
        out[r["name"]] = r
    return out


def save_index(rows: dict[str, dict], path: Path = INDEX) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for name in sorted(rows, key=lambda s: (rows[s]["family"], rows[s]["n"], s.lower())):
            r = dict(rows[name])
            r["tracks"] = ";".join(r["tracks"])
            for k in INT_FIELDS:
                r[k] = "" if r[k] is None else r[k]
            w.writerow({k: r.get(k, "") for k in FIELDS})


def instance_path(row: dict, root: Path = PROBLEM_DIR) -> Path:
    return root / "instances" / row["family"] / f"{row['name']}.mc.gz"


def target(row: dict) -> int | None:
    """The value a solver is measured against: the larger of the verified and the literature value.

    For planted instances the reference value is the optimum known by construction."""
    vals = [v for v in (row["best_known"], row["reference_value"]) if v is not None]
    return max(vals) if vals else None


def refresh_status(row: dict) -> None:
    bk, ub, ref = row["best_known"], row["upper_bound"], row["reference_value"]
    if bk is not None and ub is not None and bk >= ub:
        row["status"] = "optimal"
    elif bk is None:
        row["status"] = "open"
    elif ref is not None and bk < ref:
        row["status"] = "below-reference"
    else:
        row["status"] = "best-known"
