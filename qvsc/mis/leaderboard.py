"""Validate every submission and build the static leaderboard.

    python -m qvsc.mis.leaderboard --check      # CI on pull requests: validate only
    python -m qvsc.mis.leaderboard              # validate, update records, write LEADERBOARD.md + docs/data/mis.json

A submission is a folder problems/mis/submissions/<YYYY-MM-DD>_<method>_<team>/ containing
submission.toml, solutions/<instance>.sol and optionally results.csv (timings).
Sizes are always recomputed from the solution files: reported numbers are never trusted.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .graph import read_dimacs, read_solution
from .registry import INDEX, PROBLEM_DIR, ROOT, instance_path, load_index, save_index
from .verify import verify

REQUIRED = ["method", "authors", "paradigm", "date", "hardware", "time_limit_s"]
PARADIGMS = {"classical", "quantum", "hybrid"}
TRACKS = [
    ("all", "All instances"),
    ("quantum-scale", "Quantum-scale (n ≤ 128)"),
    ("review-qbench", "Quantum benchmark set of Marino, Buffoni & Zavalnij (2026)"),
    ("review-evil", "EVIL set"),
]


@dataclass
class Submission:
    id: str
    meta: dict
    sizes: dict[str, int] = field(default_factory=dict)
    times: dict[str, dict] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def load_submission(folder: Path, idx: dict, graphs: dict) -> Submission:
    s = Submission(folder.name, {})
    toml_path = folder / "submission.toml"
    if not toml_path.exists():
        s.errors.append("missing submission.toml")
        return s
    try:
        s.meta = tomllib.loads(toml_path.read_text(encoding="utf-8")).get("submission", {})
    except tomllib.TOMLDecodeError as e:
        s.errors.append(f"submission.toml: {e}")
        return s
    for k in REQUIRED:
        if k not in s.meta:
            s.errors.append(f"submission.toml: missing field '{k}'")
    if s.meta.get("paradigm") not in PARADIGMS:
        s.errors.append(f"submission.toml: paradigm must be one of {sorted(PARADIGMS)}")
    sols = sorted((folder / "solutions").glob("*.sol"))
    if not sols:
        s.errors.append("no solutions/*.sol files")
    for p in sols:
        name = p.stem
        if name not in idx:
            s.errors.append(f"{p.name}: unknown instance '{name}'")
            continue
        if name not in graphs:
            graphs[name] = read_dimacs(instance_path(idx[name]))
        try:
            v = verify(graphs[name], read_solution(p))
        except ValueError as e:
            s.errors.append(str(e))
            continue
        if not v.valid:
            s.errors.append(f"{p.name}: " + "; ".join(v.errors[:3]))
            continue
        ub = idx[name]["upper_bound"]
        if ub is not None and v.size > ub:
            s.errors.append(f"{p.name}: size {v.size} exceeds the proven upper bound {ub} (please report!)")
            continue
        s.sizes[name] = v.size
    res = folder / "results.csv"
    if res.exists():
        for r in csv.DictReader(open(res, encoding="utf-8")):
            s.times[r["instance"]] = r
    return s


def update_records(subs: list[Submission], idx: dict) -> list[str]:
    """Raise best-known values from verified solutions; earliest submission wins ties."""
    changes = []
    for s in sorted(subs, key=lambda s: (str(s.meta.get("date")), s.id)):
        for name, size in s.sizes.items():
            r = idx[name]
            if size > r["best_known"]:
                changes.append(f"{name}: {r['best_known']} -> {size} ({s.id})")
                r["best_known"], r["record_source"] = size, s.id
                r["status"] = "optimal" if r["upper_bound"] == size else "best-known"
        if s.meta.get("exact"):  # proven bounds from exact solvers (maintainer-reviewed)
            for name, t in s.times.items():
                ub = t.get("upper_bound")
                if name in idx and ub:
                    r, ub = idx[name], int(ub)
                    if r["upper_bound"] is None or ub < r["upper_bound"]:
                        r["upper_bound"] = ub
                        changes.append(f"{name}: upper bound {ub} ({s.id})")
                    if r["best_known"] == r["upper_bound"] and r["status"] != "optimal":
                        r["status"] = "optimal"
                        changes.append(f"{name}: proven optimal ({s.id})")
    return changes


def summarize(subs, idx, track):
    names = [n for n, r in idx.items() if track in r["tracks"]]
    rows = []
    for s in subs:
        att = [n for n in names if n in s.sizes]
        if not att:
            continue
        hits = sum(s.sizes[n] >= idx[n]["best_known"] for n in att)
        gap = sum((idx[n]["best_known"] - s.sizes[n]) / idx[n]["best_known"] for n in att) / len(att)
        rows.append(dict(id=s.id, method=s.meta.get("method", s.id), paradigm=s.meta.get("paradigm", "?"),
                         authors=", ".join(s.meta.get("authors", [])), hardware=s.meta.get("hardware", ""),
                         time_limit=s.meta.get("time_limit_s", ""), attempted=len(att), total=len(names),
                         hits=hits, gap=100 * gap))
    rows.sort(key=lambda r: (-r["hits"], r["gap"], -r["attempted"]))
    return rows


def write_markdown(subs, idx, path: Path):
    L = ["# QvsC leaderboard: Maximum Independent Set", "",
         "> Auto-generated by `python -m qvsc.mis.leaderboard` — do not edit by hand.",
         "> **Hits** = instances where the submission matches the best-known value; **gap** = mean relative",
         "> distance from the best-known value over the instances the submission attempted.",
         "> Time limits and hardware differ between submissions: read them before comparing.", ""]
    for track, title in TRACKS:
        rows = summarize(subs, idx, track)
        if not rows:
            continue
        L += [f"## {title}", "",
              "| # | Method | Paradigm | Authors | Hits | Attempted | Mean gap | Time limit (s) | Hardware | Submission |",
              "|--:|:--|:--|:--|--:|--:|--:|--:|:--|:--|"]
        for i, r in enumerate(rows, 1):
            L.append(f"| {i} | {r['method']} | {r['paradigm']} | {r['authors']} | {r['hits']} | "
                     f"{r['attempted']}/{r['total']} | {r['gap']:.2f}% | {r['time_limit']} | {r['hardware']} | "
                     f"[{r['id']}](submissions/{r['id']}) |")
        L.append("")
    L += ["## Per-instance results", "",
          "| Instance | Family | n | m | Best known | Status | " + " | ".join(s.meta.get("method", s.id) for s in subs) + " |",
          "|:--|:--|--:|--:|--:|:--|" + "--:|" * len(subs)]
    for name in sorted(idx, key=lambda n: (idx[n]["family"], idx[n]["n"], n.lower())):
        r = idx[name]
        cells = []
        for s in subs:
            v = s.sizes.get(name)
            cells.append("" if v is None else (f"**{v}**" if v >= r["best_known"] else str(v)))
        L.append(f"| {name} | {r['family']} | {r['n']} | {r['m']} | {r['best_known']} | {r['status']} | " + " | ".join(cells) + " |")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def write_site(subs, idx, folder: Path):
    """Write the data the landing page (docs/index.html) renders. The page itself is static."""
    folder.mkdir(parents=True, exist_ok=True)
    data = {"problem": "mis",
            "title": "Maximum Independent Set",
            "track_titles": dict(TRACKS),
            "tracks": {t: summarize(subs, idx, t) for t, _ in TRACKS},
            "instances": idx,
            "submissions": {s.id: {"meta": s.meta, "sizes": s.sizes} for s in subs}}
    (folder / "mis.json").write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    a = ap.parse_args(argv)
    idx = load_index()
    graphs: dict = {}
    subs = [load_submission(f, idx, graphs) for f in sorted((PROBLEM_DIR / "submissions").iterdir()) if f.is_dir()]
    bad = [s for s in subs if s.errors]
    for s in subs:
        status = "INVALID" if s.errors else "ok"
        print(f"[{status}] {s.id}: {len(s.sizes)} verified solutions")
        for err in s.errors:
            print("    -", err)
    if bad:
        return 1
    changes = update_records(subs, idx)
    for c in changes:
        print("record:", c)
    if a.check:
        return 0
    save_index(idx, INDEX)
    write_markdown(subs, idx, PROBLEM_DIR / "LEADERBOARD.md")
    write_site(subs, idx, ROOT / "docs" / "data")
    print("wrote problems/mis/LEADERBOARD.md and docs/data/mis.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
