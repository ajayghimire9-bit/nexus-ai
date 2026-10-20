# Frozen investigation tree + selective greedy fallback

Registered development intervention; basec41b07fd04f2c85158b48dba8a407cf2a90ece85,
branchcodex/seed-investigation-hybrid. Commit tested implementation and this
protocol before one run. Preserve prior negative results and closed tasks.

## Hypothesis and fixed components

H-hybrid: switching to greedy information gain ONLY at an abandoned source-tree
leaf removes the long question tail while preserving early tree decisions and
reducing computation relative to pure greedy, without worse question efficiency
or materially worse prediction. Alternatives: the early tree splits themselves
are unsuitable, or greedy's small search is already a better trade-off.

Use EXACTLY the previous13-node tree (hash
c5e68b085ebd654e7dcc57c3319f0099e778dc4bc359aa6cb88b862f67b4e80e), source traces,
eight-law Boolean grammar, uniform surviving-hypothesis predictions and supplied
temporal/spatial sensor bindings. Verify the parent artifact hash before loading.
NO refitting the tree, neural models, grammar or preprocessing. Source tasks are
inherited, NOT newly collected or claimed fresh. All evaluated TARGET tasks and
support/final realization seeds are fresh. Frozen model hashes are checked.

Reuse `investigation_transfer` collection, posterior, source-retention replay,
`question_selection.LabelOracle`, `structure.investigation` tree format and the
EXPERIMENTAL host/journal; add only the selective fallback and audit profile.

## Fresh tasks and conditions

Executable exact-checked config: configs/seed_investigation_hybrid.json.
32 fresh target tasks983200–983231: first16 temporal, next16 spatial. An exact
six-digit scan of tracked configs/docs/artifacts found no seed collisions.
Inherited source tasks982100–982131 are provenance only. Previous target
tasks982200–982231 are closed and NEVER recollected or scored.

Keep the original generation rules: public role permutation RNG task+11;
evaluator-only law RNG task+101; support inputs cover all8 Boolean combinations
with raw realization seeds task*1000+q. Final32 observations/task use RNG
task+90000 and realization seeds task*1000+100+j. Final identifiers differ from
support. New realizations repeat the finite input grammar by construction.

Five paired methods, identical source-frozen grammar, support inputs and up to
8 revealed answers per target:
1. tree_fixed: frozen tree, fixed-order fallback after a leaf.
2. tree_greedy: SAME tree until abandon; then greedy information-gain fallback.
   A source stop leaf that is not uniquely identified uses the original fixed
   fallback. This safety rule cannot be changed after observing outcomes.
3. greedy: pure expected partition-size minimization, canonical tie break.
4. fixed_order: lowest remaining canonical question index.
5. no_library: random order, seed task+700, without replacement.

All use the SAME version-space checker; never treat a source leaf identity as
ground truth. Stop revealing answers only at a unique surviving law. Snapshots
at1/2/4/8 are cumulative teaching budgets, with no fictitious extra questions
after early identification. Choices are saved before final observations exist.
Target labels and final outcomes cannot change the tree or global library.

## Locked advancement screen — all requirements

- Every hybrid choice and posterior before its first fallback must exactly
  reproduce tree_fixed, with zero greedy calls during that prefix.
- Remove the five-question tail: maximum hybrid identification cost<=4, zero
  tasks>=5; tree_fixed must show at least one such task for a demonstrated tail
  removal. If no control tail occurs, tail evidence is inconclusive, not a pass.
- Mean hybrid questions<=pure greedy (zero practical regression margin), and
  accuracy at EACH budget1/2/4/8 no more than.01 below pure greedy. This is a
  deliberately conservative operationalization of “match or beat in questions
  or accuracy”; a high early accuracy cannot hide later query inefficiency.
- At least30% fewer target greedy-search hypothesis checks, AND at least20%
  lower total decision work than pure greedy after charging inherited source
  predicate-comparison cost in full over these32 tasks.
- Exact tree/grammar/checkpoint preservation, source behavior unchanged, complete
  finite grid, locked provenance and all resource caps satisfied.

Report each gate separately. The source-development screen is point-estimate
engineering evidence, not a confirmation significance test. Report paired
task-level exploratory95% t intervals (df31) for all question differences,
conditional on ONE frozen library and TWO target encodings; no claim of32
independent learners or family-level generality. Report each family, every task,
tail, accuracy and Brier at1/2/4/8, plus all five controls.

## Honest compute and retention accounting

Inherited source cost:256 labeled observations,32 traces,13-node tree and the
recorded source-fit wall time (about.000338s). Charge this upfront cost to BOTH
tree methods, report an8-observation/task amortization; it is cached historical
collection and is NOT debited as new collection or wall time a second time.
Recount the original ID3 partition predicate comparisons from the saved tree
and source traces:2*rows*available questions at each split. Include all candidate
tests, not just the selected split. This does not include entropy arithmetic;
recorded fit time is separately disclosed. Never label it complete FLOP cost.

For each method separately record target search hypothesis comparisons, greedy
calls, posterior filtering checks, tree-node visits and fallback calls. Total
decision-work PROXY = those search comparisons + posterior checks + tree visits
+ inherited source split comparisons for tree methods. Heterogeneous operations
are unit-weighted; no wall-speed claim is permitted from this proxy alone.
The old greedy helper constructs two Boolean partitions separately. This study
uses a single-pass count with the IDENTICAL squared-partition score and tie
rule, verified on all255 nonempty hypothesis subsets. It charges every actual
table lookup once. Old recorded resource counts are preserved; comparisons
here use the same optimized scoring operator for hybrid and pure greedy.
Report target-only and source-inclusive totals, and include cached retention
reads and final scoring separately. Actual full-run CPU/wall and RSS remain metered.

New observations:256 shared target support-bank rows +1024 final rows=1280.
Method-specific revealed answers are cached exposures, not extra collection.
Zero neural forwards, optimizer updates, imagined transitions or source fitting.
Hash and replay the same source traces before/after, including original abandons.

## Budget, failure and interpretation

Existing owner standing authority plus explicit current request. One run;
60s CPU/wall,2048MiB sampled RSS,5000 authored observations. Carry
1981.6321034559958s used /1618.3678965440042remaining; no reset. Fail closed on
missing/hash-mismatched parents, stale ledger or duplicate configuration. Save
partial/invalid failures without automatic retry or reducing the grid.

If the hybrid fails, distinguish a retained bad early split from an ineffective
fallback or source-cost overhead using recorded traces. No architecture sweep,
confirmation, live promotion or further experiment in this run. Even a passing
screen demonstrates only selective source-question reuse in the supplied grammar,
not general learning-to-learn. Independently verify saved arithmetic/choices,
show results in the read-only GUI, commit results separately and push.
