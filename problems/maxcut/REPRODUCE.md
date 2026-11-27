# Reproducing the Max-Cut baselines

Every number on the Max-Cut leaderboard comes from code in this repository. This page lists how
the reference baselines of 2026-11-27 were run, so anyone can rerun them and compare.

## Machine and software

| | |
|:--|:--|
| Machine | cloud Linux container (Linux 6.18), Intel Xeon Processor @ 2.10GHz, 4 cores (1 thread per core), 15 GB RAM |
| Compiler | g++ 13.3.0, flags `-O3 -std=c++17` |
| Python | CPython 3.13 (any ≥ 3.11 works; the checker and leaderboard have no dependencies) |
| CP-SAT | `ortools` 9.15.6755 |
| Topologies (instance generation only) | `dwave-networkx`, `rustworkx`, `qiskit-ibm-runtime` (fake backends FakeSherbrooke, FakeTorino, FakeFez) |

Heuristics run single-threaded, four instances at a time (`--jobs 4`). CP-SAT runs one instance at a
time with 4 worker threads. Times are wall-clock, exclude reading the input file, and are measured
by the solver itself.

## Budgets and seeds

| Baseline | Command | Budget per instance | Seed | Instances |
|:--|:--|--:|--:|:--|
| `greedy_ls` | `run_baselines.py greedy_ls --jobs 4` | single pass | deterministic | all 401 |
| `exact` | `run_baselines.py exact --max-n 32 --jobs 4` | to completion | deterministic | the 16 with n ≤ 32 |
| `sa` | `run_baselines.py sa --time 10 --jobs 4` | 10 s | 1 | all 401 |
| `tabu` | `run_baselines.py tabu --time 10 --jobs 4` | 10 s | 1 | all 401 |
| `bm` | `run_baselines.py bm --time 10 --jobs 4` | 10 s | 1 | all 401 |
| `cpsat` | `run_baselines.py cpsat --time 10 --workers 4 --max-n 400 --max-edges 20000` | 10 s | 1 | the 250 with n ≤ 400 and m ≤ 20,000 |

Heuristics stop early only when they reach a value already *proven* optimal in `index.csv`.
On these first runs no value was proven yet, so every heuristic used its full budget.

## Steps

```bash
git clone https://github.com/qvsc-bench/qvsc && cd qvsc
g++ -O3 -std=c++17 -o problems/maxcut/baselines/maxcut_heur problems/maxcut/baselines/maxcut_heur.cpp
pip install ortools                      # only for cpsat

R=problems/maxcut/scripts/run_baselines.py
python $R greedy_ls --jobs 4            --name mine_greedy-ls
python $R exact --max-n 32 --jobs 4     --name mine_exact
python $R sa   --time 10 --jobs 4       --name mine_sa
python $R tabu --time 10 --jobs 4       --name mine_tabu
python $R bm   --time 10 --jobs 4       --name mine_bm
python $R cpsat --time 10 --workers 4 --max-n 400 --max-edges 20000 --name mine_cpsat

python -m qvsc.maxcut.leaderboard --check   # verifies every cut, including yours
```

Each run writes a submission folder under `problems/maxcut/submissions/` with one solution file per
instance, `results.csv` (cut, time to best, total time, seed, proven bound) and, for the anytime
heuristics, `trajectories/` (time and value of every improvement within 2% of the final cut).

What to expect: the heuristics depend on timing, so on a different machine the cuts can differ
slightly. The exhaustive search and the checker are deterministic and must give identical values.

## Single instance

```bash
zcat problems/maxcut/instances/gset/G22.mc.gz | problems/maxcut/baselines/maxcut_heur tabu - --time 10 --seed 1 --out G22.sol --trajectory G22.traj
python -m qvsc.maxcut.verify problems/maxcut/instances/gset/G22.mc.gz G22.sol
```

## Instances

`python problems/maxcut/scripts/import_sources.py --hardware` downloads the literature instances
from the public MQLib S3 bucket and regenerates every random family from its public seed. The
`sha256` column of `instances/index.csv` checks that you obtained the same graphs. Planted instances
use a secret seed (see `instances/SOURCES.md`).
