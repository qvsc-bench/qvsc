# QvsC track: Max-Cut

The second problem of [QvsC](../../README.md). Given a graph with integer edge weights, split the
vertices into two sides so that the total weight of the edges between the sides is as large as possible.

Why Max-Cut? It is the standard benchmark of quantum optimisation. It is the textbook QAOA problem,
and it is equivalent to finding the ground state of a zero-field Ising spin glass, which is what
quantum annealers sample natively on their own hardware graph (other graphs need minor embedding).
Many quantum-optimisation demonstrations use it. It also has some of the strongest classical
heuristics and exact solvers, so it is where a fair comparison matters most.

Equivalence used throughout: with spins s_i = ±1 and weights w_ij, the cut value is
(W − Σ w_ij s_i s_j) / 2, where W is the sum of all weights. Maximising the cut is minimising the
Ising energy H(s) = Σ w_ij s_i s_j.

## Instances

401 instances in four groups. Sources, licences and how optima are known: [`instances/SOURCES.md`](instances/SOURCES.md).

| Group | Families | # | n (vertices) | What they are |
|:--|:--|--:|--:|:--|
| Literature | `gset`, `biqmac`, `mqlib` | 283 | 60 – 20,000 | the classical Max-Cut benchmarks: G-set, the Biq Mac library (optimal values published), DIMACS tori and 3D spin glasses from MQLib. Each comes with the best value reported in the literature |
| Hardware-native | `pegasus`, `zephyr`, `heavyhex` | 40 | 19 – 5,640 | the qubit connectivity graphs of D-Wave (Pegasus, Zephyr) and IBM (Eagle, Heron and generic heavy-hex), with random ±1 weights. On the ideal device graph they run with no embedding (annealers) and no SWAP gates (QAOA); real devices miss a few qubits and couplers |
| QAOA | `reg3`, `sk` | 50 | 20 – 10,000 | random 3-regular graphs and Sherrington–Kirkpatrick ±1 instances, the families used in many QAOA papers |
| Planted | `planted` | 28 | 32 – 5,640 | new to QvsC: instances built so that the optimum is known by construction (frustrated loops on hardware graphs, integer Wishart ensemble on complete graphs). Several are not solved by any baseline |

### Tracks

The leaderboard is computed separately on six subsets of instances, so a method can be compared on the
instances it was designed for:

| Track | Instances | Who it is for |
|:--|:--|:--|
| `all` | all 401 | general comparison |
| `literature` | G-set, Biq Mac, MQLib | comparison with decades of classical results |
| `hardware-native` | Pegasus, Zephyr, heavy-hex, and the planted instances on those graphs | quantum annealers and QAOA on the native qubit graph |
| `qaoa` | 3-regular and SK, all sizes | QAOA and its classical competitors |
| `planted` | the 28 planted instances | anyone who wants a certified answer: here the optimum is known |
| `gate-scale` | every instance with n ≤ 156 | gate-based devices with one qubit per vertex (156 = IBM Heron r2). Dense graphs of this size still need SWAP routing |

## How the leaderboard works

### The target of an instance

Every instance has a **target**, the value a method is measured against:

* for planted instances, the optimum, known by construction;
* otherwise, the larger of two numbers: the best cut **verified in this repository** (a solution file
  that CI has checked) and the best value **reported in the literature**.

Literature values are used as targets but never treated as verified: if nobody here can reproduce
one, the instance is marked `below-reference`. The `best_known` column changes only when a
solution file reaches a higher value.

### The columns

For each submission and track:

| Column | Meaning |
|:--|:--|
| **Hits** | number of instances where the submitted cut is at least the target |
| **Attempted** | instances with a solution file in the submission / instances in the track |
| **Mean ratio** | average of cut / target over the attempted instances (see below) |
| **Time to target** | median *time-to-target* over the hits: the wall-clock time at which the run first reached the target |
| **Time limit** | the budget per instance declared by the submitter |

Rows are sorted by hits, then mean ratio, then number of attempted instances.

### How to read the mean ratio

For each attempted instance we divide the verified cut by the instance's target, then average.
Example: the target of G39 is 2,407. A run that finds a cut of 2,390 scores 2390 / 2407 = 99.29% on
G39. A mean ratio of 99.78% means that the method's cuts are, on average, 0.22% below the best
values known.

Three caveats:

1. **It is relative to the target, not to the true optimum.** Where the optimum is not known,
   100% means "as good as the best value known", not "optimal". The target is certainly the optimum
   only for planted instances, for instances with status `optimal`, and (on the authors' word) for
   the Biq Mac optimal values.
2. **It compresses differences.** On Max-Cut even trivial methods cut most of the weight (the
   greedy baseline averages about 89%), so the gap between 99.2% and 99.8% is large in practice.
   Read the mean ratio together with hits.
3. **It moves with the target.** When a submission raises a best-known value, the target goes up
   and every other submission's ratio on that instance goes down. This is intended: the leaderboard
   always measures the distance from the best value known.

This is not the approximation ratio of approximation-algorithm theory (cut / optimum, guaranteed in
the worst case, e.g. 0.878 for Goemans–Williamson): it is an empirical average over a fixed set of
instances.

### How to read the time to target

Time-to-target (also called time-to-solution) is the usual way to compare a fast method with a slow
one: not "how good is the final answer" but "how long until the answer reaches the target". It is
computed only on the instances the method hits; on the others it never reached the target.

Why not a looser threshold such as 99% of the target? On Max-Cut it does not discriminate: the
reference simulated annealing reaches 99% of the target on 372 of 401 instances, with a median time
of about 0.01 s. Only reaching the target itself separates good methods from very good ones.

* It is computed from the submission's trajectory files (`trajectories/<instance>.traj`, one line
  `time_s cut` per improvement), so it is recomputed against the current target whenever the target
  moves. Without trajectories, the `time_to_best_s` column of `results.csv` is used.
* It is a median over the instances the method hits, which are not the same instances for every
  method: compare times between two methods only together with their hits.
* Times are **reported by the submitter**, not measured by QvsC. Budgets and hardware are in each
  `submission.toml`; the reference baselines are documented in [REPRODUCE.md](REPRODUCE.md).

### Status of an instance

In `instances/index.csv` and in the per-instance table of `LEADERBOARD.md`:

| Status | Meaning |
|:--|:--|
| `optimal` | a verified solution reaches a proven upper bound (exhaustive search, CP-SAT, or the planted optimum) |
| `best-known` | the verified best is at least the literature value, but optimality is not proven here |
| `below-reference` | no solution in this repository reaches the literature value (or the planted optimum) yet |
| `open` | no solution yet |

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
| `sa` | simulated annealing, Metropolis 1-flip moves, restarts with doubled length (C++) | the classical analogue of quantum annealing |
| `tabu` | 1-flip tabu search with incremental gains and perturbation restarts (C++) | tabu search is the core of the best Max-Cut heuristics (e.g. breakout local search) |
| `bm` | Burer–Monteiro low-rank SDP (mixing method) + Goemans–Williamson rounding + local search (C++) | Goemans–Williamson is the classical algorithm QAOA is most often compared with |
| `cpsat` | Google OR-Tools CP-SAT on the XOR formulation | a free exact solver: finds solutions and proves upper bounds on small instances |
| `exact` | Gray-code enumeration of all cuts, n ≤ 32 (C++) | certifies the optimum of the smallest instances, the size of many QAOA experiments |

These are deliberately simple, readable reference implementations (a few hundred lines in total),
not the state of the art: a quantum method that beats them has cleared the first bar, not the last.
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
