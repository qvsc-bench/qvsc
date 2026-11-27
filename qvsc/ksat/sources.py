"""Readers for the original formats of the K-SAT instance sources.

* RandCSPBench (kSAT.zip): DIMACS CNF files, used as they are.
* SATLIB uf20-91 (uf20-91.tar.gz): DIMACS CNF files ending with "%" and "0" (handled by parse_cnf).
* Pelofske et al. (2023), Zenodo 10.5281/zenodo.8201693: the instances are Python literals in
  dataset/problems.md, one block per (k, n):

      variables = [[0, 1, 2], ...]     # 0-based variables of each clause
      signs = [[0, 0, 1], ...]         # 1 = positive literal, 0 = negated
      max_obj = 23                     # maximum number of satisfiable clauses
      ...
      probs[(3,6)] = {...}

  Measurements (dataset/<device>_samples/k3_p<p>_n<n>[_<shots>_shots].json) map raw readout
  bit strings to counts; "the bitstring order is reversed from the variable indices" (dataset README),
  so character j of the readout is variable n-1-j.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from .cnf import CNF

DEVICES = {"IonQ_Forte_samples": "IonQ Forte", "Quantinuum_H1_1_samples": "Quantinuum H1-1",
           "IonQ_Aria_samples": "IonQ Aria 1", "IonQ_Harmony_samples": "IonQ Harmony"}


def parse_pelofske_problems(text: str) -> dict[int, dict]:
    """{n: {"cnf": CNF, "max_obj": int}} from problems.md."""
    out = {}
    cur: dict = {}
    for line in text.splitlines():
        m = re.match(r"^(variables|signs|max_obj)\s*=\s*(.+)$", line.strip())
        if m:
            cur[m.group(1)] = ast.literal_eval(m.group(2))
            continue
        m = re.match(r"^probs\[\((\d+),\s*(\d+)\)\]", line.strip())
        if m:
            k, n = int(m.group(1)), int(m.group(2))
            clauses = []
            for vs, ss in zip(cur["variables"], cur["signs"], strict=True):
                if len(vs) != k:
                    raise ValueError(f"(k={k}, n={n}): clause {vs} has {len(vs)} literals")
                clauses.append(tuple((v + 1) if s else -(v + 1) for v, s in zip(vs, ss, strict=True)))
            out[n] = {"k": k, "cnf": CNF(n, clauses), "max_obj": int(cur["max_obj"])}
            cur = {}
    return out


def write_dimacs(f: CNF, path: Path, comment: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"c {c}" for c in comment.splitlines() if c] + [f"p cnf {f.n} {f.m}"]
    lines += [" ".join(map(str, c)) + " 0" for c in f.clauses]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def pelofske_samples(dataset: Path):
    """Yield (device, p, n, shots_label, {assignment bit string in variable order: count})."""
    for sub, device in DEVICES.items():
        for p in sorted((dataset / sub).glob("k3_p*_n*.json")):
            m = re.match(r"k3_p(\d+)_n(\d+)(?:_(\d+)_shots)?\.json$", p.name)
            if not m:
                continue
            raw = json.loads(p.read_text(encoding="utf-8"))
            yield device, int(m.group(1)), int(m.group(2)), m.group(3), {b[::-1]: c for b, c in raw.items()}
