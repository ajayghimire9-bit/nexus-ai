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

## Completed recovery — negative overall

Recovery execution `e01a5020b10e4b52053feb0f9f2135e6992d717d` is recorded inside
`artifacts/unified_e225_e30_recovery.json`; verify that field rather than
this short display. Recovery capture SHA256
`5e3cf22d21957bbc6700df5632d6e6d0e75cf50a1144ccba2f1eaa21a8778561`.
The original incomplete capture remains unchanged. No architecture/feature/
threshold tuning followed the results. A separate saved-data audit is
`artifacts/unified_e225_e30_audit.json`; no replanning/fitting in that audit.

**A fails, B passes on this finite source witness, C/D/E fail.** This is not
a working self-improving general learner. It is a tested optional predictor,
executable typed generator and connected feedback loop with a negative
matched source-proxy improvement result.

### Prediction

Frozen held-bundle fixed-domain advantage MAE **0.000685291**, versus zero
advantage **0.000314323**. On300 common-support rows: ridge **0.000702215**,
paired mean **0.000382788**, observation kernel **0.000506623**. These300
rows are not independent scientific samples. The full fixed prediction grid
has576 rows; novel-descriptor grid15,840. Novel MAE **0.000687918**, zero
baseline **0.000303970**. Fixed/novel sign accuracy0.34375/0.33030;
abstention0.8125/0.80890 at |prediction|<0.001. Calibration bias
+0.000256064/+0.000271262. Detailed fixed-catalogue pair-ranking accuracy
and tied/no-informative-pair cases are saved separately in the capture.

The ranker handles unseen structural fingerprints using descriptors, but
that is an interface capability, not accurate extrapolation. With192
coefficients and only24 source observations per fit (including zero anchor
differences), the effective information is limited. Antisymmetric rows and
2,880 repeated fits do not create additional feedback. No larger model or
post-result regularization search was attempted.

### Generation, feedback and comparisons

The342 typed policies include330 structural compositions. Their action
vectors on the16 registered source contexts realize8 distinct patterns,
**4 beyond the fixed catalogue**. This finite-suite behavioral witness and
the deterministic composition test support B; they do not show new scientific
algorithms or better return. Source signatures are a finite empirical
equivalence check, not proof of equivalence across all observations.

Mean cumulative free-slot regret, lower is better (fixed analytic unit scale):

- Persistent catalogue **0.000156255**.
- Quality-ranked catalogue **0.000156255**.
- Random generation **0.000164918**.
- Feedback generation without quality **0.000228159**.
- Unified **0.000224160**.
- Reassigned feedback **0.000405140**.
- Withheld feedback **0.000324324**.
- Ungated, consensus and evidence controls each **0.000156255**.
- Nearest memory **0.000150806**, strongest pooled comparator.

Unified minus feedback-generation regret is−0.000003999, a small descriptive
gain, but unified loses to random generation, persistent, quality-only and
nearest memory. It beats its reassigned/withheld ablations; this does **not**
rescue C because feedback-only generation loses to random. All selected labels
are observed evaluator proxies; no prediction is recycled as feedback.
Weights and later candidate sets change, without established useful learning.

First-free regret is0 for persistent/quality/ungated/consensus/evidence,
0.000050269 for nearest,0.000063866 for random and withheld,
0.000073951 for feedback generation,0.000106716 for unified,
0.000121645 for reassigned feedback. Raw curves and per-generation values
are in all528 six-receipt traces; positive last-minus-first-generation point
estimates do not establish improvement against a matched baseline.

Unified versus persistent cumulative-regret differences by held fold:
Pendulum0 **+0.000896640** (worse), Pendulum1 **0**, Acrobot0
**−0.000314975** and Acrobot1 **−0.000310047** (better). Thus performance
depends on the source family/bundle. Unified beats the strongest pooled
comparator in only2/4 folds, does not improve either family's strongest
baseline, and fails E. These are inspected default-physics source folds,
not new physics/task-family transfer or confirmation.

### Evaluator headroom and limitations

All methods find the same best observed score, mean0.319638027, and the
forced anchors already attain that best in **528/528 traces**. Generated
novel action patterns therefore have no demonstrated discovery headroom
under this common-neutral-continuation FakeStepModel label. This does not
prove generation would fail on real dynamics; it shows this source fixture
cannot support a claim that new strategies improve the best found controller.
Very small unit regret differences reflect that restricted label, not
measured environment-return margins. Do not promote any strategy.

