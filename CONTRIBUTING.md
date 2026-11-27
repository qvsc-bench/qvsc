# Submitting results to QvsC

QvsC compares quantum, hybrid and classical solvers on the same instances. Results enter the
leaderboard through a pull request, and nothing is taken on trust: CI recomputes the value of every
solution from the file you send.

Quantum and hybrid submissions are the reason this benchmark exists. Classical submissions are just as
welcome: a stronger classical baseline raises the bar every quantum claim has to clear.

The steps below are for the Maximum Independent Set track (`problems/mis/`), the only one live today.
Other problems will follow the same layout.

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
`total_time_s` the full run. Quantum submissions may add a `qpu_time_s` column.

## 5. Validate and open the PR

```bash
python -m qvsc.mis.leaderboard --check
```

Do not edit `problems/mis/LEADERBOARD.md`, `docs/data/` or `problems/mis/instances/index.csv`: they are regenerated after merge.
If your solution beats a best-known value, the record moves to your submission automatically.

## Rules of thumb for a fair comparison

1. Report **wall-clock** time, including queueing-free compilation, embedding and post-processing.
2. Say whether a classical post-processing step (repair, local search) was applied to quantum samples.
3. Use the same time budget across instances, and state it.
4. Report all instances you tried, not just the good ones.
5. One submission folder per method and configuration.

## Questions

Open an issue. If you are preparing a quantum run and want an instance subset or format that is not here yet, ask first: we would rather adapt the benchmark than lose a submission.
