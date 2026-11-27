"""Validate every K-SAT submission and build the static leaderboard.

    python -m qvsc.ksat.leaderboard --check [--instances data/ksat]   # CI on pull requests: validate only
    python -m qvsc.ksat.leaderboard [--instances data/ksat]           # also write LEADERBOARD.md + docs/data/ksat.json

Two kinds of rows:

* **Reported (paper)**: the per-instance results of Skenderi et al. (2026), imported from
  RandCSPBench into problems/ksat/reference/. The paper did not publish assignments, so QvsC
  cannot check them; they are shown as reported.
* **Verified (QvsC)**: submissions in problems/ksat/submissions/<YYYY-MM-DD>_<method>_<team>/ with
  submission.toml and assignments in solutions.txt.gz (one line "<instance> <bit string>") and/or
  solutions/<instance>.sol. The number of unsatisfied clauses is always recomputed here from the
  assignment and the CNF file (downloaded with `python -m qvsc.ksat.fetch`). Optional results.csv
  (instance,time_to_solution_s,total_time_s) gives the self-reported times.

Metrics, per track (definitions of the paper, Sec. 2.3)
    solved             instances where the assignment satisfies every clause
    score S            solved / known satisfiable, in % ; an instance is known satisfiable if at least
                       one algorithm of the paper or one verified QvsC submission solved it
    residual energy    mean of (unsatisfied clauses / M) over the attempted instances the method did not solve
    time to solution   median over the solved instances of the run time to the first satisfying assignment
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import statistics
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .cnf import parse_assignment, read_cnf
from .registry import (INDEX, PROBLEM_DIR, REFERENCE_DIR, ROOT, TRACKS, instance_file, load_index,
                       refresh_status, save_index, target_known, target_unsat)
from .verify import unsat_clauses

REQUIRED = ["method", "authors", "paradigm", "date", "hardware", "time_limit_s"]
PARADIGMS = {"classical", "quantum", "hybrid"}
DEFAULT_INSTANCES = ROOT / "data" / "ksat"


@dataclass
class Entry:
    id: str
    meta: dict
    verified: bool
    source: str = ""
    unsat: dict[str, int] = field(default_factory=dict)       # instance -> unsatisfied clauses
    tts: dict[str, float] = field(default_factory=dict)       # instance -> time to solution (s)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- reference results of the paper

def load_reference(idx: dict) -> list[Entry]:
    meta_path = REFERENCE_DIR / "randcspbench" / "algorithms.toml"
    if not meta_path.exists():
        return []
    algos = tomllib.loads(meta_path.read_text(encoding="utf-8"))["algorithms"]
    out = []
    for key, m in algos.items():
        e = Entry(f"paper:{key}", {**m, "paradigm": "classical", "authors": ["Skenderi et al. 2026"],
                                    "hardware": "AMD Threadripper PRO 5975WX (paper, Table 3)",
                                    "time_limit_s": m.get("budget", "")}, verified=False,
                  source="reported (paper)")
        for k in (3, 4):
            p = REFERENCE_DIR / "randcspbench" / f"{k}SAT_{key}.csv.gz"
            if not p.exists():
                continue
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    if r["name"] in idx:
                        e.unsat[r["name"]] = int(r["unsat"])
                        if r["time_s"] and int(r["unsat"]) == 0:
                            e.tts[r["name"]] = float(r["time_s"])
        out.append(e)
    return out


def load_pelofske(idx: dict) -> list[Entry]:
    """QAOA runs of Pelofske et al. (2023): best measured assignment per device and instance.

    The unsatisfied clauses are recomputed by QvsC from the published measurement bit strings
    (problems/ksat/scripts/import_extra.py), so these rows are checked, but that the bit strings
    came from the devices is the authors' statement."""
    p = REFERENCE_DIR / "pelofske2023" / "devices.csv.gz"
    if not p.exists():
        return []
    by_dev: dict[str, Entry] = {}
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["name"] not in idx:
                continue
            dev = r["device"]
            if dev not in by_dev:
                by_dev[dev] = Entry(f"pelofske2023:{dev}", {
                    "method": f"QAOA on {dev}", "kind": "QAOA (hardware)", "paradigm": "quantum",
                    "authors": ["Pelofske, Bärtschi, Golden & Eidenbenz 2023"], "hardware": dev,
                    "time_limit_s": "best of all measured shots, all depths p"}, verified=False,
                    source="published samples, rechecked")
            by_dev[dev].unsat[r["name"]] = int(r["unsat"])
    return list(by_dev.values())


