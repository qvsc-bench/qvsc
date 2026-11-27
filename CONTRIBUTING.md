# Submitting results to QvsC

QvsC compares quantum, hybrid and classical solvers on the same instances. Results enter the
leaderboard through a pull request, and nothing is taken on trust: CI recomputes the value of every
solution from the file you send.

Quantum and hybrid submissions are the reason this benchmark exists. Classical submissions are just as
welcome: a stronger classical baseline raises the bar every quantum claim has to clear.

Three problems are live: Maximum Independent Set (`problems/mis/`), Max-Cut (`problems/maxcut/`) and
K-SAT (`problems/ksat/`). The steps below use MIS as the example; the other two work the same way,
with the differences listed in [Max-Cut submissions](#max-cut-submissions) and
[K-SAT submissions](#k-sat-submissions).

## 1. Create a folder

```
problems/mis/submissions/<YYYY-MM-DD>_<method>_<team>/
├── submission.toml        # required: who, what, on which hardware, with which budget
├── results.csv            # optional but strongly encouraged: timings per instance
└── solutions/
    ├── karate.sol         # one file per instance you solved, named <instance>.sol
    └── ...
```

You do not need to solve every instance. The leaderboard shows how many you attempted.

## 2. `submission.toml`

```toml
[submission]
method = "My QAOA variant"                 # required
authors = ["Ada Lovelace", "Alan Turing"]   # required
paradigm = "quantum"                        # required: classical | quantum | hybrid
date = "2026-12-01"                         # required
hardware = "IBM Heron r2, 156 qubits"       # required: CPU/GPU/QPU model
time_limit_s = 60                           # required: wall-clock budget per instance
code = "https://github.com/you/your-code"   # strongly encouraged
reference = "https://arxiv.org/abs/..."     # paper or preprint, if any
description = "One paragraph on the method."

# Quantum and hybrid submissions: please fill these in, they make comparisons fair.
[submission.quantum]
qpu = "ibm_fez"
shots_per_instance = 4000
qpu_time_s = "see results.csv"             # pure device time
includes_classical_postprocessing = true   # e.g. greedy repair of infeasible samples
includes_embedding_and_compilation_time = true
```

## 3. `solutions/<instance>.sol`

The vertices of your independent set, one per line, 1-based (the numbering of the `.gph` file). Lines starting with `#` are comments.

```
# size = 20
5
8
9
```

Check it locally:

```bash
python -m qvsc.mis.verify problems/mis/instances/qoblib/karate.gph.gz problems/mis/submissions/<yours>/solutions/karate.sol
```

## 4. `results.csv` (optional)

```
instance,reported_size,time_to_best_s,total_time_s,seed,upper_bound
karate,20,0.01,10.0,1,
```

`time_to_best_s` is the wall-clock time at which the returned solution was first found,
`total_time_s` the full run. Quantum submissions may add a `qpu_time_s` column (pure device time).
`upper_bound` is for exact solvers: a proven bound on the optimum. It is used only if
`submission.toml` contains `exact = true` and a maintainer has reviewed the method.

## 5. Validate and open the PR

```bash
python -m qvsc.mis.leaderboard --check
```

Do not edit `problems/mis/LEADERBOARD.md`, `docs/data/` or `problems/mis/instances/index.csv`: they are regenerated after merge.
If your solution beats a best-known value, the record moves to your submission automatically.

## Max-Cut submissions

Same folder layout, under `problems/maxcut/submissions/<YYYY-MM-DD>_<method>_<team>/`, same `submission.toml`.

* **`solutions/<instance>.sol`**: the vertices on *one* side of your cut, one per line, 1-based
  (either side: a cut and its complement have the same value). The checker recomputes the cut value.

  ```bash
  python -m qvsc.maxcut.verify problems/maxcut/instances/gset/G1.mc.gz solutions/G1.sol
  ```

* **`results.csv`** (optional): `instance,reported_cut,time_to_best_s,total_time_s,seed,upper_bound`,
  plus `qpu_time_s` if you have it.
* **`trajectories/<instance>.traj`** (optional, recommended): one line `time_s cut` each time your best
  cut improves. The leaderboard uses it to compute the time at which you first reached the target,
  against the *current* target, so it stays correct when someone later raises a best-known value.
  Without trajectories, `time_to_best_s` is used.
* Validate with `python -m qvsc.maxcut.leaderboard --check`. Do not edit `problems/maxcut/LEADERBOARD.md`,
  `docs/data/` or `problems/maxcut/instances/index.csv`.

How your results are scored (target, hits, mean ratio, time-to-target):
[problems/maxcut/README.md](problems/maxcut/README.md#how-the-leaderboard-works).

For annealers: the hardware-native instances (`pegasus`, `zephyr`, and the planted instances on those
graphs) are defined on the ideal device graph, so they need no embedding apart from the few qubits
and couplers missing on a real chip. The unweighted topologies are in `problems/maxcut/instances/topologies/`.
For gate-based devices: the `heavyhex` instances use IBM coupling maps (no SWAP gates needed), and the
`gate-scale` track collects every instance with at most 156 vertices (one qubit per vertex on IBM Heron r2).
The `qaoa` track contains the usual QAOA families at all sizes, up to 10,000 vertices, for comparison
with simulators and classical methods.

## K-SAT submissions

Same folder layout, under `problems/ksat/submissions/<YYYY-MM-DD>_<method>_<team>/`, same `submission.toml`
(you may add `kind = "..."`, e.g. `"QAOA (hardware)"` or `"local search"`, shown in the leaderboard).
The instances are not in the repository: download them first with
`python -m qvsc.ksat.fetch --out data/ksat` (add `--only randcspbench`, `--only pelofske2023` or
`--only satlib` to fetch one source).

* **Assignments**, in either form (both may be used in one submission):
  * `solutions.txt.gz`: one line `<instance> <bit string>` per instance, where character i of the bit
    string is the value of variable i+1. This is the practical choice for many instances.
  * `solutions/<instance>.sol`: a bit string, or literals in SAT Competition style (`v 1 -2 3 ... 0`,
    every variable exactly once).

  ```bash
  python -m qvsc.ksat.verify data/ksat/3SAT/test/N256_M1075_id3.cnf solutions/3SAT_test_N256_M1075_id3.sol
  ```

  Instance names are in `problems/ksat/instances/index.csv.gz` (`name` column; `path` is the file
  below `data/ksat`). Assignments that do not satisfy the formula are accepted: they count toward the
  residual energy, not toward the score.
* **`results.csv`** (optional): `instance,time_to_solution_s,total_time_s`, plus `qpu_time_s` and
  `shots` if you have them.
* Validate with `python -m qvsc.ksat.leaderboard --check --instances data/ksat`. Do not edit
  `problems/ksat/LEADERBOARD.md`, `docs/data/` or `problems/ksat/instances/index.csv.gz`.

How your results are scored (score S, residual energy, time to solution, as in Skenderi et al. 2026):
[problems/ksat/README.md](problems/ksat/README.md#how-the-leaderboard-works).

For gate-based devices: the `qaoa-hardware` track has the 17 instances (N = 6 to 22) that Pelofske et
al. ran on trapped-ion hardware, with their measured results as reference rows, and `satlib-uf20` has
1000 satisfiable instances with 20 variables. Both need one qubit per variable and 3-body terms. On
the RandCSPBench tracks, N = 16 to 128 fits current devices too.

## Rules of thumb for a fair comparison

1. Report **wall-clock** time per instance: include compilation, embedding and post-processing, and
   leave out time spent waiting in a cloud queue (report it separately if you like).
2. Say whether a classical post-processing step (repair, local search) was applied to quantum samples.
3. Use the same time budget across instances, and state it.
4. Report all instances you tried, not just the good ones.
5. One submission folder per method and configuration.

## Questions

Open an issue. If you are preparing a quantum run and want an instance subset or format that is not here yet, ask first: we would rather adapt the benchmark than lose a submission.
