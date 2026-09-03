# Evaluation

How each headline number is checked, and where it is weak. The first half describes the
five evaluation modules; the second half is a candid account of the metrics that are
partly tautological, the assumptions the pipeline makes, and the bugs that produced
reassuring wrong answers during development.

The evaluation modules write to [`../results/metrics/`](../results/metrics) and are driven
by `scripts/run_evaluation.py`. The numbers below are from the committed metric JSON
files.

## The measurement discipline

Two claims are measured separately and never blended into one end-to-end score:

- The **safety** claim is about provenance: every alert carries a resolvable path, and
  every "not affected" is a proven graph absence or an explicit "unverified, review". It
  is checked by the counterfactual ablation (does the alert rate track the evidence) and
  by the path-materialisation audit (does every alert in fact carry a path).
- The **quality** claim is about whether routing triage through the graph helps: does it
  reduce review burden or catch exposures a flat scanner misses, at acceptable coverage.
  It is checked head-to-head against `osv-scanner` and by the feature ablation.

Each layer also has its own ground truth (grounding against a curated name-to-PURL map,
resolution against deps.dev and real lockfiles, advisory matching against `osv-scanner`,
reachability against VEX statements), because an end-to-end score hides a layer that is
wrong in a way that happens to improve the number. The "bugs that produced reassuring
wrong answers" section at the end is the evidence that this is not a hypothetical concern.

---

## 1. Query latency and throughput

**File:** [`timing.json`](../results/metrics/timing.json).

**What it measures.** The cost of the "CSR memmap, not a graph database" decision, as four
things: the one-time build from Parquet, the per-process load, query latency, and the
graph-science algorithm runtimes.

**Method.** `osv.materialise` and `kgstore.build` are timed on the full corpus.
`KGStore.__init__` is timed and peak resident set is sampled. `exposure_paths` and
`audit_manifest` (the whole ground-then-paths-then-ladder operation) are timed over a
random sample of real manifest roots and reported as p50, p90 and p99. Throughput is
audits per second in a single process with no inter-process communication. The graph
algorithms are timed on the 4.46-million-package, 6.68-million-edge package graph, and
`scaling.json` repeats a subset on edge-sampled subgraphs from 2 percent to 100 percent.

**Result.** Build 27.9 s plus 140.3 s (about 2.3 minutes for the CSR store). Load 13.19 s,
16,047 MB peak. Full-audit latency **p50 0.02 ms, p90 0.97 ms, p99 6.82 ms**. Throughput
**2,546 audits per second**. Reverse PageRank 4.3 s, articulation points and bridges
7.5 s, k-core 3.8 s, label propagation 216 s, sampled betweenness 166 s (over its 150 s
budget, fell back). Scaling is near-linear for k-core, PageRank, articulation points and
connected components.

**Where it is weak.** Betweenness does not fit its budget. The latency figures are for a
warm page cache; a cold start pays the 13-second load first.

---

## 2. Power-law goodness-of-fit

**File:** [`powerlaw_gof.json`](../results/metrics/powerlaw_gof.json).

**What it measures.** Whether the degree distribution is actually a power law, not just
heavy-tailed.

**Method.** The Clauset-Shalizi-Newman bootstrapped goodness-of-fit test: fit the exponent
by maximum likelihood, then draw 300 synthetic datasets of the same size from the fitted
power law, fit each, and compute the fraction whose own Kolmogorov-Smirnov distance is at
least the observed distance. That fraction is the p-value. The discrete power-law CDF uses
the Hurwitz zeta function. The KS statistic was itself validated against known
true-power-law, lognormal and Poisson inputs after an earlier version reported a wrong KS
of 0.376.

**Result.** In-degree `alpha = 1.957`, corrected KS 0.0479, **p = 0.0**. Out-degree
`alpha = 1.918`, KS 0.0874, **p = 0.0**. The power law is rejected for both.

**Where it is weak.** At a tail size of roughly 285,000 the strict test rejects almost any
real distribution, so "rejected" here means "not a clean power law", not "not
heavy-tailed". The distribution is heavy-tailed; the exact tail family (power law with
cutoff versus lognormal) is neither resolvable at this scale nor load-bearing for the
downstream analysis.

---

## 3. Resolver fidelity against deps.dev

**File:** [`resolver_fidelity.json`](../results/metrics/resolver_fidelity.json).

**What it measures.** Whether `resolve.resolve` picks the same concrete version that
Google's deps.dev resolver picks, for a spread of well-known packages.

**Method.** For each `(dependency, declared range)` pair, compare the version `scgraph`
resolves against the version deps.dev resolved. Because our corpus is a January 2020
snapshot and deps.dev is live, the honest number is restricted to pairs where deps.dev's
pick also exists in our snapshot (so both resolvers could have chosen it), which isolates
resolver logic from data vintage.

**Result.** Raw exact-match 9.3 percent over 1,121 edges. **In-snapshot agreement 97.2
percent** over 107 comparable pairs: npm 97.6 percent (42 pairs), Cargo 100 percent (63
pairs). PyPI and Maven had too few in-snapshot pairs to score.

