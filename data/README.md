# data/

This directory is not version-controlled (only this file and `.gitkeep` are). The data
tiers are acquired or rebuilt by the scripts.

## Tiers

| tier | what | how to get it | size |
|---|---|---|---|
| smoke corpus | real OSV feed plus a curated deps.dev sample, five ecosystems | `python scripts/acquire_smoke.py` | about 5 MB, 3 min |
| full parquet | the parsed Libraries.io plus OSV corpus, eight ecosystems | `python scripts/fetch_artifacts.py --set full` | about 550 MB |
| full raw | the 24.89 GB Libraries.io Zenodo dump plus OSV feeds | `python scripts/acquire_full.py` (needs about 130 GB of disk) | about 25 GB in, 100 GB out |
| CSR graph store | the memory-mapped graph built from parquet | `python scripts/build_graph.py` | about 2 GB, 2.3 min |
| embeddings | BGE-small vectors for advisory-touched packages | `python scripts/fetch_artifacts.py --set full`, or rebuild on a GPU | about 120 MB |

## Layout once populated

```
data/
  raw/
    osv/            OSV all.zip per ecosystem
    depsdev/        resolved dependency-graph samples (smoke)
    ghsa/           GitHub Advisory Database clone (full)
    librariesio/    the Zenodo dump and its extracted CSVs (full)
  parquet/          columnar edge tables: packages, versions, resolved, advisories,
                    affected, affected_versions, aliases
  graph/            the CSR memmap store (res_*, rdep_*, pkgdep_*, aff_*, ver_*, adv_*)
  emb/              pkg_emb.npy + pkg_ids.npy
  out/              output of a fresh notebook or evaluation run (not the committed
                    reference; that is in results/)
```

## Provenance

Source versions, DOIs, and licenses are in [`docs/data-sources.md`](../docs/data-sources.md).
The parsed parquet is a deterministic function of the raw inputs; the CSR store is a
deterministic function of the parquet.
