# Glossary

Terms a reader of this repository will hit, defined in two to four sentences each. Where a
term has a specific role in `scgraph`, that role is noted.

---

### Articulation point

A node in an undirected graph whose removal increases the number of connected components.
It is a true single point of failure: there is no path around it. `scgraph` finds all
articulation points with Hopcroft-Tarjan in linear time; the full run has 88,273 of them,
and the most-depended-on are packages like `lodash`, `react` and `express`. See
[methodology.md](methodology.md) section 4.

### Betweenness centrality

The fraction of all shortest paths in a graph that pass through a given node: a measure of
how much traffic would route through it. Exact computation is the Brandes algorithm at
`O(VE)` cost, infeasible at ecosystem scale, so `scgraph` samples source pivots and uses
the Riondato-Kornaropoulos bound to size the sample. It identifies different packages than
PageRank or in-degree do.

### Blast radius

For a package, the number of application packages whose transitive dependency closure
contains it: "if this package is compromised or must be yanked, how many projects are
affected". `scgraph` computes it with a bounded reverse breadth-first search over the
dependency graph. It is used as an escalation-priority signal, and it disagrees with
"highest severity" on the top package to escalate about two-thirds of the time.

### Bridge (graph)

An edge whose removal disconnects the graph: the edge analogue of an articulation point. A
bridge dependency is one the ecosystem has no redundant path around. `scgraph` reports
386,554 bridges in the full package graph, found in the same Hopcroft-Tarjan pass as the
articulation points.

### CSR (Compressed Sparse Row)

A layout for a sparse graph or matrix: edges are sorted by source node, an `indptr` array
holds the offset where each node's neighbour list begins, and an `indices` array holds the
concatenated neighbour lists. A neighbour lookup is one array slice at `O(degree)` cost
with no allocation. `scgraph` stores the whole dependency graph this way, memory-mapped,
instead of using a graph database.

### CVSS

The Common Vulnerability Scoring System: a specification that turns a vector string
describing a vulnerability (attack vector, complexity, privileges, impact on
confidentiality, integrity and availability) into a base score from 0 to 10. The base
score is a fully specified deterministic function of the vector; `scgraph` computes it
with arithmetic in `cvss.py`, no model. Versions 3.1 and 4.0 are in current use.

### CWE

The Common Weakness Enumeration: a taxonomy of software weakness classes (for example
CWE-79 cross-site scripting, CWE-89 SQL injection). Advisories carry one or more CWE
identifiers to classify the kind of flaw. `scgraph` reads CWE identifiers from the GitHub
Advisory Database.

### CycloneDX

An open standard for a software bill of materials: a machine-readable list of the
components in a piece of software, with optional vulnerability annotations. `scgraph`
emits a CycloneDX SBOM per exposure report, with each component's exposure paths attached
as annotations. Committed examples are in [`../results/sbom/`](../results/sbom).

### Densification law

The observation (Leskovec, Kleinberg, Faloutsos, 2005) that real growing networks get
denser over time: the edge count grows as a super-linear power of the node count,
`|E| proportional to |V|^a` with `a > 1`. `scgraph` fits `a` across yearly snapshots of
the dependency graph and finds `a = 1.153` (R-squared 0.9977): each cohort of new packages
depends on more existing ones than the last.

### Dependency confusion

A supply-chain attack in which an attacker publishes a public package with the same name
as a private internal one, so a misconfigured resolver installs the attacker's version.
It is a graph-reachability question over the resolution graph: which name resolves to
which published artifact. `scgraph`'s deterministic grounding and resolution are designed
so that a name maps to exactly one published identity.

### Exposure path

The core deliverable of `scgraph`: a concrete path in the resolved dependency tree from an
application to an affected version, for example `your-app -> framework -> ... ->
log4j-core@2.14.1` where the terminal is in an advisory's affected range. The path is the
proof of the alert; absence of a path is a proven property of the graph. Paths are
classified DIRECT (depth 1) or TRANSITIVE (deeper), and every hop is a resolver-produced
edge.

### GHSA

A GitHub Security Advisory identifier, for example `GHSA-jfh8-c2jp-5v3q`. GHSA records are
published in the OSV schema and often carry curated CWE identifiers and CVSS vectors.
`scgraph` treats GHSA ids as aliases and maps them to a canonical CVE via a union-find, so
a user can ask about either id.

### Gini coefficient

A measure of inequality in a distribution, from 0 (perfectly equal) to 1 (all mass on one
element). `scgraph` applies it to the reverse-PageRank vector to summarise how concentrated
systemic influence is: the full run gives 0.262 over the connected core, meaning influence
is concentrated but not extremely so.

### GraphSAGE

An inductive graph neural network (Hamilton, Ying, Leskovec, 2017) that computes a node
embedding by aggregating features from its neighbourhood over a few message-passing
layers. `scgraph` uses a 2-layer mean-aggregator GraphSAGE for a temporal, leakage-free
task (predict which packages get their first CVE next), compared against the identical
features in a non-graph model. The graph model wins, but the confidence interval on the
margin only just clears zero.

### k-core

The maximal subgraph in which every node has degree at least `k`. A node's coreness is the
largest `k` whose k-core contains it: high coreness means deeply embedded infrastructure,
coreness 0 or 1 means a leaf. `scgraph` computes coreness by Batagelj-Zaversnik bucket
peeling at `O(E)` cost, and restricts the GraphSAGE task to the 2-core of the giant
component.

