# NEXUS — Seven Learning Milestones: Implementation and E3.8 Results

## Outcome at a glance

User attachment described proposed milestones, not existing capabilities. The engineering paths below are implemented and exercised; real-environment utility of later interfaces remains untested. The ONE targeted compact interaction experiment completed and **failed** its registered selection rule. No default controller, neural architecture, historical weights or regularization was promoted/retuned. No further feature-search rounds were run on the36-pair bank.

Branch codex/e3-8-interactions-and-learning-interfaces from verified4c31881209467cafb1ecc92b182702b366f4f854. Protocol/tested implementation execution commit **21ba36cdda5133bb29c7d955b0db151300834aad** preceded real-data fitting. Protocol NEXUS_E3_8_COMPACT_INTERACTIONS_PROTOCOL.md and exact executable config configs/e3_8_compact_interactions.json. Later engineering fixes/tests/viewer text are committed with results; scientific coefficients and protocol remain frozen.

## 1. Compact observation–support interaction: implemented and executed

compact_interactions.py provides ONE versioned builder: compact_observation_support_v1. Additive=[1,z6,c2] has9 coefficients; interaction appends12 z×c products,21 coefficients. z is the existing six-coordinate padded normalized/tanh observation; c is E3.7's two nonconstant source-transition summaries. Constant action coverage and repeated strategy-descriptor coordinates are dropped. The414-value provenance/design container never becomes a414-parameter learner.

Existing AdvantagePredictor, ridge1, fit-only RMS, source-normalization and blocked-reset host are reused. Compression changes effective regularization relative to192 repeated-coordinate features; equal numeric ridge is NOT equal effective capacity. Compact additive and interaction share the same first9 coordinates/RMS; interaction has12 additional parameters.

Exactly36 permitted E3.4 training pairs,9 folds,32 fit/4 query rows per fold, two existing models/family. Both representations have19 paired within-model training-feature permutations, no label/model-mean shuffling. No closed E3.4 evaluation parsing. Known model means are computed from eight fit resets, never the query. Source support32 rows from four pinned TRAIN arrays;4 descriptor least-squares calls, no neural fits.

Primary screen required >=1-point interaction-minus-model-mean FAMILY return gain in both families, strict positive gains in all four models, and family interaction return no worse than compact additive. Prediction MAE and permutation ranks support interpretation, not hidden primary gates. Result **compact_interaction_selection_not_established**, both family rules fail.

### Family cached selection results

Pendulum: model mean−356.130684; compact additive−342.388155; interaction−366.748053. Additive-minus-mean+13.742529; interaction-minus-mean **−10.617369**; interaction-minus-additive−24.359898.

Acrobot: mean−293.983034; additive−293.111743; interaction−293.517227. Additive-minus-mean+0.871291; interaction-minus-mean **+0.465807**; interaction-minus-additive−0.405483.

These are out-of-fold choices scored on cached TRAINING returns, not newly executed control episodes. Additive's positive means are retained but not posthoc promoted: its model consistency also fails. Same36 inspected training pairs cannot establish independent confirmation.

### Model-specific useful and harmful corrections

- Pendulum0: additive gain−0.104935; interaction−0.117774 versus means. Interaction overrides1/9 choices,0 helpful/1 harmful; summed helpful return0, harmful−1.059970.
- Pendulum1: additive+27.589993; interaction−21.116964. Interaction overrides4/9,1 helpful/3 harmful; sums+248.309938/−438.362616.
- Acrobot0: additive+2.754487; interaction+5.012918. Interaction overrides5/9,5 helpful/0 harmful; sums+45.116262/0.
- Acrobot1: additive−1.011906; interaction−4.081304. Interaction overrides7/9,2 helpful/5 harmful; sums+48.566227/−85.297961.

One local positive model is not a cross-model selection success. Counts alone conceal asymmetric mistake costs; gain/loss magnitudes are reported. Nine-reset averaging explains why summed gains differ from per-model means.

### Prediction and permutation diagnostics

Pendulum advantage MAE: mean202.678198, additive220.994051, interaction246.538626. Acrobot16.110576,21.515681,27.940486. Interaction MAE is worse than mean in all four models. Additive improves Pendulum1 MAE by20.010400 (~7.75%) but harms the other three. Do not equate lower error in one model with reliable decision learning.

Unpermuted interaction MAE beats2/19,13/19,19/19 and14/19 corresponding permutations for Pendulum0/1 and Acrobot0/1. Acrobot0's strong descriptive permutation rank coexists with worse magnitude error than means. These ranks are not p-values; no independent-model inference from permutations/folds. Regret reduction equals cached return gain, and two-arm sign/ranking accuracy are dependent evidence.

