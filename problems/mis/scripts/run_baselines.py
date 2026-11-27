"""Run a reference baseline on every registered instance and write a submission folder.

    python problems/mis/scripts/run_baselines.py greedy
    python problems/mis/scripts/run_baselines.py arw_ils --time 10 --jobs 4
    python problems/mis/scripts/run_baselines.py cpsat --time 30 --max-edges 300000
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import json
import platform
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # problems/mis
sys.path.insert(0, str(ROOT.parents[1]))
from qvsc.mis.registry import instance_path, load_index  # noqa: E402

META = {
    "greedy": dict(method="Minimum-degree greedy", paradigm="classical",
                   description="Adds a minimum-degree vertex, deletes its neighbourhood, repeats. Deterministic, single pass."),
    "arw_ils": dict(method="ARW iterated local search", paradigm="classical",
                    description="Iterated local search with (1,2)-swaps and random kicks, after Andrade, Resende and Werneck (J. Heuristics 2012).",
                    reference="https://doi.org/10.1007/s10732-012-9196-4"),
    "cpsat": dict(method="OR-Tools CP-SAT (edge formulation)", paradigm="classical",
                  description="Exact branch-and-bound / clause learning solver from Google OR-Tools, used as an anytime solver with a time limit; certifies optimality when it closes the gap."),
}


def cpu_name():
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def run_one(algo, row, sol_path, a):
    inst = instance_path(row)
    if algo == "greedy":
        cmd = [sys.executable, str(ROOT / "baselines/greedy.py"), str(inst), "--out", str(sol_path)]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    elif algo == "arw_ils":
        cmd = [str(a.binary), "-", "--time", str(a.time), "--seed", str(a.seed), "--out", str(sol_path)]
        if row["status"] == "optimal":
            cmd += ["--target", str(row["best_known"])]  # stop early once optimal
        out = subprocess.run(cmd, input=gzip.decompress(inst.read_bytes()), capture_output=True, check=True).stdout.decode()
    elif algo == "cpsat":
        cmd = [sys.executable, str(ROOT / "baselines/cpsat.py"), str(inst), "--time", str(a.time),
               "--workers", str(a.workers), "--out", str(sol_path)]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return json.loads(out.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("algo", choices=sorted(META))
    ap.add_argument("--time", type=float, default=10)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--workers", type=int, default=8, help="CP-SAT threads")
    ap.add_argument("--max-edges", type=int, default=0, help="skip instances with more edges (0 = no limit)")
    ap.add_argument("--binary", type=Path, default=ROOT / "baselines" / "arw_ils")
    ap.add_argument("--only", nargs="*", help="instance names")
    ap.add_argument("--name", help="submission folder name")
    a = ap.parse_args()

    idx = load_index()
    names = [n for n in idx if (not a.only or n in a.only) and (not a.max_edges or idx[n]["m"] <= a.max_edges)]
    today = dt.date.today().isoformat()
    sub = ROOT / "submissions" / (a.name or f"{today}_{a.algo}_qvsc-baselines")
    (sub / "solutions").mkdir(parents=True, exist_ok=True)

    def job(name):
        try:
            r = run_one(a.algo, idx[name], sub / "solutions" / f"{name}.sol", a)
        except subprocess.CalledProcessError as e:
            print(f"{name}: FAILED {e}", file=sys.stderr)
            return name, None
        print(f"{name}: {r.get('size')} (best known {idx[name]['best_known']})", flush=True)
        return name, r

    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        results = dict(ex.map(job, names))

    with open(sub / "results.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["instance", "reported_size", "time_to_best_s", "total_time_s", "seed", "upper_bound"])
        for n in names:
            r = results.get(n)
            if r and r.get("size") is not None:
                w.writerow([n, r["size"], r.get("time_to_best", ""), r.get("total_time", ""),
                            r.get("seed", a.seed if a.algo != "greedy" else ""), r.get("upper_bound", "")])

    m = META[a.algo]
    limit = 0 if a.algo == "greedy" else a.time
    toml = [
        "[submission]",
        f'method = "{m["method"]}"',
        'authors = ["QvsC maintainers"]',
        f'paradigm = "{m["paradigm"]}"   # classical | quantum | hybrid',
        f'date = "{today}"',
        f'hardware = "{cpu_name()}, {"%d CP-SAT threads" % a.workers if a.algo == "cpsat" else "1 thread"}"',
        f"time_limit_s = {limit:g}   # wall-clock budget per instance (0 = run to completion)",
        f'code = "https://github.com/qvsc-bench/qvsc/tree/main/problems/mis/baselines"',
        f'description = "{m["description"]}"',
    ]
    if a.algo == "cpsat":
        toml.append("exact = true   # results.csv upper_bound column holds proven bounds")
    if "reference" in m:
        toml.append(f'reference = "{m["reference"]}"')
    (sub / "submission.toml").write_text("\n".join(toml) + "\n")
    print(f"wrote {sub}")


if __name__ == "__main__":
    main()
