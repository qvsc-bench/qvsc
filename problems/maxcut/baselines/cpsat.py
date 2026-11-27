"""Max-Cut with Google OR-Tools CP-SAT: anytime solver that also proves upper bounds.

    pip install ortools
    python problems/maxcut/baselines/cpsat.py INSTANCE.mc.gz --time 30 --workers 8 --out sol.sol

Model: one Boolean x_i per vertex (side of the cut) and one Boolean y_e per edge with
y_e = x_u XOR x_v; maximise sum_e w_e y_e. Vertex 1 is fixed to side 0 to break the symmetry.
Prints one JSON line: cut, proven upper bound, status, time.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from qvsc.maxcut.graph import read_maxcut, write_solution  # noqa: E402


def solve(g, time_limit: float, workers: int, seed: int = 1, hint=None):
    from ortools.sat.python import cp_model

    m = cp_model.CpModel()
    x = [m.NewBoolVar(f"x{i}") for i in range(g.n)]
    if g.n:
        m.Add(x[0] == 0)
    obj = []
    for k, (u, v, w) in enumerate(g.edges):
        y = m.NewBoolVar(f"y{k}")
        m.AddBoolXOr([x[u], x[v], y.Not()])  # y == x_u xor x_v
        obj.append(w * y)
    m.Maximize(sum(obj))
    if hint:
        for i in range(g.n):
            m.AddHint(x[i], i in hint)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = time_limit
    s.parameters.num_search_workers = workers
    s.parameters.random_seed = seed
    t0 = time.perf_counter()
    st = s.Solve(m)
    dt = time.perf_counter() - t0
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, None, s.StatusName(st), dt
    val = round(s.ObjectiveValue())
    side = [i for i in range(g.n) if s.Value(x[i])]
    ub = val if st == cp_model.OPTIMAL else math.floor(s.BestObjectiveBound() + 1e-6)
    return side, (val, ub), s.StatusName(st), dt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance")
    ap.add_argument("--time", type=float, default=30)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out")
    a = ap.parse_args()
    g = read_maxcut(a.instance)
    side, vals, status, dt = solve(g, a.time, a.workers, a.seed)
    if side is None:
        print(json.dumps({"cut": None, "status": status, "total_time": round(dt, 3)}))
        return 1
    if a.out:
        write_solution([i + 1 for i in side], a.out, [f"cut = {vals[0]} (CP-SAT, {status})"])
    print(json.dumps({"cut": vals[0], "upper_bound": vals[1], "status": status,
                      "total_time": round(dt, 3), "seed": a.seed}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