Within each source model, context remains static: additive centered rank3(Pendulum)/6(Acrobot); interaction has more varying coordinates9/18 but the same within-model ranks3/6. Bilinear features allow different pooled-model slopes, not new within-model observations. This failure does not prove absence of all usable context information, but ends this registered representation test. Shared fits/two pretrained models per family do not justify confidence intervals, general control transfer, learning-to-learn or AGI.

## 2. Episode-local context: implemented, contract-tested

core/episode_context.py supplies observe(observation,action,next_observation,reward), features(), reset_episode(). Rolling window<=128, action-conditioned changes, observed reward/history statistics, evidence counts and optional pre-action prediction-error registration. Arrays are copied; context is reset across episodes; source context remains separate. Continuity, episode/step identity, finite values and exact predecision-prefix bounds are enforced.

from_cached_prefix rejects future/extra rows. No current-episode context is inferred from the future full trajectories behind reset-level return labels. No episode-context performance experiment was run. Trusted recorder chronology still needs environment-host attestation, not arbitrary caller-provided labels.

## 3. Planner-specific evidence: implemented, synthetic contract-tested

planner_evidence.py sits alongside existing planner_adapter.score_open_loop, reusing RandomShootingMPC scoring and ReservationLedger. It accepts exactly incumbent/challenger proposal sets with identical horizon/candidate shape, common observation and reward function. Reserves each model call before dispatch; validates finite states/termination forecasts; logs actions, trajectories, scores and actual imagined-row costs; checks caller-supplied frozen state/context fingerprint.

These are forecast inputs, NEVER observed return feedback. Different internal horizon maxima are not compared. Proposal generation costs are additional and must be separately charged by a future host. evidence_disagreement computes raw same-action forecast sensitivity, explicitly not calibrated failure probability. No learned-model inference is run for this milestone; tests use FakeStepModel only. No claim of cheap strategy selection after secretly executing the entire catalogue.

Remaining production obligation: trusted fingerprint/accounting callback, registered reward definition and reviewed worker. Pure Python contracts do not sandbox a hostile generated model or prove a caller's network-forward declaration.

## 4. Fresh-study runner: implemented coordinator; production collection blocked

staged_study.py separates fit_source, frozen recipe hash, adapt_support and evaluate. It rejects unregistered/unauthorized studies before callbacks, closed seeds, missing/unpaired conditions, mismatched probes/horizons, incomplete/invalid resource receipts and recipe/context mutation. SourcePrior uses training means for known source models and source-family prior for unfamiliar models; no true target mean input.

Shared8-step probe is charged once physically using an existing-ledger receipt, reused logically across conditions; each remaining192-step evaluation is separately charged and its return reported alongside probe and full-accounted return. Complete accounting is not “baseline from reset versus selector after8 free steps.” Production worker must restore/attest the same probe endpoint and enforce per-call CPU/model caps. Interrupted execution is consumed once, with partial rows/pending-case snapshot; trusted pending ledger must be settled externally.

configs/fresh_contextual_selection_design.json remains registered=false/authorized=false, cases empty, no fresh numeric seed registration/allocation. scripts/run_fresh_contextual_study.py was actually invoked: exit2, BLOCKED fresh_collection_not_registered_or_authorized, collection=false. Its gate is intentional. The coordinator executes end-to-end against an authored host fixture, including392 logical fixture environment-step receipts for one shared probe and two192-step conditions; these are NOT real simulator interactions.

The real environment worker, independent-data protocol, seed/resource review and frozen scientifically selected recipe are still missing. This is not a completed fresh-control study. E3.4 evaluation remains closed; E2.17 grant is not reused.

## 5. Structural parent–child mutation credit: implemented opt-in

The SAME StrategyGenerator gains mutation_credit=True and observe_mutation. Accepts only single structural additions to a parent leaf under exactly matched context/reset/planner seed/horizon/cap, observed full-policy TRAINING outcomes and positive measured costs. Forecast/final/unmatched/replayed feedback is rejected. Parent, child, context, raw gain, cost and event provenance are journaled.

Credit=tanh((child_return−parent_return)/registered_return_scale)/(1+paired_CPU_seconds); mean credit by switch/rank_blend produces softmax kind probabilities used by later propose calls. The leaves receive NO credit through this new path. Historical default/coarse update stays unchanged. Scale100 is fixed for authored examples, not tuned to scientific outcomes. Real studies must register family reward units/scales before feedback.

The deterministic example changes switch probability0.5→0.653546 from one positive authored pair; paired leaf-proposer weights remain unchanged. This proves that structural feedback can affect proposal preferences; it does not prove useful environment discovery or promotion. The independent development-promotion/rollback contracts remain necessary; training gain alone does not replace an incumbent.

