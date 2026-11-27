"""Cut checker: is a vertex list a valid side of a cut, and what is the cut value?

Usage:
    python -m qvsc.maxcut.verify INSTANCE.mc.gz SOLUTION.sol
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

from .graph import WGraph, read_maxcut, read_solution


@dataclass
class Verdict:
    valid: bool
    cut: int
    side_size: int = 0
    errors: list[str] = field(default_factory=list)


def cut_value(g: WGraph, side0: set[int]) -> int:
    """Total weight of edges with exactly one endpoint in side0 (0-based ids)."""
    return sum(w for u, v, w in g.edges if (u in side0) != (v in side0))


def verify(g: WGraph, side_1based: list[int], max_errors: int = 10) -> Verdict:
    errors: list[str] = []
    side: set[int] = set()
    for v in side_1based:
        if not 1 <= v <= g.n:
            errors.append(f"vertex {v} out of range 1..{g.n}")
        elif v - 1 in side:
            errors.append(f"vertex {v} listed twice")
        else:
            side.add(v - 1)
        if len(errors) >= max_errors:
            break
    if errors:
        return Verdict(False, 0, 0, errors)
    return Verdict(True, cut_value(g, side), len(side))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance")
    ap.add_argument("solution")
    a = ap.parse_args(argv)
    v = verify(read_maxcut(a.instance), read_solution(a.solution))
    if v.valid:
        print(f"VALID cut of value {v.cut} ({v.side_size} vertices on the listed side)")
        return 0
    print("INVALID solution:")
    for e in v.errors:
        print("  -", e)
    return 1


if __name__ == "__main__":
    sys.exit(main())
