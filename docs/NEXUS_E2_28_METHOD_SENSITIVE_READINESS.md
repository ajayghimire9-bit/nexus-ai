# Evolution-2.28 — method-sensitive study readiness audit

Protocol and source review, 2026-10-19. Starting local/remote SHA:
`6b1be164a58153070f87c87d9a2f4c8b67aa2e93`, verified against GitHub
`codex/evolution2.27-frozen-feedback-integration`. Separate branch:
`codex/evolution2.28-method-sensitive-readiness`. Preserve unrelated untracked
E1 adapter files. No scientific experiment is registered or authorized here.

## Question and bounded procedure

Does E2.27's tested feedback boundary make the existing persist/reset study
scientifically executable? Inspect source, existing JSON and file hashes only.
Do not import execution modules in the audit, fit/load models, invoke planners,
collect environments, replay learning feedback, or select physics/seeds.
Use a standard-library read-only inventory script and focused deterministic
tests. Commit this implementation/review before capturing the inventory.
Existing results, allocation files and session ledger stay unchanged.

Reuse, do not replace: `AdaptiveProposer`, `ContextualStrategyMemory`,
`evolution2.methods`, `TrustedEvaluator`, `MethodSensitiveHiddenEval`,
`prospective_hidden_evaluator`, and `ReservationLedger`. No additional
proposer, memory, meter or scientific runner is implemented.

## Verdict

**BLOCKED_SCIENTIFIC_RUNNER_AND_PROTOCOL_GAPS.** E2.27 is a valid synthetic
integration result, not evidence that a prospective real-return runner exists.
This targeted inspection is not an exhaustive certification of all branches,
checkpoint producers or historical registrations. Readiness remains blocked
even if every inventory test passes.

## Findings tied to the actual execution paths

1. `persist_reset_science.run_authorized()` still invokes historical
   `run_bundle()`. Its hidden loop assigns the same return to every method.
   That closed E2.17 result remains inconclusive. Do not reuse this runner.
   `corrected_hidden_scores()` selects method-dependent planners but constructs
   `MethodSensitiveHiddenEval` directly; it does not use the manifest factory.
   The only invocation of `prospective_hidden_evaluator` in production source
   is inside the E2.27 synthetic audit. A factory passing tests does not wire
   the scientific training and hidden-evaluation phases.

2. `fixture_hidden_return()` returns `max(decision.scores)`: a learned-model
   forecast, not actual episodic reward. E2.21's authored FakeStepModel scores
   and E2.27's authored 2/8 scores test plumbing only. Do not substitute them
   for control-quality labels. A prospective evaluator must attach the selected
   planner to actual metered environment returns, with the same reset/search
   opportunities for every method. No such evaluation is run in this audit.

3. Reference fairness is still a **study-design gap**. E2.27 freezes a declared
   two-anchor reference with synthetic scores. A prospective study must specify
   which permitted source observations produce one shared family/bundle scale,
   when it freezes, its collection costs, and how every method receives equal
   information. Existing training uses four proposals, including two forced
   anchors, from six revealed variants; that is not exhaustive twelve-arm
   search. Freezing from a method-specific exposed set after adaptive choices
   could produce unfair scales. Do not infer a reference rule from query
   extrema. Training/query separation must be established by data provenance,
   not merely a manifest checksum.

4. Raw reward and learning feedback are distinct. The prospective evaluator
   stores raw/unit/clipping metadata on physical outcomes, but the existing
   `corrected_hidden_scores` summary averages only the returned scaled scores.
   Cached logical receipts do not append another physical outcome. A future
   analysis must reconstruct all planned method/family/slot cells, report raw
   family returns separately, and attribute clipping/cache hits to each logical
   comparison. Clipping can erase meaningful differences outside the training
   range. The old unbounded revealed normalization and a new clipped scale are
   different estimands: do not silently carry the old 0.05 margin onto a revised
   primary endpoint. Predeclare family aggregation, clipping sensitivity and
   multiplicity before collecting outcomes.

