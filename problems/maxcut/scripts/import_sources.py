"""Build the Max-Cut instance set of QvsC.

    python problems/maxcut/scripts/import_sources.py            # everything that does not need extra packages
    python problems/maxcut/scripts/import_sources.py --hardware  # also Pegasus/Zephyr/IBM topologies
                                                                 # (pip install dwave-networkx rustworkx qiskit-ibm-runtime)
    QVSC_PLANTED_SECRET=... python problems/maxcut/scripts/import_sources.py --planted --hardware

Families
    gset      G-set (Helmberg & Ye), 71 graphs, from the public MQLib S3 bucket
    biqmac    Biq Mac library Max-Cut instances (rudy g05/pm1s/pm1d/w/pw, Ising chains, tori), optima known
    mqlib     MQLib standard Max-Cut instances besides G-set: DIMACS tori and 3D spin glasses (Festa et al.)
    pegasus   D-Wave Pegasus P(m) topologies with random +-1 weights (Advantage = P16)
    zephyr    D-Wave Zephyr Z(m,4) topologies with random +-1 weights (Advantage2 = Z(12,4))
    heavyhex  IBM heavy-hex: coupling maps of Eagle (127), Heron r1 (133), Heron r2 (156) and generic
              heavy-hex lattices, random +-1 weights (heavy-hex is bipartite, so unit weights would be trivial)
    reg3      random 3-regular graphs, unit weights (the standard QAOA Max-Cut benchmark)
    sk        Sherrington-Kirkpatrick: complete graphs with random +-1 weights
    planted   instances with an optimum known by construction (frustrated loops on hardware graphs,
              integer Wishart ensemble on complete graphs). Seeds are secret: see SOURCES.md.

Random families use fixed public seeds and the pure-Python generators in qvsc.maxcut.generators,
so they are reproducible bit for bit. Existing best-known values in index.csv are kept.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
import random
import sys
import urllib.request
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # problems/maxcut
sys.path.insert(0, str(ROOT.parents[1]))
from qvsc.maxcut import generators as gen  # noqa: E402
from qvsc.maxcut.graph import graph_hash, make_graph, read_maxcut, write_maxcut  # noqa: E402
from qvsc.maxcut.registry import INDEX, instance_path, load_index, refresh_status, save_index  # noqa: E402

MQLIB = "https://mqlibinstances.s3.amazonaws.com/"
GATE_SCALE = 156          # largest gate-based device modelled here (IBM Heron r2)
LIC_GEN = "CC-BY-4.0 (QvsC)"

REG3_N = [20, 30, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
SK_N = [20, 30, 50, 100, 200, 500]
SK_LARGE_N = [1000, 2000]
PEGASUS_M = [2, 3, 4, 6, 8, 16]
ZEPHYR_M = [2, 3, 4, 6, 12]
HEAVYHEX_D = [3, 5, 7, 9, 11, 15]
IBM_DEVICES = {"eagle127": "FakeSherbrooke", "heron133": "FakeTorino", "heron156": "FakeFez"}
WISHART = [(32, 0.25), (32, 0.5), (64, 0.25), (64, 0.5), (100, 0.25), (100, 0.5), (128, 0.25), (128, 0.5),
           (156, 0.25), (156, 0.5), (256, 0.25), (256, 0.5), (512, 0.25), (512, 0.5)]
LOOPS = [("pegasus-P6", 0.15), ("pegasus-P6", 0.3), ("pegasus-P16", 0.15), ("pegasus-P16", 0.3),
         ("zephyr-Z4", 0.15), ("zephyr-Z4", 0.3), ("zephyr-Z12", 0.15), ("zephyr-Z12", 0.3),
         ("ibm-eagle127", 0.1), ("ibm-heron156", 0.1), ("heavyhex-d15", 0.1),
         ("cubic-L8", 0.2), ("cubic-L16", 0.15), ("cubic-L16", 0.3)]


def tracks_for(family: str, n: int, hardware: bool = False) -> list[str]:
    t = ["all"]
    if family in ("gset", "biqmac", "mqlib"):
        t.append("literature")
    if family in ("pegasus", "zephyr", "heavyhex") or hardware:
        t.append("hardware-native")
    if family in ("reg3", "sk"):
        t.append("qaoa")
    if family == "planted":
        t.append("planted")
    if n <= GATE_SCALE:
        t.append("gate-scale")
    return t


class Builder:
    def __init__(self, cache: Path):
        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        self.old = load_index() if INDEX.exists() else {}
        self.rows: dict[str, dict] = {}

    def add(self, name, family, g, origin, license_, tracks=None, reference=None, ref_source="",
            upper_bound=None, comments=()):
        row = dict(name=name, family=family, n=g.n, m=g.m, weights=g.weight_kind(),
                   tracks=tracks or tracks_for(family, g.n), best_known=None, status="open",
                   upper_bound=upper_bound, reference_value=reference, reference_source=ref_source,
                   record_source="", sha256=graph_hash(g), origin=origin, license=license_)
        old = self.old.get(name)
        if old and old["sha256"] == row["sha256"]:
            row["best_known"], row["record_source"] = old["best_known"], old["record_source"]
            if old["upper_bound"] is not None and (upper_bound is None or old["upper_bound"] < upper_bound):
                row["upper_bound"] = old["upper_bound"]
        refresh_status(row)
        path = instance_path(row)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or graph_hash(read_maxcut(path)) != row["sha256"]:
            write_maxcut(g, path, [f"QvsC Max-Cut instance {name}", *comments])
        self.rows[name] = row
        print(f"{family:9s} {name:32s} n={g.n:6d} m={g.m:8d} {row['weights']}", flush=True)

    # ---- literature -------------------------------------------------------------------------
    def fetch_mqlib(self, key: str) -> Path:
        dst = self.cache / key.replace(".zip", ".txt")
        if not dst.exists():
            with urllib.request.urlopen(MQLIB + key, timeout=120) as r:
                data = r.read()
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                dst.write_bytes(z.read(z.namelist()[0]))
        return dst

    def literature(self):
        for r in csv.DictReader(open(ROOT / "instances" / "references.csv", encoding="utf-8")):
            g = read_maxcut(self.fetch_mqlib(r["mqlib_key"]))
            fam = r["family"]
            origin = {"gset": "https://web.stanford.edu/~yyye/yyye/Gset/ (via MQLib S3)",
                      "biqmac": "https://biqmac.aau.at/biqmaclib.html (via MQLib S3)",
                      "mqlib": "https://github.com/MQLib/MQLib (S3 bucket mqlibinstances)"}[fam]
            self.add(r["name"], fam, g, origin, "see upstream", reference=int(r["reference_value"]),
                     ref_source=r["reference_source"], comments=[f"source: {origin}", f"MQLib key: {r['mqlib_key']}"])

    # ---- topologies ---------------------------------------------------------------------------
    def topologies(self, hardware: bool) -> dict[str, tuple[int, list]]:
        topo: dict[str, tuple[int, list]] = {}
        for L in (8, 16):
            topo[f"cubic-L{L}"] = gen.cubic_lattice(L)
        if not hardware:
            return topo
        warnings.filterwarnings("ignore")
        import dwave_networkx as dnx
        import rustworkx as rx

        def relabel(nodes, edges):
            ix = {v: i for i, v in enumerate(sorted(nodes))}
            return len(ix), sorted({(min(ix[a], ix[b]), max(ix[a], ix[b])) for a, b in edges})

        for m in PEGASUS_M:
            G = dnx.pegasus_graph(m)
            topo[f"pegasus-P{m}"] = relabel(G.nodes(), G.edges())
        for m in ZEPHYR_M:
            G = dnx.zephyr_graph(m, 4)
            topo[f"zephyr-Z{m}"] = relabel(G.nodes(), G.edges())
        for d in HEAVYHEX_D:
            G = rx.generators.heavy_hex_graph(d)
            topo[f"heavyhex-d{d}"] = relabel(G.node_indices(), G.edge_list())
        from qiskit_ibm_runtime import fake_provider
        for nm, cls in IBM_DEVICES.items():
            b = getattr(fake_provider, cls)()
            topo[f"ibm-{nm}"] = relabel(range(b.num_qubits), b.coupling_map.get_edges())
        tdir = ROOT / "instances" / "topologies"
        tdir.mkdir(parents=True, exist_ok=True)
        for nm, (n, edges) in topo.items():
            p = tdir / f"{nm}.mc.gz"
            g = gen.unit_weights(n, edges)
            if not p.exists() or graph_hash(read_maxcut(p)) != graph_hash(g):
                write_maxcut(g, p, [f"QvsC hardware topology {nm} (unit weights; not a benchmark instance)"])
        return topo

    def hardware(self, topo):
        for nm, (n, edges) in topo.items():
            fam = nm.split("-")[0]
            if fam == "ibm":
                fam = "heavyhex"
            if fam not in ("pegasus", "zephyr", "heavyhex"):
                continue
            for seed in (1, 2):
                g = gen.pm1_weights(n, edges, random.Random(f"{nm}-pm1-s{seed}"))
                self.add(f"{nm}-pm1-s{seed}", fam, g, "generated (qvsc.maxcut.generators.pm1_weights)", LIC_GEN,
                         comments=[f"{nm} topology, random +-1 weights, seed '{nm}-pm1-s{seed}'"])

    # ---- QAOA families --------------------------------------------------------------------------
    def qaoa(self):
        for n in REG3_N:
            for seed in (1, 2, 3):
                g = gen.unit_weights(n, gen.random_regular(n, 3, random.Random(f"reg3-n{n}-s{seed}")))
                self.add(f"reg3-n{n}-s{seed}", "reg3", g, "generated (qvsc.maxcut.generators.random_regular)", LIC_GEN,
                         comments=[f"random 3-regular graph, unit weights, seed 'reg3-n{n}-s{seed}'"])
        for n in SK_N + SK_LARGE_N:
            for seed in ((1, 2, 3) if n in SK_N else (1,)):
                g = gen.pm1_weights(n, gen.complete(n), random.Random(f"sk-n{n}-s{seed}"))
                self.add(f"sk-n{n}-s{seed}", "sk", g, "generated (qvsc.maxcut.generators.pm1_weights)", LIC_GEN,
                         comments=[f"Sherrington-Kirkpatrick +-1 instance, seed 'sk-n{n}-s{seed}'"])

    # ---- planted --------------------------------------------------------------------------------
    def planted(self, topo, secret: str, private: Path):
        private.mkdir(parents=True, exist_ok=True)
        rows = []

        def seed(name):
            return int(hashlib.sha256(f"{secret}:{name}".encode()).hexdigest(), 16)

        def save(name, g, side, opt, construction, params, hardware):
            sol = private / f"{name}.sol"
            sol.write_text(f"# planted optimal cut of {name}: {opt}\n" + "\n".join(str(i + 1) for i in side) + "\n")
            digest = hashlib.sha256(sol.read_bytes()).hexdigest()
            rows.append(dict(name=name, construction=construction, params=params, optimum=opt, solution_sha256=digest))
            self.add(name, "planted", g, f"generated ({construction})", LIC_GEN,
                     tracks=tracks_for("planted", g.n, hardware), reference=opt,
                     ref_source="optimum known by construction (planted)", upper_bound=opt,
                     comments=[f"planted instance ({construction}, {params}); optimum known by construction",
                               "the seed is secret; the planted cut's SHA-256 is in planted.csv"])

        for n, a in WISHART:
            name = f"planted-wishart-n{n}-a{a}"
            g, side, opt = gen.planted_wishart_pm1(n, max(1, round(a * n)), random.Random(seed(name)))
            save(name, g, side, opt, "integer Wishart planted ensemble", f"n={n}, alpha={a}", False)
        for tname, a in LOOPS:
            if tname not in topo:
                print(f"skipping {tname} (topology not available: run with --hardware)")
                continue
            n, edges = topo[tname]
            name = f"planted-loops-{tname}-a{a}"
            g, side, opt = gen.planted_frustrated_loops(n, edges, a, random.Random(seed(name)))
            save(name, g, side, opt, "frustrated loops", f"{tname}, alpha={a}, |J|<=3", not tname.startswith("cubic"))
        with open(ROOT / "instances" / "planted.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)

    def keep_old(self, family):
        """Keep rows of a family that this run did not rebuild (e.g. planted without the secret)."""
        for name, r in self.old.items():
            if r["family"] == family and name not in self.rows and instance_path(r).exists():
                self.rows[name] = r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hardware", action="store_true", help="build Pegasus/Zephyr/IBM topologies (extra packages)")
    ap.add_argument("--planted", action="store_true", help="rebuild planted instances (needs QVSC_PLANTED_SECRET)")
    ap.add_argument("--private", type=Path, default=Path(os.environ.get("QVSC_PRIVATE", "../qvsc-private/maxcut-planted")),
                    help="where planted solutions are written (never inside the repository)")
    ap.add_argument("--cache", type=Path, default=Path(".cache/mqlib"))
    a = ap.parse_args()
    b = Builder(a.cache)
    b.literature()
    topo = b.topologies(a.hardware)
    if a.hardware:
        b.hardware(topo)
    else:
        for fam in ("pegasus", "zephyr", "heavyhex"):
            b.keep_old(fam)
    b.qaoa()
    if a.planted:
        secret = os.environ.get("QVSC_PLANTED_SECRET")
        if not secret:
            sys.exit("QVSC_PLANTED_SECRET is not set")
        if str(a.private.resolve()).startswith(str(ROOT.parents[1].resolve())):
            sys.exit("refusing to write planted solutions inside the repository")
        b.planted(topo, secret, a.private)
    else:
        b.keep_old("planted")
    save_index(b.rows)
    print(f"wrote {INDEX} ({len(b.rows)} instances)")


if __name__ == "__main__":
    main()
