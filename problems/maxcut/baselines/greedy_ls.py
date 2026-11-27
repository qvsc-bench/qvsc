"""The floor: greedy construction followed by 1-flip local search. Pure Python, deterministic.

    python problems/maxcut/baselines/greedy_ls.py INSTANCE.mc.gz --out sol.sol

Vertices are placed one at a time (highest weighted degree first) on the side that cuts more
weight towards the vertices already placed; then single vertices are moved while that increases
the cut. The result is a local optimum, so it is at least half of the total positive weight on
unit-weight graphs. Any serious method should beat it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from qvsc.maxcut.graph import read_maxcut, write_solution  # noqa: E402


def greedy_local_search(n: int, adj) -> tuple[list[int], int]:
    order = sorted(range(n), key=lambda i: -sum(abs(w) for _, w in adj[i]))
    x = [-1] * n
    for i in order:
        to0 = sum(w for j, w in adj[i] if x[j] == 0)   # gained by putting i on side 1
        to1 = sum(w for j, w in adj[i] if x[j] == 1)   # gained by putting i on side 0
        x[i] = 1 if to0 >= to1 else 0
    gain = [sum(w if x[j] == x[i] else -w for j, w in adj[i]) for i in range(n)]
    stack = [i for i in range(n) if gain[i] > 0]
    while stack:
        i = stack.pop()
        if gain[i] <= 0:
            continue
        x[i] ^= 1
        gain[i] = -gain[i]
        for j, w in adj[i]:
            gain[j] += -2 * w if x[i] != x[j] else 2 * w
            if gain[j] > 0:
                stack.append(j)
    cut = sum(w for i in range(n) for j, w in adj[i] if i < j and x[i] != x[j])
    return x, cut


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance")
    ap.add_argument("--out")
    a = ap.parse_args()
    g = read_maxcut(a.instance)
    t0 = time.perf_counter()
    x, cut = greedy_local_search(g.n, g.adjacency())
    dt = time.perf_counter() - t0
    if a.out:
        write_solution([i + 1 for i in range(g.n) if x[i] == 1], a.out, [f"cut = {cut} (greedy + local search)"])
    print(json.dumps({"cut": cut, "time_to_best": round(dt, 4), "total_time": round(dt, 4)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
