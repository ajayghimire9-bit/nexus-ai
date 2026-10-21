# Query-context sufficiency — locked source-only audit

Base 94bdad2a7c5c080e6bf105089243e225f3876579; fetched GitHub matches.
Branch `codex/seed-query-context-sufficiency`. Main/unrelated files unchanged.

## Question and competing explanations

The previous ten-feature selector failed both registered screens. It omits query
inputs. Does that omission prevent a query-blind selector from always choosing
the expected-best question, even when the fixed learner and supplied prior are
correct? Alternatives: no material query dependence here; training/utility noise;
source-prefix versus selected-prefix shift; the prior may not reflect actual
tasks. This audit tests only the first representation limitation, not all causes.

## Frozen inputs and predeclared grid

Reuse `source_acquisition.features/expected_gain/update/split_inputs/catalogue`,
the same supplied 910-program interpreter and uniform posterior learner. No
new neural network, learner, fitting, teaching or simulator. Config is validated
against executable settings. Parent artifact SHA256:
`afff98802bbadd0cc79ea2f5fd786c37c9a3670347e4ba01290f461b71e6f370`.
Only its 128 SOURCE histories and eight frozen source selector coefficients/RMS
are projected. Closed target rows and query outcomes are not used. Reconstruct
the original random teaching prefix at lengths 0, 1, 2, 4. Thus 512 contexts;
8 public singleton query sets per context (the original held-out input indices).
Candidate pool, prefix, posterior, features and model are identical across the
eight query contexts. Source answers are used ONLY for the observed prefix;
source query labels and hypothetical real task identity do not score utility.

## Endpoint, practical criterion and arithmetic

For each candidate x and singleton query q, uniform-posterior expected MSE
reduction is Cov(Yx,Yq)^2 / Var(Yx), zero when Var=0. Verify it independently
against the existing branch-enumeration expected_gain and direct squared-error
summation. Do not describe expected gains as actual observed task improvements.

Record the full candidate-by-query gain matrix, ten-feature rows, locked learned,
variance and original-order choices. With tolerance 1e-10, intersect each query's
optimal-candidate set. An empty intersection means no query-blind choice is
optimal for all eight query contexts. The mean-query lower bound on regret for
ANY query-blind deterministic or randomized choice is:

`mean_q(max_x gain[x,q]) - max_x(mean_q(gain[x,q]))`.

Predeclared diagnostic verdict `query_information_missing` requires at least
one empty intersection and at least one context with this gap >= 1e-4. Otherwise
`not_demonstrated`. This is an information counterexample criterion, not a
success/promotion claim or an estimated frequency in unknown environments.
Report all contexts, prefix/block sensitivity and average expected regrets for
learned, variance, original-order, best query-blind upper reference and full
query-aware scoring. Average tasks/prefixes equally inside each source selector,
then all eight selectors equally. No confidence intervals: deterministic reused
source audit, not fresh independent evaluation. Singleton queries are a probe;
the previous experiment used eight-query averages. This cannot explain its
effect size, establish necessity of architecture growth or justify promotion.

## Boundaries, costs and failure handling

One execution through existing EXPERIMENTAL Sandbox/worker, E1 Journal and
execute_study; 60 seconds CPU/wall, 2048 MiB sampled RSS, ZERO new interactions,
ZERO training updates/neural forwards/imagined transitions. Count matrix entries,
covariance multiply-adds and public interpreter instructions separately, not
FLOPs or environment steps. Cached source data: 2048 existing labels available;
512 distinct labels used in prefixes, with 128*(0+1+2+4)=896 prefix reads.
Public hypothesis-table construction is supplied prior
computation, not collecting hidden task labels. Preserve every historical file
and frozen checkpoint; record before/after hashes. Cap/error means incomplete
or invalid, never `not_demonstrated`. Save partial attempts without retry.

Carry 1996.6321034559958 seconds used / 1603.3678965440042 remaining. Debit
ceil(host wall)+1 through the shared runner; do not reset. Commit tested protocol
and implementation before audit. Independently verify saved gain cells, counts,
source-only projection, zero resource usage and all prior artifact hashes;
show read-only results in existing GUI. No live promotion, main merge, new target
tasks, closed evaluation rerun, architecture sweep or learning-to-learn claim.

Tests: query changes cannot change candidate features/learned choices; target
fields and unobserved source outcomes cannot enter projection/context scoring;
covariance formula vs enumerated outcomes; constant candidates; disjoint input
validation; raw missing task/prefix/query/candidate rejection; nonfinite rejection;
frozen model and completeness; independently verified aggregation and provenance.

Pre-execution checks: 106 focused/regression tests passed in 52.33 seconds,
covering the new audit, original source-acquisition unit/evidence tests,
source-inferred investigation, EXPERIMENTAL host and Lab sessions/release.
The initial regression invocation exposed an obsolete fixture using future
configs instead of its historical registry snapshot; the fixture is corrected
without changing prior artifacts. Browser test syntax and repository link/
preservation checks pass. Test fixtures do not launch the registered audit.
