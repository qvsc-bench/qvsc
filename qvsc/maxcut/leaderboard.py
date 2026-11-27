"""Validate every Max-Cut submission and build the static leaderboard.

    python -m qvsc.maxcut.leaderboard --check   # CI on pull requests: validate only
    python -m qvsc.maxcut.leaderboard           # validate, update records, write LEADERBOARD.md + docs/data/maxcut.json

A submission is a folder problems/maxcut/submissions/<YYYY-MM-DD>_<method>_<team>/ with
submission.toml, solutions/<instance>.sol, and optionally results.csv (timings) and
trajectories/<instance>.traj (one "time_s cut" line per improvement of the best cut).
Cut values are always recomputed from the solution files: reported numbers are never trusted.

Metrics, per track
    hits        instances where the cut reaches the target (best verified or literature value)
    mean ratio  mean of cut / target over the attempted instances
    at 99%      instances where the cut is at least 99% of the target
    TTT99       median time-to-target: first time the run reached 99% of the target, taken from
                the trajectory if there is one, else from the time_to_target_s column (self-reported)
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .graph import read_maxcut, read_solution
from .registry import INDEX, PROBLEM_DIR, ROOT, instance_path, load_index, refresh_status, save_index, target
from .verify import verify

REQUIRED = ["method", "authors", "paradigm", "date", "hardware", "time_limit_s"]
PARADIGMS = {"classical", "quantum", "hybrid"}
TTT_FRACTION = 0.99
TRACKS = [
    ("all", "All instances"),
    ("literature", "Literature (G-set, Biq Mac, MQLib)"),
    ("hardware-native", "Hardware-native graphs (Pegasus, Zephyr, heavy-hex)"),
    ("qaoa", "QAOA families (3-regular, SK)"),
    ("planted", "Planted (optimum known by construction)"),
    ("gate-scale", "Gate-scale (n ≤ 156)"),
]


@dataclass
class Submission:
    id: str
    meta: dict
    cuts: dict[str, int] = field(default_factory=dict)
    times: dict[str, dict] = field(default_factory=dict)
    traj: dict[str, list[tuple[float, int]]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def read_trajectory(path: Path) -> list[tuple[float, int]]:
    out = []
    for line in open(path, encoding="utf-8"):
        s = line.split("#", 1)[0].split()
        if len(s) >= 2:
            out.append((float(s[0]), int(float(s[1]))))
    return out


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
            graphs[name] = read_maxcut(instance_path(idx[name]))
        try:
            v = verify(graphs[name], read_solution(p))
        except ValueError as e:
            s.errors.append(str(e))
            continue
        if not v.valid:
            s.errors.append(f"{p.name}: " + "; ".join(v.errors[:3]))
            continue
        ub = idx[name]["upper_bound"]
        if ub is not None and v.cut > ub:
            s.errors.append(f"{p.name}: cut {v.cut} exceeds the proven upper bound {ub} (please report!)")
            continue
        s.cuts[name] = v.cut
    res = folder / "results.csv"
    if res.exists():
        for r in csv.DictReader(open(res, encoding="utf-8")):
            s.times[r["instance"]] = r
    for p in sorted((folder / "trajectories").glob("*.traj")):
        try:
            s.traj[p.stem] = read_trajectory(p)
        except ValueError as e:
            s.errors.append(f"trajectories/{p.name}: {e}")
    return s


def update_records(subs: list[Submission], idx: dict) -> list[str]:
    """Raise best-known values from verified cuts (earliest submission wins ties); take proven bounds."""
    changes = []
    for s in sorted(subs, key=lambda s: (str(s.meta.get("date")), s.id)):
        for name, cut in s.cuts.items():
            r = idx[name]
            if r["best_known"] is None or cut > r["best_known"]:
                changes.append(f"{name}: {r['best_known']} -> {cut} ({s.id})")
                r["best_known"], r["record_source"] = cut, s.id
        if s.meta.get("exact"):  # proven bounds from exact solvers (maintainer-reviewed)
            for name, t in s.times.items():
                ub = t.get("upper_bound")
                if name in idx and ub:
                    r, ub = idx[name], int(ub)
                    if r["upper_bound"] is None or ub < r["upper_bound"]:
                        r["upper_bound"] = ub
                        changes.append(f"{name}: upper bound {ub} ({s.id})")
    for r in idx.values():
        before = r["status"]
        refresh_status(r)
        if r["status"] == "optimal" and before != "optimal":
            changes.append(f"{r['name']}: proven optimal")
    return changes


def time_to_target(s: Submission, name: str, tgt: int) -> float | None:
    """First time the run reached TTT_FRACTION of the target, if known."""
    if tgt is None or tgt <= 0:
        return None
    thr = TTT_FRACTION * tgt
    if name in s.traj:
        for t, c in s.traj[name]:
            if c >= thr:
                return t
        return None
    v = (s.times.get(name) or {}).get("time_to_target_s")
    return float(v) if v not in (None, "") else None


def summarize(subs, idx, track):
    names = [n for n, r in idx.items() if track in r["tracks"]]
    rows = []
    for s in subs:
        att = [n for n in names if n in s.cuts and (target(idx[n]) or 0) > 0]
        if not att:
            continue
        tg = {n: target(idx[n]) for n in att}
        hits = sum(s.cuts[n] >= tg[n] for n in att)
        ratio = sum(s.cuts[n] / tg[n] for n in att) / len(att)
        at99 = [n for n in att if s.cuts[n] >= TTT_FRACTION * tg[n]]
        ttts = [t for t in (time_to_target(s, n, tg[n]) for n in at99) if t is not None]
        rows.append(dict(id=s.id, method=s.meta.get("method", s.id), paradigm=s.meta.get("paradigm", "?"),
                         authors=", ".join(s.meta.get("authors", [])), hardware=s.meta.get("hardware", ""),
                         time_limit=s.meta.get("time_limit_s", ""), attempted=len(att), total=len(names),
                         hits=hits, ratio=100 * ratio, at99=len(at99),
                         ttt99=statistics.median(ttts) if ttts else None, ttt_n=len(ttts)))
    rows.sort(key=lambda r: (-r["hits"], -r["ratio"], -r["attempted"]))
    return rows


def _fmt_t(t):
    if t is None:
        return "–"
    return f"{t:.3g}"


def write_markdown(subs, idx, path: Path):
    L = ["# QvsC leaderboard: Max-Cut", "",
         "> Auto-generated by `python -m qvsc.maxcut.leaderboard` — do not edit by hand.",
         "> **Target** = the larger of the best cut verified in this repository and the best value reported in the",
         "> literature (for planted instances: the optimum known by construction). **Hits** = cut ≥ target;",
         "> **ratio** = mean cut / target; **at 99%** = instances within 1% of the target; **TTT99** = median",
         "> time to first reach 99% of the target over those instances (from trajectories, self-reported timings).",
         "> Time limits and hardware differ between submissions: read them before comparing.",
         "> How to read these numbers, with an example: [README.md](README.md#how-to-read-the-mean-ratio).", ""]
    for track, title in TRACKS:
        rows = summarize(subs, idx, track)
        if not rows:
            continue
        L += [f"## {title}", "",
              "| # | Method | Paradigm | Hits | At 99% | Attempted | Mean ratio | TTT99 (s) | Time limit (s) | Hardware | Submission |",
              "|--:|:--|:--|--:|--:|--:|--:|--:|--:|:--|:--|"]
        for i, r in enumerate(rows, 1):
            L.append(f"| {i} | {r['method']} | {r['paradigm']} | {r['hits']} | {r['at99']} | {r['attempted']}/{r['total']} | "
                     f"{r['ratio']:.3f}% | {_fmt_t(r['ttt99'])} | {r['time_limit']} | {r['hardware']} | "
                     f"[{r['id']}](submissions/{r['id']}) |")
        L.append("")
    L += ["## Per-instance results", "",
          "Bold: the cut reaches the target. Status: *optimal* (best known = proven bound), *best-known*,",
          "*below-reference* (no solution in this repository reaches the literature value yet), *open*.", "",
          "| Instance | Family | n | m | Weights | Target | Best verified | Upper bound | Status | "
          + " | ".join(s.meta.get("method", s.id) for s in subs) + " |",
          "|:--|:--|--:|--:|:--|--:|--:|--:|:--|" + "--:|" * len(subs)]
    for name in sorted(idx, key=lambda n: (idx[n]["family"], idx[n]["n"], n.lower())):
        r = idx[name]
        tg = target(r)
        cells = []
        for s in subs:
            v = s.cuts.get(name)
            cells.append("" if v is None else (f"**{v}**" if tg is not None and v >= tg else str(v)))
        L.append(f"| {name} | {r['family']} | {r['n']} | {r['m']} | {r['weights']} | {'' if tg is None else tg} | "
                 f"{'' if r['best_known'] is None else r['best_known']} | {'' if r['upper_bound'] is None else r['upper_bound']} | "
                 f"{r['status']} | " + " | ".join(cells) + " |")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def write_site(subs, idx, folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    data = {"problem": "maxcut",
            "title": "Max-Cut",
            "track_titles": dict(TRACKS),
            "tracks": {t: summarize(subs, idx, t) for t, _ in TRACKS},
            "instances": {n: {**r, "target": target(r)} for n, r in idx.items()},
            "submissions": {s.id: {"meta": s.meta, "cuts": s.cuts} for s in subs}}
    (folder / "maxcut.json").write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    a = ap.parse_args(argv)
    idx = load_index()
    graphs: dict = {}
    folders = sorted(f for f in (PROBLEM_DIR / "submissions").iterdir() if f.is_dir()) \
        if (PROBLEM_DIR / "submissions").exists() else []
    subs = [load_submission(f, idx, graphs) for f in folders]
    bad = [s for s in subs if s.errors]
    for s in subs:
        status = "INVALID" if s.errors else "ok"
        print(f"[{status}] {s.id}: {len(s.cuts)} verified cuts")
        for err in s.errors:
            print("    -", err)
    if bad:
        return 1
    for c in update_records(subs, idx):
        print("record:", c)
    if a.check:
        return 0
    save_index(idx, INDEX)
    write_markdown(subs, idx, PROBLEM_DIR / "LEADERBOARD.md")
    write_site(subs, idx, ROOT / "docs" / "data")
    print("wrote problems/maxcut/LEADERBOARD.md and docs/data/maxcut.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
