"""CSR memmap graph store — the notebook §5/§6 argument, transplanted.

Neo4j has no bulk edge loader; billions of `CREATE` at 1-5 ms each is days before a
query runs, and a server cannot answer a k-hop expansion in the microseconds an agent
loop needs. Compressed Sparse Row: edges sorted by source give
`indptr[i]..indptr[i+1]` -> a slice of `indices` = i's neighbours. O(degree), no
allocation, no IPC. Both directions are stored so "what breaks if I bump X" is also
one slice.

Arrays (all int32, saved as .npy, opened mmap_mode='r'):
  res_indptr, res_indices        Version --RESOLVES_TO--> Version   (forward)
  rdep_indptr, rdep_indices      Version <--RESOLVES_TO-- Version   (reverse / dependents)
  aff_adv_indptr, aff_adv_ids    Version --is affected by--> Advisory
  ver_pkg                        ver_id -> pkg_id
  pkg_eco (object), pkg_name (object)
  adv_sev (float32), adv_withdrawn (bool), adv_published (object), adv_canon (object)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq


def _csr(src, dst, n):
    """Build (indptr, indices) for edges src->dst over n source nodes, sorted."""
    src = np.asarray(src, np.int64)
    dst = np.asarray(dst, np.int64)
    order = np.argsort(src, kind="stable")
    src, dst = src[order], dst[order]
    indptr = np.zeros(n + 1, np.int64)
    np.add.at(indptr, src + 1, 1)
    np.cumsum(indptr, out=indptr)
    return indptr.astype(np.int64), dst.astype(np.int32)


def build(pq_dir: str, graph_dir: str) -> dict:
    PQ, G = Path(pq_dir), Path(graph_dir)
    G.mkdir(parents=True, exist_ok=True)

    pkgs = pq.read_table(PQ / "packages.parquet").to_pydict()
    vers = pq.read_table(PQ / "versions.parquet").to_pydict()
    res = pq.read_table(PQ / "resolved.parquet").to_pydict()
    advs = pq.read_table(PQ / "advisories.parquet").to_pydict()
    affv = pq.read_table(PQ / "affected_versions.parquet").to_pydict()
    meta = json.loads((PQ / "_osv_meta.json").read_text())

    N = len(vers["ver_id"])
    A = len(advs["adv_id"])

    ri, rx = _csr(res["ver_id"], res["res_ver_id"], N)
    di, dx = _csr(res["res_ver_id"], res["ver_id"], N)  # reverse
    ai, ax = _csr(affv["ver_id"], affv["adv_id"], N)

    np.save(G / "res_indptr.npy", ri)
    np.save(G / "res_indices.npy", rx)
    np.save(G / "rdep_indptr.npy", di)
    np.save(G / "rdep_indices.npy", dx)
    np.save(G / "aff_adv_indptr.npy", ai)
    np.save(G / "aff_adv_ids.npy", ax)
    ver_pkg = np.asarray(vers["pkg_id"], np.int32)
    np.save(G / "ver_pkg.npy", ver_pkg)

    # ---- package-level resolved graph: pkg A -> pkg B if any A-version resolves to
    #      any B-version. This is the graph for centrality / k-core / systemic risk.
    P = len(pkgs["pkg_id"])
    pe = ver_pkg[np.asarray(res["ver_id"], np.int64)]
    pd = ver_pkg[np.asarray(res["res_ver_id"], np.int64)]
    m = pe != pd
    pairs = np.unique(np.stack([pe[m], pd[m]], 1), axis=0)
    pi, px = _csr(pairs[:, 0], pairs[:, 1], P)
    ppi, ppx = _csr(pairs[:, 1], pairs[:, 0], P)  # reverse (dependents)
    np.save(G / "pkgdep_indptr.npy", pi)
    np.save(G / "pkgdep_indices.npy", px)
    np.save(G / "pkgrev_indptr.npy", ppi)
    np.save(G / "pkgrev_indices.npy", ppx)
    np.save(G / "ver_str.npy", np.array(vers["version"], dtype=object), allow_pickle=True)
    np.save(G / "ver_default.npy", np.asarray(vers["is_default"], bool))
    if "published" in vers:  # FULL loader carries version dates
        np.save(
            G / "ver_published.npy", np.array(vers["published"], dtype=object), allow_pickle=True
        )
    np.save(G / "pkg_eco.npy", np.array(pkgs["ecosystem"], dtype=object), allow_pickle=True)
    np.save(G / "pkg_name.npy", np.array(pkgs["name"], dtype=object), allow_pickle=True)

    canon = meta["canon"]
    wd = set(meta["withdrawn"])
    al = pq.read_table(PQ / "aliases.parquet").to_pydict()
    alias_map: dict[str, list[str]] = {}
    for oid, a in zip(al["osv_id"], al["alias"]):
        alias_map.setdefault(oid, []).append(a)
    np.save(G / "adv_id_str.npy", np.array(advs["osv_id"], dtype=object), allow_pickle=True)
    np.save(
        G / "adv_canon.npy",
        np.array([canon.get(o, o) for o in advs["osv_id"]], dtype=object),
        allow_pickle=True,
    )
    (G / "adv_aliases.json").write_text(
        json.dumps({o: alias_map.get(o, []) for o in advs["osv_id"] if alias_map.get(o)})
    )
    np.save(G / "adv_sev.npy", np.asarray(advs["severity"], np.float32))
    np.save(G / "adv_withdrawn.npy", np.asarray([o in wd for o in advs["osv_id"]], bool))
    np.save(G / "adv_published.npy", np.array(advs["published"], dtype=object), allow_pickle=True)
    np.save(G / "adv_summary.npy", np.array(advs["summary"], dtype=object), allow_pickle=True)

    stats = {"versions": N, "advisories": A, "resolves_edges": len(rx), "affected_edges": len(ax)}
    (G / "_csr_stats.json").write_text(json.dumps(stats, indent=2))
    return stats


class KGStore:
    def __init__(self, graph_dir: str):
        t0 = time.time()
        G = Path(graph_dir)
        L = lambda n: np.load(G / f"{n}.npy", mmap_mode="r")  # noqa: E731
        LO = lambda n: np.load(G / f"{n}.npy", allow_pickle=True)  # noqa: E731
        self.res_indptr, self.res_indices = L("res_indptr"), L("res_indices")
        self.rdep_indptr, self.rdep_indices = L("rdep_indptr"), L("rdep_indices")
        self.aff_indptr, self.aff_ids = L("aff_adv_indptr"), L("aff_adv_ids")
        self.pkgdep_indptr, self.pkgdep_indices = L("pkgdep_indptr"), L("pkgdep_indices")
        self.pkgrev_indptr, self.pkgrev_indices = L("pkgrev_indptr"), L("pkgrev_indices")
        self.ver_pkg = L("ver_pkg")
        self.ver_str = LO("ver_str")
        self.ver_default = L("ver_default")
        try:
            self.ver_published = LO("ver_published")
        except Exception:
            self.ver_published = None
        self.pkg_eco = LO("pkg_eco")
        self.pkg_name = LO("pkg_name")
        self.adv_id = LO("adv_id_str")
        self.adv_canon = LO("adv_canon")
        try:
            self.adv_aliases = json.loads((G / "adv_aliases.json").read_text())
        except Exception:
            self.adv_aliases = {}
        self.adv_sev = L("adv_sev")
        self.adv_withdrawn = L("adv_withdrawn")
        self.adv_published = LO("adv_published")
        self.adv_summary = LO("adv_summary")
        self.N, self.A = len(self.ver_pkg), len(self.adv_id)
        self.canon_to_idx: dict[str, int] = {}
        for i, c in enumerate(np.asarray(self.adv_canon)):
            self.canon_to_idx.setdefault(str(c), i)
        # name index: (ecosystem, name) -> pkg_id ; pkg_id -> ver_ids
        self.pkg_index = {(e, n): i for i, (e, n) in enumerate(zip(self.pkg_eco, self.pkg_name))}
        self.pkg_vers: dict[int, list[int]] = {}
        for vid, pid in enumerate(np.asarray(self.ver_pkg)):
            self.pkg_vers.setdefault(int(pid), []).append(vid)
        self.load_secs = time.time() - t0

    # --- traversal ---
    def resolves_to(self, vid):
        return self.res_indices[self.res_indptr[vid] : self.res_indptr[vid + 1]]

    def dependents(self, vid):
        return self.rdep_indices[self.rdep_indptr[vid] : self.rdep_indptr[vid + 1]]

    def advisories_of(self, vid):
        return self.aff_ids[self.aff_indptr[vid] : self.aff_indptr[vid + 1]]

    def pkg_deps(self, pid):
        return self.pkgdep_indices[self.pkgdep_indptr[pid] : self.pkgdep_indptr[pid + 1]]

    def pkg_dependents(self, pid):
        return self.pkgrev_indices[self.pkgrev_indptr[pid] : self.pkgrev_indptr[pid + 1]]

    # --- lookup ---
    def pkg_id(self, ecosystem, name):
        return self.pkg_index.get((ecosystem, name), -1)

    def versions_of(self, pid):
        return self.pkg_vers.get(int(pid), [])

    def default_version(self, pid):
        for vid in self.versions_of(pid):
            if self.ver_default[vid]:
                return vid
        vs = self.versions_of(pid)
        return vs[-1] if vs else -1


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    print(json.dumps(build(str(base / "data" / "parquet"), str(base / "data" / "graph")), indent=2))
    S = KGStore(str(base / "data" / "graph"))
    print(f"load {S.load_secs * 1000:.1f} ms  versions={S.N:,}  advisories={S.A:,}")
