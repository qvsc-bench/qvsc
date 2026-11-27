"""Run a reference baseline on the registered Max-Cut instances and write a submission folder.

    g++ -O3 -std=c++17 -o problems/maxcut/baselines/maxcut_heur problems/maxcut/baselines/maxcut_heur.cpp
    python problems/maxcut/scripts/run_baselines.py greedy_ls
    python problems/maxcut/scripts/run_baselines.py sa   --time 10 --jobs 4
    python problems/maxcut/scripts/run_baselines.py tabu --time 10 --jobs 4
    python problems/maxcut/scripts/run_baselines.py bm   --time 10 --jobs 4
    python problems/maxcut/scripts/run_baselines.py cpsat --time 30 --max-edges 50000
    python problems/maxcut/scripts/run_baselines.py exact --max-n 30

The heuristics stop early when they reach a value already proven optimal. Every improvement of the
best cut is logged in trajectories/<instance>.traj, from which the leaderboard computes time-to-target.
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

ROOT = Path(__file__).resolve().parents[1]          # problems/maxcut
sys.path.insert(0, str(ROOT.parents[1]))
from qvsc.maxcut.registry import instance_path, load_index  # noqa: E402

CODE = "https://github.com/qvsc-bench/qvsc/tree/main/problems/maxcut/baselines"
META = {
    "greedy_ls": dict(method="Greedy + 1-flip local search", description="Places vertices one at a time on the better side, then moves single vertices while the cut grows. Deterministic, single pass: the floor."),
    "tabu": dict(method="Tabu search (1-flip)", description="1-flip tabu search with incremental gains, random tenure, aspiration and perturbation restarts from the best cut.",
                 reference="https://doi.org/10.1016/j.engappai.2012.09.001"),
    "sa": dict(method="Simulated annealing", description="Metropolis 1-flip simulated annealing, geometric schedule scaled to the instance, restarts with doubled length until the budget ends.",
               reference="https://doi.org/10.1126/science.220.4598.671"),
    "bm": dict(method="Burer-Monteiro SDP + rounding", description="Low-rank SDP relaxation solved by the mixing method, Goemans-Williamson hyperplane rounding and 1-flip local search, restarted until the budget ends.",
               reference="https://doi.org/10.1137/S1052623400382467"),
    "cpsat": dict(method="OR-Tools CP-SAT", description="Exact solver from Google OR-Tools on the XOR formulation, used as an anytime solver with a time limit; certifies optimality when it closes the gap."),
    "exact": dict(method="Exhaustive enumeration", description="Gray-code enumeration of all 2^(n-1) cuts: certifies the optimum of instances with n <= 30."),
}


def cpu_name():
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def run_one(algo, row, sub, a):
    inst = instance_path(row)
    name = row["name"]
    sol = sub / "solutions" / f"{name}.sol"
    if algo == "greedy_ls":
        cmd = [sys.executable, str(ROOT / "baselines/greedy_ls.py"), str(inst), "--out", str(sol)]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    elif algo == "cpsat":
        cmd = [sys.executable, str(ROOT / "baselines/cpsat.py"), str(inst), "--time", str(a.time),
               "--workers", str(a.workers), "--out", str(sol)]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    else:
        traj = sub / "trajectories" / f"{name}.traj"
        cmd = [str(a.binary), algo, "-", "--time", str(a.time), "--seed", str(a.seed), "--out", str(sol)]
        if algo != "exact":
            cmd += ["--trajectory", str(traj)]
        if row["status"] == "optimal":
            cmd += ["--target", str(row["best_known"])]  # stop early once optimal
        out = subprocess.run(cmd, input=gzip.decompress(inst.read_bytes()), capture_output=True, check=True).stdout.decode()
        if traj.exists():
            thin_trajectory(traj)
    return json.loads(out.strip().splitlines()[-1])


def thin_trajectory(path: Path, keep: float = 0.98) -> None:
    """Keep the improvements within 2% of the final cut: enough for time-to-target at any
    target at or above the final cut, and much smaller files."""
    pts = [line.split() for line in path.read_text().splitlines() if line.strip()]
    if not pts:
        return
    final = int(pts[-1][1])
    thr = keep * final if final > 0 else float("-inf")
    path.write_text("".join(f"{t} {c}\n" for t, c in pts if int(c) >= thr))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("algo", choices=sorted(META))
    ap.add_argument("--time", type=float, default=10)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--workers", type=int, default=8, help="CP-SAT threads")
    ap.add_argument("--max-edges", type=int, default=0, help="skip instances with more edges (0 = no limit)")
    ap.add_argument("--max-n", type=int, default=0, help="skip instances with more vertices (0 = no limit)")
    ap.add_argument("--binary", type=Path, default=ROOT / "baselines" / "maxcut_heur")
    ap.add_argument("--only", nargs="*", help="instance names")
    ap.add_argument("--families", nargs="*", help="only these families")
    ap.add_argument("--name", help="submission folder name")
    a = ap.parse_args()
    if a.algo == "exact" and not a.max_n:
        a.max_n = 30

    idx = load_index()
    names = [n for n in idx if (not a.only or n in a.only) and (not a.families or idx[n]["family"] in a.families)
             and (not a.max_edges or idx[n]["m"] <= a.max_edges) and (not a.max_n or idx[n]["n"] <= a.max_n)]
    today = dt.date.today().isoformat()
    sub = ROOT / "submissions" / (a.name or f"{today}_{a.algo}_qvsc-baselines")
    (sub / "solutions").mkdir(parents=True, exist_ok=True)
    if a.algo not in ("greedy_ls", "cpsat", "exact"):
        (sub / "trajectories").mkdir(exist_ok=True)

    def job(name):
        try:
            r = run_one(a.algo, idx[name], sub, a)
        except subprocess.CalledProcessError as e:
            print(f"{name}: FAILED {e} {e.stderr[-300:] if e.stderr else ''}", file=sys.stderr)
            return name, None
        print(f"{name}: {r.get('cut')} (target {idx[name]['reference_value'] or idx[name]['best_known']})", flush=True)
        return name, r

    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        results = dict(ex.map(job, names))

    old = {}
    if (sub / "results.csv").exists():  # allow running a baseline in several batches into one folder
        old = {r["instance"]: r for r in csv.DictReader(open(sub / "results.csv"))}
    with open(sub / "results.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["instance", "reported_cut", "time_to_best_s", "total_time_s", "seed", "upper_bound"])
        for n in sorted(set(old) | set(names)):
            r = results.get(n)
            if r and r.get("cut") is not None:
                w.writerow([n, r["cut"], r.get("time_to_best", ""), r.get("total_time", ""),
                            r.get("seed", "" if a.algo in ("greedy_ls", "exact") else a.seed),
                            r.get("upper_bound", r["cut"] if a.algo == "exact" else "")])
            elif n in old:
                o = old[n]
                w.writerow([n, o["reported_cut"], o["time_to_best_s"], o["total_time_s"], o["seed"], o["upper_bound"]])

    m = META[a.algo]
    limit = 0 if a.algo in ("greedy_ls", "exact") else a.time
    threads = f"{a.workers} CP-SAT threads" if a.algo == "cpsat" else "1 thread"
    toml = [
        "[submission]",
        f'method = "{m["method"]}"',
        'authors = ["QvsC maintainers"]',
        'paradigm = "classical"   # classical | quantum | hybrid',
        f'date = "{today}"',
        f'hardware = "{cpu_name()}, {threads}"',
        f"time_limit_s = {limit:g}   # wall-clock budget per instance (0 = run to completion)",
        f'code = "{CODE}"',
        f'description = "{m["description"]}"',
    ]
    if a.algo in ("cpsat", "exact"):
        toml.append("exact = true   # results.csv upper_bound column holds proven bounds")
    if "reference" in m:
        toml.append(f'reference = "{m["reference"]}"')
    (sub / "submission.toml").write_text("\n".join(toml) + "\n")
    print(f"wrote {sub}")


if __name__ == "__main__":
    main()
