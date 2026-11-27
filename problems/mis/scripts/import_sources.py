"""Build instances/ and instances/index.csv from the upstream sources.

Sources (clone them first, at the pinned commits, see instances/SOURCES.md):
  --qoblib DIR      QOBLIB problem 07 (MIS) folder: instances/*.gph, record-mis.csv
  --qbench DIR      github.com/zbogdan/qbenchmarks (max-clique, n <= 128)
  --evil DIR        github.com/zbogdan/evil2 (max-clique EVIL set)

Max-clique instances are complemented (MIS(complement(G)) = omega(G)). Graphs whose
content hash equals one already imported are skipped, so each graph appears once.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from qvsc.mis.graph import graph_hash, read_dimacs, write_dimacs  # noqa: E402
from qvsc.mis.registry import PROBLEM_DIR, save_index  # noqa: E402

QOBLIB_URL = "https://git.zib.de/qopt/qoblib-quantum-optimization-benchmarking-library"
QBENCH_URL = "https://github.com/zbogdan/qbenchmarks"
EVIL_URL = "https://github.com/zbogdan/evil2"
QUANTUM_N = 128  # "quantum-scale" track: graphs small enough for today's hardware


def omega_from_header(path: Path):
    m = re.search(r"omega\(E\)\s*=\s*(\d+)", path.read_text(errors="ignore")[:4000])
    return int(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--qoblib", type=Path, required=True)
    ap.add_argument("--qbench", type=Path, required=True)
    ap.add_argument("--evil", type=Path, required=True)
    a = ap.parse_args()

    rows: dict[str, dict] = {}
    by_hash: dict[str, str] = {}

    def add(name, family, g, best, status, src, origin, lic, comments, tracks=()):
        h = graph_hash(g)
        if h in by_hash:
            print(f"skip {family}/{name}: same graph as {by_hash[h]}")
            rows[by_hash[h]]["tracks"] = sorted(set(rows[by_hash[h]]["tracks"]) | set(tracks))
            return
        tr = set(tracks) | {"all"}
        if g.n <= QUANTUM_N:
            tr.add("quantum-scale")
        out = PROBLEM_DIR / "instances" / family / f"{name}.gph.gz"
        out.parent.mkdir(parents=True, exist_ok=True)
        write_dimacs(g, out, comments)
        by_hash[h] = name
        rows[name] = dict(name=name, family=family, tracks=sorted(tr), n=g.n, m=g.m, best_known=best,
                          status=status, upper_bound=best if status == "optimal" else None,
                          record_source=src, sha256=h, origin=origin, license=lic)
        print(f"add  {family}/{name}: n={g.n} m={g.m} best={best} ({status})")

    # 1) QOBLIB MIS (already MIS instances)
    rec = {r["istanza"]: r for r in csv.DictReader(open(a.qoblib / "record-mis.csv", encoding="utf-8"))}
    for p in sorted((a.qoblib / "instances").glob("*.gph")):
        r = rec[p.stem]
        status = "optimal" if r["stato"] == "optimal" else "best-known"
        add(p.stem, "qoblib", read_dimacs(p), int(r["migliore_noto"]), status,
            "qoblib:" + r["fonte"], QOBLIB_URL, "see QOBLIB",
            [f"QvsC instance {p.stem}", f"source: QOBLIB problem 07 ({QOBLIB_URL})"])

    # 2) EVIL max-clique graphs (qbenchmarks small ones + evil2 test set), complemented
    evil_files = {}
    for p in sorted((a.evil / "evil-tests").glob("evil-*.clq")):
        evil_files[p.stem] = (p, ["review-evil"])
    for p in sorted(a.qbench.glob("evil-*.clq")):
        prev = evil_files.get(p.stem)
        evil_files[p.stem] = (p, sorted(set((prev[1] if prev else [])) | {"review-qbench"}))
    for name, (p, tracks) in sorted(evil_files.items(), key=lambda kv: int(re.search(r"N(\d+)", kv[0]).group(1))):
        om = omega_from_header(p)
        url = QBENCH_URL if "review-qbench" in tracks else EVIL_URL
        add(name, "evil", read_dimacs(p).complement(), om, "optimal" if om else "unknown",
            "construction (omega in generator header)", url, "AFL-3.0",
            [f"QvsC instance {name}", f"complement of the max-clique graph {p.name} ({url})",
             "EVIL generator by S. Szabo and B. Zavalnij, Academic Free License 3.0",
             f"alpha = omega(original) = {om}"], tracks)

    # 3) other qbenchmarks graphs (coding theory + DIMACS), complemented
    for p in sorted(a.qbench.glob("*.clq")):
        if p.stem.startswith("evil-"):
            continue
        if p.stem.startswith("a265032"):  # complement of a code graph -> back to the code graph
            fam, name = "codes", p.stem.replace(".", "-").removesuffix("-c")
        else:  # DIMACS clique graph -> its complement is a new MIS instance
            fam, name = "dimacs-comp", p.stem.replace(".", "-") + "-comp"
        add(name, fam, read_dimacs(p).complement(), 0, "unknown", "", QBENCH_URL, "see upstream",
            [f"QvsC instance {name}", f"complement of the max-clique graph {p.name} ({QBENCH_URL})"],
            ["review-qbench"])

    save_index(rows)
    print(f"{len(rows)} instances written to instances/index.csv")


if __name__ == "__main__":
    main()
