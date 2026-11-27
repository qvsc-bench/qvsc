import tempfile
import unittest
from pathlib import Path

from qvsc.mis.graph import Graph, graph_hash, read_dimacs, write_dimacs
from qvsc.mis.verify import verify


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.g = Graph(4, [(0, 1), (1, 2), (2, 3)])  # path 1-2-3-4

    def test_valid(self):
        v = verify(self.g, [1, 3])
        self.assertTrue(v.valid)
        self.assertEqual(v.size, 2)

    def test_edge_inside(self):
        self.assertFalse(verify(self.g, [1, 2]).valid)

    def test_out_of_range_and_duplicates(self):
        self.assertFalse(verify(self.g, [5]).valid)
        self.assertFalse(verify(self.g, [1, 1]).valid)

    def test_roundtrip_gzip_and_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "g.gph.gz"
            write_dimacs(self.g, p, ["test"])
            h = read_dimacs(p)
            self.assertEqual(graph_hash(h), graph_hash(self.g))

    def test_complement(self):
        self.assertEqual(self.g.complement().m, 3)


class BaselineTest(unittest.TestCase):
    def test_greedy_is_independent(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "problems" / "mis" / "baselines"))
        from greedy import min_degree_greedy
        g = Graph(5, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)])  # 5-cycle, alpha = 2
        sol = min_degree_greedy(g.n, [list(s) for s in g.adjacency()])
        self.assertTrue(verify(g, [v + 1 for v in sol]).valid)
        self.assertEqual(len(sol), 2)


if __name__ == "__main__":
    unittest.main()
