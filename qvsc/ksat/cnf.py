"""CNF formulas (DIMACS) and assignments.

Instance format: DIMACS CNF, as in RandCSPBench (`p cnf N M`, then one clause per line, literals
+v / -v with 1-based variables, each clause terminated by 0; lines starting with 'c' are comments).

Assignment (solution) format, one of:

* a bit string of length N, '0'/'1' per variable in order (character i is variable i+1); this is
  what a quantum sampler usually returns. Whitespace inside the string is ignored.
* signed literals as in the SAT Competition output format: `v 1 -2 3 ... 0`. Every variable must
  appear exactly once. Lines starting with 'c' or 's' are ignored, and so is the 'v' prefix.
"""

from __future__ import annotations

import gzip
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CNF:
    n: int
    clauses: list[tuple[int, ...]]

    @property
    def m(self) -> int:
        return len(self.clauses)


def parse_cnf(text: str) -> CNF:
    n = None
    declared_m = None
    clauses: list[tuple[int, ...]] = []
    cur: list[int] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s[0] == "c":
            continue
        if s[0] == "%":          # SATLIB files end with "%" and a stray "0"
            break
        if s[0] == "p":
            parts = s.split()
            if len(parts) < 4 or parts[1] != "cnf":
                raise ValueError(f"bad header: {s!r}")
            n, declared_m = int(parts[2]), int(parts[3])
            continue
        for tok in s.split():
            x = int(tok)
            if x == 0:
                clauses.append(tuple(cur))
                cur = []
            else:
                cur.append(x)
    if cur:
        clauses.append(tuple(cur))
    if n is None:
        raise ValueError("missing 'p cnf' header")
    for c in clauses:
        for lit in c:
            if not 1 <= abs(lit) <= n:
                raise ValueError(f"literal {lit} out of range 1..{n}")
    if declared_m is not None and declared_m != len(clauses):
        raise ValueError(f"header declares {declared_m} clauses, file has {len(clauses)}")
    return CNF(n, clauses)


def read_cnf(path: str | Path) -> CNF:
    p = Path(path)
    raw = p.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return parse_cnf(raw.decode("ascii"))


def cnf_hash(f: CNF) -> str:
    """SHA-256 of a canonical text form (header + clauses in file order, single spaces).

    Independent of whitespace, comments and compression, so the same formula has the same hash
    whether it comes from kSAT.zip or from the RandCSPBench generator. The index stores the first
    16 hex digits."""
    h = hashlib.sha256()
    h.update(f"p cnf {f.n} {f.m}\n".encode())
    for c in f.clauses:
        h.update((" ".join(map(str, c)) + " 0\n").encode())
    return h.hexdigest()


def parse_assignment(text: str, n: int) -> list[bool]:
    """Return x[0..n-1] (x[i] = value of variable i+1). Raises ValueError on a malformed assignment."""
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln and ln[0] not in "cs#"]
    body = " ".join(ln[1:] if ln.startswith("v") else ln for ln in lines).split()
    if not body:
        raise ValueError("empty assignment")
    joined = "".join(body)
    # a bit string, possibly wrapped over several lines (every piece longer than one character,
    # so that it cannot be confused with literals such as "1 0")
    if set(joined) <= {"0", "1"} and len(joined) == n and (len(body) == 1 or all(len(t) > 1 for t in body)):
        return [ch == "1" for ch in joined]
    x: list[bool | None] = [None] * n
    for tok in body:
        try:
            lit = int(tok)
        except ValueError:
            raise ValueError(f"not a literal: {tok!r}") from None
        if lit == 0:
            continue
        v = abs(lit)
        if v > n:
            raise ValueError(f"variable {v} out of range 1..{n}")
        if x[v - 1] is not None:
            raise ValueError(f"variable {v} assigned twice")
        x[v - 1] = lit > 0
    missing = [i + 1 for i, b in enumerate(x) if b is None]
    if missing:
        raise ValueError(f"{len(missing)} variables not assigned (first: {missing[:5]})")
    return [bool(b) for b in x]


def read_assignment(path: str | Path, n: int) -> list[bool]:
    raw = Path(path).read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return parse_assignment(raw.decode("ascii"), n)


def to_bitstring(x: list[bool]) -> str:
    return "".join("1" if b else "0" for b in x)
