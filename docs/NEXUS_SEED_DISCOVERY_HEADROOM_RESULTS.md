# Baseline-first discovery headroom: complete, practical screen failed

The exact source-free baseline solved **28/28** authored workflows, including
**8/8 new compositions**. All eight new compositions were initially ambiguous.
Their median measured discovery was **8.101 ms**, below the locked **10 ms**
floor. The practical discovery-headroom screen **FAILED**. No abstraction
learner, model change, new learning comparison or second run followed.

This is a **symbolic preflight**, not a new persistent-assistant result. It makes
zero neural calls; it does not establish how a language model would perform on
this workload or what fraction of assistant latency discovery would consume.
The previous v2.1 assistant study remains closed, negative and byte-unchanged.

## Provenance and scope

Base: `7c244860015c8a0e9a49203d93cb9bac7f853b75`, verified against GitHub before
branch creation. Branch: `codex/seed-discovery-headroom-audit`.
Pre-run implementation/protocol execution SHA:
`50d231555952f630d3debc1f3c4be2233d1bf054` (committed and pushed before outcomes).
[Protocol](NEXUS_SEED_DISCOVERY_HEADROOM_PROTOCOL.md),
[config](../configs/seed_discovery_headroom.json),
[raw records](../artifacts/seed_discovery_headroom_raw.jsonl),
[primary result](../artifacts/seed_discovery_headroom.json),
[independent audit and ledger](../artifacts/seed_discovery_headroom_audit.json).

Config SHA256 `c936f508593bc9666fcf6d24f54c896107d5715c39c4fa2324895ebefe3c870d`;
protocol `fefea307ac19c7055059e0511f2d01b9acf8566f304b52742694da502502fa01`;
raw `ade904f3656e57618cab566fd9a0e4d62bd2240b40d98735eadfe678aff4bb1d`.
The persistent runtime source remains SHA256
`967842923d5e43c64732094f8e829d9b6995f07e80dce60ca1ce4c76ca0b3fda`.
No model server was started, no weights loaded or replaced, and no runtime
settings changed. No main merge or live-agent promotion.

## What the baseline was allowed to do

The 192-plan canonical typed grammar composes parsing, normalization,
arithmetic, grouping, aggregation, optional threshold placement and ordering.
The five-column schemas have unfamiliar names and unknown operand/group roles,
but their broad text/numeric types are supplied. This is not open-ended schema
understanding. Candidate ambiguity comes from normally drawn teaching examples;
there was no difficulty-conditioned resampling.

Complete specifications compile directly. Otherwise the solver filters against
teaching evidence, chooses maximally discriminating registered probes, memoizes
predictions and exact AST prefixes, and retains uniquely solved public problems
in an ordinary cache. It never has to enumerate candidates on explicit requests
or blindly execute complete pipelines when cached fragments suffice. This is
ordinary exact computation, not a learned substructure advantage.

Source/new composition triples are disjoint. A descriptive post-run audit fixes
operand/group bindings and evaluates the compositions on all 128 saved source
and new-composition probe batches: all eight new composition signatures differ
from the source signatures. Thus these are more than renamed fields or exact
repeats on those witnesses. This finite check is not a global equivalence proof.

## Results, controls and costs

- Source-design tasks: 8/8 correct, eight teaching questions; median discovery
  **8.839 ms**, range 5.880–31.955 ms.
- New compositions: 8/8 correct, seven questions; median **8.101 ms**, range
  6.826–29.903 ms. All eight had multiple initial candidates. One needed no
  further question because the available probes could not distinguish its
  remaining alternatives.
- Complete-specification controls: 4/4 correct, **zero questions and zero
  candidate/fragment executions**; median compilation/lookup **0.0619 ms**.
- Renamed-schema controls: 4/4 correct, five questions; median **9.455 ms**.
- Exact repeats: 4/4 correct, one question in an unresolved repeated problem,
  **zero newly executed candidate predictions**; median **0.0641 ms**.
  Three resolved repeats were direct solution-cache hits. The unresolved repeat
  deliberately was not mislabeled a uniquely learned solution.

Across all tasks: **21 selected teaching probes**; 28 demonstration exposures
and 28 final assessment responses give **77 authored response events**. The
16 original demonstrations were computed once; controls reuse their inputs.
No simulator/environment collection occurred. Teaching-oracle execution is
included in discovery time; there is no measured human-answer latency.