## 6. Bounded continual task stream: implemented and fixture-tested

continual_state.TaskStream reuses StrategyGenerator/AdaptiveProposer, Journal and the EXISTING meta.controller.EpsilonGreedyController statistics. The adapter never calls its architecture-mutating propose method. No parallel RL, memory database or unrestricted self-modification engine is created; ContextualStrategyMemory remains the established task-memory implementation.

A→B→A→C, persistent/reset/shuffled preference controls and adaptive/random/fixed schedules are executable. Reset controls archive generator journals rather than erase attempt history. Reward is observed return improvement per measured CPU, not prediction error. Zero-gain exploration stops rather than treat noise as endless opportunity; total choices are bounded. Physical work remains the trusted ReservationLedger host's responsibility.

scripts/demo_learning_interfaces.py saves authored non-scientific illustrations. Persistent/adaptive authored gain6, random2, fixed7; reset/adaptive4; shuffled/adaptive8. These rankings come from an explicitly authored payoff/cost table, not environment measurements. A simple fixed schedule beats the adaptive one in this illustration; shuffled memory can also win. No synthetic “continual learning established” claim. Genuine transfer, forgetting, recovery curves and efficient experimental choices require a real persistent-feedback study.

## 7. NEXUS Learning Lab: working offline replay

learning_lab.py plus scripts/build_learning_lab_replay.py generate artifacts/nexus_learning_lab.html. The read-only adapter requires a complete verified result and matching result/frozen-file hashes. Viewer shows108 source-training rows (36 contexts×3 methods), predicted versus observed advantage, selected controller, cached return/regret and mistakes, with family/method filters. Different family reward scales are explicit. Mutation lineage/task-memory fixtures are separate and prominently labeled synthetic.

No evaluator, model training, live environment or network calls in the viewer. Serialized data and engineering events are escaped. Node syntax and mocked-DOM execution checked:108 rows initially,54 Pendulum rows,18 Pendulum interaction rows after filters. This checks script behavior; a real-browser visual/accessibility audit has not been performed. The local HTML opens directly; no paid hosting/service or commercial-demand claim.

## Execution, audit and reproducibility

Registered experiment:360 ridge fits+4 source descriptor LS; wall0.408135417s, CPU0.405110s. Independent verifier:0 ridge fits,4 explicit LS recomputations,0.385980583s. Combined charged research time0.794116s. No new real interactions, imagined transitions or neural execution in this registered study. Synthetic interface forecasts/receipts are separately labeled engineering fixtures, not added real-world experience.

Session ledger carried785.453092043025→**786.2472080430296 used /2813.75279195697 remaining**. No retries, reset or consumed-grant reuse. Local Python3.13.5/NumPy2.5.4; BLAS/OMP/VECLIB threads each1. No fresh simulator collection, checkpoint modification or main merge.

Config SHA0556fb9a8c4bbb929a45b63e939c1029437b11a0bab2e90930e90c51b4912caa; protocol e862faa8bdc54bae7f4950e41d65e43a62675ece07ada273eb10731bb7173e8b. Capture02b05a00e5b605b7c8e56277e3aeffd213cf613e01ce48333937840b69f76d5e; frozen folds8ec283b253c446155096e270be9ab576f9bf21a00363ab9cf2a8b9d5bc1fbc78. Full code/source-prefix/data/normalizer hashes and receipts are in e3_8 artifacts.

Independent audit verified all360 normal equations/predictions,36 queries and362 pre-existing JSON bytes. It recomputes source LS rather than silently calling the entire audit fit-free. Historical E3.7 preflight incident stays preserved; no repeat of its learned-inference regression occurred here. Unrelated untracked adapters remain excluded.

Pre-execution relevant suite476 passed in10.27s; earlier focused53 passed in2.01s. Final command/counts plus viewer/gate checks are in artifacts/e3_8_test_report.json. Tests cover hidden/outcome boundary, context chronology/freeze/reset, pre-call reservations and failed-cost charges, missing result cells, mutation feedback/provenance/duplicates, memory controls, fresh prior/gate/pairing and offline replay. No full historical-suite claim.

Final relevant suite: **478 passed in10.65s**, including saved no-fit coefficient replay and a synthetic scoring test that accepts consistent positive selection but rejects a failed model. The original historical artifact paths remain unchanged.

## One next scientific milestone

**Register and audit one budget-matched fresh-feedback study of candidate-specific planner evidence before further representation selection.** First bind/review the existing metered environment worker and seed/probe/cost rules, freeze the evidence extractor and baselines, then consider a bounded run under standing authority. Current source-bank interaction failed; do not continue another dozen feature variants or promote compact additive from these inspected means. Neither source fitting nor interfaces alone demonstrates reliable autonomous learning.
