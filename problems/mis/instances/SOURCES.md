# Instance sources and licences

The code in this repository is MIT-licensed (see `LICENSE`). The graphs in `instances/`
come from third parties and keep their original terms; please cite the sources below.

| Family | Count | Origin | What we did | Licence |
|:--|--:|:--|:--|:--|
| `qoblib` | 50 | [QOBLIB](https://git.zib.de/qopt/qoblib-quantum-optimization-benchmarking-library), problem 07 (MIS). Graphs originally from DIMACS, BHOSLIB, Network Repository, SteinLib, Sloane's coding-theory tables | copied unchanged (gzip) | see QOBLIB |
| `evil` | 85 | EVIL generator by S. Szabó and B. Zaválnij: [zbogdan/evil2](https://github.com/zbogdan/evil2) @ `66e48ab` and the small graphs of [zbogdan/qbenchmarks](https://github.com/zbogdan/qbenchmarks) @ `1407a6c` | complemented (they are max-clique instances), α = ω from the generator header | Academic Free License 3.0 |
| `codes` | 4 | [zbogdan/qbenchmarks](https://github.com/zbogdan/qbenchmarks) @ `1407a6c`, single-error-correcting codes from [OEIS A265032](https://oeis.org/A265032/a265032.html) | complemented back to the code graph | see upstream |
| `dimacs-comp` | 4 | DIMACS clique graphs from [zbogdan/qbenchmarks](https://github.com/zbogdan/qbenchmarks) | complemented: MIS on these equals max clique on the DIMACS graph | DIMACS (public benchmark) |

Duplicates are removed by graph content hash (`sha256` column of `index.csv`), so a graph that
appears in two sources is stored once and tagged with both tracks.

The `review-qbench` track is the quantum benchmark set proposed in
R. Marino, L. Buffoni, B. Zavalnij, *A short review on the maximum clique problem algorithms
with classical, AI, and quantum methods*, Communications Physics 9, 239 (2026),
https://doi.org/10.1038/s42005-026-02606-7 — rewritten as MIS instances.

To rebuild `instances/` from the upstream sources:

```bash
git clone https://github.com/zbogdan/qbenchmarks && git -C qbenchmarks checkout 1407a6c
git clone https://github.com/zbogdan/evil2       && git -C evil2 checkout 66e48ab
python scripts/import_sources.py --qoblib PATH/TO/QOBLIB/07-independentset --qbench qbenchmarks --evil evil2
```

## `index.csv` columns

| Column | Meaning |
|:--|:--|
| `name` | instance id = file name without `.gph.gz`; solutions must be named `<name>.sol` |
| `family` | sub-folder of `instances/` |
| `tracks` | `;`-separated leaderboard tracks (`all`, `quantum-scale` = n ≤ 128, `review-qbench`, `review-evil`) |
| `n`, `m` | vertices, edges (after removing duplicates and self-loops) |
| `best_known` | largest independent set known to QvsC: reported by QOBLIB, known by construction (EVIL), or found by a verified submission (see `record_source`) |
| `status` | `optimal` (matches a proven upper bound) or `best-known` |
| `upper_bound` | proven upper bound on α(G), if any |
| `record_source` | who first reached `best_known` |
| `sha256` | hash of the graph content (see `qvsc.mis.graph.graph_hash`) |
