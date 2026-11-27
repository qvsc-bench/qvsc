# How the K-SAT index and reference rows were built

Everything in `instances/` and `reference/` is produced by two scripts from published data. Nothing
was run by QvsC except the exhaustive search on the small instances.

## 1. RandCSPBench index and paper results

```bash
git clone https://github.com/ArtLabBocconi/RandCSPBench          # results_evaluation/ (per-instance results)
python -m qvsc.ksat.fetch --out data/ksat --only randcspbench      # kSAT.zip from Hugging Face
python problems/ksat/scripts/import_randcspbench.py --randcspbench RandCSPBench --instances data/ksat
```

The script reads each instance in scope (the paper's test and N = 512, 1024 OOD sets, K = 3, 4),
stores its hash, and joins `paper_solved` from `<K>SAT-best_per_sample.csv`. It then copies, for the
six algorithms in `reference/randcspbench/algorithms.toml`, the per-instance number of unsatisfied
clauses `E` and (FMS, SP) the run time from `results_evaluation/<K>SAT/<K>SAT_<algo>.csv`.
RandCSPBench commit used: `20702c0` (main, 27 November 2026).

**Check against the paper.** With these files, `python -m qvsc.ksat.leaderboard` reproduces the
scores of RandCSPBench's `analysis-results/score.csv` and `score_ood_Nmin512_Nmax1024.csv` to the
second decimal for every algorithm (for example 3-SAT, N ≤ 256: FMS 99.99, SA 98.75, QuerySAT 92.39,
NeuroSAT 84.49, SP 82.29; 4-SAT: FMS 95.15, SA 82.62, QuerySAT 66.57, NeuroSAT 47.55), and the residual
energies `E_unsolved`. `tests/test_ksat.py` checks part of this in CI. Table 1 of the paper prints
99.98 for FMS on 3-SAT, where `score.csv` gives 99.99 (28,653 / 28,656 = 99.990%).

**How the hashes were computed.** Hugging Face was not reachable from the machine that built this
index, so the files were produced with the paper's own generator (`datasets/gen_graphs_sat.jl` at the
commit above, Julia 1.13.4, StableRNGs 1.1.0, StatsBase 0.34.14) with the paper's seeds and settings.
Two checks that these are the paper's files: the CaDiCaL assignments shipped with RandCSPBench
(`datasets/3SAT/train_labels.csv`) satisfy 2029 of 2029 regenerated 3-SAT training formulas checked
(the training and test sets come from the same random stream); and the hash does not depend on the
file layout. The CI job `ksat-instances` downloads `kSAT.zip` and checks every hash on each pull
request, so a mismatch with the published archive shows up there.

## 2. Pelofske et al. and SATLIB

```bash
python -m qvsc.ksat.fetch --out data/ksat --only pelofske2023 --only satlib
g++ -O3 -std=c++17 -o problems/ksat/baselines/exhaustive problems/ksat/baselines/exhaustive.cpp
python problems/ksat/scripts/import_extra.py --instances data/ksat \
    --pelofske-dataset <unzipped Zenodo 8201693>/dataset --exhaustive problems/ksat/baselines/exhaustive
```

The script

* indexes the 17 Pelofske instances and the 1000 uf20-91 instances, runs the exhaustive search on each,
  and stops if an optimum differs from the published `max_obj` (Pelofske) or is not 0 (SATLIB);
* reads every measurement file of the Zenodo dataset (`<device>_samples/k3_p<p>_n<N>*.json`), reverses
  each readout bit string into variable order as the dataset README prescribes, recomputes its
  unsatisfied clauses, and keeps per device and instance the best assignment, the total shots and the
  shots that reached the optimum (`reference/pelofske2023/devices.csv.gz`);
* writes the exhaustive-search submission `submissions/2026-11-27_exhaustive_qvsc-baselines`
  (assignments and timings).

Exhaustive search: Gray-code enumeration of all 2^N assignments, one thread, on an Intel Xeon
Processor @ 2.30 GHz, g++ -O3. The longest run (N = 22) took 0.077 s. `time_to_solution_s` is the
moment the enumeration first met an optimal assignment, which depends on the enumeration order;
`total_time_s` is the full proof of optimality.

## 3. Leaderboard

```bash
python -m qvsc.ksat.leaderboard --instances data/ksat
```

writes `LEADERBOARD.md` and `docs/data/ksat.json`. The CNF files are needed only to check submitted
assignments; the reference rows come from `reference/`.