**Where it is weak.** The in-snapshot sample is small (107 pairs), and it is dominated by
npm and Cargo. PyPI and Maven resolver logic is essentially unvalidated by this module.
The raw 9.3 percent is a data-coverage artefact, not a resolver defect, but it does mean
the full graph's `RESOLVES_TO` edges for post-2020-heavy ecosystems are less trustworthy
than the in-snapshot number suggests.

---

## 4. Feature ablation across three decision surfaces

**File:** [`ablation.json`](../results/metrics/ablation.json).

**What it measures.** Whether the advanced graph signals (articulation points,
betweenness, community structure, blast radius) change what a triage engineer actually
does, or are decoration.

**Method.** Three concrete decision surfaces, each computed with and without the
structural signals:

1. **Alert ordering.** Baseline priority is severity then depth; advanced adds a
   structural-criticality boost. Measured by Kendall's tau and top-k overlap between the
   two orderings over 56,496 exposures.
2. **Escalation target.** When a manifest has an unfixable package, baseline escalates the
   highest-severity one, advanced escalates the highest-blast-radius one. Measured as how
   often they disagree on the number-one package, over 1,885 manifests.
3. **High-risk classifier.** A logistic model flags high-advisory-load manifests, with and
   without the structural features. Measured by AUROC delta and flagged-set overlap, over
   2,123 manifests.

**Result.**

- Alert ordering: Kendall's tau 0.86; top-20 overlap 0.50, so **10 of the top 20 reorder**
  under the structural boost.
- Escalation target: severity and blast radius disagree on the number-one package in
  **67.5 percent** of manifests (613 agree, 1,272 disagree).
- Classifier: AUROC **0.9954 with or without** the structural features (delta 0.0001),
  though the advanced model flags a different set (top-200 overlap 0.535, 93 manifests
  flagged only by the advanced model).

**Verdict:** the advanced graph signals **do** change decisions, but selectively. They
change **which package you fix first**; they do not make a binary risk classifier more
accurate, because severity and tree shape already carry that signal.

**Where it is weak.** This is a consistency analysis, not a ground-truth evaluation: there
is no labelled "correct escalation target" to check against, only a measurement that two
reasonable heuristics disagree. The classifier AUROC of 0.9954 is suspiciously high and
probably reflects an easy target (high advisory load is close to a function of tree size).

---

## 5. Comparison against osv-scanner

**File:** [`vs_osvscanner_big.json`](../results/metrics/vs_osvscanner_big.json).

**What it measures.** How `scgraph`'s post-ladder alert set compares to `osv-scanner`,
Google's reference OSV client and the tool teams actually run.

**Method.** Take 150 manifest roots, serialise each resolved tree as a lockfile
(`requirements.txt` or `package-lock.json`), run `osv-scanner --format json` on each, and
compare its vulnerability set to `scgraph`'s alerting set. Report the confusion (both,
only-us, only-scanner), not a winner.

**Result.** **96.9 percent agreement**: 1,748 findings in common, 45 only from `scgraph`
(deeper transitive resolution, alias mapping `osv-scanner` did not perform), 10 only from
`osv-scanner` (advisories `scgraph` gates out as withdrawn or resolved out of range).

**Where it is weak.** The lockfiles are generated from the graph, so both tools see the
same tree by construction; this measures advisory-matching agreement, not resolution
agreement. It is not a recall benchmark: `scgraph` is a governance layer that gates on
provenance, and "only-scanner" findings are mostly gates working as intended, not misses.

---

## Known limitations and caveats

### The three partly-tautological or lexical metrics

**1. "100 percent path retention" is a tautology.** The decision block in
[`run_manifest.json`](../results/run_manifest.json) reads `retention_pct: 100.0`. That
check asks "do the endpoints of a `RESOLVES_TO` edge exist as version nodes", and they
always do, because an edge is only emitted when both endpoints were interned. The number
that actually measures resolution coverage is **parse retention: 96.64 percent** of
declared dependencies found a satisfying published version (2.88 million of 85.8 million
are dangling). Resolver *logic* is a separate question, answered by the deps.dev
comparison (section 3): 97.2 percent in-snapshot.

**2. Ablation monotonicity is a consistency check, not a causal proof.** The ablation
tiers are nested drop-sets (T3 is a superset of T2 is a superset of T1), so a system that
only ever counts current alerts will produce a monotone curve by construction. The test
catches a system that alerts on nothing (flat at zero) or one that is non-monotone (a
bug, and one was caught and fixed this way), but a monotone curve down to zero is
evidence of consistency, not proof that alerts are caused by the specific graph elements
removed. The claim it supports is "anything untraceable is not alerted", and that claim is
real; "the ablation proves causality" would be an overstatement.

