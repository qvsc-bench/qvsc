"""Reading graphs in DIMACS format (plain or gzip-compressed) and solution files."""

from __future__ import annotations

import gzip
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Graph:
    n: int
    edges: list[tuple[int, int]]  # 0-based, u < v, no duplicates, no self-loops

    @property
    def m(self) -> int:
        return len(self.edges)

    def adjacency(self) -> list[set[int]]:
        adj: list[set[int]] = [set() for _ in range(self.n)]
        for u, v in self.edges:
            adj[u].add(v)
            adj[v].add(u)
        return adj

    def complement(self) -> "Graph":
        adj = self.adjacency()
        edges = [(u, v) for u in range(self.n) for v in range(u + 1, self.n) if v not in adj[u]]
        return Graph(self.n, edges)


def _open_text(path: Path):
    path = Path(path)
    if path.suffix == ".gz":
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="ascii")
    return open(path, "r", encoding="ascii")


def read_dimacs(path: str | Path) -> Graph:
    """Read a DIMACS graph ('p edge n m' / 'p col n m', then 'e u v', 1-based).

    Duplicate edges and self-loops are dropped; the declared edge count is not trusted."""
    n = None
    seen: set[tuple[int, int]] = set()
    with _open_text(Path(path)) as fh:
        for line in fh:
            if not line or line[0] in "c\n%#":
                continue
            parts = line.split()
            if parts[0] == "p":
                n = int(parts[2])
            elif parts[0] == "e":
                u, v = int(parts[1]) - 1, int(parts[2]) - 1
                if n is None:
                    raise ValueError(f"{path}: edge before 'p' line")
                if not (0 <= u < n and 0 <= v < n):
                    raise ValueError(f"{path}: vertex out of range in line {line!r}")
                if u == v:
                    continue
                seen.add((u, v) if u < v else (v, u))
    if n is None:
        raise ValueError(f"{path}: missing 'p' line")
    return Graph(n, sorted(seen))


def write_dimacs(g: Graph, path: str | Path, comments: list[str] = ()) -> None:
    """Write a graph in DIMACS format; '.gz' paths are written as reproducible gzip (mtime=0)."""
    lines = [f"c {c}".rstrip() for c in comments]
    lines.append(f"p edge {g.n} {g.m}")
    lines.extend(f"e {u + 1} {v + 1}" for u, v in g.edges)
    data = ("\n".join(lines) + "\n").encode("ascii")
    path = Path(path)
    if path.suffix == ".gz":
        with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
            gz.write(data)
    else:
        path.write_bytes(data)


def graph_hash(g: Graph) -> str:
    """Content hash of the graph (independent of comments, edge order and compression)."""
    h = hashlib.sha256(f"{g.n}\n".encode())
    for u, v in g.edges:
        h.update(f"{u + 1} {v + 1}\n".encode())
    return h.hexdigest()


def read_solution(path: str | Path) -> list[int]:
    """Read a node-list solution: one 1-based vertex per line, '#' comments allowed.

    Returns 1-based vertex ids exactly as written (validation happens in verify)."""
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            s = line.split("#", 1)[0].strip()
            if not s:
                continue
            for tok in s.split():
                try:
                    out.append(int(tok))
                except ValueError:
                    raise ValueError(f"{path}:{lineno}: not a vertex index: {tok!r}") from None
    return out


def write_solution(vertices, path: str | Path, header: list[str] = ()) -> None:
    vs = sorted(int(v) for v in vertices)
    lines = [f"# {h}" for h in header] + [str(v) for v in vs]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
