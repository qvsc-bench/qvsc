"""Minimum-degree greedy for MIS (the simplest sensible baseline).

Repeatedly picks a vertex of minimum degree in the remaining graph, adds it to the
set and deletes it together with its neighbours.

    python baselines/greedy.py INSTANCE.gph[.gz] [--out SOLUTION.sol]
"""

from __future__ import annotations

import argparse
import heapq
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from qvsc.mis.graph import read_dimacs, write_solution  # noqa: E402


def min_degree_greedy(n, adj):
    alive = [True] * n
    deg = [len(a) for a in adj]
    heap = [(deg[v], v) for v in range(n)]
    heapq.heapify(heap)
    sol = []
    while heap:
        d, v = heapq.heappop(heap)
        if not alive[v] or d != deg[v]:
            continue
        sol.append(v)
        alive[v] = False
        removed = [u for u in adj[v] if alive[u]]
        for u in removed:
            alive[u] = False
        for u in removed:
            for w in adj[u]:
                if alive[w]:
                    deg[w] -= 1
                    heapq.heappush(heap, (deg[w], w))
    return sol


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    g = read_dimacs(a.instance)
    t0 = time.perf_counter()
    sol = min_degree_greedy(g.n, [list(s) for s in g.adjacency()])
    dt = time.perf_counter() - t0
    if a.out:
        write_solution([v + 1 for v in sol], a.out, [f"QvsC baseline greedy_mindeg", f"size = {len(sol)}"])
    print(json.dumps({"size": len(sol), "time_to_best": round(dt, 4), "total_time": round(dt, 4)}))


if __name__ == "__main__":
    main()
