# QvsC track: K-SAT

The third problem of [QvsC](../../README.md). A K-SAT formula is a list of clauses, each the OR of
K literals (a variable or its negation). The task is to find an assignment of the N Boolean
variables that satisfies every clause. When none exists, the best one can do is to satisfy as many
clauses as possible (MAX-K-SAT).

Why K-SAT? It is the canonical NP-complete problem, and random K-SAT has a sharp, well understood
hardness landscape. As the clause density α = M/N grows, the instances go from easy and satisfiable
to hard and satisfiable, and then to unsatisfiable. The thresholds are known from statistical physics
(for 3-SAT, satisfiability is lost at α_s ≈ 4.267), so it is clear where the hard instances are. For quantum
methods, a K-SAT formula maps directly to a cost Hamiltonian: one qubit per variable, with K-body
terms. It has been run with QAOA on trapped-ion devices, and with Grover-type search and quantum
annealing.

## Reference benchmark: RandCSPBench

The main instances and all the reference results come from

> G. Skenderi, L. Buffoni, F. D'Amico, D. Machado, R. Marino, M. Negri, F. Ricci-Tersenghi, C. Lucibello,
> M. C. Angelini, *Benchmarking Graph Neural Networks in Solving Hard Constraint Satisfaction Problems*,
> [arXiv:2602.18419](https://arxiv.org/abs/2602.18419) (2026). Code and data:
> [ArtLabBocconi/RandCSPBench](https://github.com/ArtLabBocconi/RandCSPBench); instances on Hugging Face
> ([CarloLucibello/CSPBenchmarks](https://huggingface.co/datasets/CarloLucibello/CSPBenchmarks)).

QvsC does not copy, regenerate or re-select these instances. It uses the paper's own test sets,
under their original file names: random 3-SAT and 4-SAT with N = 16 to 1024 variables, on a grid of
densities around the satisfiability threshold. It also imports, instance by instance, the results
the paper reports for its classical and neural solvers. The paper compares classical algorithms with
graph neural networks; it has no quantum method. On this track, quantum entries are the ones that
QvsC adds (below) and the ones submitted from now on.

What QvsC adds on top of the paper:

* **a checker**: a submitted assignment counts only if CI recomputes it as satisfying the formula;
* **a hash for every formula** in [`instances/index.csv.gz`](instances/index.csv.gz), so a submission is
  tied to exactly the file the paper used (`python -m qvsc.ksat.fetch --check` verifies all of them);
* **time to solution**, next to the paper's score and residual energy;
* **two small families with quantum-hardware relevance** (below), where the optimum is proven.

## Instances

89,217 instances in three groups. Sources, licences and how each optimum is known:
[`instances/SOURCES.md`](instances/SOURCES.md).

| Group | Instances | N | M | What they are |
|:--|--:|--:|--:|:--|
| RandCSPBench 3-SAT | 58,800 | 16 – 1024 | α N, α = 3.0, 3.1, …, 5.0 | the paper's test set (N ≤ 256, 400 per (N, α)) and out-of-distribution set (N = 512, 1024) |
| RandCSPBench 4-SAT | 29,400 | 16 – 1024 | α N, α = 8.0, 8.1, …, 10.0 | the same for 4-SAT (200 per (N, α)) |
| QAOA hardware (Pelofske et al. 2023) | 17 | 6 – 22 | 4N | the random MAX 3-SAT instances that Pelofske, Bärtschi, Golden & Eidenbenz ran with QAOA on Quantinuum H1-1 and IonQ Harmony, Aria 1 and Forte. 13 are satisfiable and 4 are not (optimum: 1 unsatisfied clause) |
| SATLIB uf20-91 | 1,000 | 20 | 91 | the classical small random 3-SAT set (α = 4.55, all satisfiable), used for example on a CMOS Ising chip (Cilasun et al. 2024) and included in HamLib |

The RandCSPBench instances are random K-SAT formulas: each clause picks K distinct variables
uniformly at random and negates each with probability 1/2; M = round(α N). Thresholds quoted by the
paper: 3-SAT α_d = α_c = 3.86, α_s = 4.267; 4-SAT α_d = 9.38, α_c = 9.547, α_s = 9.931.
Near and above α_s many instances are unsatisfiable. Which ones is not proven; see "known
satisfiable" below.

### Tracks

| Track | Instances | What it reproduces |
|:--|:--|:--|
| `3sat` | RandCSPBench 3-SAT, N = 16 – 256 (42,000) | Table 1 of the paper |
| `3sat-ood` | RandCSPBench 3-SAT, N = 512 and 1024 (16,800) | Supplementary Table 1 |
| `4sat` | RandCSPBench 4-SAT, N = 16 – 256 (21,000) | Table 1 |
| `4sat-ood` | RandCSPBench 4-SAT, N = 512 and 1024 (8,400) | Supplementary Table 1 |
| `qaoa-hardware` | the 17 Pelofske et al. instances | QAOA on trapped-ion hardware |
| `satlib-uf20` | the 1000 uf20-91 instances | the usual small-scale SAT test of quantum and Ising hardware |

## How the leaderboard works

### Two kinds of rows

* **Reported**: results published by others, imported per instance. For RandCSPBench these are the
  numbers of the paper: unsatisfied clauses (and, for FMS and SP, run time) for each instance and
  algorithm, from `results_evaluation/` in the paper's repository. The paper did not publish the
  assignments, so QvsC cannot recheck them. For Pelofske et al. the measured bit strings *were*
  published: QvsC recomputes the clauses they satisfy (that the bit strings came from the devices is
  the authors' statement).
* **Verified**: submissions to QvsC. The number of unsatisfied clauses is recomputed by CI from the
  submitted assignment and the original CNF file; reported numbers are never used.

### The target of an instance

An instance is **solved** when the assignment leaves no clause unsatisfied. For the instances with a
proven optimum (Pelofske et al. and SATLIB, by exhaustive search over all 2^N assignments), it is solved
when the assignment reaches that optimum, for example 1 unsatisfied clause on the 4 unsatisfiable
Pelofske instances.

An instance is **known satisfiable** (more generally: has a known target) when its optimum is proven
or when at least one algorithm of the paper, or one verified submission, solved it. This is the
paper's definition (Sec. 2.3): an instance that nobody solved is either unsatisfiable or very hard,
and the benchmark does not try to tell which.

### The columns

| Column | Meaning |
|:--|:--|
| **Solved** | instances solved / instances attempted |
| **Score S** | solved / known satisfiable, over the attempted instances, in %. This is the score of the paper's Table 1 |
| **Residual energy** | mean of (unsatisfied clauses / M) over the attempted instances the method did *not* solve. This is the RE of the paper's Table 1 |
| **Time to solution** | median, over the solved instances, of the run time until the first satisfying (or optimal) assignment |
| **Budget** | the algorithm's budget (steps, iterations, or wall-clock time per instance) |

Rows are sorted by number solved, then by score, then by time. On the RandCSPBench tracks every
reference row attempts every instance, so this is also the order by score.

### How to read the score S

Example: on the `3sat` track 28,656 of the 42,000 instances are known satisfiable. The paper's
simulated annealing solves 28,299 of them: S = 28,299 / 28,656 = 98.75%. Three caveats:

1. **S = 100% does not mean that every satisfiable instance was solved.** It means: every instance that
   *some* method solved. A new method that solves a formula nobody solved before raises the denominator,
   and lowers everyone else's score. This is intended: the score always measures the distance from the
   best that is known.
2. **The instance mix includes easy and unsatisfiable formulas.** Unsatisfiable instances count in
   neither the numerator nor the denominator. Easy instances (low α) are solved by every method.
   The differences between methods come from α near the threshold: read the per-N tables and the
   per-instance results together with S.
3. **Scores on different tracks are not comparable.** The tracks have different sizes and densities.

### How to read the residual energy

It says how far a method gets on the instances it does not solve. Example: 0.0061 on 3-SAT means
that the final assignment leaves 0.61% of the clauses unsatisfied, about 7 clauses at N = 256, α = 4.3.
It is averaged over a different set of instances for each method (the ones *it* did not solve), and
that set includes unsatisfiable formulas, where even the best assignment leaves some clauses
unsatisfied. So a method that solves more instances can have a *higher* residual energy, because
it is left with the harder ones. Read it as secondary to S.

### How to read the time to solution

The median time over the solved instances, as reported (the paper's per-instance times for FMS and
SP, on an AMD Threadripper PRO 5975WX; the paper does not report per-instance times for SA and the
GNNs, see its Table 3 for average times). Two methods that solve different instances are timed on
different sets, so compare times together with the number solved. Times are never measured by QvsC.

### The QAOA hardware track

The rows "QAOA on <device>" take, for each instance, the best assignment among all the shots that
Pelofske et al. measured on that device, pooling all the QAOA depths p they ran (depths p = 1 to 20, and
between 80 and 15,000 shots per instance and device in total). This is generous to QAOA:
it is the best of every run, not the result of a single fixed protocol. Not every device ran every
instance.

The section "QAOA hardware runs in detail" of [LEADERBOARD.md](LEADERBOARD.md) gives the fraction of shots
that reached the optimum, next to the probability that one uniformly random assignment is optimal
(computed exactly by exhaustive search). That is the fairest single comparison these data allow:
QAOA helps on an instance when its fraction of optimal shots is higher than random guessing. For
calibration: on these sizes (N ≤ 22) a plain exhaustive search, included as a verified submission,
proves the optimum of each instance in less than 0.08 s on one CPU core.

## Quick start

From the repository root (Python ≥ 3.11, no dependencies):

```bash
# download the instances from their original sources (Hugging Face, Zenodo, SATLIB) and check the hashes
python -m qvsc.ksat.fetch --out data/ksat --check

# check an assignment: a bit string ('0'/'1' per variable) or literals 'v 1 -2 3 ... 0'
python -m qvsc.ksat.verify data/ksat/3SAT/test/N256_M1075_id3.cnf my.sol

# exact optimum of a small instance (N <= 30)
g++ -O3 -std=c++17 -o problems/ksat/baselines/exhaustive problems/ksat/baselines/exhaustive.cpp
problems/ksat/baselines/exhaustive data/ksat/pelofske2023/k3_n12.cnf --out k3_n12.sol

# validate every submission and rebuild the leaderboard, as CI does
python -m qvsc.ksat.leaderboard --check --instances data/ksat
```

Instance names: `<K>SAT_<split>_N<N>_M<M>_id<i>` for RandCSPBench (split `test` or `test_ood`, the
rest is the paper's file name), `pelofske_k3_n<N>`, `satlib_uf20-<i>`. The file of each instance is
the `path` column of `instances/index.csv.gz`.

A quantum sampler usually returns bit strings. Write the best one as `<instance> <bits>` on one line
of `solutions.txt.gz` (character i is variable i+1). Many samplers print qubit 0 last: check the
order with `python -m qvsc.ksat.verify` before submitting.

## Submitting

Same folder layout as the other tracks, under `problems/ksat/submissions/<YYYY-MM-DD>_<method>_<team>/`,
with `submission.toml` and the assignments, in either form:

* `solutions.txt.gz`: one line `<instance> <bit string>` per instance (convenient for thousands of
  instances);
* `solutions/<instance>.sol`: one file per instance, a bit string or `v` literals.

Optionally, `results.csv` with columns `instance,time_to_solution_s,total_time_s`. You may submit
assignments that do not satisfy the formula: they count toward the residual energy. Details:
[CONTRIBUTING.md](../../CONTRIBUTING.md#k-sat-submissions).

## Layout

```
instances/index.csv.gz   one row per instance: source, path, K, N, M, alpha, hash, paper_solved, optimum, status
instances/SOURCES.md     where the instances come from, licences, how the optimum is known
reference/randcspbench/  per-instance results of the paper (FMS, SA, SP, NeuroSAT, QuerySAT) + algorithms.toml
reference/pelofske2023/  best measured assignment per device and instance; optimal assignments per instance
baselines/exhaustive.cpp exhaustive search (Gray code), certifies optima for N <= 30
scripts/                 import_randcspbench.py, import_extra.py: how the index and the references were built
submissions/             one folder per submitted method
LEADERBOARD.md           generated, do not edit
```

How the index and the reference rows were built, and how to rebuild them: [REPRODUCE.md](REPRODUCE.md).
