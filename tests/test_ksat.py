import gzip
import tempfile
import unittest
from pathlib import Path

from qvsc.ksat.cnf import CNF, cnf_hash, parse_assignment, parse_cnf, read_cnf
from qvsc.ksat.leaderboard import known_sat, load_reference, summarize
from qvsc.ksat.registry import load_index, target_known, target_unsat
from qvsc.ksat.sources import parse_pelofske_problems
from qvsc.ksat.verify import unsat_clauses

SATLIB_TAIL = """c comment
p cnf 3  2
 1 -2 3 0
-1 2 0
%
0
"""


class CNFTest(unittest.TestCase):
    def test_parse_satlib_trailer(self):
        f = parse_cnf(SATLIB_TAIL)
        self.assertEqual((f.n, f.m), (3, 2))
        self.assertEqual(f.clauses, [(1, -2, 3), (-1, 2)])

    def test_clause_count_mismatch(self):
        with self.assertRaises(ValueError):
            parse_cnf("p cnf 2 2\n1 2 0\n")

    def test_hash_ignores_layout_and_gzip(self):
        a = parse_cnf("p cnf 3 2\n1 -2 3 0\n-1 2 0\n")
        b = parse_cnf("c x\np cnf 3 2\n 1  -2 3 0 -1 2 0\n")
        self.assertEqual(cnf_hash(a), cnf_hash(b))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.cnf.gz"
            p.write_bytes(gzip.compress(b"p cnf 3 2\n1 -2 3 0\n-1 2 0\n"))
            self.assertEqual(cnf_hash(read_cnf(p)), cnf_hash(a))


class AssignmentTest(unittest.TestCase):
    f = CNF(3, [(1, -2, 3), (-1, 2), (2, 3)])

    def test_bitstring_and_literals_agree(self):
        x1 = parse_assignment("110", 3)
        x2 = parse_assignment("s SATISFIABLE\nv 1 2 -3 0\n", 3)
        self.assertEqual(x1, x2)
        self.assertEqual(unsat_clauses(self.f, x1), 0)

    def test_unsat_count(self):
        self.assertEqual(unsat_clauses(self.f, parse_assignment("100", 3)), 2)   # (-1 v 2) and (2 v 3)

    def test_wrapped_bitstring(self):
        self.assertEqual(parse_assignment("110\n01", 5), [True, True, False, False, True])

    def test_malformed(self):
        for text in ("1 -2 0", "1 2 -2 3", "1101", "1 2 7 0"):
            with self.assertRaises(ValueError, msg=text):
                parse_assignment(text, 3)


class PelofskeTest(unittest.TestCase):
    def test_parse_block(self):
        text = """variables = [[0, 1, 2], [0, 1, 3]]
signs = [[0, 0, 1], [1, 1, 1]]
max_obj = 2
angles = [[1.0, 2.0]]
probs[(3,4)] = {'variables' : variables}
"""
        p = parse_pelofske_problems(text)
        self.assertEqual(p[4]["cnf"].clauses, [(-1, -2, 3), (1, 2, 4)])
        self.assertEqual(p[4]["max_obj"], 2)


class IndexTest(unittest.TestCase):
    """The committed index and reference results reproduce the paper's Table 1."""

    @classmethod
    def setUpClass(cls):
        cls.idx = load_index()
        cls.ks = known_sat(cls.idx)

    def test_counts(self):
        rows = [r for r in self.idx.values() if r["source"] == "randcspbench"]
        self.assertEqual(len(rows), 42000 + 16800 + 21000 + 8400)
        self.assertEqual(sum(r["paper_solved"] for r in rows if r["k"] == 3 and r["n"] <= 256), 28656)
        self.assertEqual(sum(r["paper_solved"] for r in rows if r["k"] == 4 and r["n"] <= 256), 19806)

    def test_targets(self):
        r = self.idx["pelofske_k3_n6"]
        self.assertEqual((target_unsat(r), target_known(r)), (1, True))
        r = next(r for r in self.idx.values() if r["source"] == "randcspbench" and not r["paper_solved"])
        self.assertEqual((target_unsat(r), target_known(r)), (0, False))

    def test_paper_scores(self):
        ref = load_reference(self.idx)
        # results_evaluation/analysis-results/score.csv and score_ood_Nmin512_Nmax1024.csv of RandCSPBench
        expected = {("3sat", "FMS_nsteps=100N^2"): 99.99, ("3sat", "SimulatedAnnealing_nsteps=1000N^2"): 98.75,
                    ("3sat", "QuerySAT_niters=2N_Ntrain=256"): 92.39, ("4sat", "FMS_nsteps=100N^2"): 95.15,
                    ("4sat", "NeuroSAT_unsupervised_niters=2N_Ntrain=256"): 47.55,
                    ("3sat-ood", "SimulatedAnnealing_nsteps=1000N^2"): 95.29, ("4sat-ood", "FMS_nsteps=100N^2"): 98.60}
        for (track, algo), score in expected.items():
            rows = {r["id"]: r for r in summarize(ref, self.idx, track, self.ks)}
            self.assertAlmostEqual(round(rows[f"paper:{algo}"]["score"], 2), score, msg=(track, algo))


if __name__ == "__main__":
    unittest.main()
