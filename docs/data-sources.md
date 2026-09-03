# Data sources

Every input the pipeline uses, with what it provides, its exact version and identifier,
its license, how `scgraph` ingests it, and any provenance caveat. All sources are bulk
and free, and only one (deps.dev) is used outside the pipeline itself, as evaluation
ground truth.

---

## 1. Libraries.io Open Data (primary corpus)

**Provides.** The dependency graph: package names and platforms, versions with publish
dates, and declared dependency rows (`project, version, dependency name, requirement,
kind, optional, dependency platform`). This is where the `RESOLVES_TO` edges come from.

**Version.** Libraries.io Open Data **v1.6.0**, the final published release, snapshot date
**2020-01-12**.

- Zenodo record **3626071**, DOI **10.5281/zenodo.3626071**
- File `libraries-1.6.0-2020-01-12.tar.gz`
- Size **24,890,021,718 bytes** (about 24.89 GB), expanding to roughly 100 GB of CSV
- MD5 **`4f2275284b86827751bb31ce74238b15`**
- Contents: 34 package managers, roughly 4.2 million projects, 26 million versions, 105
  million dependency rows

**License.** Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0).

**How `scgraph` ingests it.** `acquire_full.fetch_libraries_io` downloads the pinned
tarball with a resumable transfer, verifies the size and MD5, and extracts it.
`acquire_full.build_full_tables` streams the `projects`, `versions` and `dependencies`
CSVs into the Parquet edge tables. Version-range resolution (`resolve.py`) turns each
declared requirement into a concrete version; where the CSV row already carries a
`resolved_version` it is used like a lockfile pin. Resolution is memoised by
`(package, range, ecosystem)`.

**Provenance caveat.** The snapshot is from **January 2020**. It does not contain any
package version released after that date. This has one important consequence for the
resolver comparison in [evaluation.md](evaluation.md): when deps.dev (which is live)
picks a post-2020 version, the two resolvers cannot agree because our data does not
contain that version. The honest comparison is therefore restricted to cases where
deps.dev's chosen version also exists in the snapshot, which the evaluation calls
"in-snapshot" and where agreement is 97.2 percent. The 2025 Libraries.io release has the
same schema and is larger; v1.6.0 is used because it is the fully documented, DOI-pinned,
citable baseline.

---

## 2. OSV (advisory layer)

**Provides.** The advisory layer: every advisory in the OSV schema, with
`affected[].ranges` (curated version events: `introduced`, `fixed`, `last_affected`),
`affected[].versions` (explicit version lists where the curator provided them), `aliases`
(CVE to GHSA to RUSTSEC to PYSEC), `severity` (CVSS vectors), `withdrawn`, and
references.

**Version.** OSV `all.zip`, fetched per ecosystem, **live on each run** (there is no fixed
version; the advisory feed is refreshed every time the pipeline runs). The full run's
snapshot contains **285,698 advisories**.

- URL pattern `https://osv-vulnerabilities.storage.googleapis.com/<ECOSYSTEM>/all.zip`
- Ecosystem names as OSV spells them: `npm`, `PyPI`, `Maven`, `crates.io`, `Go`,
  `RubyGems`, `Packagist`, `NuGet`

**License.** Per source, mostly open; the OSV aggregate is distributed under Creative
Commons Attribution 4.0 (CC BY 4.0). Individual records carry their upstream database's
terms.

**How `scgraph` ingests it.** `acquire.fetch_osv` downloads each ecosystem's `all.zip`
and keeps it **as a zip** (one file write, not hundreds of thousands), then
`acquire.iter_osv_records` streams records out of the zip. `parse.py` interns each
advisory by its OSV id and emits one row per unique advisory, because a single OSV record
can appear in several ecosystem zips; each `affected[]` entry is tagged with its own
`package.ecosystem`, not the zip's. `osv.materialise` then evaluates every affected range
against the version table to produce the `affected_versions` bitsets, builds the alias
union-find that maps every id to a canonical CVE, and builds the `withdrawn` mask.

**Provenance caveat.** Advisory ranges are curator artefacts. They are sometimes too
broad, occasionally wrong, and sometimes withdrawn. The graph represents them faithfully;
it does not correct them without an upstream signal. The over-claim measurement in
[methodology.md](methodology.md) quantifies the range-versus-explicit-list gap at about 1
percent where it can be checked. Advisories published after the version a project ships
are gated out at query time by the as-of-date gate, not removed from the data.

The advisory feed is also dominated in recent years by malware advisories (the `MAL-`
prefix): [`temporal.json`](../results/metrics/temporal.json) records 197,809 advisories
published in 2025 and 31,365 in 2026, most of them malware records naming removed
packages. The grounder indexes only packages with at least one real published version, so
substring matches against those removed-package names do not become false alerts (this
was a real bug, see [evaluation.md](evaluation.md)).

---

## 3. GitHub Advisory Database

**Provides.** The weakness and curation layer: GHSA records in OSV format, with
`database_specific.cwe_ids` (the CWE weakness class) and curated CVSS v3.1 and v4.0
vectors and patched versions. Used here for **CWE identifiers and CVE aliases**.

**Version.** A shallow `git clone` of `https://github.com/github/advisory-database`,
current at run time.

**License.** Creative Commons Attribution 4.0 (CC BY 4.0).

