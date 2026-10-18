# E2.24 — Evidence-weighted strategy arbitration

## Pre-development protocol

Base `3bf0a97f15f98af5e28dcf619fe8c1332eea2818`, verified after
fetching GitHub and Origin. Branch
`codex/evolution2.24-evidence-weighted-arbitration`. Two pre-existing
untracked Evolution-1 adapter files remain outside this work.

This is a recorded-source, FakeStepModel development audit, **not**
real control, scientific confirmation, learning-to-learn or AGI.
No simulator collection, neural training, checkpoint replacement,
H17 work, allocation, or E2.17 authorization reuse. Scientific ledger
remains 327.869 seconds used / 3272.131 remaining. Proxy imagined
transitions are counted separately. Source-only wall cap: 60 seconds.

Reuse `ObservationAwareAdaptive` and its memory entries,
`AdaptiveProposer`, `TrustedEvaluator`, `raw_catalogue_scores` and
`make_e222_tasks`. `ContextualStrategyMemory` remains canonical and
is not replaced. Historical modes retain their choices; only richer
optional diagnostic traces are added. No parallel framework.

### Competing explanations

Hard confidence can erase useful persistent scores; negligible
kernels can expose ties and rounding artifacts; sparse coverage can
make a missing arm's 0.5 prior attractive; observation similarity
need not predict planner quality. Arm rows are not independent tasks.
Agreement between neighbors alone need not establish applicability.
The benchmark will trace these together rather than assuming one cause.

### Frozen arbitration rule

Group historical rows by family, support digest and planning embedding.
One context contributes one weight regardless of arms or repeats.
Exclude active task provenance and unknown support identity. Distinct
support contexts are **not** independent physics replications.

For each available arm compare it with the current persistent
proposer's chosen arm using only contexts that observed both arms
and both anchor planners. No missing-arm pseudo-score. Gaussian
weights use E2.23's source LOBO median length; the distance gate is
diagnostic and cannot grant confidence. Record coverage.

Use weighted paired advantage, effective mass, ESS, positive-delta
agreement, weighted spread, and absolute prediction error on the two
current anchor receipts. Subtract source empirical paired-error
allowance, anchor error and spread/sqrt(ESS) from advantage. Override
only with at least two distinct contexts, mass >=1, ESS >=1.5,
positive agreement >=0.75, both current anchors, and positive remaining
advantage (>1e-12). Choose the largest remaining advantage, then the
existing tie order. Otherwise preserve the proposer. These sufficiency
constants are fixed design requirements, not fitted development knobs.
Reported evidence weight is mass/(1+mass) × ESS/(1+ESS) × agreement ×
coverage; it is **not a probability**, and does not reach 1 at finite
mass. It does not replace the explicit acceptance tests.

Source empirical allowance: E2.8 **train only**, bundles0/1, both
families; offsets0/32/64/96, support32. Reuse six-proposal source
receipts per context. Holding out each entire bundle, predict covered
arm-pair differences from the other bundle. Use maximum absolute
paired prediction error as the allowance (1 if unavailable). Full
source catalogue scores provide calibration truth only. Record all
residuals. This small, inspected source calibration is not a
distribution-free bound, independent task validation or proof that
anchors identify unseen task quality. It is computed before constructing
any E2.22 development task. No development outcome chooses a rule,
threshold, coefficient, or configuration.

Neighbor-consensus baseline uses paired task contexts and >=0.75
positive agreement with >=2 contexts, but omits mass, anchor-match
and calibration vetoes. This isolates consistency from applicability.

### Matched benchmark and decision criteria

Seed7, exact E2.22 task order, six proposals/two anchors/four free,
same catalogue, tied RNG order and identical score tables. Compare
persistent, E2.23 cross-bundle, ungated, consensus, evidence arbitration
and reset. Legitimate receipts update each method sequentially,
including development as historically; no hidden/future score reaches
the proposer. Full tables and unit scaling are evaluator-side proxy
oracles inherited from E2.23, not realistic hidden-control evaluation.

Familiar, zero-observation, far and collision scenarios are **already
observed development**. No p-values or generalization claim. Report
first-free regret, **actual sum over all four free slots** (E2.23's
`dev_free_regret_sum` summed first-free only), best-six, regret
differences from persist/ungated, accept/abstain, actual overrides,
posthoc correct/harmful/neutral overrides versus the same-path
proposer, anchors, coverage, effective mass, ESS, context counts,
runtime and serialized store bytes. Posthoc outcome annotations are
written after choice; never feed them back through arbitration.

Desirable outcomes are preserving familiar first-free, improving
shifted first-free versus persist, rejecting misleading retrieval
better than ungated, and genuine useful planner changes. If any
fails, label partial/negative. Abstention that ties persist is not
an adaptive improvement. Complete-grid validation precedes completion.
Historical JSON bytes are hashed and checked unchanged. No extra
planner evaluations for anchors. Count full-grid audit/calibration
scoring separately from cached six-receipt method opportunities.

### Tests and execution

Synthetic tests cover useful overrides, task disagreement, missing
arms, alias/repeat inflation, missing anchors, misleading nearest
neighbors, shuffled coordinates, negligible mass under an open gate,
policy immutability, typed receipts and replay rejection. Existing
benchmark-writer tests must be redirected to temporary paths when
run so historical result files remain byte-identical.

Commit this protocol and implementation before scoring development.
Command:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_evolution2_24_evidence_arbitration.py`.
Result: `artifacts/evolution2_24_evidence_arbitration.json`, raw traces
included. Record execution SHA, source file hashes, source calibration
hash, wall/CPU, actual fake-step calls/states, cached receipts and
memory footprint. Previous results remain unchanged.

## Results

Pending the committed implementation and source-only benchmark.
