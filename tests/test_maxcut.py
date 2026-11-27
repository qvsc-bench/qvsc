import random
import sys
import tempfile
import unittest
from pathlib import Path

from qvsc.maxcut.generators import (complete, cubic_lattice, planted_frustrated_loops, planted_wishart_pm1,
                                    pm1_weights, random_regular)
from qvsc.maxcut.graph import WGraph, graph_hash, make_graph, read_maxcut, write_maxcut
from qvsc.maxcut.verify import cut_value, verify

ROOT = Path(__file__).resolve().parents[1]


def brute_force(g: WGraph) -> int:
    best = 0
    for mask in range(1 << (g.n - 1)):
        best = max(best, cut_value(g, {i for i in range(g.n) if mask >> i & 1}))
    return best


class GraphTest(unittest.TestCase):
    def test_merge_and_drop(self):
        g = make_graph(3, [(0, 1, 2), (1, 0, -2), (1, 2, 1), (2, 2, 5)])
        self.assertEqual(g.edges, [(1, 2, 1)])

    def test_roundtrip_gzip_and_hash(self):
        g = make_graph(4, [(0, 1, 1), (1, 2, -3), (2, 3, 2)])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "g.mc.gz"
            write_maxcut(g, p, ["test"])
            self.assertEqual(graph_hash(read_maxcut(p)), graph_hash(g))

    def test_reads_gset_style_without_weights(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "g.txt"
            p.write_text("# comment\n3 2\n1 2\n2 3 -1\n")
            g = read_maxcut(p)
            self.assertEqual(g.edges, [(0, 1, 1), (1, 2, -1)])


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.g = make_graph(4, [(0, 1, 1), (1, 2, 1), (2, 3, 1), (3, 0, 1)])  # 4-cycle

    def test_cut(self):
        self.assertEqual(verify(self.g, [1, 3]).cut, 4)
        self.assertEqual(verify(self.g, [2, 4]).cut, 4)
        self.assertEqual(verify(self.g, []).cut, 0)

    def test_invalid(self):
        self.assertFalse(verify(self.g, [5]).valid)
        self.assertFalse(verify(self.g, [1, 1]).valid)

    def test_negative_weights(self):
        g = make_graph(2, [(0, 1, -2)])
        self.assertEqual(verify(g, [1]).cut, -2)


class GeneratorTest(unittest.TestCase):
    def test_regular(self):
        edges = random_regular(20, 3, random.Random(1))
        deg = [0] * 20
        for u, v in edges:
            deg[u] += 1
            deg[v] += 1
        self.assertEqual(set(deg), {3})

    def test_cubic_lattice(self):
        n, edges = cubic_lattice(4)
        self.assertEqual((n, len(edges)), (64, 192))

    def test_reproducible(self):
        a = pm1_weights(10, complete(10), random.Random("sk-n10-s1"))
        b = pm1_weights(10, complete(10), random.Random("sk-n10-s1"))
        self.assertEqual(graph_hash(a), graph_hash(b))

    def test_planted_loops_optimum(self):
        n = 14
        edges = random_regular(n, 4, random.Random(5))
        for seed in range(3):
            g, side, opt = planted_frustrated_loops(n, edges, 0.4, random.Random(seed), min_len=3)
            self.assertEqual(verify(g, [i + 1 for i in side]).cut, opt)
            self.assertEqual(brute_force(g), opt)

    def test_planted_wishart_optimum(self):
        for seed in range(3):
            g, side, opt = planted_wishart_pm1(14, 4, random.Random(seed))
            self.assertEqual(verify(g, [i + 1 for i in side]).cut, opt)
            self.assertEqual(brute_force(g), opt)


class BaselineTest(unittest.TestCase):
    def test_greedy_local_search(self):
        sys.path.insert(0, str(ROOT / "problems" / "maxcut" / "baselines"))
        from greedy_ls import greedy_local_search
        g = make_graph(5, [(0, 1, 1), (1, 2, 1), (2, 3, 1), (3, 4, 1), (4, 0, 1)])  # 5-cycle, max cut 4
        x, cut = greedy_local_search(g.n, g.adjacency())
        self.assertEqual(cut, verify(g, [i + 1 for i in range(g.n) if x[i]]).cut)
        self.assertEqual(cut, 4)


if __name__ == "__main__":
    unittest.main()