**How `scgraph` ingests it.** `acquire_full.fetch_ghsa` performs the shallow clone. The
CWE and alias mappings are folded into the advisory table during parsing. The clone is
non-fatal: if it fails, the CWE mapping degrades gracefully and the rest of the pipeline
is unaffected.

**Provenance caveat.** GHSA covers reviewed advisories only, a subset of OSV. It is used
as an enrichment layer, not as a primary source of affected ranges.

---

## 4. deps.dev API (evaluation only)

**Provides.** Google's resolved transitive dependency closure for npm, PyPI, Maven, Go and
Cargo, with the declared requirement on every edge. Used as **resolver ground truth**, and
as the source of the smoke corpus.

**Version.** The live API at `https://api.deps.dev/v3`, no key required.

**License.** Per the deps.dev terms of service (the underlying data is CC BY, from
Google).

**How `scgraph` ingests it.** For the smoke corpus, `scripts/acquire_smoke.py` walks
about 50 seed packages per ecosystem plus a set of known-vulnerable version pins, fetching
each package's default version and its resolved dependency graph. For evaluation, the
resolver-fidelity module takes each `(dependency, declared range)` pair from a spread of
well-known packages and checks whether `resolve.resolve` picks the same concrete version
deps.dev's resolver picked.

**Provenance caveat.** deps.dev is the one soft-login source in the wider design (its
BigQuery bulk export needs a Google Cloud account), so it is quarantined to evaluation and
the small smoke sample and never used in the full pipeline; the "no login" property of the
pipeline itself holds. The API is live while our corpus is a 2020 snapshot, so the
comparison is restricted to in-snapshot version picks (section 1 above). Full-run
agreement: **97.2 percent in-snapshot** over 107 comparable pairs (npm 97.6 percent, Cargo
100 percent; PyPI and Maven had too few in-snapshot pairs to score),
[`resolver_fidelity.json`](../results/metrics/resolver_fidelity.json).

---

## 5. CVSS specifications (FIRST.org)

**Provides.** The base-score formula that turns a CVSS vector string into a number.

**Version.** CVSS v3.1 Specification Document (section 7.1 for base scoring) and CVSS v4.0
Specification, both from FIRST.org.

**License.** Published by FIRST for open use.

**How `scgraph` ingests it.** `cvss.py` implements the v3.1 arithmetic directly: impact
and exploitability sub-scores, the scope-change branch, and the round-up rule. It is
arithmetic, not a model. CVSS v4.0 base scoring is a lookup table; the module approximates
it from the v3-equivalent metrics and marks that it did so.

**Provenance caveat.** OSV records carry a mix of CVSS v2, v3.0, v3.1 and v4.0 vectors.
The v4.0 approximation is explicitly flagged in the code and should be read as an estimate
rather than an authoritative v4.0 base score.

---

## 6. The eight ecosystems

The full run covers eight package ecosystems
([`run_manifest.json`](../results/run_manifest.json), field `ecosystems`):

| ecosystem | registry | range grammar (`resolve.py`) |
|---|---|---|
| npm | npmjs.com | node-semver |
| PyPI | pypi.org | PEP 440 (`packaging.specifiers`) |
| Maven | Maven Central | interval notation `[a,b)` |
| Cargo | crates.io | node-semver style |
| Go | pkg.go.dev | exact / semver `>=` |
| RubyGems | rubygems.org | node-semver style |
| Packagist | packagist.org | node-semver style |
| NuGet | nuget.org | interval / exact |

---

## 7. The parsed tables

`parse.py` and `osv.materialise` write these Parquet tables under `data/parquet/`. Row
counts are the full-run figures from
[`run_manifest.json`](../results/run_manifest.json):

| table | rows | what a row is |
|---|---|---|
| `packages` | **4,460,049** | one package: `(pkg_id, ecosystem, name)` |
| `versions` | **21,415,461** | one published version: `(ver_id, pkg_id, version, is_default, published)` |
| `resolved` | **82,807,953** | one `RESOLVES_TO` edge: `(ver_id, res_ver_id)` |
| `advisories` | **285,698** | one OSV record: `(adv_id, osv_id, canon_id, summary, severity, withdrawn, published)` |
| `affected` | one per raw OSV `affected[]` entry | `(adv_id, pkg_id, entry_json)`, the unparsed entry kept for the over-claim check |
| `affected_versions` | **1,350,518** | one materialised match: `(adv_id, ver_id)`, "this concrete version is in this advisory's affected range" |
| `aliases` | one per alias pair | `(osv_id, alias)`, feeds the union-find that maps every id to a canonical CVE |

The package-level dependency graph derived from `resolved` for the structural analyses has
**6,682,795 edges** (`run_manifest.json`, field `package_dep_edges`).

The `affected` and `aliases` tables scale with the advisory feed rather than the
dependency graph; their exact row counts are not recorded in the run manifest, but
`affected_versions` (1,350,518) is the materialised relation the pipeline actually queries.

---

## 8. What is downloaded when

| tier | sources fetched | approximate download |
|---|---|---|
| smoke | OSV `all.zip` (5 ecosystems) + deps.dev sample | tens of MB |
| full, from Release artifacts | the parsed Parquet tables + embeddings | about 550 MB |
| full, from scratch | Libraries.io v1.6.0 tarball + OSV (8 ecosystems) + GHSA clone | about 25 GB |

See [reproducing.md](reproducing.md) for the exact commands for each tier.
