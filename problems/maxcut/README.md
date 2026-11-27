# QvsC track: Max-Cut

The second problem of [QvsC](../../README.md). Given a graph with integer edge weights, split the
vertices into two sides so that the total weight of the edges between the sides is as large as possible.

Why Max-Cut? It is the standard benchmark of quantum optimisation: the textbook QAOA problem, and
equivalent to finding the ground state of a zero-field Ising spin glass, which quantum annealers
sample natively on their own hardware graph (other graphs need minor embedding). Many
quantum-optimisation demonstrations use it. It also has some of the strongest classical
heuristics and exact solvers, so it is where a fair comparison matters most.

## Instances

401 instances in four groups. Sources, licences and how optima are known: [`instances/SOURCES.md`](instances/SOURCES.md).

| Group | Families | # | n | Notes |
|:--|:--|--:|--:|:--|
| Literature | `gset`, `biqmac`, `mqlib` | 283 | 60 – 20,000 | G-set, Biq Mac (optima known), DIMACS tori and 3D spin glasses from MQLib, with literature reference values |
| Hardware-native | `pegasus`, `zephyr`, `heavyhex` | 40 | 19 – 5,640 | D-Wave Pegasus and Zephyr, IBM Eagle / Heron coupling maps and heavy-hex lattices, ±1 weights: no embedding or SWAP overhead |
| QAOA | `reg3`, `sk` | 50 | 20 – 10,000 | random 3-regular graphs and Sherrington–Kirkpatrick ±1 instances, the families of most QAOA papers |
| Planted | `planted` | 28 | 32 – 5,640 | optimum known by construction: frustrated loops on hardware graphs, integer Wishart ensemble on complete graphs. New to QvsC |

Leaderboard tracks: **all**, **literature**, **hardware-native** (includes the planted instances on
hardware graphs), **qaoa**, **planted**, and **gate-scale** (n ≤ 156, what gate-based devices hold today).

## Metrics

Every instance has a **target**: the larger of the best cut verified in this repository and the best
value reported in the literature (for planted instances, the optimum). Per submission and track:

* **hits**: instances where the cut reaches the target;
* **mean ratio**: average of cut / target;
* **at 99%** and **TTT99**: how many instances the method brings within 1% of the target, and the
  median *time-to-target*, the wall-clock time at which the run first got there. TTT99 is computed
  from the trajectory file (`time_s cut` per improvement) if the submission provides one, so it stays
  correct when the target moves. Times are self-reported; budgets are in `submission.toml`.

## Quick start

From the repository root (Python ≥ 3.11, no dependencies):

```bash
# check a solution (the vertices of one side of the cut, one per line, 1-based)
python -m qvsc.maxcut.verify problems/maxcut/instances/gset/G1.mc.gz my_G1.sol

# run the baselines
g++ -O3 -std=c++17 -o problems/maxcut/baselines/maxcut_heur problems/maxcut/baselines/maxcut_heur.cpp
zcat problems/maxcut/instances/gset/G1.mc.gz | problems/maxcut/baselines/maxcut_heur sa - --time 10 --out G1.sol --trajectory G1.traj
python problems/maxcut/baselines/greedy_ls.py problems/maxcut/instances/reg3/reg3-n100-s1.mc.gz --out r.sol
pip install ortools && python problems/maxcut/baselines/cpsat.py problems/maxcut/instances/biqmac/g05_60.0.mc.gz --time 30

# run a baseline on every instance (writes a submission folder)
python problems/maxcut/scripts/run_baselines.py tabu --time 10 --jobs 4
```

A quantum sampler usually returns spins or bits. To write a solution file from a bit string `x`
(one character per vertex): `print("\n".join(str(i + 1) for i, b in enumerate(x) if b == "1"))`.

## Baselines

| Baseline | What it is | Why it is here |
|:--|:--|:--|
| `greedy_ls` | greedy placement + 1-flip local search, pure Python | the floor |
| `sa` | simulated annealing, Metropolis 1-flip moves, restarts with doubled length (C++) | the classical twin of quantum annealing |
| `tabu` | 1-flip tabu search with incremental gains and perturbation restarts (C++) | the workhorse of Max-Cut heuristics |
| `bm` | Burer–Monteiro low-rank SDP (mixing method) + Goemans–Williamson rounding + local search (C++) | the relaxation-and-rounding approach QAOA is usually compared with |
| `cpsat` | Google OR-Tools CP-SAT on the XOR formulation | the solver many quantum papers compare against; proves bounds |
| `exact` | Gray-code enumeration of all cuts, n ≤ 32 (C++) | certifies the optimum of the small QAOA-size instances |

These are deliberately simple, readable reference implementations, not the state of the art.
Stronger classical solvers (BLS, MQLib heuristics, Biq Mac/BiqBin, McSparse, Gurobi, simulated
bifurcation, parallel tempering) are welcome as ordinary submissions, and raise the bar for everyone.

## Layout

```
instances/      graphs (*.mc.gz) by family, index.csv, references.csv, planted.csv, topologies/, SOURCES.md
baselines/      maxcut_heur.cpp (sa, tabu, bm, exact), greedy_ls.py, cpsat.py
scripts/        import_sources.py (rebuild instances), run_baselines.py
submissions/    one folder per submitted method
LEADERBOARD.md  generated, do not edit
```

How the reference baselines were run (machine, versions, seeds, budgets): [REPRODUCE.md](REPRODUCE.md).

Submitting: see [CONTRIBUTING.md](../../CONTRIBUTING.md).