### Label propagation

A near-linear community-detection method (Raghavan, Albert, Kumara, 2007): every node
repeatedly adopts the label most common among its neighbours until the labelling
stabilises. Each sweep is `O(E)` and a handful of sweeps converge. `scgraph` uses it with
a seeded permutation and a random tie-break so the result is deterministic.

### Lockfile

A file that records the exact resolved version of every direct and transitive dependency,
so an install is reproducible: `package-lock.json`, `poetry.lock`, `Cargo.lock`,
`go.sum`, `pnpm-lock.yaml`. Lockfiles exist because resolution is expensive and
non-deterministic, so it is solved once and frozen. `scgraph` uses lockfile pins directly
where the source data carries them.

### Manifest

The file where a project declares its direct dependencies as ranges rather than exact
versions: `package.json`, `pyproject.toml` or `requirements.txt`, `pom.xml`,
`Cargo.toml`, `go.mod`, `*.gemspec`. A manifest declares intent; a lockfile records the
resolution of that intent. In `scgraph` a "manifest root" is the default version of a
package that nothing else depends on, the root of a resolved tree.

### Modularity

A score (Newman, Girvan, 2004) for a partition of a graph into communities: the fraction
of edges that fall inside communities minus the fraction expected if the same-degree nodes
were wired at random. `Q > 0.3` means the partition captures real structure. `scgraph`
finds `Q = 0.518` on the dependency graph, though the communities it finds mostly
correspond to ecosystems.

### OSV

The Open Source Vulnerabilities schema and database: a machine-readable format for
advisories, with affected version ranges as event lists (`introduced`, `fixed`,
`last_affected`), explicit version lists, aliases, CVSS severity and a `withdrawn` flag.
`scgraph` uses the per-ecosystem `all.zip` exports as its advisory layer, fetched live on
each run.

### Power law

A distribution of the form `P(k) proportional to k^(-alpha)`, meaning a few values are
enormous and most are tiny, with no characteristic scale. `scgraph` fits `alpha` for the
in-degree distribution by maximum likelihood (`alpha = 1.957`) and then runs the Clauset
bootstrapped goodness-of-fit test, which **rejects** a pure power law (p = 0.0). The
distribution is heavy-tailed but not scale-free.

### Preferential attachment

The mechanism (Barabasi, Albert, 1999) by which a growing network becomes heavy-tailed: a
new node attaches to an existing node with probability proportional to that node's current
degree, so popular nodes get more popular. `scgraph` measures the attachment kernel across
snapshots and finds a slope of 0.936, consistent with roughly linear attachment rather
than winner-takes-all.

### PURL

A package URL: a compact, deterministic identifier of the form
`pkg:type/namespace/name@version`, for example
`pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1`. It is the supply-chain analogue of
a controlled-vocabulary identifier, and `scgraph`'s grounder resolves an explicit PURL
before it tries any looser match.

### Reverse PageRank

PageRank run on the graph with every edge reversed, so probability mass flows toward
widely-depended-on packages rather than away from them. The stationary distribution ranks
how load-bearing each package is: the systemic-risk lens. `scgraph` computes it by power
iteration on the reverse CSR, about 40 sparse matrix-vector products.

### SAT / constraint satisfaction

Boolean satisfiability: deciding whether a set of logical clauses can all be made true.
Version resolution encodes SAT (each package-version is a variable, each declared range is
a clause), which makes resolution NP-complete in the general case with peer dependencies
and diamond conflicts. This is why lockfiles exist and why `scgraph`'s bulk resolver
implements a well-defined common subset rather than a full solver.

### SBOM

A software bill of materials: a formal, machine-readable inventory of the components in a
piece of software and their relationships. SBOMs are increasingly mandated for classes of
software (US Executive Order 14028, the EU Cyber Resilience Act). An SBOM is a static
list; the impact analysis on top of it (what is exposed, by what path, and how to fix it)
is what `scgraph` produces.

### Semantic versioning (semver)

A version-numbering convention, `MAJOR.MINOR.PATCH`, where a major bump signals a breaking
change, a minor bump adds backward-compatible features, and a patch bump is a
backward-compatible fix. Range operators like `^1.2.0` (compatible within the same major)
and `~1.2.0` (compatible within the same minor) are defined against it. `scgraph`'s
remediation avoids crossing a major boundary because that is where builds break.

### Transitive dependency

A dependency of a dependency: a package your project pulls in indirectly, not one you
declared. Most of a resolved tree is transitive (an average npm project resolves dozens to
hundreds of transitive packages), and most unactionable audit noise is about transitive
packages. `scgraph`'s exposure paths name every transitive hop.

### VEX

A Vulnerability Exploitability eXchange statement: a machine-readable assertion that a
given product is or is not affected by a given vulnerability, with a justification (for
example "vulnerable code not in the execution path"). VEX "not affected" statements are
the ground truth `scgraph` uses to evaluate its reachability layer. It lets a vendor say
"we ship this library but the bug does not reach us" in a form a scanner can consume.

---

See [methodology.md](methodology.md) for the methods these terms name and
[architecture.md](architecture.md) for how they fit into the pipeline.