There were **5,944 newly materialized plan/batch predictions**, evaluated using
**15,544 actual interpreter fragment calls** with exact prefix reuse. These are
different units; a materialized prediction is not a fresh whole-pipeline
execution. Additionally, code generates 16 demonstration references, executes
21 probe answers, performs 28 public validation executions, executes 28 selected
assessment plans and computes 28 evaluator-only assessment references.

Catalogue construction: **0.0875 ms**. All-task stage totals: discovery
**233.561 ms**, public validation **0.253 ms**, solution retention **0.00479 ms**,
selected final execution **1.458 ms**. Cache insertion/prefix lookup costs are
inside discovery; raw serialization, generator/reference work, cache-size
inspection and worker/import overhead are outside these four stage totals but
inside measured process wall/CPU. Solution retention here is an in-memory
dictionary update, not durable learned-library validation.

Serialized caches: predicted outcomes **591,931 B**; prefixes **3,333,256 B**;
16 ordinary solved-problem entries **2,458 B**. These are serialized sizes, not
Python heap measurements. No retained abstractions were trained or compared.
Their future construction/validation/retention costs are **unmeasured**, not
assumed free or inferred from this cache's costs.

## Gate, integrity and limitations

All completeness, exact accuracy, initial ambiguity, composition-count and
relative-discovery gates passed. Discovery was **99.4216%** of the four timed
pipeline stages on new compositions. The absolute-discovery gate failed. A
large fraction of a tiny total is insufficient; the threshold was not lowered.

Nine tasks retain multiple candidates after the registered probe pool. Their
assessment outputs happen to agree with the truth. Perfect observed accuracy
does not establish exact identification or behavior outside these rows.

The initial independent verifier incorrectly required every repeated problem to
be resolved with no new question. That exceeded the protocol's cache contract:
only uniquely solved problems are retained. It rejected `repeat_2`, which reused
all predicted outcomes but legitimately asked one question. The assertion was
corrected to apply to explicit specifications and actual solution-cache hits.
An ambiguous-repeat regression test was added. **The runner, config, protocol,
raw data, recorded timings and primary gate were not changed or rerun.** The
separate audit records this post-run verifier correction.

Independent saved-data arithmetic recomputes every output without the AST
executor, checks the exact cohort grid, stage values, question limits, cached
execution accounting and gate arithmetic. E1 events 96–98 reconstruct the
two-second debit from the prior anchored balance. Hashes establish consistency,
not external authentication against an owner who can edit local files.

One machine run, eight authored new-composition tasks and one supplied grammar
do not supply independent model replications or timing confidence intervals.
No claim of useful learning-to-learn, general language or assistant speedup.

## Tests and resources actually used

Pre-run: **84 targeted tests passed in 15.85 s**. Post-run: **91 passed in
15.66 s**, including saved-data corruption cases and independent output checks.
These are relevant regressions, not the full historical repository suite.

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:$NEXUS_LOCAL_DEPS python3 -m pytest -o addopts= -q \
  tests/test_seed_discovery_headroom.py tests/test_seed_assistant_benchmark_v2.py \
  tests/test_seed_experimental.py tests/test_learning_lab_sessions.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:$NEXUS_LOCAL_DEPS \
  python3 scripts/run_seed_discovery_headroom.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python3 scripts/verify_seed_discovery_headroom.py
```

The bounded run completed once: **0.365530 s wall**, **0.369488 s waited worker
CPU**, **79.4375 MiB** peak sampled summed host/worker RSS. Sampling every 100 ms
can miss short peaks; shared pages can double-count. Cap: 60 s wall/CPU and
1024 MiB sampled RSS. Conservative debit **2 s**. Carried ledger now
**2188.632103455996 s used / 1411.367896544004 s remaining**. The older v1
missing-debit evidence gap remains; this run does not repair it by invention.

## One next recommendation

Perform a source-only identifiability audit of the nine unresolved candidate
sets: distinguish actual semantic equivalences from distinct transformations
that the available probe pool fails to separate. Do not enlarge the model or
force additional search. Retained-abstraction learning remains gated off; the
unchanged persistent direct/tool baseline is also still unmeasured here.
