# Frozen investigation reuse — Phase 3 authored development protocol

Registered before any source/target collection. Base
`6f4b17ff2297aec9c7f54966d9d7a9ff9712e24f`, research branch
`codex/seed-investigation-transfer`. No main change or live-agent promotion.

## Hypothesis and limits of the test

A source-learned, frozen probe tree reduces teaching questions needed to identify
a task rule across fresh observable encodings versus fixed-order and no-library
questioning, while remaining competitive with greedy and bounded exhaustive
search. Competing explanations: the source order transfers; it overfits source
law frequencies; or a simple online information-gain calculation is sufficient.

This is a narrow first Phase3 test. The existing investigation tree is a
source-trace classifier, so we test its learned ordering, not invent a new
neural questioner. All methods share eight SUPPLIED Boolean candidate laws on
three observable roles: role0/role1/role2, AND, OR, XOR, majority, NOT-role0.
This grammar and the raw-to-role sensor adapters are authored. New domain
encodings are not independently learned perceptual grounding. A positive result
cannot establish open-ended knowledge discovery or general learning-to-learn.

## Data, bindings and freeze order

Config `configs/seed_investigation_transfer.json` is executable and exact-checked.
Fresh source tasks982100–982131 use attribute flags and integer-threshold
observations,16 per family. Fresh targets982200–982231 use temporal event-order
and spatial comparisons,16 per family. One task-specific public role-name
permutation comes from seed+11; it never depends on the hidden rule. The rule is
sampled by evaluator-only RNG seed+101. All targets are fresh authored source-
development tasks, not confirmation. No previous outcome bank is opened.

Each source task supplies eight binary-input combinations and observed labels.
Its candidate identity is inferred by the shared checker from those labels.
The existing `structure.investigation.learn` fits one max-depth3/max15-node tree
to the32 source traces. Save the tree/source hashes BEFORE target collection.

Each target receives eight candidate teaching inputs, one per public Boolean
combination. Raw data and explicit role bindings are available to all methods.
The evaluator collects a shared eight-answer support bank, kept private behind
the existing `LabelOracle`. A policy locks its next question before revealing
that answer. All requested-answer sequences are saved BEFORE final episodes.
Final32 episodes/task use RNG seed+90000 and raw realization seeds
task*1000+100+j, separate from support task*1000+q. Episode identifiers differ.
The three Boolean features necessarily repeat: this is fresh realization/domain
encoding generalization within a shared finite grammar, not novel logical laws.

## Methods and adaptation contract

- Learned: traverse the frozen source tree using only revealed answers. After
  a stop/abandon leaf, use the fixed-order fallback. Do not trust the tree's
  predicted class as truth; every method uses the SAME version-space checker.
- Fixed-order: lowest remaining canonical question index.
- No-library: seeded random order (seed+700), without replacement.
- Greedy: maximize current version-space expected information via squared
  partition sizes; canonical-index tie break. No source fitting.
- Exhaustive: minimum expected identification cost under uniform surviving
  hypotheses, exact memoized recursion,4096 search-node cap/decision. Exhaustion
  invalidates execution; it cannot silently fall back or drop a method.

All methods have up to8 labels/target, identical inputs and question costs, stop
only at a unique surviving hypothesis, and freeze snapshots at budgets1/2/4/8.
These are cumulative teaching trajectories. Once identified, later budgets
reuse that snapshot and do not charge fictitious questions. Predictions average
the surviving hypotheses. Accuracy uses probability>=.5; also record Brier.
No target answer, outcome or final metric changes the global source tree.

## Predeclared decision

Primary efficiency endpoint: mean questions until unique identification (censor
at9 if unresolved after8). Target tasks are paired units; report exploratory
task-level t95% intervals, df31, conditional on ONE learned library and TWO
target families. This is not32 independent architectures/family replications.
Report each target, each family,1/2/4/8 accuracy/Brier, and compute separately.

Pass only if ALL apply:
1. At least0.5 fewer questions versus both fixed-order and no-library, and both
   paired task-level interval lower bounds exceed zero.
2. At budget2, at least0.05 absolute accuracy gain versus both of those controls.
3. No more than0.25 extra questions and0.01 accuracy loss versus EACH of greedy
   and exhaustive. Strong-baseline failures cannot be hidden by weaker wins.
4. Exact frozen-library hash and source-probe replay retention before/after.
5. Complete finite planned task/method/budget/episode grid and valid provenance.

Retention measures the frozen global investigation behavior, not neural
continual learning or retention of arbitrary target task knowledge. Failure is
valid scientific evidence; invalid/incomplete execution is a different label.
Do not retune, retry, extend the tree or replace the registered comparisons.

## Accounting and authorization

Existing EXPERIMENTAL host, immutable journal, one-use configuration, CPU/wall
watchdog and sampled-RSS policy. Standing grant plus explicit current user
authorization. Cap60seconds CPU/wall,2048MiB sampled RSS,5000 authored observations,
zero neural updates and zero imagined world-model transitions. Carry
1979.6321034559958seconds used /1620.3678965440042remaining; no reset.

Worst-case actual collection:256 source labeled observations +256 shared target
support-bank observations +1024 final observations =1536. Each collected row is
one authored observation/outcome, not a physical trajectory. Repeated labels
served to methods are cached reuse; charge up to1280 teaching-answer exposures
separately. Record predicate predictions, tree visits, search nodes, source tree
fit, source trace size, final scoring calls, wall/CPU, frozen parameter count0
and cached retention reads. Methods have equal teaching opportunities, unequal
compute. The source tree's upfront cost is not free and must be disclosed.

Commit protocol, config and tested implementation before one run. Save partial
failure receipts if capped. Independently recheck arithmetic and choice replay
without collecting new observations. Historical checkpoints and artifacts stay
unchanged; no confirmation or control experiment is authorized by this study.
