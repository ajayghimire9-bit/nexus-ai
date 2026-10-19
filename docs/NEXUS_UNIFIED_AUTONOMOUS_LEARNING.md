# Unified E2.25 + E3.0 — registered source-only development

## Provenance and boundaries

Base `48ccf446d8b7bdaa79afde7f54634a73a5cc43cf` verified on GitHub,
descendant of requested E2.24 `e9a03b96921d1340a521f148cbcece3dfff368d8`.
Ten intervening commits include the negative E2.25 and feedback-contract
repairs; retain them. Branch `codex/nexus-e225-e30-unified-learning`.
Untracked E1 adapter files and all other worktrees remain untouched.
Consulted canonical state, reuse map, registry, E2.24/E2.25 reports and
E2.26–E2.29 boundaries. This task explicitly authorizes E3.0 development;
it does not reopen E2.17's consumed grant, H17 or any closed holdout.

Reuse `AdaptiveProposer`, `ObservationAwareAdaptive`/existing strategy-memory
records, `TrustedEvaluator`, `Journal`, `ReservationLedger`, catalogue
`plan_bound`, adapter `decide`, `score_open_loop` and E2.25 ridge. No historical
algorithm, neural model, artifact or scientific runner is replaced.

## Executable configuration and bounded budget

`configs/unified_e225_e30.json` is checked exactly against runtime settings;
unknown or changed settings fail rather than silently disconnecting config.
Local CPU, one180-second dispatch deadline checked before each fake-model
step and proposal. Zero real-environment interactions and neural forwards.
No world construction, checkpoint loading/training or paid services.
Use only E2.8 **train** bundles0/1 for Pendulum and Acrobot, offsets0/32/64/96,
32-row supports; verify source episode disjointness and whole-file hashes.
No bundle2, validation, E2.17 arrays or E2.22–E2.24 development scenarios.
Both source bundles are inspected, same-default-physics data: no new confirmation.

Three proposer seeds7/17/27 share the source data and fake models. They are
not independent world-model/physics replications. Four reverse LOBO folds
(family×held bundle) share data and cannot be treated as four independent
scientific replications. Descriptive paired metrics only; no scientific CI.
The standing research ledger starts327.869/3272.131 seconds; debit actual
benchmark wall time, including failed/partial work, without rewriting old ledgers.

All existing catalogue operators at caps1536 and768 are scored once per
context, with identical candidate seeds700+offset. Exact cached leaf decisions
resolve the342-policy grammar. Reserved fake step batches count mathematical
model calls and imagined rows; the ledger's network-forward metadata denotes
fake forward work, **not neural network inference**. Reserve/settle each call
using the existing ledger. All planned leaf calls run, including evaluator-only
oracle work, and this overhead is separate from learner opportunities.
Maximum16 contexts×(24 leaves×1536 +48 probe rows)=590,592 fake imagined rows;
actual analytic bounds are slightly lower. Grammar execution/validation and
ridge fitting are CPU overhead, not extra free feedback.

## Common labels and information boundary

Heterogeneous planners' maximum internal scores are not comparable quality
labels. Instead derive a **common** sixteen-step fake-model probe for all three
first actions: take that first action, then fifteen neutral index1 actions.
Use the existing family reward and survival scoring. A strategy's label is
the probe value of its selected first action. This common-continuation proxy
is neither actual simulator return nor full-episode control quality.

Map raw proxy label r to0.5+0.5*tanh(r/100), fixed before evaluation. No query
min/max or hidden extrema set feedback. Raw values remain in traces. Oracle
tables stay evaluator-owned; algorithms get only charged selected feedback.
Two fixed anchors are jointly revealed and charged before free selection.
No predicted outcome is ever accepted as an observed update. Trusted Python
objects are an API boundary, not an adversarial process sandbox.

For each fold/seed, one persistent source policy exposes six catalogue labels
per training context: two anchors and four adaptive selections. All methods
receive the identical24 source labels. Reuse these offline labels; account
the common data preparation separately. No method sees the held bundle during
pretraining, normalization or hyperparameter selection. At each held context,
clone the source learner state; allow only two anchors plus four selected
feedback values. No local query learning carries to another held context.

## Eleven matched comparisons

Persistent fixed catalogue; quality-ranked fixed catalogue; random generation;
feedback generation without quality; unified generator+quality; unified with
reassigned feedback; unified with feedback withheld; existing ungated,
nearest-neighbor, consensus and evidence memory controls. Memory uses only
permitted source records, train-bundle normalization, fixed kernel1.0 and an
always-open radius for nearest comparison, no fitted held-query threshold.
The evidence penalty stays1.0. These are source-only comparators, not reruns of
their closed original screens or a claim of identical old calibration.

