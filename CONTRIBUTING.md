# Submitting results to QvsC

QvsC compares quantum, hybrid and classical solvers on the same instances. Results enter the
leaderboard through a pull request, and nothing is taken on trust: CI recomputes the value of every
solution from the file you send.

Quantum and hybrid submissions are the reason this benchmark exists. Classical submissions are just as
welcome: a stronger classical baseline raises the bar every quantum claim has to clear.

Two problems are live: Maximum Independent Set (`problems/mis/`) and Max-Cut (`problems/maxcut/`).
The steps below use MIS as the example; Max-Cut works the same way, with the differences listed in
[Max-Cut submissions](#max-cut-submissions).

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
  plus `qpu_time_s` and `time_to_target_s` (time to first reach 99% of the target shown in
  `instances/index.csv` when you ran) if you have them.
* **`trajectories/<instance>.traj`** (optional, recommended): one line `time_s cut` each time your best
  cut improves. The leaderboard uses it to compute time-to-target (time to reach 99% of the target)
  against the *current* target, so your TTT stays meaningful when someone later raises a best-known value.
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

## Rules of thumb for a fair comparison

1. Report **wall-clock** time per instance: include compilation, embedding and post-processing, and
   leave out time spent waiting in a cloud queue (report it separately if you like).
2. Say whether a classical post-processing step (repair, local search) was applied to quantum samples.
3. Use the same time budget across instances, and state it.
4. Report all instances you tried, not just the good ones.
5. One submission folder per method and configuration.

## Questions

Open an issue. If you are preparing a quantum run and want an instance subset or format that is not here yet, ask first: we would rather adapt the benchmark than lose a submission.