# ---------------------------------------------------------------- submissions

def read_bulk(path: Path):
    with gzip.open(path, "rt", encoding="ascii") as fh:
        for ln, line in enumerate(fh, 1):
            s = line.split("#", 1)[0].split()
            if not s:
                continue
            if len(s) != 2:
                raise ValueError(f"{path.name}:{ln}: expected '<instance> <bit string>'")
            yield s[0], s[1]


def load_submission(folder: Path, idx: dict, instances: Path, cache: dict) -> Entry:
    e = Entry(folder.name, {}, verified=True)
    tp = folder / "submission.toml"
    if not tp.exists():
        e.errors.append("missing submission.toml")
        return e
    try:
        e.meta = tomllib.loads(tp.read_text(encoding="utf-8")).get("submission", {})
    except tomllib.TOMLDecodeError as err:
        e.errors.append(f"submission.toml: {err}")
        return e
    for k in REQUIRED:
        if k not in e.meta:
            e.errors.append(f"submission.toml: missing field '{k}'")
    if e.meta.get("paradigm") not in PARADIGMS:
        e.errors.append(f"submission.toml: paradigm must be one of {sorted(PARADIGMS)}")
    items: list[tuple[str, str]] = []
    if (folder / "solutions.txt.gz").exists():
        try:
            items += list(read_bulk(folder / "solutions.txt.gz"))
        except (ValueError, OSError) as err:
            e.errors.append(str(err))
    for p in sorted((folder / "solutions").glob("*.sol")):
        items.append((p.stem, p.read_text(encoding="ascii")))
    if not items:
        e.errors.append("no assignments (solutions.txt.gz or solutions/*.sol)")
    for name, text in items:
        if name not in idx:
            e.errors.append(f"unknown instance '{name}'")
            continue
        if name in e.unsat:
            e.errors.append(f"{name}: assignment given twice")
            continue
        if name not in cache:
            cache[name] = read_cnf(instance_file(instances, idx[name]))
        f = cache[name]
        try:
            e.unsat[name] = unsat_clauses(f, parse_assignment(text, f.n))
        except ValueError as err:
            e.errors.append(f"{name}: {err}")
    res = folder / "results.csv"
    if res.exists():
        for r in csv.DictReader(open(res, encoding="utf-8")):
            n, t = r.get("instance"), r.get("time_to_solution_s")
            if n in e.unsat and e.unsat[n] <= target_unsat(idx[n]) and t not in (None, ""):
                e.tts[n] = float(t)
    return e


def update_records(subs: list[Entry], idx: dict) -> list[str]:
    changes = []
    for s in sorted(subs, key=lambda s: (str(s.meta.get("date")), s.id)):
        for name, u in s.unsat.items():
            r = idx[name]
            if r["optimum_unsat"] is not None and u < r["optimum_unsat"]:
                raise SystemExit(f"{s.id}: {name} has {u} unsatisfied clauses, below the proven optimum "
                                 f"{r['optimum_unsat']}: the index is wrong, please report it")
            if u <= target_unsat(r) and not r["sat_source"]:
                r["sat_source"] = s.id
                if not r["paper_solved"] and r["optimum_unsat"] is None:
                    changes.append(f"{name}: first satisfying assignment ({s.id})")
    for r in idx.values():
        refresh_status(r)
    return changes


# ---------------------------------------------------------------- metrics

def known_sat(idx: dict) -> set[str]:
    return {n for n, r in idx.items() if target_known(r)}