No novel-strategy library was scientifically validated or promoted. The
generator retains parents and feedback within each local task; held contexts
clone the source state to prevent cross-query leakage. Existing memory stores
credited catalogue-leaf observations, not a second persistent novel-policy
database. Continual learning, forgetting, cross-family knowledge transfer,
and improving the learning/update algorithm remain untested.

The new run records predictor abstention, not a full per-decision memory
arbitration explanation. Matching persistent choices does not prove why an
evidence/consensus comparator accepted or abstained. Earlier E2.24's40/40
abstentions remain its own closed result. No missing arbitration reason is
reconstructed as observed data. Likewise no unavailable neural prediction
residual is invented: support transition statistics and the fake probe are
the information used here.

### Costs, completeness and reporting correction

Recovery: **5.271231s wall /5.208034s CPU**,438,336 fake imagined rows,
8,000 fake step calls,3,168 logical query opportunities,1,920 returned-candidate
validations,2,194 mutation attempts,274 duplicate rejections,0 fallbacks,
2,880 small ridge fits. Sixteen resource plans complete with no unknown
reserved work. Full oracle/leaf preparation is included in this cost and is
separate from per-method logical1536-state upper opportunities. Exact shared
leaf reuse saves physical work; it does not grant extra learner feedback.
Maximum stored predictor data46,320 bytes and memory-record serialization
12,598 bytes per learner context, excluding Python/NumPy process overhead.

Both attempts combined: **6.097824s wall**,876,672 fake imagined rows,
16,000 fake calls; zero real interactions, neural forwards, world-model fitting or
checkpoint changes. Ledger after both attempts:
**333.966824 used /3266.033176 remaining**. The original failed capture is
part of this debit. All313 prior JSON hashes verified unchanged during recovery;
all528 lineage journals independently verify. Code/config/source hashes and
exact environment dependencies are reproducible through the recorded revision
and existing `.deps` runtime; no new dependency/service was installed.

One reporting bug was found offline: `predictor_parameters` is0 in the raw
capture because the final observe invalidates a cached fit. This is not the
coefficient capacity. Preserve the raw field and record the correction in the
separate audit: **192 coefficients** for trained models,0 for the withheld
model. Future reporting now reads schema capacity even when refitting is
pending. No learning behavior changed and no model experiment reran.

Pre-run relevant regressions202 passed; generator recovery regression added
and12 focused tests passed before recovery. Final saved-result and relevant
regressions **208 passed in2.95s**, including17 focused unified tests. No full
repository simulator/training/artifact-writer suite was run. Source-only
arithmetic audit was authored after the recovery; its Git HEAD identifies
execution context, not a precommitted scientific protocol.

Runtime: Python3.13.5, NumPy2.5.4, macOS26.6.2 ARM64. Test fixture fake work
is separate from the two benchmark captures; reported benchmark counts are
not a claim to include every pytest operation. Final tests also verify saved
code at its execution revision, numerical completeness and immutable history.

Audit script source SHA256
`63fd10445817e58b1f6cc0bdc8f29c8e6a800c521a2fd36a964768e316fb0668`;
audit capture SHA256
`2b9269ed4db421d9fb499e72a9b63ca270d5310b6392886e5884f1282a9a5505`.
`artifacts/unified_e225_e30_validation.json` explicitly records that the
posthoc arithmetic script was untracked when run, rather than misrepresenting
the execution HEAD as its clean implementation revision. All original
execution-code hashes independently verify with `git show` at the recorded
recovery revision; current parameter-reporting metadata changes do not rewrite
that execution. No new environment or model calls occurred in the audit.

Final relevant tests:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest \
 tests/test_unified_e225_e30.py tests/test_evolution2_return_scoring.py \
 tests/test_evolution2_readiness_audit.py tests/test_evolution2_feedback_integration.py \
 tests/test_evolution2_feedback_normalization.py tests/test_evolution1_resources.py \
 tests/test_evolution1_toy_loop.py tests/test_evolution2_planner_adapter.py \
 tests/test_evolution2_planner_quality.py -p no:cacheprovider -o addopts='' -q
```

### Single next scientific question

**Does a permitted frozen learned-dynamics source evaluator provide meaningful
decision/discovery headroom beyond the two forced anchors?** First audit that
label headroom and its reproducible source/checkpoint provenance, before
training another predictor or increasing the grammar. The present fixture
does not justify a larger encoder, more generations, another feature search,
real-environment collection or claims of general autonomous learning.
