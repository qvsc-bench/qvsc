"""Weighted graphs in rudy / G-set format (plain or gzip-compressed) and cut files.

Instance format (the one used by G-set, Biq Mac and MQLib):

    # comment lines start with '#'
    n m
    u v w        # one line per edge, 1-based vertices, integer weight (w defaults to 1)

Solution format: the vertices on one side of the cut, one per line, 1-based, '#' comments
allowed. Which side you list does not matter: a cut and its complement have the same value.
"""

from __future__ import annotations

import gzip
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WGraph:
    n: int
    edges: list[tuple[int, int, int]]  # 0-based, u < v, merged duplicates, no zero weights, no self-loops

    @property
    def m(self) -> int:
        return len(self.edges)

    @property
    def total_weight(self) -> int:
        return sum(w for _, _, w in self.edges)

    def weight_kind(self) -> str:
        ws = {w for _, _, w in self.edges}
        if ws <= {1}:
            return "unit"
        if ws <= {1, -1}:
            return "pm1"
        if min(ws, default=0) > 0:
            return "positive"
        return "integer"

    def adjacency(self) -> list[list[tuple[int, int]]]:
        adj: list[list[tuple[int, int]]] = [[] for _ in range(self.n)]
        for u, v, w in self.edges:
            adj[u].append((v, w))
            adj[v].append((u, w))
        return adj


def make_graph(n: int, triples) -> WGraph:
    """Build a WGraph from (u, v, w) triples, 0-based: merges parallel edges, drops loops and zeros."""
    acc: dict[tuple[int, int], int] = {}
    for u, v, w in triples:
        if u == v:
            continue
        if not (0 <= u < n and 0 <= v < n):
            raise ValueError(f"vertex out of range in edge ({u + 1},{v + 1})")
        key = (u, v) if u < v else (v, u)
        acc[key] = acc.get(key, 0) + int(w)
    return WGraph(n, sorted((u, v, w) for (u, v), w in acc.items() if w != 0))


def _open_text(path: Path):
    path = Path(path)
    if path.suffix == ".gz":
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="ascii")
    return open(path, "r", encoding="ascii")


def _int_weight(tok: str, path, line) -> int:
    try:
        return int(tok)
    except ValueError:
        x = float(tok)
        if x != int(x):
            raise ValueError(f"{path}: non-integer weight in line {line!r} (QvsC uses integer weights)") from None
        return int(x)


def read_maxcut(path: str | Path) -> WGraph:
    """Read a weighted graph in rudy / G-set format. The declared edge count is not trusted."""
    n = None
    triples = []
    with _open_text(Path(path)) as fh:
        for line in fh:
            s = line.split("#", 1)[0].strip()
            if not s or s[0] in "c%":
                continue
            parts = s.split()
            if n is None:
                n = int(parts[0])
                continue
            u, v = int(parts[0]) - 1, int(parts[1]) - 1
            w = _int_weight(parts[2], path, line) if len(parts) > 2 else 1
            if not (0 <= u < n and 0 <= v < n):
                raise ValueError(f"{path}: vertex out of range in line {line!r}")
            triples.append((u, v, w))
    if n is None:
        raise ValueError(f"{path}: empty file")
    return make_graph(n, triples)


def write_maxcut(g: WGraph, path: str | Path, comments=()) -> None:
    """Write rudy / G-set format; '.gz' paths are written as reproducible gzip (mtime=0)."""
    lines = [f"# {c}".rstrip() for c in comments]
    lines.append(f"{g.n} {g.m}")
    lines.extend(f"{u + 1} {v + 1} {w}" for u, v, w in g.edges)
    data = ("\n".join(lines) + "\n").encode("ascii")
    path = Path(path)
    if path.suffix == ".gz":
        with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
            gz.write(data)
    else:
        path.write_bytes(data)


def graph_hash(g: WGraph) -> str:
    """Content hash (independent of comments, edge order, duplicate splitting and compression)."""
    h = hashlib.sha256(f"{g.n}\n".encode())
    for u, v, w in g.edges:
        h.update(f"{u + 1} {v + 1} {w}\n".encode())
    return h.hexdigest()


def read_solution(path: str | Path) -> list[int]:
    """Read the vertices of one side of the cut: 1-based ids, whitespace separated, '#' comments."""
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            s = line.split("#", 1)[0].strip()
            for tok in s.split():
                try:
                    out.append(int(tok))
                except ValueError:
                    raise ValueError(f"{path}:{lineno}: not a vertex index: {tok!r}") from None
    return out


def write_solution(side, path: str | Path, header=()) -> None:
    """Write one side of a cut (1-based vertex ids)."""
    vs = sorted(int(v) for v in side)
    lines = [f"# {h}" for h in header] + [str(v) for v in vs]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