All receive six logical query opportunities, each with1536 upper imagined
work; no duplicate strategy gets a free repeated opportunity. Actual leaf/
strategy reuse is cached across methods and recorded separately. Generated
methods validate two candidates per free slot. Quality selection therefore
has additional validation/linear-algebra CPU, disclosed rather than called
compute-identical. Record source/pretraining, oracle preparation, logical
evaluation, actual fake inference, generator validation, memory and ridge
costs separately. No claim of equal neural capacity or matched FLOPs.

## Predeclared capability screens

A: frozen held-bundle fixed-domain advantage MAE at least5% lower than zero
advantage and, on shared coverage, paired mean and observation kernel. Also
report all novel-descriptor errors, ranking/sign accuracy, calibration,
abstention and unsupported baseline coverage. Improvements only on self-chosen
online labels do not establish this capability.

B: executable grammar beyond a fixed Variant, plus at least one source action
vector not realized by any of the twelve fixed policies. Synthetic witness
and source behavioral witness are separate findings; no renamed seeds count.

C: feedback-generation cumulative free-slot regret at least5% below random
generation, and unified below both reassigned/withheld feedback. Weight changes
alone do not pass. Report per-generation observed quality and immutable lineage.

D: unified cumulative regret at least5% below the strongest other method,
required pooled and in both families. First-free regret and best found at equal
budget remain secondary. If the strongest baseline has zero regret, require
a strict improvement; a zero tie is not success.

E: D's direction holds in at least three of four held family/bundle cells;
all declared cells and resources complete and finite. This is a descriptive
inspected-source transfer screen, not independent task-family validation.
Do not relax any screen after results; negative/inconclusive outcomes retained.

Average proposer seeds and offsets within folds, folds within family, families
equally. Counts are balanced. Report raw paired traces, gains/losses per fold,
latent missing metrics explicitly (e.g. no informative ranking pair) and
baseline capacity/cost differences. Never infer real control or learning-to-learn.

## Tests, execution and preservation

Test finite/canonical grammar, overbudget/invalid rejection, deterministic
execution, rank-composition action witness, feedback-dependent/withheld/random
proposals, duplicate/hidden feedback rejection, informative ridge behavior,
train/query/config isolation, exact fake-step reservations and complete-grid
rejection. Small tests are not scientific evaluations. An initial smoke test
exposed JSON serialization of Journal Event dataclasses; use `asdict` while
preserving the immutable event/hash chain. That test failed before outcomes,
was fixed, and11 focused tests then passed.

Commit tested implementation and this protocol before full benchmark.
Run `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3
scripts/run_unified_e225_e30.py`. Capture complete or honestly partial data to
`artifacts/unified_e225_e30.json`, refusing overwrite. Save source/config/code
hashes, execution revision, raw predictions, all selected receipts, strategy
lineage, resource journals and all historical JSON hashes. Audit saved
arithmetic without another model run. Commit results separately and push.

The next experiment must follow the actual failed/passed capability; do not
automatically collect environments, promote a strategy or launch another run.

## Correctness recovery v1.1, before recovery scoring

First execution `17536fed4e66ef6bd59eb99b8ac1c5d95230e30f` stopped incomplete:
`generation_budget_exhausted`,0.826593417s,438,336 fake imagined rows,8,000 fake
calls,72 logical receipts. Preserve `artifacts/unified_e225_e30.json` unchanged.
No aggregate screen was produced. Parent inheritance collapsed proposals to
only three forms once a favored leaf and complementary child stayed fixed.
This is an implementation defect, not a failed scientific improvement screen.

Repair: retain a parent's complementary child with probability0.5, otherwise
mutate that child from the existing catalogue; after32 rejected proposals use
one bounded uniform grammar fallback. Log all attempts/rejections/fallbacks.
The fallback has no claimed genetic parent. Added a three-seed, sixteen-update
deduplication regression. Keep all physics, labels, metrics, thresholds,
budgets, train/query splits and prediction rules unchanged. No extra feature
or hyperparameter search. Source-only recovery repeats inspected fixtures,
not independent confirmation. Commit this correction before its execution.
Write `artifacts/unified_e225_e30_recovery.json`, preserving the original
failure and adding both attempt costs to the session ledger. No old grant used.