def summarize(entries: list[Entry], idx: dict, track: str, ks: set[str], by_n: bool = False):
    names = [n for n, r in idx.items() if track in r["tracks"]]
    rows = []
    for e in entries:
        att = [n for n in names if n in e.unsat]
        if not att:
            continue
        solved = [n for n in att if e.unsat[n] <= target_unsat(idx[n])]
        known = [n for n in att if n in ks]
        unsolved = [n for n in att if e.unsat[n] > target_unsat(idx[n])]
        times = [e.tts[n] for n in solved if n in e.tts]
        row = dict(id=e.id, method=e.meta.get("method", e.id), paradigm=e.meta.get("paradigm", "?"),
                   kind=e.meta.get("kind", ""), verified=e.verified, source=e.source or "verified",
                   authors=", ".join(e.meta.get("authors", [])), hardware=e.meta.get("hardware", ""),
                   budget=("none (runs to completion)" if e.meta.get("time_limit_s") in (0, "0")
                           else f"{e.meta['time_limit_s']} s" if isinstance(e.meta.get("time_limit_s"), (int, float))
                           else str(e.meta.get("time_limit_s", ""))), in_table1=e.meta.get("in_table1"),
                   attempted=len(att), total=len(names), solved=len(solved), known_sat=len(known),
                   score=100 * len(solved) / len(known) if known else None,
                   residual=(statistics.fmean(e.unsat[n] / idx[n]["m"] for n in unsolved) if unsolved else None),
                   tts=statistics.median(times) if times else None, tts_n=len(times))
        if by_n:
            row["by_n"] = {}
            for N in sorted({idx[n]["n"] for n in att}):
                kn = [n for n in known if idx[n]["n"] == N]
                sv = [n for n in solved if idx[n]["n"] == N]
                row["by_n"][N] = 100 * len(sv) / len(kn) if kn else None
        rows.append(row)
    rows.sort(key=lambda r: (-r["solved"], -(r["score"] or 0), r["tts"] if r["tts"] is not None else 1e18))
    return rows


def _f(x, fmt):
    return "–" if x is None else format(x, fmt)


