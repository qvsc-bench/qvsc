"""The K-SAT instance registry: problems/ksat/instances/index.csv.gz.

QvsC does not copy the K-SAT instances. Each row points to a file published by the original
authors (RandCSPBench's kSAT.zip on Hugging Face, the Zenodo dataset of Pelofske et al. 2023,
SATLIB) and stores a hash of the formula, so anyone can check that they are solving the same
instance. `python -m qvsc.ksat.fetch` downloads everything and checks the hashes.

Columns
    name          QvsC instance name, e.g. 3SAT_test_N256_M1075_id3 (= <k>SAT_<split>_<file name>)
    source        key of SOURCES below
    path          path of the CNF file inside the source archive
    k, n, m       clause length, variables, clauses
    alpha         clause density of the generation grid (m = round(alpha * n))
    split         split of the source (test = in-distribution N <= 256, test_ood = out-of-distribution)
    tracks        ';'-separated leaderboard tracks
    cnf_sha256    first 16 hex digits of qvsc.ksat.cnf.cnf_hash (canonical text of the formula)
    paper_solved  1 if at least one algorithm of the source paper found a satisfying assignment
                  (RandCSPBench: results_evaluation/analysis-results/<k>SAT-best_per_sample.csv)
    optimum_unsat minimum number of unsatisfied clauses, when it is proven (exhaustive search over all
                  2^n assignments, problems/ksat/baselines/exhaustive.cpp); 0 = satisfiable.
                  Empty for the RandCSPBench instances, where satisfiability is not proven
    sat_source    first verified QvsC submission that satisfies the formula (empty if none)
    status        optimum-proven (optimum_unsat is known) | sat-verified (a QvsC submission satisfies
                  it) | sat-reported (only the paper reports a solution) | open (nobody reports a
                  solution: unsatisfiable or very hard)
"""

from __future__ import annotations

import csv
import gzip
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repository root
PROBLEM_DIR = ROOT / "problems" / "ksat"
INDEX = PROBLEM_DIR / "instances" / "index.csv.gz"
REFERENCE_DIR = PROBLEM_DIR / "reference"
FIELDS = ["name", "source", "path", "k", "n", "m", "alpha", "split", "tracks", "cnf_sha256",
          "paper_solved", "optimum_unsat", "sat_source", "status"]

SOURCES = {
    "randcspbench": {
        "title": "RandCSPBench (Skenderi et al. 2026)",
        "url": "https://huggingface.co/datasets/CarloLucibello/CSPBenchmarks/resolve/main/kSAT.zip",
        "archive": "kSAT.zip",
        "homepage": "https://github.com/ArtLabBocconi/RandCSPBench",
        "paper": "https://arxiv.org/abs/2602.18419",
        "license": "MIT",
    },
    "pelofske2023": {
        "title": "Pelofske, Bärtschi, Golden & Eidenbenz (2023), QAOA for MAX 3-SAT on trapped-ion hardware",
        "zenodo_record": "8201693",
        "url": "https://zenodo.org/records/8201693",
        "paper": "https://arxiv.org/abs/2306.03238",
        "license": "see the Zenodo record",
    },
    "satlib": {
        "title": "SATLIB, uniform random 3-SAT uf20-91 (Hoos & Stützle 2000)",
        "url": "https://www.cs.ubc.ca/~hoos/SATLIB/Benchmarks/SAT/RND3SAT/uf20-91.tar.gz",
        "archive": "uf20-91.tar.gz",
        "homepage": "https://www.cs.ubc.ca/~hoos/SATLIB/benchm.html",
        "license": "see SATLIB",
    },
}

TRACKS = [
    ("3sat", "3-SAT, N = 16–256 (paper Table 1)"),
    ("3sat-ood", "3-SAT, N = 512–1024 (paper SI Table 1)"),
    ("4sat", "4-SAT, N = 16–256 (paper Table 1)"),
    ("4sat-ood", "4-SAT, N = 512–1024 (paper SI Table 1)"),
    ("qaoa-hardware", "QAOA on hardware, MAX 3-SAT n = 6–22 (Pelofske et al. 2023)"),
    ("satlib-uf20", "SATLIB uf20-91 (n = 20, satisfiable)"),
]


def tracks_for(k: int, n: int, source: str = "randcspbench") -> list[str]:
    if source == "pelofske2023":
        t = ["qaoa-hardware"]
    elif source == "satlib":
        t = ["satlib-uf20"]
    else:
        t = [f"{k}sat" if n <= 256 else f"{k}sat-ood"]
    return t


def load_index(path: Path = INDEX) -> dict[str, dict]:
    with gzip.open(path, "rt", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for r in rows:
        for f in ("k", "n", "m", "paper_solved"):
            r[f] = int(r[f])
        r["alpha"] = float(r["alpha"])
        r["optimum_unsat"] = int(r["optimum_unsat"]) if r.get("optimum_unsat") not in (None, "") else None
        r["tracks"] = r["tracks"].split(";") if r["tracks"] else []
        out[r["name"]] = r
    return out


def save_index(rows: dict[str, dict], path: Path = INDEX) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    for name in sorted(rows, key=lambda s: (rows[s]["k"], rows[s]["n"], rows[s]["m"], s)):
        r = dict(rows[name])
        r["tracks"] = ";".join(r["tracks"])
        if r.get("optimum_unsat") is None:
            r["optimum_unsat"] = ""
        w.writerow({f: r.get(f, "") for f in FIELDS})
    # mtime=0: the same index gives the same bytes, so git sees no change when nothing changed
    with open(path, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(buf.getvalue().encode("utf-8"))


def target_unsat(r: dict) -> int:
    """Unsatisfied clauses an assignment may leave and still count as solved (the proven optimum, else 0)."""
    return r["optimum_unsat"] if r.get("optimum_unsat") is not None else 0


def target_known(r: dict) -> bool:
    """True if some assignment is known to reach the target (the denominator of the score)."""
    return r.get("optimum_unsat") is not None or bool(r["paper_solved"]) or bool(r.get("sat_source"))


def refresh_status(r: dict) -> None:
    if r.get("optimum_unsat") is not None:
        r["status"] = "optimum-proven"
    elif r.get("sat_source"):
        r["status"] = "sat-verified"
    elif r["paper_solved"]:
        r["status"] = "sat-reported"
    else:
        r["status"] = "open"


def instance_file(instances_dir: Path, row: dict) -> Path:
    """Where the CNF file of a row is, below the folder where the source archive was unzipped.

    Accepts the archive's own layout (e.g. 4SAT/test-ood/...) and the generator's (4SAT/test_ood/...)."""
    base = Path(instances_dir)
    p = base / row["path"]
    if p.exists():
        return p
    for alt in (row["path"].replace("test-ood", "test_ood"), row["path"].replace("test_ood", "test-ood")):
        q = base / alt
        if q.exists():
            return q
    for q in (p.with_suffix(p.suffix + ".gz"),):
        if q.exists():
            return q
    raise FileNotFoundError(f"{row['name']}: {row['path']} not found under {base} "
                            f"(download it with: python -m qvsc.ksat.fetch --out {base})")
