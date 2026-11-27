"""Build the K-SAT index and the reference results from RandCSPBench.

    git clone https://github.com/ArtLabBocconi/RandCSPBench
    python -m qvsc.ksat.fetch --out data/ksat          # or unzip kSAT.zip into data/ksat
    python problems/ksat/scripts/import_randcspbench.py --randcspbench RandCSPBench --instances data/ksat

Writes
    problems/ksat/instances/index.csv.gz              one row per instance in scope (hash, paper_solved)
    problems/ksat/reference/randcspbench/<algo>.csv.gz   per-instance results reported in the paper

Scope: the paper's test split (N = 16 ... 256) and the out-of-distribution sizes N = 512 and 1024,
for K = 3 and 4: exactly the instances behind Table 1 and Supplementary Table 1 of the paper.
Existing sat_source values in the index are kept.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from qvsc.ksat.cnf import cnf_hash, read_cnf  # noqa: E402
from qvsc.ksat.registry import INDEX, REFERENCE_DIR, load_index, refresh_status, save_index, tracks_for  # noqa: E402

NS = {"test": [16, 32, 64, 128, 256], "test_ood": [512, 1024]}
ALPHAS = {3: [round(3.0 + 0.1 * i, 1) for i in range(21)],       # gen_graphs_sat.jl: 3:0.1:5
          4: [round(8.0 + 0.1 * i, 1) for i in range(21)]}       # 4-SAT test: 8:0.1:10
SAMPLES = {3: 400, 4: 200}                                       # per (N, alpha), test and OOD
# the algorithms of Table 1 / Supplementary Table 1 (results_evaluation/<k>SAT/<k>SAT_<algo>.csv)
ALGOS = ["FMS_nsteps=100N^2", "FMS_nsteps=1000N^2", "SimulatedAnnealing_nsteps=1000N^2",
         "SurveyPropagation_frac-decimated=0.00125", "NeuroSAT_unsupervised_niters=2N_Ntrain=256",
         "QuerySAT_niters=2N_Ntrain=256"]


def name_of(k: int, split: str, N: int, M: int, i: int) -> str:
    return f"{k}SAT_{split}_N{N}_M{M}_id{i}"


def scope():
    for k in (3, 4):
        for split, Ns in NS.items():
            for N in Ns:
                for a in ALPHAS[k]:
                    M = round(N * a)
                    for i in range(1, SAMPLES[k] + 1):
                        yield k, split, N, M, a, i


def read_results(path: Path):
    """Rows of a RandCSPBench result file: N, M, id, E (unsatisfied clauses), and a time column if any."""
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    tcol = next((c for c in rows[0] if c.lower().startswith("time")), None) if rows else None
    for r in rows:
        yield int(r["N"]), int(r["M"]), int(r["id"]), int(float(r["E"])), (float(r[tcol]) if tcol and r[tcol] else None)


def write_gz_csv(path: Path, header: list[str], rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    with open(path, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(buf.getvalue().encode())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--randcspbench", required=True, type=Path, help="clone of ArtLabBocconi/RandCSPBench")
    ap.add_argument("--instances", required=True, type=Path, help="folder with 3SAT/, 4SAT/ (unzipped kSAT.zip)")
    a = ap.parse_args(argv)
    res = a.randcspbench / "results_evaluation"
    old = load_index() if INDEX.exists() else {}

    best = {}
    for k in (3, 4):
        for r in csv.DictReader(open(res / "analysis-results" / f"{k}SAT-best_per_sample.csv", encoding="utf-8")):
            best[(k, int(r["N"]), int(r["M"]), int(r["id"]))] = int(r["solved"])

    idx = {n: r for n, r in old.items() if r["source"] != "randcspbench"}   # keep the other sources
    for n_done, (k, split, N, M, alpha, i) in enumerate(scope(), 1):
        name = name_of(k, split, N, M, i)
        sub = "test-ood" if (k == 4 and split == "test_ood") else split   # kSAT.zip layout
        path = f"{k}SAT/{sub}/N{N}_M{M}_id{i}.cnf"
        p = a.instances / path
        if not p.exists():
            p = a.instances / f"{k}SAT/{split}/N{N}_M{M}_id{i}.cnf"
        f = read_cnf(p)
        if (f.n, f.m) != (N, M) or any(len(c) != k for c in f.clauses):
            raise SystemExit(f"{p}: unexpected formula (n={f.n}, m={f.m})")
        r = {"name": name, "source": "randcspbench", "path": path, "k": k, "n": N, "m": M, "alpha": alpha,
             "split": split, "tracks": tracks_for(k, N), "cnf_sha256": cnf_hash(f)[:16],
             "paper_solved": best.get((k, N, M, i), 0), "optimum_unsat": None,
             "sat_source": (old.get(name) or {}).get("sat_source", "")}
        refresh_status(r)
        idx[name] = r
        if n_done % 10000 == 0:
            print(f"  {n_done} instances", flush=True)
    save_index(idx)
    print(f"wrote {INDEX.relative_to(ROOT)}: {len(idx)} instances")

    for algo in ALGOS:
        for k in (3, 4):
            src = res / f"{k}SAT" / f"{k}SAT_{algo}.csv"
            if not src.exists():
                print("missing", src)
                continue
            rows = {}
            for N, M, i, E, t in read_results(src):
                split = "test" if N <= 256 else "test_ood"
                name = name_of(k, split, N, M, i)
                if name in idx:
                    if name in rows and rows[name][0] != E:
                        raise SystemExit(f"{src}: two different results for {name}")
                    rows[name] = (E, t)
            out = REFERENCE_DIR / "randcspbench" / f"{k}SAT_{algo}.csv.gz"
            write_gz_csv(out, ["name", "unsat", "time_s"],
                         ([n, E, "" if t is None else f"{t:.6g}"] for n, (E, t) in sorted(rows.items())))
            print(f"wrote {out.relative_to(ROOT)}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