def write_markdown(entries, idx, ks, path: Path):
    L = ["# QvsC leaderboard: K-SAT", "",
         "> Auto-generated by `python -m qvsc.ksat.leaderboard`: do not edit by hand.",
         "> Instances and reference results: RandCSPBench, Skenderi et al. (2026),",
         "> [arXiv:2602.18419](https://arxiv.org/abs/2602.18419). **Score S** = solved / known satisfiable (an",
         "> instance is known satisfiable if any algorithm of the paper or any verified submission solved it).",
         "> **Residual energy** = mean unsatisfied clauses / M over the instances the method did not solve.",
         "> **Time to solution** = median over the solved instances. *Reported* rows come from the paper (no",
         "> assignments published); *verified* rows are recomputed by QvsC from the submitted assignments.",
         "> Budgets and hardware differ between rows: read them before comparing.",
         "> How to read these numbers: [README.md](README.md#how-the-leaderboard-works).", ""]
    for track, title in TRACKS:
        rows = summarize(entries, idx, track, ks, by_n=True)
        if not rows:
            continue
        names = [n for n, r in idx.items() if track in r["tracks"]]
        nk = sum(n in ks for n in names)
        has_opt = any(idx[n]["optimum_unsat"] is not None for n in names)
        what = "with a proven optimum or a known satisfying assignment" if has_opt else "known satisfiable"
        L += [f"## {title}", "", f"{len(names)} instances, {nk} {what}.", "",
              "| # | Method | Kind | Source | Solved | Score S | Residual energy | Time to solution (s) | Budget | Submission |",
              "|--:|:--|:--|:--|--:|--:|--:|--:|:--|:--|"]
        for i, r in enumerate(rows, 1):
            src = r["source"]
            link = (f"[{r['id']}](submissions/{r['id']})" if r["verified"]
                    else "Pelofske et al." if r["id"].startswith("pelofske") else "RandCSPBench")
            L.append(f"| {i} | {r['method']} | {r['kind'] or r['paradigm']} | {src} | {r['solved']}/{r['attempted']} | "
                     f"{_f(r['score'], '.2f')}% | {_f(r['residual'], '.4f')} | {_f(r['tts'], '.3g')} | {r['budget']} | {link} |")
        Ns = sorted({N for r in rows for N in r["by_n"]})
        L += ["", "Score S by number of variables N:", "",
              "| Method | " + " | ".join(f"N={N}" for N in Ns) + " |",
              "|:--|" + "--:|" * len(Ns)]
        for r in rows:
            L.append(f"| {r['method']} | " + " | ".join(_f(r["by_n"].get(N), ".1f") for N in Ns) + " |")
        L.append("")
    L += pelofske_detail(idx)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def pelofske_detail(idx: dict) -> list[str]:
    """Shots that reached the optimum on each device, against uniform random guessing."""
    dev_p = REFERENCE_DIR / "pelofske2023" / "devices.csv.gz"
    inst_p = REFERENCE_DIR / "pelofske2023" / "instances.csv"
    if not (dev_p.exists() and inst_p.exists()):
        return []
    inst = {r["name"]: r for r in csv.DictReader(open(inst_p, encoding="utf-8"))}
    with gzip.open(dev_p, "rt", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    devices = sorted({r["device"] for r in rows})
    cell = {(r["device"], r["name"]): r for r in rows}
    L = ["## QAOA hardware runs in detail (Pelofske et al. 2023)", "",
         "For each instance and device: shots that reached the optimum / all shots, pooled over every published",
         "run (all QAOA depths p). **Random** is the probability that one uniformly random assignment is optimal",
         "(optimal assignments / 2ⁿ, counted by exhaustive search). A device beats random guessing on an",
         "instance when its fraction of optimal shots is above that probability.", "",
         "| Instance | n | m | Optimum (unsat) | Random | " + " | ".join(devices) + " |",
         "|:--|--:|--:|--:|--:|" + "--:|" * len(devices)]
    for name in sorted(inst, key=lambda n: int(inst[n]["n"])):
        r = inst[name]
        n = int(r["n"])
        pr = int(r["optimal_assignments"]) / 2 ** n
        cells = []
        for d in devices:
            c = cell.get((d, name))
            if c is None:
                cells.append("")
                continue
            o, s = int(c["optimal_shots"]), int(c["shots"])
            cells.append(f"{o}/{s} ({o / s:.2g})" if o else f"0/{s}")
        L.append(f"| {name} | {n} | {r['m']} | {r['optimum_unsat']} | {pr:.2g} | " + " | ".join(cells) + " |")
    L.append("")
    return L


def write_site(entries, idx, ks, folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    counts = {}
    for t, _ in TRACKS:
        names = [n for n, r in idx.items() if t in r["tracks"]]
        counts[t] = {"instances": len(names), "known_sat": sum(n in ks for n in names)}
    data = {"problem": "ksat", "title": "K-SAT",
            "source": "RandCSPBench, Skenderi et al. (2026), arXiv:2602.18419",
            "track_titles": dict(TRACKS), "track_counts": counts,
            "tracks": {t: summarize(entries, idx, t, ks, by_n=True) for t, _ in TRACKS}}
    (folder / "ksat.json").write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    ap.add_argument("--instances", type=Path, default=Path(os.environ.get("QVSC_KSAT_INSTANCES", DEFAULT_INSTANCES)),
                    help="folder where kSAT.zip was extracted (python -m qvsc.ksat.fetch --out ...)")
    a = ap.parse_args(argv)
    idx = load_index()
    sub_dir = PROBLEM_DIR / "submissions"
    folders = sorted(f for f in sub_dir.iterdir() if f.is_dir()) if sub_dir.exists() else []
    cache: dict = {}
    subs = []
    for f in folders:
        try:
            subs.append(load_submission(f, idx, a.instances, cache))
        except FileNotFoundError as err:
            print(f"[INVALID] {f.name}: {err}")
            return 1
    bad = False
    for s in subs:
        print(f"[{'INVALID' if s.errors else 'ok'}] {s.id}: {len(s.unsat)} assignments, "
              f"{sum(u <= target_unsat(idx[n]) for n, u in s.unsat.items())} at the target")
        for err in s.errors[:20]:
            print("    -", err)
        bad |= bool(s.errors)
    if bad:
        return 1
    for c in update_records(subs, idx):
        print("record:", c)
    ref = load_reference(idx) + load_pelofske(idx)
    print(f"reference: {len(ref)} rows from published results")
    if a.check:
        return 0
    ks = known_sat(idx)
    entries = ref + subs
    save_index(idx, INDEX)
    write_markdown(entries, idx, ks, PROBLEM_DIR / "LEADERBOARD.md")
    write_site(entries, idx, ks, ROOT / "docs" / "data")
    print("wrote problems/ksat/LEADERBOARD.md and docs/data/ksat.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
