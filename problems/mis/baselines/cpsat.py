"""Exact / anytime MIS with Google OR-Tools CP-SAT (edge formulation x_u + x_v <= 1).

This is the solver most "quantum advantage" papers compare against, so it belongs in
the baseline set. If CP-SAT closes the gap, the instance is certified optimal.

    pip install ortools
    python baselines/cpsat.py INSTANCE.gph[.gz] --time 60 [--hint SOL] [--out SOL]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from qvsc.mis.graph import read_dimacs, read_solution, write_solution  # noqa: E402


def solve(g, time_limit=60.0, workers=8, hint=None, seed=0):
    from ortools.sat.python import cp_model

    m = cp_model.CpModel()
    x = [m.NewBoolVar(f"x{v}") for v in range(g.n)]
    for u, v in g.edges:
        m.AddBoolOr([x[u].Not(), x[v].Not()])
    m.Maximize(sum(x))
    if hint:
        hs = {v - 1 for v in hint}
        for v in range(g.n):
            m.AddHint(x[v], 1 if v in hs else 0)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = time_limit
    s.parameters.num_workers = workers
    s.parameters.random_seed = seed
    t0 = time.perf_counter()
    st = s.Solve(m)
    dt = time.perf_counter() - t0
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, None, dt, False
    sol = [v for v in range(g.n) if s.Value(x[v])]
    return sol, int(s.BestObjectiveBound()), dt, st == cp_model.OPTIMAL


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance")
    ap.add_argument("--time", type=float, default=60)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--hint")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    g = read_dimacs(a.instance)
    hint = read_solution(a.hint) if a.hint else None
    sol, bound, dt, optimal = solve(g, a.time, a.workers, hint)
    if sol is None:
        print(json.dumps({"size": None, "total_time": round(dt, 3)}))
        return
    if a.out:
        write_solution([v + 1 for v in sol], a.out,
                       [f"QvsC baseline cpsat time_limit={a.time}", f"size = {len(sol)}",
                        f"upper_bound = {bound}", f"optimal = {optimal}"])
    print(json.dumps({"size": len(sol), "upper_bound": bound, "optimal": optimal, "total_time": round(dt, 3)}))


if __name__ == "__main__":
    main()
