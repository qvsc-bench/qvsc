"""Solution checker: is a vertex list an independent set of the given graph, and how big is it?

Usage:
    python -m qvsc.mis.verify INSTANCE.gph[.gz] SOLUTION.sol
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

from .graph import Graph, read_dimacs, read_solution


@dataclass
class Verdict:
    valid: bool
    size: int
    errors: list[str] = field(default_factory=list)


def verify(g: Graph, solution_1based: list[int], max_errors: int = 10) -> Verdict:
    errors: list[str] = []
    seen: set[int] = set()
    for v in solution_1based:
        if not 1 <= v <= g.n:
            errors.append(f"vertex {v} out of range 1..{g.n}")
        elif v - 1 in seen:
            errors.append(f"vertex {v} listed twice")
        else:
            seen.add(v - 1)
    if not errors:
        for u, v in g.edges:
            if u in seen and v in seen:
                errors.append(f"edge ({u + 1},{v + 1}) has both endpoints in the set")
                if len(errors) >= max_errors:
                    break
    return Verdict(valid=not errors, size=len(seen) if not errors else 0, errors=errors)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance")
    ap.add_argument("solution")
    args = ap.parse_args(argv)
    v = verify(read_dimacs(args.instance), read_solution(args.solution))
    if v.valid:
        print(f"VALID independent set of size {v.size}")
        return 0
    print("INVALID solution:")
    for e in v.errors:
        print("  -", e)
    return 1


if __name__ == "__main__":
    sys.exit(main())
