# QvsC: Quantum vs Classical Optimization Benchmark

**An open, verifiable benchmark where quantum, hybrid and classical solvers compete on the same instances.**

[Leaderboard](https://qvsc-bench.github.io/qvsc/) · [Submit results](CONTRIBUTING.md) · [MIS track](problems/mis/README.md) · [Max-Cut track](problems/maxcut/README.md)

Claims of quantum advantage in combinatorial optimisation are hard to check. Instances differ
between papers, classical baselines are often weak, and reported numbers can rarely be reproduced.
QvsC is a small, transparent fix:

* **fixed, versioned instances** with content hashes, sources and best-known values;
* **reference classical baselines**, simple and open, that anyone can rerun; stronger classical
  solvers are welcome as submissions and raise the bar;
* **a solution checker**: every solution value on the leaderboard is recomputed from the submitted
  solution file (running times are reported by the submitter and cannot be checked the same way);
* **a public leaderboard** that grows through pull requests. No accounts, no server, no fees.

The question QvsC answers is simple: *on this instance, with this budget, does the quantum method
beat the best classical result submitted so far?* If it does, the leaderboard shows it. If it does not,
it shows that too.

## Problems

| Problem | Status | Instances | Why it matters for quantum |
|:--|:--|--:|:--|
| [Maximum Independent Set](problems/mis/README.md) | **live** | 143 | native problem of Rydberg-atom processors on unit-disk graphs; one-line QUBO for annealers and QAOA |
| [Max-Cut](problems/maxcut/README.md) | **live** | 401 | the standard QAOA benchmark; a zero-field Ising ground state, native for annealers on their hardware graph |
| K-SAT | planned | | random instances with a known hardness threshold |
| LABS (low-autocorrelation binary sequences) | planned | | used in recent quantum-advantage claims |

## Current leaderboard (MIS)

On all 78 MIS instances of the quantum-scale track (graphs with at most 128 vertices, the size used in
current quantum-hardware experiments), a 250-line classical local search reaches the optimum, and
CP-SAT proves that it is the optimum. The bar a quantum claim has to clear is therefore
**speed and scale**, not solution quality on small graphs. Full tables: [web](https://qvsc-bench.github.io/qvsc/)
or [problems/mis/LEADERBOARD.md](problems/mis/LEADERBOARD.md).

## Current leaderboard (Max-Cut)

With 10 seconds per instance on one CPU core, simple simulated annealing reaches the best known value
on 287 of 401 instances, and on average its cuts are 0.22% below it. The open cases are where quantum claims should aim: on 13 of the
28 planted instances, whose optimum is known by construction, no baseline finds the optimum (this
includes complete graphs with only 100–156 vertices), and on 49 G-set graphs the baselines stay below
the best values published in the literature. Full tables: [web](https://qvsc-bench.github.io/qvsc/)
or [problems/maxcut/LEADERBOARD.md](problems/maxcut/LEADERBOARD.md); how to read them:
[problems/maxcut/README.md](problems/maxcut/README.md#how-the-leaderboard-works).

No quantum submission yet. **Be the first:** see [CONTRIBUTING.md](CONTRIBUTING.md).

## Quick start

```bash
git clone https://github.com/qvsc-bench/qvsc && cd qvsc     # Python ≥ 3.11, no dependencies

# MIS: check a solution
python -m qvsc.mis.verify problems/mis/instances/qoblib/karate.gph.gz my_karate.sol

# MIS: run the classical baselines
python problems/mis/baselines/greedy.py problems/mis/instances/qoblib/karate.gph.gz --out karate.sol
g++ -O2 -std=c++17 -o problems/mis/baselines/arw_ils problems/mis/baselines/arw_ils.cpp
zcat problems/mis/instances/qoblib/frb45-21-3.gph.gz | problems/mis/baselines/arw_ils - --time 10 --out frb.sol

# Max-Cut: check a cut (the vertices of one side), run simulated annealing
python -m qvsc.maxcut.verify problems/maxcut/instances/gset/G1.mc.gz my_G1.sol
g++ -O3 -std=c++17 -o problems/maxcut/baselines/maxcut_heur problems/maxcut/baselines/maxcut_heur.cpp
zcat problems/maxcut/instances/gset/G1.mc.gz | problems/maxcut/baselines/maxcut_heur sa - --time 10 --out G1.sol

# validate every submission, as CI does
python -m qvsc.mis.leaderboard --check
python -m qvsc.maxcut.leaderboard --check
```

## Submitting results

Open a pull request that adds one folder under `problems/<problem>/submissions/`.
CI verifies every solution; on merge the leaderboard and best-known values update automatically.
Quantum and hybrid submissions report device, shots, device time and any classical post-processing,
so that comparisons stay fair. Details: [CONTRIBUTING.md](CONTRIBUTING.md).

## Repository layout

```
qvsc/                Python package: one subpackage per problem (qvsc.mis, qvsc.maxcut: I/O, checker, leaderboard)
problems/mis/        instances, baselines, submissions and leaderboard for Maximum Independent Set
problems/maxcut/     the same for Max-Cut (plus instance generators in qvsc.maxcut.generators)
docs/                landing page and leaderboard (GitHub Pages); docs/data/*.json is generated
tests/               unit tests
```

## Citing

If you use QvsC, please cite the review that defines the MIS quantum track, and the instance sources
listed in [`problems/mis/instances/SOURCES.md`](problems/mis/instances/SOURCES.md) and
[`problems/maxcut/instances/SOURCES.md`](problems/maxcut/instances/SOURCES.md).

```bibtex
@article{marino2026clique,
  title   = {A short review on the maximum clique problem algorithms with classical, AI, and quantum methods},
  author  = {Marino, Raffaele and Buffoni, Lorenzo and Zavalnij, Bogdan},
  journal = {Communications Physics},
  volume  = {9},
  pages   = {239},
  year    = {2026},
  doi     = {10.1038/s42005-026-02606-7}
}
```

## Licence

Code: MIT. Instances taken from other benchmarks keep the licences of their sources; instances
generated by QvsC are CC-BY-4.0 (see each problem's `instances/SOURCES.md`).
