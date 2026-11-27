"""Reproducible generators for the Max-Cut instance families of QvsC.

Everything here is pure Python and driven by `random.Random(seed)`, so the same seed gives
the same instance on every machine. Hardware topologies (Pegasus, Zephyr, IBM heavy-hex) are
passed in as edge lists; see problems/maxcut/scripts/import_sources.py for where they come from.
"""

from __future__ import annotations

import random

from .graph import WGraph, make_graph


def random_regular(n: int, d: int, rng: random.Random, max_tries: int = 1000) -> list[tuple[int, int]]:
    """Uniform random simple d-regular graph (configuration model with rejection)."""
    if n * d % 2:
        raise ValueError("n*d must be even")
    for _ in range(max_tries):
        stubs = [v for v in range(n) for _ in range(d)]
        rng.shuffle(stubs)
        edges = set()
        ok = True
        for i in range(0, len(stubs), 2):
            u, v = stubs[i], stubs[i + 1]
            if u == v or (min(u, v), max(u, v)) in edges:
                ok = False
                break
            edges.add((min(u, v), max(u, v)))
        if ok:
            return sorted(edges)
    raise RuntimeError("could not sample a simple regular graph")


def complete(n: int) -> list[tuple[int, int]]:
    return [(u, v) for u in range(n) for v in range(u + 1, n)]


def pm1_weights(n: int, edges, rng: random.Random) -> WGraph:
    """Random +1/-1 weights on a fixed edge set (the +-J spin glass)."""
    return make_graph(n, [(u, v, rng.choice((-1, 1))) for u, v in edges])


def unit_weights(n: int, edges) -> WGraph:
    return make_graph(n, [(u, v, 1) for u, v in edges])


def cubic_lattice(L: int, periodic: bool = True) -> tuple[int, list[tuple[int, int]]]:
    """3D simple cubic lattice L x L x L (periodic boundary conditions by default)."""
    idx = lambda x, y, z: (x * L + y) * L + z  # noqa: E731
    edges = set()
    for x in range(L):
        for y in range(L):
            for z in range(L):
                for dx, dy, dz in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
                    X, Y, Z = x + dx, y + dy, z + dz
                    if not periodic and (X == L or Y == L or Z == L):
                        continue
                    a, b = idx(x, y, z), idx(X % L, Y % L, Z % L)
                    edges.add((min(a, b), max(a, b)))
    return L ** 3, sorted(edges)


def planted_frustrated_loops(n: int, edges, alpha: float, rng: random.Random,
                             min_len: int = 6, max_coupling: int = 3, max_tries: int = 200_000):
    """Frustrated-loop planting (Hen et al., PRA 92, 042325, 2015), rewritten for Max-Cut.

    Draw round(alpha * n) random cycles of the graph by non-backtracking random walks. On each
    cycle put J = -1 on every edge but one, which gets J = +1: every spin configuration violates
    at least one bond of the cycle, and the all-equal configuration violates exactly one, so it
    minimises each cycle's energy -(L - 2). The Ising energy H(s) = sum_ij J_ij s_i s_j is the sum
    of the cycle energies, hence the all-equal configuration is a ground state with
    E0 = -sum (L_c - 2). A random gauge t (J_ij -> J_ij t_i t_j) hides it.

    For Max-Cut with weights w = J, cut(s) = (W - H(s)) / 2 with W = sum of weights, so the optimum
    cut is (W - E0) / 2 and {i : t_i = +1} is an optimal side. Cycles that would push any |J| above
    `max_coupling` are rejected, as in the original construction.

    Returns (graph, planted_side_0based, optimum_cut).
    """
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    J: dict[tuple[int, int], int] = {}
    loops = round(alpha * n)
    e0 = 0
    tries = 0
    while loops > 0:
        tries += 1
        if tries > max_tries:
            raise RuntimeError("could not place enough loops; lower alpha or raise max_coupling")
        start = rng.randrange(n)
        if not adj[start]:
            continue
        path, pos, prev = [start], {start: 0}, -1
        while True:
            cur = path[-1]
            nbrs = [x for x in adj[cur] if x != prev] or adj[cur]
            nxt = rng.choice(nbrs)
            if nxt in pos:
                cyc = path[pos[nxt]:]
                break
            pos[nxt] = len(path)
            prev = cur
            path.append(nxt)
        L = len(cyc)
        if L < min_len:
            continue
        cyc_edges = [(cyc[i], cyc[(i + 1) % L]) for i in range(L)]
        cyc_edges = [(min(a, b), max(a, b)) for a, b in cyc_edges]
        anti = rng.randrange(L)
        delta = {e: (1 if i == anti else -1) for i, e in enumerate(cyc_edges)}
        if any(abs(J.get(e, 0) + d) > max_coupling for e, d in delta.items()):
            continue
        for e, d in delta.items():
            J[e] = J.get(e, 0) + d
        e0 -= L - 2
        loops -= 1
    t = [rng.choice((-1, 1)) for _ in range(n)]
    g = make_graph(n, [(u, v, w * t[u] * t[v]) for (u, v), w in J.items()])
    W = g.total_weight
    assert (W - e0) % 2 == 0
    optimum = (W - e0) // 2
    side = [i for i in range(n) if t[i] == 1]
    # sanity: the planted side achieves the claimed optimum
    s = set(side)
    assert sum(w for u, v, w in g.edges if (u in s) != (v in s)) == optimum
    return g, side, optimum


def planted_wishart_pm1(n: int, m: int, rng: random.Random):
    """Integer Wishart planted ensemble (after Hamze et al., PRE 101, 052102, 2020).

    Draw m random +-1 columns w_k, each with exactly n/2 entries equal to the planted spins t
    (so w_k . t = 0), and set J = W W^T. For every spin vector s, s^T J s = |W^T s|^2 >= 0, and
    W^T t = 0, so t minimises H(s) = sum_{i<j} J_ij s_i s_j with H(t) = -trace(J)/2 = -n*m/2.
    Max-Cut with weights w_ij = J_ij on the complete graph then has optimum (W_sum + n*m/2) / 2.
    The ratio alpha = m/n tunes hardness. n must be even.

    Returns (graph, planted_side_0based, optimum_cut).
    """
    if n % 2:
        raise ValueError("n must be even")
    t = [rng.choice((-1, 1)) for _ in range(n)]
    J = [[0] * n for _ in range(n)]
    for _ in range(m):
        agree = set(rng.sample(range(n), n // 2))
        w = [t[i] if i in agree else -t[i] for i in range(n)]
        for i in range(n):
            wi, Ji = w[i], J[i]
            for j in range(i + 1, n):
                Ji[j] += wi * w[j]
    g = make_graph(n, [(i, j, J[i][j]) for i in range(n) for j in range(i + 1, n)])
    W = g.total_weight
    assert (2 * W + n * m) % 4 == 0
    optimum = (2 * W + n * m) // 4
    side = [i for i in range(n) if t[i] == 1]
    s = set(side)
    assert sum(w for u, v, w in g.edges if (u in s) != (v in s)) == optimum
    return g, side, optimum
