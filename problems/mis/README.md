# QvsC track: Maximum Independent Set

The first problem of [QvsC](../../README.md). Given a graph, find the largest set of vertices with no edge between them.

Why MIS? Maximum independent set is the native problem of Rydberg-atom quantum processors on unit-disk graphs
(other graphs need embedding gadgets),
has a one-line QUBO for annealers and QAOA, and is equivalent to Maximum Clique and Minimum
Vertex Cover, so decades of classical benchmarks carry over directly.

## Instances

| Family | # | Notes |
|:--|--:|:--|
| `qoblib` | 50 | The MIS problem of [QOBLIB](https://git.zib.de/qopt/qoblib-quantum-optimization-benchmarking-library): DIMACS, BHOSLIB (`frb*`), social and biological networks, Steiner and coding-theory graphs. 10 are still open. |
| `evil` | 85 | EVIL graphs (Szabó & Zaválnij), built to be very hard for exact clique search, complemented into MIS instances. Optimum known by construction. |
| `codes` | 4 | Single-error-correcting code graphs (OEIS A265032). |
| `dimacs-comp` | 4 | Complements of DIMACS clique graphs. |

Tracks on the leaderboard:

* **all** — every instance;
* **quantum-scale** — graphs with at most 128 vertices, the size of the graphs used in current quantum-hardware experiments (larger graphs fit on annealers through embedding and on the largest Rydberg arrays);
* **review-qbench** — the quantum benchmark set proposed in Marino, Buffoni & Zavalnij,
  [*A short review on the maximum clique problem algorithms with classical, AI, and quantum methods*](https://doi.org/10.1038/s42005-026-02606-7),
  Communications Physics 9, 239 (2026), rewritten as MIS;
* **review-evil** — the full EVIL test set.

Graphs are in DIMACS format (`p edge n m`, then `e u v`, 1-based), gzip-compressed.
Sources, licences and column meanings: [`instances/SOURCES.md`](instances/SOURCES.md).

## How the leaderboard works

Each instance has a **best-known** value (`best_known` in `instances/index.csv`). It comes from one
of three places, recorded in the `record_source` column: the value reported by QOBLIB for its
instances (`qoblib:...`), the clique number known by construction for the EVIL graphs
(`construction ...`), or a submission to QvsC whose solution file CI has verified (the submission's
folder name). For each submission and track the leaderboard shows:

| Column | Meaning |
|:--|:--|
| **Hits** | instances where the submitted set is as large as the best-known value |
| **Attempted** | instances with a solution file in the submission / instances in the track |
| **Mean gap** | average of (best known − size) / best known over the attempted instances; 0% means best-known everywhere |
| **Time limit** | the budget per instance declared by the submitter |

Rows are sorted by hits, then mean gap. Example: if the best known on an instance is 50 and a
submission finds 49, its gap there is 2%.

The best-known value is not always the optimum. An instance is `optimal` when the best-known value
matches a proven upper bound (from an exact solver, or known by construction as for the EVIL graphs),
`best-known` otherwise. When a submission finds a larger set, the best-known value moves to it and
every other submission's gap on that instance grows. Running times are reported by the submitter.

The Max-Cut track goes one step further and keeps literature values in a separate column, so that
`best_known` there is always backed by a solution file in the repository.

## Quick start

Run from the repository root (Python ≥ 3.11, no dependencies):

```bash
# check a solution
python -m qvsc.mis.verify problems/mis/instances/qoblib/karate.gph.gz my_karate.sol

# run the baselines
python problems/mis/baselines/greedy.py problems/mis/instances/qoblib/karate.gph.gz --out karate.sol
g++ -O2 -std=c++17 -o problems/mis/baselines/arw_ils problems/mis/baselines/arw_ils.cpp
zcat problems/mis/instances/qoblib/frb45-21-3.gph.gz | problems/mis/baselines/arw_ils - --time 10 --out frb.sol
pip install ortools && python problems/mis/baselines/cpsat.py problems/mis/instances/evil/evil-N120-p98-myc5x24.gph.gz --time 30

# run a baseline on every instance (writes a submission folder)
python problems/mis/scripts/run_baselines.py arw_ils --time 10 --jobs 4
```

## Baselines

| Baseline | What it is | Why it is here |
|:--|:--|:--|
| `greedy` | minimum-degree greedy, one pass | the floor: any method should beat it |
| `arw_ils` | iterated local search with (1,2)-swaps (Andrade, Resende & Werneck 2012), ~250 lines of C++ | a strong, simple heuristic: the first bar a quantum claim should clear |
| `cpsat` | Google OR-Tools CP-SAT on the edge formulation | a widely used free exact solver; also certifies optima |

The baselines are deliberately simple. Stronger classical solvers (KaMIS, NuMVC, ReduMIS,
exact clique solvers) are welcome as ordinary submissions.

## Layout

```
instances/      graphs (*.gph.gz), index.csv (sizes, best known, hashes), SOURCES.md
baselines/      greedy.py, arw_ils.cpp, cpsat.py
scripts/        import_sources.py (rebuild instances), run_baselines.py
submissions/    one folder per submitted method
LEADERBOARD.md  generated, do not edit
```

Submitting: see [CONTRIBUTING.md](../../CONTRIBUTING.md).
