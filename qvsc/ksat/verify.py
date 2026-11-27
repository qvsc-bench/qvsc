"""Assignment checker: how many clauses of a CNF formula does an assignment leave unsatisfied?

Usage:
    python -m qvsc.ksat.verify INSTANCE.cnf SOLUTION.sol

The solution is a bit string ('0'/'1' per variable, in order) or signed literals (`v 1 -2 3 0`).
Exit code 0 if the assignment satisfies every clause, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys

from .cnf import CNF, parse_assignment, read_assignment, read_cnf


def unsat_clauses(f: CNF, x: list[bool]) -> int:
    """Number of clauses with no true literal (x[i] is the value of variable i+1)."""
    if len(x) != f.n:
        raise ValueError(f"assignment has {len(x)} values, formula has {f.n} variables")
    bad = 0
    for c in f.clauses:
        if not any((x[lit - 1] if lit > 0 else not x[-lit - 1]) for lit in c):
            bad += 1
    return bad


def check(f: CNF, text: str) -> int:
    return unsat_clauses(f, parse_assignment(text, f.n))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("instance")
    ap.add_argument("solution")
    a = ap.parse_args(argv)
    f = read_cnf(a.instance)
    try:
        u = unsat_clauses(f, read_assignment(a.solution, f.n))
    except ValueError as e:
        print("INVALID assignment:", e)
        return 1
    if u == 0:
        print(f"SATISFIED: all {f.m} clauses satisfied (n = {f.n})")
        return 0
    print(f"NOT SATISFIED: {u} of {f.m} clauses unsatisfied (residual energy {u / f.m:.6f})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