**3. The semantic-relevance AUROC is partly lexical overlap.** The 0.955 figure is the
AUROC of separating a real (advisory, affected-package) pair from a control pair with a
different same-ecosystem package. Advisory summaries routinely name the package
("Prototype Pollution in lodash", "RCE in Apache Commons Text"), so a substantial part of
the separation is string matching, not semantic understanding of the vulnerability. The
number is a fair measure of "can the embedding pick the named package over an impostor";
it is not evidence that the model understands whether your code path triggers the bug.

### Other caveats

**The model layer needs a GPU.** `embed`, `gnn` and `judge` require CUDA. On a CPU box
they raise a clear error, and the notebook loads cached results from the GPU run instead.
The CPU spine (data, graph store, structure, grounding, traversal, remediation, reporting)
runs anywhere.

**The corpus is a 2020 snapshot.** Libraries.io Open Data v1.6.0 is dated 2020-01-12 and
contains no package version released after that date. The OSV advisory feed is live, so
the pipeline can flag a 2024 CVE against a 2019 version, but it cannot resolve a project
to a version that shipped in 2021. This is a reproducibility feature (a DOI-pinned,
citable corpus) and an evaluation constraint (the resolver comparison must be restricted
to in-snapshot picks). The method is what is being demonstrated; a fresher corpus would
change the numbers, not the design.

**"Zero false negatives" is not claimed and is not falsifiable.** The safety claim is
about *provenance*: every alert carries a resolvable path, and every "not affected" is a
proven graph absence or an explicit "unverified, review". It is not a claim that the
pipeline finds every real exposure. Establishing a false-negative rate would require a
complete ground-truth set of real exposures, which does not exist. The pipeline can miss
an exposure through a package it failed to ground, a transitive edge the resolver dropped,
or an advisory range that is too narrow.

**Grounding is the likely ceiling.** Lay names, transferred or renamed packages, monorepo
sub-packages and vendored copies with no registry identity are the residual the grounder
cannot resolve. Coverage is measured; the residual is the honest ceiling on what the
pipeline can see.

**Reachability is undecidable in general.** For dynamic languages (reflection, dependency
injection, native addons) the honest output is a three-way `reachable / unreachable /
undetermined`, and `undetermined` dominates (79 percent in the full run). A path proves
presence in an affected range, not that your usage triggers the bug.

### Bugs that produced reassuring wrong answers

Collected because they share a signature: each made the system look better or safer than
it was, and none raised an error. Found during development and fixed:

1. **Advisory rows not indexed by advisory id** when an OSV record appeared in several
   ecosystem zips, so the alias reverse-index silently pointed at the wrong package.
2. **Alias-to-CVE canonicalisation missed the CVE** because the CVE is an alias, not an
   advisory row, so `CVE-2021-44228` grounded to nothing while `GHSA-jfh8-c2jp-5v3q`
   worked.
3. **The grounder matched malware packages:** the 200,000-plus `MAL-` advisories name
   removed packages, and a name-substring match against those is pure noise. Fixed by
   indexing only packages with at least one real published version.
4. **Remediation picked prerelease versions as the fix:** `_clean_versions` accepted any
   advisory-free version, so the greedy fixer recommended `jetty 10.0.0-alpha0` and
   similar, inflating both the "needs a major bump" and "advisories introduced" counts.
   Fixed with a prerelease filter.
5. **"Power law" reported from a KS distance alone:** an earlier KS of 0.376 was
   hand-waved as heavy-tailed; the Clauset bootstrapped test formally rejects the power
   law (p = 0.0).
6. **Betweenness ran unbounded:** the naive k-core cap did not hold on a dense real
   cluster and ran for over 25 minutes. Fixed with a hard degree-truncation and a
   wall-clock timeout with a fallback.

Every one of these mis-resolved silently and improved or preserved a metric while the
system was subtly wrong. This is the argument for per-layer ground truth: an end-to-end
score would have hidden all six.

### Changes that were rejected

The multi-agent coordination layer was built in full and then measured against the
one-pass pipeline over every exposed manifest (see [results.md](results.md) section 11).
It reduced alerts from 12,717 to 12,316 and cleared fewer advisories (273 to 178): a
coverage-for-precision trade with no clear win. It is kept in the repository as a measured
negative result and an ablation, not presented as the architecture. The companion
biomedical knowledge-graph project this pipeline shares its measurement discipline with
reached the same conclusion: an agentic refine loop, measured three ways, lost to the
one-pass pipeline.

The structural reachability prior was likewise expected to suppress a meaningful fraction
of alerts and did not: 9,853 to 9,789 (see [results.md](results.md) section 7). It is
reported at its true effect size rather than tuned until it looked useful.

## What moved the needle

The gains are in **grounding** (a deterministic name-to-PURL resolver that indexes only
real packages) and in the **provenance gates** (withdrawn, as-of-date, non-installable),
not in the model layer and not in the agent loop, even though a typical architecture
diagram would put the loop at the centre. The graph itself, built with zero model calls,
is what turns an unactionable audit list into a short list of paths plus an explicit
refusal for everything else.

For the findings these caveats apply to, see [results.md](results.md).