5. n=10 is a planning recommendation, not an implemented protocol. Existing
   `analyze()` uses the n=3 interval helper, df=2 and its critical values;
   `fit_models()` requires exactly six family/bundle fits. The interval helper
   rejects wrong lengths and nonfinite values, so it does not silently accept
   n=10, but neither it nor `analyze()` verifies unique bundle IDs, a complete
   raw family/slot grid or numeric types strictly. Duplicate bundles can
   masquerade as replications. A prospective n=10 contract needs fixed IDs,
   exact complete raw cells, ten independent model-training bundles, correct
   df=9 statistics, and explicit incomplete/invalid labels. Tasks, slots,
   cached outcomes and proposer draws are not additional independent bundles.

6. Provenance is insufficient for promotion. E2.17 records twelve source array
   hashes and six executed fit paths/model seeds, but no checkpoint SHA in its
   fit rows and `val_loss` is null. A current file digest cannot retrospectively
   authenticate those original fit bytes. The older no-fit inventory explicitly
   reports unmatched recipes (three Pendulum versus ten Acrobot weights).
   Its historical missing-source report predates E2.8 collection and must not
   be interpreted as saying the later arrays do not exist. Neither inventory
   supplies a matched twenty-fit prospective manifest. Existing closed physics
   and E2.17 source fits cannot be relabeled fresh evidence. This audit hashes
   available files only; it neither loads nor replaces checkpoints.

7. Interrupted work requires stronger accounting. Existing `rollout()` charges
   accumulated environment/imagined work only after the loop. An exception
   before that charge can underreport completed work; a cap is checked after
   the episode rather than before each operation. Hidden evaluator physical
   counts increment only on a completed callback, while logical counts increment
   before it. Therefore physical receipts are not a failed-work resource meter.
   Reuse the existing reservation ledger for prospective pre-call reservation
   and incremental settlement, with partial/failure receipts. Equal logical
   opportunities do not imply identical physical cache costs.

8. Entry points remain refused. The E2.17 grant is consumed; E2.20 still refuses
   scientific dispatch. E2.27 creates no allocation, unused holdout or numerical
   seed registration. H17 remains blocked. Budget capacity alone cannot bypass
   scientific prerequisites or reopen closed confirmation data.

## Resource arithmetic and uncertainty

Historical planning worksheet: n=3 requires at most 24,480 real steps and six
fits; n=10 requires 25,600 source + 24,000 revealed + 32,000 hidden = **81,600**
real steps and twenty fits. Hidden cache collisions could reduce physical work
but do not reduce the required upper reservation. These totals assume the
reference plan uses already-counted source/revealed work; extra reference
collection must be budgeted explicitly. At the existing conservative 1,536
imagined states per decision, n=10's 56,000 control steps imply at most
86,016,000 imagined states, separately from source collection/training.

E2.21 extrapolates about 104 seconds from E2.17, 4.05 seconds for twenty fits
from six disposable fits, and a separate planner prior about 162 seconds.
These are overlapping planning estimates, not additive measured phases or a
validated full-run duration. The twenty-fit clock is unmeasured. Actual CPU
cost, failure settlement and all reference costs must be bounded prospectively.
No new allocation or budget is created. Scientific ledger stays
**327.869 seconds used / 3272.131 remaining**.

## Verification and next action

The inventory validates the historical raw/unit bundle grid and array hashes,
records current fit presence/digests with missing original expectations clearly
labeled, hashes reviewed source and existing JSON, and refuses changed source
assumptions or overwriting its capture. These tests do not enable execution.
Results and exact test counts are appended after the source-only capture.

**One next milestone:** implement and test a prospective real-return scoring
contract in the existing evaluator path using authored, environment-free
receipts first. Lock a shared source-reference rule, raw family/slot grid,
clipping report, ten-bundle analysis and interrupted-work settlement together.
This addresses the specific forecast-versus-real-quality gap; do not start
another proxy predictor, allocate science, register holdouts or train models.
Only after this contract is auditable should a separate real study be proposed.
No learning-to-learn or general control improvement is demonstrated here.
