"""Download the K-SAT instances from their original sources and check them against the index.

    python -m qvsc.ksat.fetch --out data/ksat              # download everything, extract the indexed files
    python -m qvsc.ksat.fetch --out data/ksat --check      # also check every indexed formula's hash
    python -m qvsc.ksat.fetch --out data/ksat --only randcspbench
    python -m qvsc.ksat.fetch --out data/ksat --for-submissions   # only the sources the submissions use (CI)
    python -m qvsc.ksat.fetch --out data/ksat --local randcspbench=kSAT.zip --local satlib=uf20-91.tar \\
        --local pelofske2023=dataset.zip                   # use archives you already have

Sources (see problems/ksat/instances/SOURCES.md):

    randcspbench   kSAT.zip from Hugging Face (CarloLucibello/CSPBenchmarks); only the indexed files
                   are extracted (the archive also holds the training sets and larger OOD sizes)
    pelofske2023   Zenodo record 8201693; the instances are written to pelofske2023/k3_n<n>.cnf from
                   dataset/problems.md
    satlib         uf20-91.tar.gz from SATLIB, extracted to satlib/uf20-91/
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from .cnf import cnf_hash, read_cnf
from .registry import SOURCES, instance_file, load_index
from .sources import parse_pelofske_problems, write_dimacs

UA = {"User-Agent": "qvsc-fetch"}


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    print(f"downloading {url} ...", flush=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r, open(tmp, "wb") as fh:
        shutil.copyfileobj(r, fh, length=1 << 20)
    tmp.rename(dest)
    return dest


def _norm(p: str) -> str:
    return p.replace("test-ood", "test_ood")


def fetch_randcspbench(out: Path, rows: list[dict], local: Path | None) -> int:
    zpath = local or out / SOURCES["randcspbench"]["archive"]
    if not zpath.exists():
        download(SOURCES["randcspbench"]["url"], zpath)
    want = {_norm(r["path"]) for r in rows}
    n = 0
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            name = info.filename
            for prefix in ("kSAT/", "./"):
                if name.startswith(prefix):
                    name = name[len(prefix):]
            if info.is_dir() or _norm(name) not in want:
                continue
            target = out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            n += 1
    return n


def _pelofske_problems_text(local: Path | None, out: Path) -> str:
    """problems.md from a local folder/zip, or from the Zenodo record (all files are tried)."""
    def from_zip(zp: Path) -> str | None:
        with zipfile.ZipFile(zp) as z:
            for nm in z.namelist():
                if nm.endswith("problems.md") and "__MACOSX" not in nm:
                    return z.read(nm).decode("utf-8")
        return None
    if local is not None:
        if local.is_dir():
            hits = [p for p in local.rglob("problems.md") if "__MACOSX" not in p.parts]
            if hits:
                return hits[0].read_text(encoding="utf-8")
        elif local.suffix == ".md":
            return local.read_text(encoding="utf-8")
        elif zipfile.is_zipfile(local):
            t = from_zip(local)
            if t:
                return t
        raise SystemExit(f"problems.md not found in {local}")
    rec = SOURCES["pelofske2023"]["zenodo_record"]
    with urllib.request.urlopen(urllib.request.Request(f"https://zenodo.org/api/records/{rec}", headers=UA)) as r:
        meta = json.load(r)
    for f in meta.get("files", []):
        key = f.get("key") or f.get("filename")
        url = f["links"].get("self") or f["links"].get("download")
        dest = download(url, out / "pelofske2023" / "zenodo" / key)
        if dest.name.endswith("problems.md"):
            return dest.read_text(encoding="utf-8")
        if zipfile.is_zipfile(dest):
            t = from_zip(dest)
            if t:
                return t
    raise SystemExit(f"problems.md not found in Zenodo record {rec}")


def fetch_pelofske(out: Path, rows: list[dict], local: Path | None) -> int:
    probs = parse_pelofske_problems(_pelofske_problems_text(local, out))
    n = 0
    for r in rows:
        d = probs.get(r["n"])
        if d is None:
            continue
        write_dimacs(d["cnf"], out / r["path"], f"Pelofske et al. 2023, Zenodo 10.5281/zenodo.8201693, (k, n) = (3, {r['n']})")
        n += 1
    return n


def fetch_satlib(out: Path, rows: list[dict], local: Path | None) -> int:
    src = local or out / SOURCES["satlib"]["archive"]
    if not src.exists():
        download(SOURCES["satlib"]["url"], src)
    want = {Path(r["path"]).name: r["path"] for r in rows}
    n = 0
    if src.is_dir():
        files = {p.name: p.read_bytes() for p in src.rglob("uf20-*.cnf")}
    else:
        files = {}
        with tarfile.open(src) as t:           # .tar or .tar.gz
            for m in t.getmembers():
                if m.isfile() and Path(m.name).name in want:
                    files[Path(m.name).name] = t.extractfile(m).read()
    for nm, data in files.items():
        if nm in want:
            target = out / want[nm]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            n += 1
    return n


def submission_instances() -> set[str]:
    """Instance names that appear in the assignments of the K-SAT submissions."""
    import gzip
    from .registry import PROBLEM_DIR
    names: set[str] = set()
    for folder in sorted((PROBLEM_DIR / "submissions").glob("*/")):
        bulk = folder / "solutions.txt.gz"
        if bulk.exists():
            with gzip.open(bulk, "rt", encoding="ascii") as fh:
                names |= {ln.split()[0] for ln in fh if ln.strip() and not ln.startswith("#")}
        names |= {p.stem for p in (folder / "solutions").glob("*.sol")}
    return names


FETCHERS = {"randcspbench": fetch_randcspbench, "pelofske2023": fetch_pelofske, "satlib": fetch_satlib}


def check_all(idx: dict, out: Path) -> list[str]:
    errors = []
    for i, (name, r) in enumerate(sorted(idx.items())):
        try:
            f = read_cnf(instance_file(out, r))
        except (FileNotFoundError, ValueError) as e:
            errors.append(str(e))
            continue
        if (f.n, f.m) != (r["n"], r["m"]):
            errors.append(f"{name}: n, m = {f.n}, {f.m}, index says {r['n']}, {r['m']}")
        elif cnf_hash(f)[:16] != r["cnf_sha256"]:
            errors.append(f"{name}: hash {cnf_hash(f)[:16]} differs from the index ({r['cnf_sha256']})")
        if (i + 1) % 10000 == 0:
            print(f"  checked {i + 1}/{len(idx)}", flush=True)
    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path, help="folder where the CNF files are written")
    ap.add_argument("--only", action="append", choices=sorted(FETCHERS), help="fetch only these sources")
    ap.add_argument("--local", action="append", default=[], metavar="SOURCE=PATH",
                    help="use a local archive or folder instead of downloading")
    ap.add_argument("--for-submissions", action="store_true",
                    help="fetch only the sources of the instances used by problems/ksat/submissions")
    ap.add_argument("--check", action="store_true", help="check the hash of every indexed formula")
    a = ap.parse_args(argv)
    local = {}
    for item in a.local:
        k, _, v = item.partition("=")
        if k not in FETCHERS or not v:
            ap.error(f"--local expects SOURCE=PATH with SOURCE in {sorted(FETCHERS)}")
        local[k] = Path(v)
    idx = load_index()
    sources = a.only or sorted(FETCHERS)
    if a.for_submissions:
        used = submission_instances()
        sources = sorted({idx[n]["source"] for n in used if n in idx} & set(sources))
        print(f"submissions use {len(used)} instances from: {', '.join(sources) or 'none'}")
    for key in sources:
        rows = [r for r in idx.values() if r["source"] == key]
        if rows:
            n = FETCHERS[key](a.out, rows, local.get(key))
            print(f"{key}: wrote {n} of {len(rows)} indexed files into {a.out}", flush=True)
    if a.check:
        sub = {n: r for n, r in idx.items() if r["source"] in sources}
        errors = check_all(sub, a.out)
        for e in errors[:50]:
            print("ERROR", e)
        if errors:
            print(f"{len(errors)} errors")
            return 1
        print(f"all {len(sub)} indexed formulas match their hashes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
