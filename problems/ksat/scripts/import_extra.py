"""Add the quantum-hardware and SATLIB instances to the K-SAT index.

    python -m qvsc.ksat.fetch --out data/ksat            # downloads all sources (or see --local)
    g++ -O3 -std=c++17 -o problems/ksat/baselines/exhaustive problems/ksat/baselines/exhaustive.cpp
    python problems/ksat/scripts/import_extra.py --instances data/ksat \\
        --pelofske-dataset <unzipped Zenodo 8201693>/dataset --exhaustive problems/ksat/baselines/exhaustive

Does four things:

1. Index rows for the 17 MAX 3-SAT instances of Pelofske et al. (2023) (n = 6 ... 22, 4n clauses)
   and the 1000 SATLIB uf20-91 instances, with the optimum proven by exhaustive search.
   The Pelofske optimum is checked against the `max_obj` published with the instances.
2. problems/ksat/reference/pelofske2023/devices.csv.gz: per device and instance, the best
   assignment measured over all published runs, its unsatisfied clauses (recomputed here), the
   number of shots and the number of shots that reached the optimum.
3. problems/ksat/reference/pelofske2023/instances.csv: optimum and number of optimal assignments
   (so the success probability of uniform random guessing is known exactly).
4. The submission problems/ksat/submissions/2026-11-27_exhaustive_qvsc-baselines (the exhaustive
   search itself, with its timings on this machine).
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import platform
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from qvsc.ksat.cnf import cnf_hash, read_cnf, to_bitstring  # noqa: E402
from qvsc.ksat.registry import INDEX, PROBLEM_DIR, REFERENCE_DIR, instance_file, load_index, refresh_status, save_index, tracks_for  # noqa: E402
from qvsc.ksat.sources import parse_pelofske_problems, pelofske_samples  # noqa: E402
from qvsc.ksat.verify import unsat_clauses  # noqa: E402

SUB = PROBLEM_DIR / "submissions" / "2026-11-27_exhaustive_qvsc-baselines"


def exhaustive(binary: Path, cnf: Path) -> tuple[dict, str]:
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "x.sol"
        r = subprocess.run([str(binary), str(cnf), "--out", str(out)], capture_output=True, text=True, check=True)
        return json.loads(r.stdout), out.read_text().strip()


def gz_write(path: Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    with open(path, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(buf.getvalue().encode())


def cpu_name() -> str:
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown CPU"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instances", required=True, type=Path, help="folder written by python -m qvsc.ksat.fetch")
    ap.add_argument("--pelofske-dataset", required=True, type=Path, help="the dataset/ folder of Zenodo 8201693")
    ap.add_argument("--exhaustive", required=True, type=Path, help="compiled problems/ksat/baselines/exhaustive.cpp")
    a = ap.parse_args(argv)
    idx = load_index()
    idx = {n: r for n, r in idx.items() if r["source"] not in ("pelofske2023", "satlib")}
    sols, times, stats = [], [], []

    # 1a. Pelofske et al. (2023)
    probs = parse_pelofske_problems((a.pelofske_dataset / "problems.md").read_text(encoding="utf-8"))
    cnfs = {}
    for n, d in sorted(probs.items()):
        name = f"pelofske_k3_n{n}"
        row = {"name": name, "source": "pelofske2023", "path": f"pelofske2023/k3_n{n}.cnf", "k": 3, "n": n,
               "m": d["cnf"].m, "alpha": round(d["cnf"].m / n, 2), "split": "hardware", "tracks": tracks_for(3, n, "pelofske2023"),
               "paper_solved": 0, "sat_source": ""}
        path = instance_file(a.instances, row)
        f = read_cnf(path)
        if f.clauses != d["cnf"].clauses:
            raise SystemExit(f"{path} differs from problems.md")
        res, bits = exhaustive(a.exhaustive, path)
        if f.m - res["optimum_unsat"] != d["max_obj"]:
            raise SystemExit(f"{name}: exhaustive optimum {f.m - res['optimum_unsat']} != published max_obj {d['max_obj']}")
        row.update(cnf_sha256=cnf_hash(f)[:16], optimum_unsat=res["optimum_unsat"])
        refresh_status(row)
        idx[name] = row
        cnfs[n] = (name, f)
        sols.append((name, bits))
        times.append((name, res["time_to_solution_s"], res["total_time_s"]))
        stats.append((name, n, f.m, res["optimum_unsat"], res["optimal_assignments"]))
    print(f"pelofske2023: {len(probs)} instances, optima match the published max_obj")

    # 1b. SATLIB uf20-91
    satlib = sorted((a.instances / "satlib" / "uf20-91").glob("uf20-*.cnf"), key=lambda p: int(p.stem.split("-0")[1]))
    for p in satlib:
        name = f"satlib_{p.stem}"
        f = read_cnf(p)
        res, bits = exhaustive(a.exhaustive, p)
        if res["optimum_unsat"] != 0:
            raise SystemExit(f"{p}: not satisfiable?")
        row = {"name": name, "source": "satlib", "path": f"satlib/uf20-91/{p.name}", "k": 3, "n": f.n, "m": f.m,
               "alpha": round(f.m / f.n, 2), "split": "uf20-91", "tracks": tracks_for(3, f.n, "satlib"),
               "cnf_sha256": cnf_hash(f)[:16], "paper_solved": 0, "optimum_unsat": 0, "sat_source": ""}
        refresh_status(row)
        idx[name] = row
        sols.append((name, bits))
        times.append((name, res["time_to_solution_s"], res["total_time_s"]))
    print(f"satlib: {len(satlib)} uf20-91 instances, all satisfiable")
    save_index(idx)

    # 2. hardware samples
    agg = defaultdict(lambda: {"unsat": None, "bits": "", "shots": 0, "opt": 0, "runs": 0})
    for dev, p, n, _, samples in pelofske_samples(a.pelofske_dataset):
        name, f = cnfs[n]
        opt = idx[name]["optimum_unsat"]
        g = agg[(dev, name)]
        g["runs"] += 1
        for b, c in sorted(samples.items()):
            if len(b) != n or set(b) - {"0", "1"}:
                raise SystemExit(f"{dev} p={p} n={n}: bad bit string {b!r}")
            u = unsat_clauses(f, [ch == "1" for ch in b])
            if g["unsat"] is None or u < g["unsat"]:
                g["unsat"], g["bits"] = u, b
            g["shots"] += c
            g["opt"] += c if u == opt else 0
    gz_write(REFERENCE_DIR / "pelofske2023" / "devices.csv.gz",
             ["device", "name", "unsat", "best_assignment", "shots", "optimal_shots", "runs"],
             [(dev, name, g["unsat"], g["bits"], g["shots"], g["opt"], g["runs"])
              for (dev, name), g in sorted(agg.items(), key=lambda kv: (kv[0][0], idx[kv[0][1]]["n"]))])
    with open(REFERENCE_DIR / "pelofske2023" / "instances.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["name", "n", "m", "optimum_unsat", "optimal_assignments"])
        w.writerows(stats)
    print(f"pelofske2023: {len(agg)} (device, instance) pairs")

    # 4. the exhaustive-search submission
    SUB.mkdir(parents=True, exist_ok=True)
    buf = "".join(f"{n} {b}\n" for n, b in sols)
    with open(SUB / "solutions.txt.gz", "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(buf.encode())
    with open(SUB / "results.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["instance", "time_to_solution_s", "total_time_s"])
        w.writerows((n, f"{t:.6f}", f"{T:.6f}") for n, t, T in times)
    (SUB / "submission.toml").write_text(f'''[submission]
method = "Exhaustive search (Gray code)"
authors = ["QvsC maintainers"]
paradigm = "classical"   # classical | quantum | hybrid
kind = "exact"
date = "2026-11-27"
hardware = "{cpu_name()}, 1 thread"
time_limit_s = 0   # runs to completion: all 2^n assignments
code = "https://github.com/qvsc-bench/qvsc/tree/main/problems/ksat/baselines/exhaustive.cpp"
description = "Enumerates all 2^n assignments in Gray-code order (n <= 22 here). Proves the optimum; time_to_solution_s is when the enumeration first met an optimal assignment, total_time_s the full enumeration."
''', encoding="utf-8")
    print(f"wrote {SUB.relative_to(ROOT)}: {len(sols)} assignments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
