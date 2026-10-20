# NEXUS hypothesis register (V0.5–V0.8.9)

## Seed task-blocked cumulative learning — source screen FAILED

From5235599: curve MSE .187597 learned, .188183 source-trained static,
.189456 fixed cumulative, .187016 replay and .184388 bounded fixed. Learned
gain over static .31%, below5%; replay/bounded point differences favor those
controls. Retention passed. Three independent update-rule initialization/order
seeds, source tasks aggregated first, ONE frozen feature extractor. Narrow
conditional seed intervals do not estimate new-task/world-model uncertainty.
No fresh validation, actual-control or general learning-to-learn claim.

## Seed bounded correction — source stabilization PASSED; advancement FAILED

From269bcb6, source curve MSE .183824 versus unchanged learned .212504,
13.5% reduction, paired benefit [.004901,.052457], retention improved. Replay
.187213: only 1.81% advantage with interval including zero; fails 5% screen.
Fixed bounded .185384: learned-specific improvement .84%, below 5% despite a
positive exploratory interval. Reused source tasks, one frozen core; generic
stabilization does not establish learned-learning advantage. No promotion.
See NEXUS_SEED_BOUNDED_CORRECTION_RESULTS.md.

## Seed first-update broad-harm diagnostic — NOT_SUPPORTED

Source-only registered screen required medianlearned/replaynormratio>2 and
first-query harm on>=8/12tasks. Actual12.5538×and5/12:screenfails. Meanfirst
querychange+.032766[-.037982,+.103514],conditionalreusedsourcebank,onecore.
Large steps alone do not establish excessive-update causation. Laterprefix
instability is descriptive. No fresh generalization or learning-to-learn claim.
Protocol/code9c379aa;NEXUS_SEED_UPDATE_DIAGNOSIS_RESULTS.md.

## Seed nonlinear-feature learned update rule — registered screen FAILED

From73d1dcd: mean1/2/4/8-example MSE .170873 learned, .171423 source-trained
static, .172414 fixed, .128930 replay, .142419 none. Static reduction only .32%,
paired95% interval[-.000201,+.001301] includes0. Ten-percent intersection rule
fails. Retention passes; actual learned/static/fixed control actions identical;
return non-regression bound not established. One frozen core, outer seeds
averaged within eight task streams. No general learning-to-learn claim.
See NEXUS_SEED_NONLINEAR_LEARNING_RESULTS.md; this audit is closed.

## Seed frozen spatial-transfer screen passed,conditional on one core

Readout-minus-frozen return+1.411667[1.188644,1.634690],goal gain+.40625.
All registered conditions pass. Greedy stronger; diagonal-vs-random negative
point estimate,inconclusive interval. No meta-learning or general-control claim.
Learning-rule improvement on nonlinear frozen features remains untested.

## Latest Seed hypotheses

H-action-nonlinear: passed fresh authored development screen,not general
control. Meanregret .105208 vs .78125; goals64.58% vs12.5%; greedy100%.
H-future-edit-credit: no strongest-baseline gain; adaptive .006917 ties
historical-best on the held-out source bank. No general L2L established.
Rank4: implementation/tests only,no efficacy result. Historical failures closed.

## Seed fresh learning and actions — both registered gates FAILED

H-learning required10%curve-MSE gain versus fixed/scaled replay/none/neutral,
positive paired intervals and retention bound. Learned.181507 loses to replay
.165435; replay-minus-learned -.016072[-.029590,-.002555]. Fixed comparison
inconclusive. H-actions requires regret and goal gains plus positive returns
versus fixed/frozen: fails. Learned/fixed goals9.375%, frozen12.5%, grid100%.
Selector utility fails; language is finite/supplied and has no neural advantage.
No cross-domain run after failure. One frozen core, n8 new task-stream units,
three optimizer-order seeds averaged within streams. All intervals exploratory.


## Seed H-plasticity — structure functional; improvement NOT ESTABLISHED

Predeclared10%less held-out source learning-curve MSE versus BOTH fixed protected
and replay,no worse forgetting. Actual0.3637%versus protected,pairedreduction
.0004665[-.0011784,+.0021114];fails. Replay unstable,not a strong tuned comparator.
Three optimizer-order seeds share one frozen decoder. Local math,meta-gradients,
source isolation,real-label updates,skill edits and GUI persistence pass functional
tests;these are not independent scientific evidence of transferable learning.
Precommitbd1f8b3;see NEXUS_SEED_MEMORY_AWARE_RESULTS.md. No new simulator data.


## Seed H-contract — correctness passed; practical improvement screen FAILED

Precommit d4e6ff3;3 paired scratch seeds per original recipe,legacy vs aligned
plus untrained,pruning on/off. Regret reduction tanh+.00521[-.01720,.02762],
ReLU-.00104[-.00552,.00344]. All control-gain/pruning CIs include0. Source memory,
V3 semantics and GUI mutation corrected; no reliable decision gain established.
Separate pixel/structured ablation is weak; parser8/24. Neural known37-grammar
proposal helps over8-candidate symbolic cap, loses to full37 reference; not new
concept-language learning. Preserve old outcomes and unrun residual head.

## Seed grounded H-engineering / H-development

One locked authored pilot from fd957655ae1acde41d55d05e10e9b5c3dcfbf3cf.
Functional multimodal/RSSM/retrieval/proposal/planning/question/meta/language
paths verified. Learned capability remains mixed: tanh MPC 0/4 goals, ReLU3/4,
greedy4/4; one seed/config, no inferential superiority claim. Trace accuracy
1/44 and3/44, trained GUI concept proposal rejected. Lower loss/gradients do
not prove useful memory, meta-learning or AGI. Raw results finite/complete,
old incomplete Seed comparison unchanged. See SEED_GROUNDED_RESULTS.

## Seed H-teach / H-question — INCOMPLETE, not established

Locked0b9ae69: finite-grammar teaching versus memorization, disagreement versus
random questions,3labels per semantic task/condition. Single authored development
capture hit10000predicate-test cap,14/16cells retained. Three complete paired
tasks:1/6correct disagreement programs,0/6random/memorization,6/6privileged oracle.
These descriptive prefix counts cannot establish sample efficiency; negation
disagreement/oracle cells missing,2interrupted labels charged without full records.
Functional full-evidence teaching/correction/restart tests pass independently.
No general-language, cross-domain, neural, control or learning-to-learn claim.

## E4 short-budget same-PPO learning — registered screen failed

Three independent scratch learner seeds/family; compare new-reset episode
means with random and fixed, family-native units. Both paired95% lower bounds
must exceed0 and mean margins25(CartPole/Pendulum)/5(others); all five required.
Complete run passes0/5 family screens. MCC-vs-random positive but fixed remains
inconclusive; Acrobot-vs-random negative. Not invalid/incomplete and not proof
PPO cannot learn. No generality, transfer, continual-learning or L2L claim.
Posthoc13/15 greedy policies use a single action on recorded evaluation; this
does not identify a cause. See E4_PPO_BENCHMARK_RESULTS and raw artifacts.

## E4 foundation — technical contracts passed, scientific hypothesis untested

Shared five-family algorithm bindings and bounded modifications are engineering
capabilities.945 tests and80 smoke steps establish API compatibility/replay and
budget accounting only. No scratch-learning, transfer, architecture advantage,
continual-learning or self-improvement hypothesis was evaluated. Proposed
five-family PPO scratch comparison requires separate full registration and
allocation; F v2 and all closed negative outcomes remain unchanged.

## F v2 — assignment primary, estimation secondary; both untested

Primary remains blocked-minus-random raw-average selection,1-point BOTH-family
screen across2 models/family. New prespecified paired-parent-gain secondary
tests estimation separately on the same observed feedback, with parent score0
and parent-first ties. Unadjusted secondary intervals cannot upgrade primary.
Observe parent-return group offsets and changed choices; neither matching nor
training gains prove fresh-return improvement. Corrected source-only budget
bound is1622400 calls/forwards, not the unsafe1440000 estimate. No allocation,
scientific registration or run. Repeatability/transfer remain future questions.

## E3.12F engineering update — hypothesis remains untested

Runtime binding and independent arithmetic export now exist on the same
scientific stack. Authored fixture callbacks verify ordering, feedback
isolation, masks, resource receipts and model-level aggregation only.
No new scientific outcome or protocol lock. The original reset-blocking
hypothesis/one-point BOTH-family screen remain unchanged. Numerical fresh
registration and collection authorization are still absent; see
NEXUS_E3_12F_RUNNER_INTEGRATION.md.

## E3.12F — public reset blocking, proposed and untested

Hypothesis: pre-feedback observation-based pairing improves held-out raw
parent-inclusive selection versus random balanced exploration at equal revealed
feedback budgets. Null: public proximity does not remove relevant offsets or
the selector remains unreliable. Primary proposed blocked-minus-random query
return; n2 pretrained models/family, df1 exploratory intervals, >=1-point gain
and positive lower bound in both families. Shared physical panels are not
independent replications or demonstrated online interaction savings. Pure
adapter/tests complete; no scientific protocol lock/registration/execution.
E3.12E's algebraic sign discrepancy motivates this question, not a proven
causal mechanism. See NEXUS_E3_12F_RESET_BLOCKED_PREPARATION.md.

## E3.12E — exploratory training-estimate diagnosis, not policy validation

Observed pooled-versus-matched comparison offsets can reverse parent-advantage
signs (both selected Pendulum arms do). Raw choices are nevertheless stable
under every registered deletion, so a single removed observation does not
explain their ordering in this sample. This is not systematic-bias proof or
query-performance attribution. Existing credit rules differ on two Acrobot0
balanced-deletion cases but no fresh-task utility is scored. No learner or
rule promoted. See E3.12E protocol/results; D's screen remains failed/closed.

## Completed — E3.12D parent-aware screen failed

H: adding parent to raw-mean selection avoids harmful changes while preserving
fresh-query improvement. Locked a5d13d768; complete valid grid, no parent
choices0/4. Primary versus two-child0 [0,0] both families; equal credit choices.
Uniform+175.087 [−412.671,762.845] Pendulum/+4.794 [−71.914,81.502] Acrobot.
Both screens and parent noninferiority fail. This configuration does not
establish useful parent retention. Parent availability alone does not resolve
reset-difficulty confounding of unpaired raw means. Four observations/child,
two models/family; no generalization claim. No new rule fitted to D queries.
Report NEXUS_E3_12D_PARENT_RETENTION_RESULTS.md; all earlier results preserved.

## Proposed — parent-inclusive limited-feedback selection, untested

H: the raw-mean choice over parent/switch/rank_blend reduces harmful changes
while retaining useful fresh-query gains versus a forced two-child choice.
Implemented, deterministic tests pass; no new scientific evidence. D proposal
requires fresh seeds/commit/allocation before execution; never score the new
rule on closed C queries. Durable persistence and training-incumbent progress
are functional capabilities, not established retention or learning-to-learn.
See NEXUS_PARENT_RETENTION_DEVELOPMENT.md for proposed thresholds and costs.

## Latest — E3.12C partial feedback selection unestablished

H: eight single-child exploration trials permit useful frozen selection.
Precommitted9ae94386a84ae5863776cba20f0420679711e051; four observed outcomes/
operator/model. Primary raw mean versus uniform+87.562 [−392.932,568.056]
Pendulum,+8.283 [−123.217,139.783] Acrobot; both interval screens fail. Credit
vs uniform−37.816/+10.349; no superiority over simple means. Parent-relative
and absolute training estimates disagree for Pendulum0; four-point groups have
different parent means. Descriptive imbalance, not isolated causation. Paired-
gain guard retains parent0/4; a simple three-way raw-average rule was not tested.
Complete valid grid/frozen/meter checks pass;764 tests. Closed C cannot be
relabeled as the new parent-inclusive experiment requested afterward.

## Latest — E3.12B operator headroom visible, overall selection unestablished

H-stable: source-training operator preference transfers to fresh episode
returns. Precommitted570d10184354901291f2903eb4e8de20203e9839, full paired
feedback, two independent models/family. Primary training-mean minus uniform
expected: Pendulum+119.727 [3.139,236.315], Acrobot+7.298 [−34.703,49.298].
Both-family interval rule fails. Finite-suite hindsight headroom>=5 both
families, not proof of learnability. H-credit: existing cost/tanh credit offers
no advantage over raw means; identical selected operators all4 models. Oracle,
uniform/regret/winner metrics derive from same paired paths, not independent
evidence. Query ordering differs between models and sometimes between resets;
observed means preserve training sign in all4. No causal attribution of E3.12's
failure to one change: feedback coverage and exploitation rule both differ.
No new-physics/continual learning/L2L claim; see E3.12B report. Closed seeds stay
closed. Next partial-feedback explore-then-commit study is a separate proposal.

## Latest — E3.12 useful mutation learning not established

H: measured parent–child return credit improves fresh-episode structural
proposals versus uniform choice. Precommitted629c8d2cbb30632acab2d3e633b64fc19cccf46a;
two independently pretrained models/family; train8/query4 contexts each.
Both families fail mean>=1/both-model-positive/CI-lower>0 screen:0 [0,0].
All48 sampled choices unchanged despite32 preference updates. Mechanism
connected, utility unresolved; empirical zero interval does not establish
population equality. Acrobot sampled mixtures underperform parent by−3.407,
exploratory df1. No general learning or new-physics claim. Complete finite
grid and exact meter/frozen checks pass. Closed outcomes must not be retuned.
See NEXUS_E3_12_MUTATION_CONTROL_RESULTS.md; next balanced operator audit only
proposed, not executed or allocated.

## Latest — bounded cycle mechanics demonstrated; utility unestablished

Authored-fixture E3.12/E3.13/E3.14/E4.0/E4.1 screens all fail in132 paired
method/bank runs. Actual feedback changes proposal preferences but mutation
transfer gain−.0164 and memory return-A gain−.0479 versus controls; intervals
include0. No real-environment learning claim. Existing E3.11D failed longer
forecast test is not rerun as E3.11C. Next one proposed real measured parent–child
credit comparison, not a new success label. See NEXUS_BOUNDED_LEARNING_CYCLE.md.

## Latest — E3.11D longer forecast usefulness not established

64 versus16-prefix forecast comparison fails both family practical screens.
Primary192-step direction accuracy unchanged Pendulum, lower Acrobot; selected
return−13.777/−6.953 with exploratory df1 intervals including0. n=2 existing
pretrained models/family, no extra episode replications. Extending forecasts
does not establish a remedy. Model compounding versus imagined-action divergence
remains unresolved; next proposed source-only action-matched replay, not run.
See NEXUS_E3_11D_HORIZON_CALIBRATION_RESULTS.md. No prior results reinterpreted.

## Latest — E3.11B forecast usefulness not established

Complete precommitted fresh calibration fails both family intersection screens.
Direction accuracy versus means:75% vs87.5% Pendulum,62.5% vs62.5% Acrobot.
Return contrasts−1.558/+1.570, both exploratory paired model intervals include0.
Numerical headroom is not enough; lower magnitude error can leave decisions
unimproved. n=2 pretrained models/family. Next proposed horizon-calibration
question, not executed; no generalization/L2L claim. Ledger948.6320812930051/
2651.3679187069947. Report NEXUS_E3_11B_FORECAST_CALIBRATION_RESULTS.md.

## Latest — proposed E3.11B actual-return calibration, not executed

Fixed controller-specific16-step forecasts predict the direction of192-step
actual strategy advantage better than common-tail and legitimate training-model
means. Proposed practical point screen>=0.125 accuracy gain versus both and
positive selected-return gain per family without negative model gains. n=2
models/family, exploratory paired intervals; no confirmation claim. No numerical
seed registration, allocation or execution; real metered worker pending. See
NEXUS_E3_11B_FORECAST_CALIBRATION_PROTOCOL.md. Later E3.11C–E4.0 conditional.

## Latest — H-headroom visible, utility unknown (E3.11A)

Registered source-only forecast screen passes: different later actions/scores
in6/7 Pendulum and5/5 Acrobot equal-first-action contexts. Common-tail scores
identical. All16 source contexts retained,0 real outcomes or learning updates.
This tests expressive headroom, not accuracy, strategy ranking or return gain.
No independent context replications or generalization inference. Next separately
lock fresh paired-return forecast calibration; do not fit on closed E3.11 data.
Report NEXUS_E3_11A_ROLLOUT_HEADROOM_RESULTS.md.

## Latest — H-evidence post-probe selection not established (E3.11)

Precommitted fresh-source comparison complete: contextual-minus-model-mean
return0 for both families and all4 models, identical choices16/16. Registered
>=1 family/all-model-positive screen fails. Zero-width paired intervals are
structural cached-path identity, not proof of population equivalence. Two
models/family only. First-action/common-tail evidence collapses15/16 held-out
contexts; normalized probe residuals vary. No causal proof of sole failure
mechanism. Next separately lock a controller-specific imagined-rollout headroom
audit on permitted source observations; no fitting on these closed evaluation
episodes. See NEXUS_E3_11_POST_PROBE_RESULTS.md. Historical hypotheses unchanged.

## Latest — E3.10 engineering equivalence verified; utility untested

Metered evidence equals direct existing scoring on four frozen source MLPs,
two original observations each.512 observed forwards/8192 imagined rows,
0 real steps or optimization. No difference in scores/rankings/selected
candidate/states/termination. Reward replay and frozen-file checks pass.
This validates the inference instrumentation only. H-planner-evidence useful
return selection remains unregistered/untested; E3.8 negative result preserved.
Next E3.11 fresh post-probe comparison, not E3.12–14 simultaneous claims.

## Latest — E3.9 readiness is engineering evidence only

No new scientific hypothesis tested. H-planner-evidence selection utility
remains untested/unregistered. Four checkpoint/eight source file hashes match,
but fresh study blocked pending metered host, independent grid/seed rules,
compute fairness and allocation.503 relevant tests establish boundary behavior
only. Existing E3.8 negative result remains unchanged; no more36-pair tuning.
Report NEXUS_E3_9_PLANNER_EVIDENCE_READINESS.md. Ledger unchanged.

## Latest — H-compact-interaction selection not established

E3.8 compact interaction failed its registered source-training selection screen.
Native additive9/interaction21 coefficients reuse SAME ridge1; compression
changes effective penalty versus historical192. Interaction-minus-model-mean
cached returns Pendulum−10.617369/Acrobot+0.465807; inconsistent model gains,
no promotion or more36-pair feature sweeps. Additive+13.742529/+0.871291 is
retained as exploratory, not selected after the fact.360 ridge fits/4 source
LS;0.408135s+0.385981s audit,0 new scientific real/imagined/neural work.
Execution21ba36cdda5133bb29c7d955b0db151300834aad;362 prior JSON preserved.
Ledger786.2472080430296/2813.75279195697. EpisodeContext, common-scoring
budgeted planner evidence, gated staged study, opt-in parent-child mutation
credit in StrategyGenerator, bounded TaskStream reusing existing meta controller,
and offline Learning Lab are implemented/fixture-tested. They are engineering
interfaces, not environment-learning successes. Fresh collection remains
unregistered/unauthorized; reviewed worker binding and independent protocol
missing. Synthetic fixtures are labeled, including fixed beating adaptive.
One next milestone: register/audit budget-matched fresh-feedback planner-
evidence study, not more selection on inspected36 pairs. Report
NEXUS_LEARNING_MILESTONES_IMPLEMENTATION.md. Closed splits/H17/main unchanged.

## Latest — H-transition not established (E3.7)

E3.7 actual transition-evidence ablation completed; no improvement established.
Original32-row source support yields normalized delta/linear residual/action
coverage in place of schema slots, same192 coefficients/ridge1. Transition
MAE269.204 versus mean202.678 Pendulum,20.212 versus16.111 Acrobot; worse
than means all four models. Cached return gain−17.757927/−0.531026. All
model screens fail. Static support adds no within-model variation; no proof
of feature impossibility.360 ridge fits+4 descriptor LS,0 new real/imagined/
neural work in registered run;0.493148s+0.330873s audit (4 LS/0 ridge fits).
Execution95c206d87aaa60696e1774e899fcebe10c74e253;357 pre-existing JSON
verified. Before lock, legacy regressions wrote six historical paths and ran
one unmetered learned-inference benchmark; archived outputs/restored originals,
isolated seven writer tests, excluded inference test from source-only suite,
charged10.44s. See e3_7_preflight_recovery.json, not scientific evidence.
Ledger785.453092043025 used/2814.546907956975 remaining. Closed E3.4/E2.17/
H17 boundaries unchanged. One next question: prespecified observation×support
interaction under fixed learner/budget; proposed only, not implemented or
allocated. Report NEXUS_E3_7_TRANSITION_EVIDENCE_RESULTS.md.

## Latest — E3.6 H-feature not established

E3.6 training-only feature audit completed: full and observation-only MAE
worse than model means in all four existing pretrained models. No feature
group clears >=5% reduction/all-model and18/19 permutation screen. Existing
support_stats[:3] are schema (obs dim/action count/episode length), NOT
transition evidence; support_schema/anchor groups have zero within-model
variation and reproduce means. Full MAE202.678→267.827 Pendulum,16.111→18.327
Acrobot; observation240.075/19.645.720 ridge fits,0 real/imagined/neural work;
0.510764s plus0.314667s zero-fit audit;351 prior JSON unchanged. Execution
ebdeddc9914eed84f4bcba7f21321600d7f7fb9c. Ledger774.1890710430174 used/
2825.8109289569825 remaining. No proof of information-theoretic absence.
One next proposal: fixed-dimension true-transition-statistic representation
ablation with the same learner/training boundary, not implemented/allocated/
executed. No new strategies, model or regularization changes. Closed E3.4,
consumed E2.17 and blocked H17 unchanged. Report NEXUS_E3_6_FEATURE_INFORMATIVENESS_RESULTS.md.

## Latest — E3.5 H-residual not established

Predeclared model-mean-plus-context correction fails both family screens:
return gain−8.479216 Pendulum/+0.514255 Acrobot; model gains−0.104935/
−16.853497 and+5.637196/−4.608687. Magnitude MAE worse than model means
both. Valid blocked-reset training-only result, not independent confirmation.
Do not infer feature impossibility or general learning. Next hypothesis:
current predecision features contain reproducible within-model advantage
signal; proposed source-only audit, no execution. Report
NEXUS_E3_5_RESIDUAL_ADVANTAGE_RESULTS.md. Earlier entries remain historical.

## Latest — E3.4 feedback-coverage primary and broad screens fail

Fresh nested feedback3/6/9 with unchanged features/ridge/controllers. Primary9
return gain versus model means: Pendulum−111.942, Acrobot+3.498 (models
−0.090/+7.086), so neither family passes the full point rule. More feedback
improves Acrobot return9−3 by5.164, leaves Pendulum predictor return unchanged
and improves its mean baseline. No general learning success, budget6 promotion,
or inference across only2 source models/family. Report
`NEXUS_E3_4_FEEDBACK_COVERAGE_RESULTS.md`; evaluation is closed. Next hypothesis:
a fixed residual correction can retain useful model-mean priors; training-only
blocked-reset test proposed, not executed. No bigger model justified here.

## Latest — E3.3 feature-signal intersection screen not established

Training-only three-fold audit, eight fit pairs/four query pairs per fold:
predictor minus model-mean return Pendulum−0.833, Acrobot+11.569. Both Acrobot
models gain, but magnitude MAE worsens both families; preregistered screen
fails. Do not infer no information or promote source selection to confirmation.
Fold-only anchor means/RMS prevent held-out label leakage; all E3.2 evaluation
stays closed. n=2 existing models/family; folds are dependent, no p-values.
Report `NEXUS_E3_3_TRAINING_FEEDBACK_RESULTS.md`. Next proposed hypothesis is
feedback-coverage scaling at fixed representation/regularization, not executed.

## Latest — E3.2 quality learning on fresh full-return feedback: screen failed

Existing ridge/descriptor predictor does not beat model means meaningfully on
both known source families: Pendulum−31.912, Acrobot+0.317. It beats shuffled
labels but loses to stronger simple baselines. No overall quality-learning or
generalization success; no inference across only two pretrained models/family.
Twelve training pairs fit two predictors before sixteen evaluation choices.
Both complete fixed controller trajectories were collected per reset; no
bandit-efficiency claim. Report `NEXUS_E3_2_RETURN_FEEDBACK_RESULTS.md`.
Next hypothesis: existing features add predictive signal under training-only
blocked-reset cross-validation; not executed and no closed evaluation reuse.

## Latest — E3.1 evaluator sufficiency separated from learner quality

Old frozen-model neutral-tail headroom remains0/16, with342 strategies collapsing
to1–3 first-action labels per state. Existing full-policy returns discriminate
fixed compositions on familiar source models, but no autonomous discovery is
demonstrated. Old A/C/D/E learning failures remain unchanged. New calibration
H-state direction fails descriptively: model0 angular error is lower, while raw
overall/cosine/sine errors are higher. H-stop has a small aggregate Brier
difference with visitor-stratum sign reversals, no causal inference or positive
class calibration. Recorded future-query errors must not be predictor features.
Report `NEXUS_E3_1_LEARNED_MODEL_HEADROOM.md`; no new collection or fitting.

## Latest — H-model crossed-reset descriptive split supported on finite source set

Two unchanged Pendulum bundles face the same four new resets and planner streams.
Rank−successor+392.654 on model0 (3/4 positive),−130.778 on model1 (4/4 negative);
registered1-point/sign split screen passes, paired interaction+523.431. Thus
different reset blocks are insufficient to explain the split on these tested
conditions. Does not isolate weights from RMS/training data, remove later path
divergence or establish generalization. No new independent models or formal CI.
Report `NEXUS_UNIFIED_CROSSED_RESET_RESULTS.md`; all previous results unchanged.

## Latest — H-repeat source episode screen partly supported

Same frozen policies/models, fresh episodes: Acrobot rank blend beats both
anchors by>=1 point, each model positive (+15.317/+19.298 means). Descriptive
episode-direction replication passes. Pendulum harm versus successor does not
repeat as an aggregate directional screen: mean+87.762, model blocks+245.452 /
−69.928. Cross-family advantage still fails. No new model/generalization claim.
Different model reset blocks confound a causal model-quality explanation.
All contrasts retained in `NEXUS_UNIFIED_FULL_POLICY_REPLICATION_RESULTS.md`;
n=2/family, no inferential CI or learning-to-learn claim. Closed seeds preserved.

## Latest — full-policy composition source headroom is family/model dependent

Registered exploratory screen (>=1 point, both models positive versus both
anchors in both families) fails for switch and rank blend. Rank blend exceeds
both anchors on Acrobot and loses to successor on Pendulum. Full repeated
execution reveals return variation absent from the previous neutral-tail proxy;
it does not establish general improvement or useful feedback learning. All eight
contrasts reported in `NEXUS_UNIFIED_FULL_POLICY_RESULTS.md`. n=2 models/family,
no confidence or transfer claim. Closed episode seeds retained, no retuning.

## Latest — H-source-headroom not supported

Preregistered1.0-unit/4-state/2-per-family screen fails:0/16 states have
positive headroom of any size beyond forced anchors under frozen learned
model/common-neutral-continuation self-evaluation. Zero fitting/real steps;
not a control or learning hypothesis. No existing scientific outcome changed.
Report `NEXUS_UNIFIED_HEADROOM_AUDIT.md`. Need a full-policy quality target
before training another strategy selector on this source label.

## Latest — unified source-only A–E screen, only novelty B supported

A quality generalization fails: fixed MAE0.000685291 versus zero0.000314323;
common ridge0.000702215 versus paired mean0.000382788. B finite-source
behavioral novelty passes:4 action patterns beyond catalogue. C useful
feedback fails (feedback generation regret0.000228159 versus random0.000164918).
D unified strongest-baseline fails (0.000224160 versus nearest0.000150806).
E held-bundle screen fails,2/4 strict wins versus strongest pooled baseline.
All methods already find their best during anchors. Inspected source bundles,
three shared-data proposer seeds, no scientific CIs or new environment data.
No learning-to-learn or general control result. Original incomplete attempt
and all historic artifacts preserved. See `NEXUS_UNIFIED_AUTONOMOUS_LEARNING.md`.

## Latest — E2.29 receipt-contract correctness, engineering evidence only

Complete-grid, shared-reference, raw-versus-clipped and independent-bundle
arithmetic checks pass on authored fixtures. Outcomes are prescribed and no
proposer/model learns; no scientific improvement hypothesis was evaluated.
E2.17 stays inconclusive, H17 blocked and all closed outcomes unchanged.
Report `NEXUS_E2_29_RETURN_CONTRACT.md`. Next is worker integration review.

## Latest — E2.28 readiness review, no scientific hypothesis evaluated

Verdict BLOCKED_SCIENTIFIC_RUNNER_AND_PROTOCOL_GAPS. E2.27 establishes
synthetic boundary correctness, not real-return labels or a complete n=10
comparison. Forecast fixtures cannot establish useful learned proposal
transfer. No existing hypothesis is reopened, promoted or retested. Source
and artifact integrity checks are engineering evidence only. Report
`NEXUS_E2_28_METHOD_SENSITIVE_READINESS.md`; ledger unchanged.

## Latest — E2.27 prospective evaluation contract, engineering pass only

Manifest-gated frozen feedback preserves selected-planner sensitivity,
query-extreme invariance, raw/unit separation, cache fairness and hidden
training isolation in synthetic fixtures. Guarded cache hits reject bool
aliases. No learning, transfer or control hypothesis was tested. No
scientific gate is unlocked. Report `NEXUS_E2_27_FEEDBACK_INTEGRATION.md`.

## Latest — E2.26 feedback-isolation contract, engineering pass only

An opt-in frozen training-reference scale passes synthetic invariance
under opposite unobserved query extrema. Feedback, proposer weights and
choice stay equal; refitting and invalid references fail. No control,
generalization, autonomy or learning-to-learn hypothesis was evaluated.
Historical transductive fixtures remain unchanged. Report
`NEXUS_E2_26_FEEDBACK_BOUNDARY.md`.

## Latest — H-E2.25 candidate-conditioned source quality prediction fails screen

The fixed candidate/context ridge representation is worse than paired
mean, observation kernel and config-only ridge on both source families.
Pooled paired-advantage MAE0.08141 versus0.01100/0.01229/0.06289.
Identical six-receipt training information, held-bundle normalization,
260 audited query pairs. Negative, inspected-source proxy evidence;
no confidence interval, control claim, promotion or post-result tuning.
Post-run audit also finds inherited oracle min/max scaling leaks query
extrema into public anchors. Mechanical completion is not independent
evaluation; fix future normalization before scientific use.
Report `NEXUS_E2_25_PLANNER_QUALITY.md`.

## Latest — H-E2.24 evidence arbitration does not retain useful shift adaptation

Precommitted source-only rule combines paired score evidence, ESS,
context agreement, anchor residuals and source LOBO error allowance.
It preserves familiar first-free0 only by abstaining40/40 and loses
the shifted gain (0.062745 versus ungated/consensus0). No genuine
development overrides. Negative outcome; synthetic functional tests
are not adaptive-improvement evidence. FakeStep proxies, no scientific
replications or real control. Report `NEXUS_E2_24_EVIDENCE_ARBITRATION.md`.

## Latest — H-E2.23 cross-bundle recall rises; first-free falls

LOBO p95 accepts familiar neighbors the E2.22 gate refused. Hard NN
retrieve loses familiar first-free to persist (0.155 vs 0) and does
not beat ungated. Failure: planner-quality prediction. FakeStep
proxy. Not science. Report `NEXUS_E2_23_CROSS_BUNDLE_MEMORY.md`.

## Latest — H-E2.22 observation gate reuses exact matches, not stored-obs neighbors

Gated AdaptiveProposer memory changes the zero-obs first-free planner
to the shifted oracle and beats persist (0 vs 0.063). Familiar
development first-free 0 is proposer fallback, not retrieval
(inter-bundle 1.216 > gate 0.491). Shuffle harms. FakeStep proxy.
Not science. Report `NEXUS_E2_22_OBSERVATION_MEMORY.md`.

## Latest — H-core-7 residual identity memory loses to default bundle 0

One revealed MAE on E2.9 residuals. Memory matches persist-best
(dev regret 0.00061, arms 0/1) and loses to always-bundle-0 (0).
Causal pend0/pend2 and acro0/acro2 choices do not change. 8-step
clone SGD raises val MAE. Not science. Report
`NEXUS_CORE_STRATEGY_MEMORY.md`.

## Latest — H-core-6 disposable residuals do not change the winning planner

E2.9 residual `decide()` scores pick flat H=4 on every locked task.
Persist and retrieved-mean both reach first-free regret 0. Not a
memory result. Stop this catalogue line. Not science. Report
`NEXUS_CORE_STRATEGY_MEMORY.md`.

## Latest — H-core-5 persist+obs cannot use start state on FakeStepModel

A 22-weight persist wrapper with rule/horizon × observation
interactions does not change locked first-free versus 6-weight
persist and does not change choice when only the planning obs
changes. Stop this FakeStepModel line. Not science. Report
`NEXUS_CORE_STRATEGY_MEMORY.md`.

## Latest — H-core-4 retrieved-mean follows memory but loses to persist

Ridge-shrunk retrieved means change the zero-obs planner and beat
combined LinUCB on the locked shift (0.755 vs 1.0 first-free). Persist
stays better (0.188). Stored-obs development remains 0. Not science.
Report `NEXUS_CORE_STRATEGY_MEMORY.md`.

## Latest — H-core-3 observation sketch is not enough to change choose()

Planning-observation features separate stored-obs from zero-obs
descriptors and move retrieved neighbors. Combined LinUCB still
selects the stored-obs winner on a zero-obs query. Persist remains
better on the locked shift. Failure: strategy-value prediction. Not
science. Report `NEXUS_CORE_STRATEGY_MEMORY.md`.

## Latest — H-core-2 retrieval can harm decide() start-state transfer

On FakeStepModel returns, memory ties persist on stored-obs
development and has first-free regret 1.0 on zero-obs Acrobot versus
persist 0.188. Retrieve-on/off did not change the development choice.
Not a scientific result. Report `NEXUS_CORE_STRATEGY_MEMORY.md`.

## Latest — H-core-1 task-conditioned memory can change planner choice

Retrieval changes the first free catalogue choice under matched seed
and frozen weights. It does not beat persist/reset on synthetic
development regret. Inverted-successor negative transfer is not
avoided. Not a scientific result. Report
`NEXUS_CORE_STRATEGY_MEMORY.md`.

## Latest — H-e2.21 hidden scores must follow the selected planner

Fixture `decide()` scores change when the selected planner changes.
Isolation is hidden-return provenance. Not a transfer result. Report
`NEXUS_EVOLUTION2_PERSIST_RESET_SCORING.md`.

## Latest — H-e2.20 method-sensitive screen remains unauthorized

The corrected hidden loop is locked and still ungranted. Not a
transfer result. Report
`NEXUS_EVOLUTION2_PERSIST_RESET_METHOD_SENSITIVE.md`.

## Latest — H-e2.19 retained proposer memory can change planner choice

The 6-weight linear policy translates remembered feedback into a
different unconstrained or hidden selection when only weights are
cleared. Forced anchors often restore the same training argmax. Not a
transfer result. Report `NEXUS_EVOLUTION2_PERSIST_RESET_POLICY_STATE.md`.

## Latest — H-e2.18 hidden evaluation was non-identifying; repair is untested scientifically

The E2.17 zero contrast cannot identify persist versus reset. Synthetic
causal-sensitivity tests now pass. Not a transfer result. Report
`NEXUS_EVOLUTION2_PERSIST_RESET_SCIENCE.md`.

## Latest — H-e2.17 persist-versus-reset is inconclusive on n=3

Persist-minus-reset was identically 0 because hidden scores were
method-independent. Not a transfer result. Not n=10. Report
`NEXUS_EVOLUTION2_PERSIST_RESET_SCIENCE.md`.

## Latest — H-e2.16 four-role assignments validate; persist-versus-reset still unauthorized

Locked unused source/development roles match existing SHA256 digests
and stay off historical exclusion lists. The gated executor is
development-ready. Not a transfer result. Science stays blocked.
Reports `NEXUS_EVOLUTION2_PERSIST_RESET_ROLES.md` and
`NEXUS_EVOLUTION2_PERSIST_RESET_EXECUTOR.md`.

## Latest — H-e2.15 persist-versus-reset remains unauthorized after vague approval

The message did not cite the locked hash, name a holdout, or set
17280. Not a transfer result. Report
`NEXUS_EVOLUTION2_PERSIST_RESET_APPROVAL.md`.

## Latest — H-e2.14 receding planner cost is a default-obs prior, not a screen

800 stored-state decisions took 2.305 s. Not new physics. Not a
transfer result. Report `NEXUS_EVOLUTION2_PERSIST_RESET_RECEDE.md`.

## Latest — H-e2.13 persist-versus-reset budget is locked, not executed

17,280 fresh steps and 14,745,600 imagined are the locked first-screen
budget. 7680 is not granted. Not a transfer result. Report
`NEXUS_EVOLUTION2_PERSIST_RESET_BUDGET.md`.

## Latest — H-e2.12 persist-versus-reset science remains blocked after readiness audit

17,280 fresh steps would be required for a new-physics n=3 first
screen. Holdout unnamed. Not a transfer result. Report
`NEXUS_EVOLUTION2_PERSIST_RESET_READINESS.md`.

## Latest — H-e2.12 persist-versus-reset dry-run is development only

The n=3 persist/reset/random/evolution wiring runs on synthetic
fixtures. Not a transfer result. Scientific dispatch stays blocked.
Report `NEXUS_EVOLUTION2_PERSIST_RESET_DRY_RUN.md`.

## Latest — H-e2.11 persist-versus-reset is requested, not collected

n=3 persist minus reset is specified and unauthorized. Not a transfer
result. Report `NEXUS_EVOLUTION2_PERSIST_RESET_REQUEST.md`.

## Latest — H-e2.10 twelve-arm development scores are not a scientific screen

All twelve catalogue variants bind and produce development scores.
Scientific dispatch stays blocked. Holdout unnamed. Report
`NEXUS_EVOLUTION2_EVALUATOR_READINESS.md`.

## Latest — H-e2.9 six disposable residual fits are a clock, not confirmation

Cited config `277d7ba6…`, `env_cap=0`, `n_fits=6`. Wall 1.215 s. Not
v2. Not a control result. Twenty-fit cost remains unmeasured. Report
`NEXUS_EVOLUTION2_FIT_CLOCK_RESULTS.md`.

## Latest — H-e2.8 7680 persist is a development pilot, not confirmation

Cited config `325cd42b…` and `env_cap=7680`. Twelve source arrays
exist. Not v2. Not a residual fit clock. Report
`NEXUS_EVOLUTION2_SOURCE_PERSIST_7680.md`.

## Latest — H-e2.7 source persist is requested, not collected

A 7,680- or 25,600-step persist is specified and unauthorized. Not
a transfer result. Report `NEXUS_EVOLUTION2_SOURCE_PERSIST_REQUEST.md`.

## Latest — H-e2.6 execution is blocked, not collected

Bound residual checkpoints are weights-only. No source arrays can
be recovered from them. Not a transfer result. Report
`NEXUS_EVOLUTION2_EXECUTION_BLOCKERS.md`.

## Latest — H-e2.5 n=3 micro is designed, not collected

df=2 Bonferroni cannot be swapped for the v2 df=9 constant.
Unmatched residuals keep the gate at `not_ready_recipe_mismatch`.
Not a transfer result. Report
`NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL_N3_MICRO.md`.

## Latest — H-e2.4 no-fit ten-bundle is unavailable, not collected

Three Pendulum residual MLPs cannot fill n=10. Acrobot lookahead
weights are a closed development set. Not a transfer result. Report
`NEXUS_EVOLUTION2_NOFIT_INVENTORY.md`.

## Latest — H-e2.3 source fitting is unavailable, not collected

No stored Pendulum/Acrobot train/val arrays. Trusted cache now
evaluator-owned. Not a transfer result. Report
`NEXUS_EVOLUTION2_SOURCE_FITTING_BENCHMARK.md`.

## Latest — H-e2.2 adapter correctness is engineered, not collected

Catalogue H=16 at cap 1536 is not historical 16×16. Balanced
dispatch keeps the 12-arm screen blocked. Not a transfer result.
Report `NEXUS_EVOLUTION2_ADAPTER_CORRECTNESS.md`.

## Latest — H-e2 residual-MLP timing is measured, not a transfer result

Frozen-file successor H=16 rates: Pendulum 2.95–3.01 µs, Acrobot
5.24 µs. Full v2 still likely censors under 900 s after source
fitting. Report `NEXUS_EVOLUTION2_RESIDUAL_TIMING_PROBE_RESULTS.md`.

## Latest — H-e2-pendulum-acrobot four-role rules are locked, unnamed

A Pendulum unused-instance grid and four-role assignment exist as
digests. No tuple is named. Not a transfer result. Report
`NEXUS_EVOLUTION2_PENDULUM_ACROBOT_INSTANCE_RULES.md`.

## Latest — H-e2-pendulum-acrobot unused-instance naming is blocked

The independent review does not name a holdout. Occupancy is
complete; a live Acrobot unused cell exists; a Pendulum unused
rule does not. Not a transfer result. Report
`NEXUS_EVOLUTION2_PENDULUM_ACROBOT_HOLDOUT_REVIEW.md`.

## Latest — H-e2-pendulum-acrobot-persistence v2-pilot is designed, not collected

A prospective six-row / two-condition worksheet exists so a 900 s
grant is less likely to censor than full v2. n=10 and Bonferroni
versus all five controls stay. Not a transfer result. Report
`NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL_V2_PILOT.md`.

## Latest — H-e2-planner-adapter is engineered, not collected

A catalogue-faithful fake-model adapter and population-4 evolution
exist. Full v2 remains likely incomplete under 900 s at historical
rates. Not a transfer result. Report
`NEXUS_EVOLUTION2_TRUSTED_PLANNER_ADAPTER.md`.

## Latest — H-e2-pendulum-acrobot-persistence v2 contracts exist, untested

v2 locks paired bundles, two H=16 anchors, mutation-only evolution,
and Bonferroni-versus-all-five-controls. Collection unauthorized.
Holdout unnamed. Not a scientific result. Report
`NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL_V2.md`.

## Latest — H-e2-pendulum-acrobot-persistence v1 is not ready

Independent review against Evolution-1 feasibility: statistical
weakening, incomplete bundles, missing two-anchor fairness,
undefined outcomes, illegal crossover language, and a 40k/0-imagined
worksheet. v1 preserved. v2 is design-only and unauthorized.
Report `NEXUS_EVOLUTION2_PENDULUM_ACROBOT_READINESS.md`.

## Latest — H-e2-pendulum-acrobot-persistence is locked, not collected

Question: after AdaptiveProposer training on default Pendulum
`(10, 1, 1)`, does retained proposer state improve Acrobot
discovery versus reset, random, evolution, retrieval, and a frozen
catalogue index? Protocol locked. Holdout unnamed. Collection
unauthorized. Not LEVEL 3/4, not H17, not learning-to-learn.
Report `NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL.md`.

## Latest — H-e2-cross-task-persistence is designed, not tested scientifically

Question: does retained proposal-policy state improve discovery on
new algorithm-improvement tasks versus memory reset? Synthetic
contracts exist. No authorized scientific comparison. Not LEVEL 3/4.
Report `NEXUS_EVOLUTION2_CROSS_TASK_SCREEN.md`.

## Evolution-1 functional intervention — synthetic evidence only

The first toy loop's proposal weights and third choice change after permitted
training feedback, while withheld feedback leaves weights unchanged. Altering
development scores leaves training identical; the separate gate can reject
the training winner. Fixed search beats the adaptive policy on a crafted
counterexample. This verifies functional feedback use, not transferable
algorithm improvement, scientific generalization or learning-to-learn. The
central Evolution-1 hypothesis remains untested. No protocol, allocation,
holdout or ledger change. See `NEXUS_EVOLUTION1_AUTONOMOUS_LOOP_PROTOTYPE.md`.

## Evolution-1 — transferable proposal memory, proposed and untested

Hypothesis: permitted memory of algorithm-improvement attempts helps discover
planning configurations that transfer better than random, fixed and equal-budget
evolutionary baselines. The feasibility comparison remains prospective; no
scientific protocol is locked or authorized. Source-only catalogue/broker fixture
tests check engineering contracts, not this hypothesis or learning-to-learn.
See `NEXUS_EVOLUTION1_FEASIBILITY.md` and
`NEXUS_EVOLUTION1_SOURCE_CONTRACTS.md`. H12–H17 evidence is unchanged.

## H17 preparation — historical seed dependency arithmetic, no scientific test

The source-only dependency review resolves76 historical registry-function/version
records and classifies299 root artifact seed schemas without altering the
preserved reservations.171 source-only tests passed. This supplies registration
evidence, not evidence for H17's occupancy/library hypothesis. RNG-call-site
dataflow remains unverified; H17 stays blocked, unlocked and unauthorized.
No target or numerical H17 seeds selected; no scientific execution; H14–H16
remain closed. See `NEXUS_H17_SEED_DEPENDENCY_CLOSURE.md`.

## Latest — H16 diagnosis separates ranking from the unresolved interaction

Source-only reanalysis preserves the registered inconclusive H16 label.
Multitask ranks/selects better than scratch in both libraries; that does
not establish a library-dependent advantage. Shared oracle values cancel
exactly from within-library arm comparisons. t8 versus t12 and reference
state sensitivity are exploratory, not extra replications. Occupancy and
compounding remain compatible explanations, not identified causes.
No new hypothesis is locked, no H17 is designed, and no experiment ran.
Report `NEXUS_H16_SELECTION_MECHANISM_DIAGNOSIS.md`.

## Latest — H-same-state-library-ranking is not established on this holdout

H16: D_same **+0.023 [−0.014, +0.060]** (df 9, 6/10 positive).
Label `h16_same_state_library_effect_not_established`. Same-state
L0-versus-redraw selection quality was not resolved. H14/H15 stay
closed. Not a control result. Report
`NEXUS_H16_SAME_STATE_LIBRARY_RESULTS.md`.

## Latest — H-same-state-library-ranking runner is audit-ready, not collected

Independent source-only audit of the H16 runner. Locked design
unchanged. Verdict READY_FOR_SEPARATE_ONE_RUN_AUTHORIZATION.
Collection unauthorized (`authorized: false`, `runs: 0`). This is
not a control result. Report
`NEXUS_H16_INDEPENDENT_READINESS_AUDIT.md`.

## Latest — H-same-state-library-ranking has a runner, not a result

H16 execution logic is implemented against unused MCC
(0.0015, 0.0014, 0.055). The locked design is unchanged. Collection
unauthorized (`authorized: false`, `runs: 0`). This is not a control
result. Report `NEXUS_H16_SAME_STATE_LIBRARY_RUNNER.md`.

## Latest — H-same-state-library-ranking is locked, not collected

H16: same-state L0-versus-redraw selected-return DiD on unused MCC
(0.0015, 0.0014, 0.055). Primary: mean D_same and CI entirely above
or below 0, else not established. Collection unauthorized. This is
not a result. Protocol `NEXUS_H16_SAME_STATE_LIBRARY_PROTOCOL.md`.

## Latest — H-same-state-library-ranking is designed, not tested

Proposed H16: at model-independent later states t=8 and t=12, compare
selected returns of L0 versus redraw for both arms. Primary D_same
cancels oracle library value. Collection unauthorized. No physics
chosen. This is not a result. Report
`NEXUS_H16_SAME_STATE_LIBRARY_FEASIBILITY.md`.

## Latest — H-reuse-mechanism is descriptively constrained, not identified

Source-only H14/H15 audit. A (stability) is a treatment behavior in
both arms. B (library distribution) is not testable without later
counterfactual returns. C (occupancy shift) is a correlate; seed-level
D does not track occupancy L2. D (prediction residuals) is not a
chosen-residual-magnitude story; full predicted next states are
missing. No causal mechanism is established. Report
`NEXUS_H14_H15_CANDIDATE_REUSE_MECHANISM_AUDIT.md`.

## Latest — H-h14-interaction-replicates-on-new-holdout was supported in this configuration

Complete H15 grid on unused MCC physics: DiD
**+0.230 [+0.111, +0.349]**. Label
`h15_fixed_library_helps_multitask_relative`. Closes only this
same-design confirmation. No retune. Not a 200-step control claim.
Report `NEXUS_H15_CANDIDATE_REUSE_CONFIRM_RESULTS.md`.

## Latest — H-h14-interaction-replicates-on-new-holdout is audit-ready, not collected

Independent readiness audit: runner may be authorized once, separately.
Collection unauthorized. This is not a result. Report
`NEXUS_H15_INDEPENDENT_READINESS_AUDIT.md`.

## Latest — H-h14-interaction-replicates-on-new-holdout has a runner, not a result

H15 execution logic is implemented against unused MCC
(0.004, 0.0021, 0.05). The locked design is unchanged. Collection
unauthorized (`authorized: false`, `runs: 0`). This is not a control
result. Report `NEXUS_H15_CANDIDATE_REUSE_CONFIRM_RUNNER.md`.

## Latest — H-h14-interaction-replicates-on-new-holdout is locked, not collected

H15: exact H14 fixed-versus-redraw DiD on unused MCC
(0.004, 0.0021, 0.05). Primary: mean D_s and CI entirely above or
below 0, else not established. Collection unauthorized. This is not
a result. Protocol `NEXUS_H15_CANDIDATE_REUSE_CONFIRM_PROTOCOL.md`.

## Latest — H-shared-proposal-resampling-changes-relative-recede was supported in this configuration

Complete H14 grid on unused MCC physics: DiD
**+0.178 [+0.009, +0.348]**. Label
`h14_fixed_library_helps_multitask_relative`. Closes only this
shared-proposal fixed-versus-redraw comparison. No retune. Not a
200-step control claim. Report `NEXUS_H14_CANDIDATE_REUSE_RESULTS.md`.

## Latest — H-shared-proposal-resampling-changes-relative-recede is audit-ready, not collected

Independent readiness audit: runner may be authorized once, separately.
Collection unauthorized. This is not a result. Report
`NEXUS_H14_INDEPENDENT_READINESS_AUDIT.md`.

## Latest — H-shared-proposal-resampling-changes-relative-recede has a runner, not a result

H14 execution logic is implemented. The locked design is unchanged.
Collection unauthorized (`authorized: false`, `runs: 0`). This is not
a control result. Report `NEXUS_H14_CANDIDATE_REUSE_RUNNER.md`.

## Latest — H-shared-proposal-resampling-changes-relative-recede is locked, not collected

H14: fixed-library recede versus redraw recede, both arms seeing the
same candidate matrices on unused MCC (0.0023, 0.0019, 0.065).
Primary: mean D_s > 0 and CI lower bound > 0, or the reverse, else
not established. Collection unauthorized. This is not a result.
Protocol `NEXUS_H14_CANDIDATE_REUSE_PROTOCOL.md`.

## Latest — H-shared-proposal-resampling-changes-relative-recede is designed, not locked

H14 draft: fixed-library recede versus redraw recede, both arms seeing
the same candidate matrices, DiD primary. Collection unauthorized.
This is not a result. Report
`NEXUS_H14_CANDIDATE_REUSE_FEASIBILITY.md`.

## Latest — H-reset-ranking-is-insufficient-for-MCC-H16-recede is supported on saved artifacts

Source-only: H12 and H13 ranking primaries recompute exactly. At
`obs0`, multitask ranks the shared 16-set far better than scratch.
H13 redraw recede favors scratch. The loss equals scratch’s larger
recede-over-commitment bonus. Later-state ranking, compounding error,
and occupancy remain untested. Recede is not a registered primary.
Report `NEXUS_H12_H13_CONTROL_DISAGREEMENT_AUDIT.md`.

## Latest — H-h12-ranking-replicates-on-new-holdout was supported in this configuration

Complete ranking confirmation on unused MCC physics:
`scratch − multitask` sequence regret **+0.156 [+0.086, +0.226]**.
Label `mcc_planning_ranking_confirm_multitask_better`. Closes only this
same-design ranking confirmation. H12 ranking now has two holdouts.
No retune. Recede favored scratch and is not the primary. Report
`NEXUS_MCC_PLANNING_RANKING_CONFIRM_RESULTS.md`.

## Latest — H-h12-ranking-replicates-on-new-holdout is locked, not collected

H13: the frozen H12 ranking recipe on unused MCC (0.0039, 0.002, 0.075)
beats scratch on same-state sequence regret. Same sources, four reset
states, and decision rule. Primary: `scratch_regret − multitask_regret`
mean > 0 and CI lower bound > 0. Collection unauthorized. This is not
a result. Protocol `NEXUS_MCC_PLANNING_RANKING_CONFIRM_PROTOCOL.md`.

## Latest — H-h10-recipe-ranks-shared-h16-candidates-better-than-scratch was supported in this configuration

Complete ranking primary on unused MCC physics:
`scratch − multitask` sequence regret **+0.144 [+0.095, +0.193]**.
Label `mcc_planning_ranking_multitask_better`. Closes only this
four-state same-state ranking configuration. No retune. Not a 200-step
control claim. Report `NEXUS_MCC_PLANNING_RANKING_RESULTS.md`.

## Latest — H-h10-recipe-ranks-shared-h16-candidates-better-than-scratch has a runner, not a result

H12 execution logic is implemented. The locked design is unchanged.
Collection unauthorized (`authorized: false`, `runs: 0`). This is not
a ranking result. Report `NEXUS_MCC_PLANNING_RANKING_RUNNER.md`.

## Latest — H-h10-recipe-ranks-shared-h16-candidates-better-than-scratch is locked, not collected

H12: frozen H10 multitask has lower same-state sequence regret than
scratch on four unused-MCC reset states. Primary:
`scratch_regret − multitask_regret` mean > 0 and CI lower bound > 0.
Collection unauthorized. This is not a result. Protocol
`NEXUS_MCC_PLANNING_RANKING_PROTOCOL.md`.

## Latest — H-one-step-val-MAE-is-insufficient-for-MCC-H16-control is supported on saved artifacts

Source-only: H10 and H11 paired returns reconstruct; late-window
deltas match the primaries; H11 seeds 4 and 5 have lower val MAE and
large negative control deltas. Ranking and multi-step mechanisms remain
untested. Not a harm label. Report
`NEXUS_H10_H11_CONTROL_DISAGREEMENT_AUDIT.md`.

## Latest — H-within-family-mcc-multitask-128-replicates-on-new-holdout was not established

Complete 128-only confirmation on unused MCC physics:
`multitask − scratch` **+18.879 [−65.988, +103.747]**. Label
`mcc_multitask_128_confirm_not_established`. Closes only this
same-design confirmation. H10 remains a single-holdout positive
screen. No retune. Report `NEXUS_MCC_MULTITASK_128_CONFIRM_RESULTS.md`.

## Latest — H-within-family-mcc-multitask-128-replicates-on-new-holdout is locked, not collected

H11: the frozen H10 recipe on unused MCC (0.0022, 0.0016, 0.07) beats
scratch at 128. Same sources, target RMS, and decision rule. Primary:
`multitask − scratch` mean > 0 and CI lower bound > 0. Collection
unauthorized. This is not a result. Protocol
`NEXUS_MCC_MULTITASK_128_CONFIRM_PROTOCOL.md`.

## Latest — H-within-family-mcc-multitask-improves-128-transition-adaptation was supported in this configuration

Complete 128-only primary on unused MCC physics:
`multitask − scratch` **+145.785 [+106.617, +184.953]**. Label
`mcc_multitask_128_beats_scratch`. Closes only this three-source
weight-pretrain configuration. No retune. Report
`NEXUS_MCC_MULTITASK_128_RESULTS.md`.

## Latest — H-within-family-mcc-multitask-improves-128-transition-adaptation is locked, not collected

H10: a residual world model pretrained on three other MCC physics and
fine-tuned on 128 unused-MCC transitions beats scratch on the same 128.
Both arms share target RMS. Primary: `multitask − scratch` mean > 0 and
CI lower bound > 0. Collection unauthorized. This is not a result.
Protocol `NEXUS_MCC_MULTITASK_128_PROTOCOL.md`.

## Latest — H-source-mcc-residual-scale-improves-128-transition-adaptation was harmful in this configuration

Complete 128-only primary on unused MCC physics:
`source_scale − unit_scale` **−54.381 [−105.776, −2.987]**. Label
`mcc_residual_scale_harm_established`. Closes only this 2-d source
residual-scale configuration. No retune. Report
`NEXUS_MCC_RESIDUAL_SCALE_RESULTS.md`.

## Latest — H-source-mcc-residual-scale-improves-128-transition-adaptation is locked, not collected

H9: a residual world model trained on 128 unused-MCC transitions with a
frozen 2-d source residual scale beats unit scale. Both arms share target
RMS. Primary: `source_scale − unit_scale` mean > 0 and CI lower bound > 0.
Collection unauthorized. This is not a result. Protocol
`NEXUS_MCC_RESIDUAL_SCALE_PROTOCOL.md`.

## Latest — H-source-mcc-rms-improves-128-transition-adaptation was not established

Complete 128-only primary on unused MCC physics: `source_rms − scratch_rms`
**+2.185 [−64.564, +68.935]**. Label `mcc_native_rms_not_established`.
Closes only this source-RMS configuration. No retune. Report
`NEXUS_MCC_NATIVE_RMS_RESULTS.md`.

## Latest — H-source-mcc-rms-improves-128-transition-adaptation is locked, not collected

H8: a residual world model trained on 128 unused-MCC transitions with
frozen source `mcc_default` observation RMS beats the identical model
with fresh target RMS. Primary: `source_rms − scratch_rms` mean > 0 and
CI lower bound > 0. Collection unauthorized. This is not a result.
Protocol `NEXUS_MCC_NATIVE_RMS_PROTOCOL.md`.

## Latest — H-shared-hidden-layer-is-the-wrong-cross-family-unit is a supported interpretation, not a trained label

Synthesis of seven closed `not_established` primaries plus the V0.6.6
RMS result: a shared 64-d hidden matrix between incompatible embeddings
is the wrong transfer object. Next untested hypothesis:
family-native interface adaptation on unused MCC physics. Not a result.
Not authorized. Report `NEXUS_XENV_TRANSFER_FAILURE_SYNTHESIS.md`.

## Latest — H-cartpole-target-shared-layer-improves-new-environment-adaptation was not established

Complete matched-data rung: primary `xenv − scratch` **−2.500 [−10.359,
+5.359]** on unused CartPole physics. Label
`xenv_cartpole_target_not_established`. Family swap off MCC did not
establish transfer. No retune. Report
`NEXUS_XENV_CARTPOLE_TARGET_RESULTS.md`.

## Latest — H-cartpole-target-shared-layer-improves-new-environment-adaptation is locked, not collected

H7: closed rung-1 `XEnvNet` pretrained on Acrobot + MountainCar + MCC
improves matched-data unused CartPole adaptation versus the identical
architecture trained from scratch. Target physics `cartpole_xenv_v1`
**(6.5, 0.57, 0.28)**. Primary: mean over {128, 1024} `xenv − scratch`
with CI lower bound > 0. Collection unauthorized. This is not a result.
Protocol `NEXUS_XENV_CARTPOLE_TARGET_PROTOCOL.md`.

## Latest — H-128-only-prior-establishes-scarce-target-transfer was not established

Complete 128-only primary on unused MCC physics: `xenv − scratch`
**+18.453 [−20.207, +57.113]**. Label `xenv_low_budget_not_established`.
Rung 5's @128 secondary did not replicate as a primary. No retune of
`mcc_xenv_v6` or `mcc_xenv_v7`. Report `NEXUS_XENV_LOW_BUDGET_RESULTS.md`.

## Latest — H-2x-prior-data-establishes-shared-layer-transfer was not established

Complete matched-data rung: primary `xenv − scratch` **−4.761 [−36.121,
+26.599]** on unused MCC physics. Label `xenv_prior_scale_not_established`.
Starvation at 2× is not supported on the preregistered average of {128,
1024}. The @128 secondary must not be promoted. No retune. Report
`NEXUS_XENV_PRIOR_SCALE_RESULTS.md`.

## Latest — H-residual-aware-context-code-improves-new-environment-adaptation was not established

Complete matched-data rung: `xenv − scratch` **−1.819 [−23.729, +20.091]**
on unused MCC physics. Label `xenv_residual_context_not_established`. Closes
only this residual-aware FiLM configuration. No retune. Report
`NEXUS_XENV_RESIDUAL_CONTEXT_RESULTS.md`.

## Latest — H-support-inferred-context-code-improves-new-environment-adaptation was not established

The complete matched-data rung passed its integrity gates but failed the
predeclared rule: `xenv − scratch` **−2.300 [−9.921, +5.320]** (student-t
95%, df 9) on new unused MountainCarContinuous physics, both per-budget
intervals including 0, prediction MAE intervals including 0. Label
`xenv_context_code_not_established`. This closes only the occupancy-only
`(obs, action)` FiLM configuration. It does not test residual-aware
support encoding. No retune, no rerun. Report
`NEXUS_XENV_CONTEXT_CODE_RESULTS.md`.

## Latest — H3 source audit: occupancy-conditioned FiLM, not residual inference

The locked H3 encoder never sees `next_obs` or `s'−s`. A later complete
grid would test pretrained occupancy-conditioned FiLM versus scratch, not
whether support recovered unseen dynamics. Epoch label `10` is not a
10-epoch cap. Collection unauthorized. Audit
`NEXUS_XENV_CONTEXT_CODE_SOURCE_AUDIT.md`.

## Latest — H-support-inferred-context-code-improves-new-environment-adaptation is locked, not collected

H3: a support-inferred 8-d FiLM context on the closed rung-1 shared trunk
improves matched-data MountainCarContinuous adaptation versus the identical
architecture trained from scratch. No family-ID table. Target physics
`mcc_xenv_v4` **(0.0027, 0.0009, 0.05)** unused. Primary: `xenv − scratch`
mean > 0 and CI lower bound > 0 over ten seeds. Collection unauthorized.
This is not a result. Protocol `NEXUS_XENV_CONTEXT_CODE_PROTOCOL.md`.

## Latest — H-deep-shared-trunk-across-environments-improves-new-environment-adaptation was not established

The complete matched-data rung passed its integrity gates but failed the
predeclared rule: `xenv − scratch` **+2.575 [−16.248, +21.399]** (student-t
95%, df 9) on new unused MountainCarContinuous physics, both per-budget
intervals including 0, and the deeper multi-head architecture underperformed
the single-family reference @1024. Label `xenv_deep_trunk_not_established`.
With rung 1 also closed, naive weight sharing across heterogeneous families
has two consecutive not-established rungs at these pretraining scales. This
closes the configuration only; the multitask-across-physics lever within a
family remains established. No retune, no rerun. Report
`NEXUS_XENV_DEEP_TRUNK_RESULTS.md`.

## Latest — H-one-shared-layer-across-environments-improves-new-environment-adaptation was not established

The complete matched-data pilot passed its integrity gates but failed the
predeclared decision rule: `xenv − scratch` **+18.618 [−20.400, +57.636]**
(student-t 95%, df 9) on a new unused MountainCarContinuous physics, both
per-budget intervals including 0, prediction MAE unchanged. Label
`xenv_shared_layer_not_established`. This closes only the minimal-sharing
configuration (one shared 64→64 layer, per-family heads); it does not disprove
cross-environment adaptation in general, and the multitask-across-physics
lever within a family remains established. No retune, no rerun on this
sample. Report `NEXUS_XENV_TRANSFER_PILOT_RESULTS.md`.

## Latest — H-lookahead-transfers-on-new-mountaincarcontinuous-physics passed on one confirmation holdout

The complete confirmation screen passed the 25-point rule: lookahead minus
H=16 **81.518 [55.450, 107.586]** (student-t 95%, df 9, n=10) on holdout
`bc7c74c781c9e24f` with the frozen development recipe and no retuning. Label
`mountaincar_continuous_lookahead_transfer_established`. Development split
stays closed; H=16, candidates and dense height were not retuned; the
confirmation holdout is consumed by this one run. This is algorithm transfer
with separately trained family models, not cross-family weight learning and
not learning-to-learn. Report
`NEXUS_MOUNTAINCAR_CONTINUOUS_LOOKAHEAD_CONFIRM_RESULTS.md`.

## Latest — H-prefix-max-tree-reuse-beats-h16-on-mountaincar was not established

The complete development screen failed the 25-point rule: prefix-max minus H=16 **−9.832 [−31.108, 11.445]**. Label `prefix_max_tree_reuse_not_established`. Prefix hit-rate 0.999. Max remaining at matching first-action t=1 nodes did not replace successor H=16 search. Closed nearest-neighbor tree-reuse stays closed. Do not retune from this sample. Report `NEXUS_PREFIX_MAX_TREE_REUSE_RESULTS.md`.

## Latest — H-prefix-max-tree-reuse-beats-h16-on-mountaincar is implemented, not yet tested

Nearest remaining failed. This protocol tests max remaining at cached t=1 nodes whose first action matches `a` versus 16-candidate H=16 on frozen MountainCar development checkpoints, margin 25, 259 imagined/step. Confirmation unused. No 771 arm. No fitted critic. Collection unauthorized until a bound one-run allocation exists. Report `NEXUS_PREFIX_MAX_TREE_REUSE_PROTOCOL.md`.

## Latest — H-tree-reuse-beats-h16-on-mountaincar was not established

The complete development screen failed the 25-point rule: tree-reuse minus H=16 **−14.751 [−37.142, 7.641]**. Label `tree_reuse_lookahead_not_established`. Nearest remaining open-loop height from the current-step tree did not replace successor H=16 search. Mean nearest-neighbor distance ~0. Closed Q/V failures stay closed. Do not retune from this sample. Report `NEXUS_TREE_REUSE_LOOKAHEAD_RESULTS.md`.

## Latest — H-tree-reuse-beats-h16-on-mountaincar is implemented, not yet tested

Source synthesis: extra H=16 search explains the Acrobot unmatched remainder relative to the 25-point rule, not Pendulum or MountainCar. Closed Q/V readouts failed to replace successor search. This protocol tests whether nearest remaining open-loop height from the current-step H=16 tree keeps the MountainCar 25-point gain at 259 imagined states/step versus 16-candidate H=16. No fitted critic. Confirmation unused. Collection unauthorized. Report `NEXUS_TREE_REUSE_LOOKAHEAD_PROTOCOL.md`.

## Latest — H-lookahead-algorithm-generalizes-without-weight-sharing is supported as algorithm copy, not as cross-family learning

Four dense-height families established unmatched lookahead versus H=16 with separately trained world models. Compute-matched backup holds on Pendulum and MountainCar, not Acrobot. CartPole H=3 failed three draws. No shared weights, no meta-update, historical Pendulum disjoint-physics control transfer was negative. Do not upgrade these labels to learning-to-learn. Report `NEXUS_LOOKAHEAD_GENERALIZATION_SYNTHESIS.md`.

## Latest — H-lookahead-beats-h16-on-mountaincar-continuous passed on development; confirmation untested

The complete development screen passed the 25-point rule: lookahead minus H=16 **69.758 [29.321, 110.196]**. Label `mountaincar_continuous_lookahead_established`. Dense valley height, not Gymnasium sparse +100. Discrete MountainCar unused. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused. Do not retune from this sample. Confirmation transfer is unimplemented. Report `NEXUS_MOUNTAINCAR_CONTINUOUS_LOOKAHEAD_RESULTS.md`.

## Latest — H-lookahead-beats-h16-on-mountaincar-continuous is implemented, not yet tested

MountainCar compute-matched passed. This protocol tests one-step backup of frozen H=16 dense valley-height value versus receding H=16 on unused MountainCarContinuous physics, margin 25. Discrete MountainCar, CartPole H=3, Pendulum FiLM, and Acrobot unused. Collection unauthorized. Report `NEXUS_MOUNTAINCAR_CONTINUOUS_LOOKAHEAD_PROTOCOL.md`.

## Latest — H-lookahead-beats-compute-matched-h16-on-mountaincar passed on development

The complete development screen passed the 25-point rule: lookahead minus 48-candidate H=16 **54.649 [26.611, 82.686]**. Label `mountaincar_compute_matched_lookahead_established`. Extra search did not remove the remainder on these physics. This does not reverse the closed Acrobot compute-matched miss. Do not retune from this sample. Report `NEXUS_MOUNTAINCAR_COMPUTE_MATCHED_RESULTS.md`.

## Latest — H-lookahead-beats-compute-matched-h16-on-mountaincar is implemented, not yet tested

MountainCar lookahead transferred versus 16-candidate H=16. That comparison used 771 versus 256 imagined states per step. This protocol tests the same frozen lookahead against 48-candidate H=16 (768 imagined/step) on development physics with fresh seeds, margin 25. Confirmation unused. Collection unauthorized. Report `NEXUS_MOUNTAINCAR_COMPUTE_MATCHED_PROTOCOL.md`.

## Latest — H-lookahead-transfers-on-new-mountaincar-physics passed on one confirmation holdout

The complete confirmation screen passed the 25-point rule: lookahead minus H=16 **50.366 [36.493, 64.239]**. Label `mountaincar_lookahead_transfer_established`. Dense valley height, not Gymnasium −1/step. Development physics unused. H=16 not retuned. This is not learning-to-learn. Report `NEXUS_MOUNTAINCAR_LOOKAHEAD_CONFIRM_RESULTS.md`.

## Latest — H-lookahead-transfers-on-new-mountaincar-physics is implemented, not yet tested

Development lookahead versus H=16 passed. Transfer uses a new holdout (`bf4b4412f4f683dd`), not the development split. H=16, candidates, and dense height are not retuned. Collection unauthorized. Report `NEXUS_MOUNTAINCAR_LOOKAHEAD_CONFIRM_PROTOCOL.md`.

## Latest — H-lookahead-beats-h16-on-mountaincar passed on development; confirmation untested

The complete development screen passed the 25-point rule: lookahead minus H=16 **44.092 [13.945, 74.239]**. Label `mountaincar_lookahead_established`. Dense valley height, not Gymnasium −1/step. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused. Do not retune from this sample. Confirmation transfer is unimplemented. Report `NEXUS_MOUNTAINCAR_LOOKAHEAD_RESULTS.md`.

## Latest — H-lookahead-beats-h16-on-mountaincar is implemented, not yet tested

Pendulum compute-matched passed. This protocol tests one-step backup of frozen H=16 dense valley-height value versus receding H=16 on unused MountainCar physics, margin 25. CartPole H=3, Pendulum FiLM, and Acrobot unused. Collection unauthorized. Report `NEXUS_MOUNTAINCAR_LOOKAHEAD_PROTOCOL.md`.

## Latest — H-lookahead-beats-compute-matched-h16-on-pendulum passed on development

The complete development screen passed the 25-point rule: lookahead minus 48-candidate H=16 **60.182 [11.439, 108.924]**. Label `pendulum_compute_matched_lookahead_established`. Extra search did not remove the remainder on these physics. This does not reverse the closed Acrobot compute-matched miss. Do not retune from this sample. Report `NEXUS_PENDULUM_COMPUTE_MATCHED_RESULTS.md`.

## Latest — H-lookahead-beats-compute-matched-h16-on-pendulum is implemented, not yet tested

Acrobot compute-matched failed the 25-point rule. Pendulum's unmatched development gap was larger. This protocol tests frozen 16-candidate lookahead against 48-candidate H=16 (768 imagined/step) on development physics with fresh seeds, margin 25. Confirmation unused. Collection unauthorized. Report `NEXUS_PENDULUM_COMPUTE_MATCHED_PROTOCOL.md`.

## Latest — H-lookahead-beats-compute-matched-h16-on-acrobot was not established

The complete development screen failed the 25-point rule: lookahead minus 48-candidate H=16 **12.834 [3.815, 21.853]**. Label `acrobot_compute_matched_lookahead_not_established`. The lower bound is above 0, but the mean is below 25. Extra H=16 search closed most of the earlier 16-candidate gap. Do not retune from this sample. Report `NEXUS_ACROBOT_COMPUTE_MATCHED_RESULTS.md`.

## Latest — H-lookahead-beats-compute-matched-h16-on-acrobot is implemented, not yet tested

Acrobot lookahead transferred versus 16-candidate H=16. That comparison used 771 versus 256 imagined states per step. This protocol tests the same frozen lookahead against 48-candidate H=16 (768 imagined/step) on development physics with fresh seeds, margin 25. Confirmation unused. Collection unauthorized. Report `NEXUS_ACROBOT_COMPUTE_MATCHED_PROTOCOL.md`.

## Latest — H-lookahead-transfers-on-new-acrobot-physics passed on one confirmation holdout

The complete confirmation screen passed the 25-point rule: lookahead minus H=16 **37.961 [21.106, 54.816]**. Label `acrobot_lookahead_transfer_established`. Dense height, not Gymnasium −1/step. Development physics unused. H=16 not retuned. This is not learning-to-learn. Report `NEXUS_ACROBOT_LOOKAHEAD_CONFIRM_RESULTS.md`.

## Latest — H-lookahead-transfers-on-new-acrobot-physics is implemented, not yet tested

Development lookahead versus H=16 passed. Transfer uses a new holdout (`b309bd481fd8abcb`), not the development split. H=16, candidates, and dense height are not retuned. Collection unauthorized. Report `NEXUS_ACROBOT_LOOKAHEAD_CONFIRM_PROTOCOL.md`.

## Latest — H-lookahead-beats-h16-on-acrobot passed on development; confirmation untested

The complete development screen passed the 25-point rule: lookahead minus H=16 **27.914 [13.962, 41.867]**. Label `acrobot_lookahead_established`. Dense upright height, not Gymnasium −1/step. CartPole H=3 unused. Pendulum FiLM unused. Do not retune from this sample. Confirmation transfer is unimplemented. Report `NEXUS_ACROBOT_LOOKAHEAD_RESULTS.md`.

## Latest — H-lookahead-beats-h16-on-acrobot is implemented, not yet tested

CartPole lookahead versus H=3 failed three development draws because of the survival ceiling. This protocol tests one-step backup of frozen H=16 dense-height value versus receding H=16 on unused Acrobot physics, margin 25. CartPole H=3 and Pendulum FiLM unused. Collection unauthorized. Report `NEXUS_ACROBOT_LOOKAHEAD_PROTOCOL.md`.

## Latest — H-lookahead-beats-h3-on-unsaturated-cartpole was not established

The complete six-task screen failed the 25-point rule: lookahead minus H=3 **14.000 [−4.621, 32.621]**. Label `cartpole_sat_lookahead_not_established`. Ceilinged tasks were kept. Do not retune H=3 from this sample. CartPole lookahead versus H=3 is now not established on three development draws. Report `NEXUS_CARTPOLE_LOOKAHEAD_SAT_RESULTS.md`.

## Latest — H-lookahead-beats-h3-on-unsaturated-cartpole is implemented, not yet tested

The H=3-only diagnostic passed. This protocol tests one-step backup of frozen H=3 versus receding H=3 on the same six-task split `a69833ab38a34ab4`, margin 25. Ceilinged tasks are kept. Collection unauthorized. Report `NEXUS_CARTPOLE_LOOKAHEAD_SAT_PROTOCOL.md`.

## Latest — H-frozen-h3-unsaturated-on-stricter-cartpole passed; lookahead still untested

The complete H=3-only diagnostic passed the 25-point gap-from-ceiling rule: **33.183 [2.481, 63.886]**. Label `cartpole_h3_unsaturated`. Lookahead was not run. 50/60 episodes still hit 500; do not drop those tasks. A later lookahead-versus-H=3 screen on this same holdout is unimplemented. Report `NEXUS_CARTPOLE_H3_SATURATION_RESULTS.md`.

## Latest — H-frozen-h3-unsaturated-on-stricter-cartpole is implemented, not yet tested

Two CartPole lookahead screens could not measure lookahead because H=3 was at the TimeLimit. This diagnostic keeps frozen H=3, withholds lookahead, and tests six unused stricter-corner physics, margin 25 below 500. Collection unauthorized. Report `NEXUS_CARTPOLE_H3_SATURATION_PROTOCOL.md`.

## Latest — H-lookahead-beats-h3-on-hard-cartpole was not established (still near ceiling)

The complete harder-physics screen failed the 25-point rule: lookahead minus H=3 **4.600 [−7.481, 16.681]**. Label `cartpole_hard_lookahead_not_established`. Frozen H=3 was already at the 500-step cap on 8/10 seed means and 28/30 episodes. Do not retune H=3 from this sample. Report `NEXUS_CARTPOLE_LOOKAHEAD_HARD_RESULTS.md`.

## Latest — H-lookahead-beats-h3-on-hard-cartpole is implemented, not yet tested

The ceilinged CartPole draw could not measure lookahead. This protocol keeps frozen H=3 and tests unused hard physics in the published V0.7.3 off-ceiling region, margin 25. Collection unauthorized. Report `NEXUS_CARTPOLE_LOOKAHEAD_HARD_PROTOCOL.md`.

## Latest — H-lookahead-beats-frozen-h3-on-cartpole was not established (ceiling)

The complete development screen failed the 25-point rule: lookahead minus H=3 **4.000 [−5.048, 13.048]**. Label `cartpole_lookahead_not_established`. Frozen H=3 was already at the 500-step cap on 9/10 seeds. Do not retune H=3 from this sample. Report `NEXUS_CARTPOLE_LOOKAHEAD_RESULTS.md`.

## Latest — H-lookahead-beats-frozen-h3-on-cartpole is implemented, not yet tested

Pendulum lookahead transfer passed and is not used to copy H=16 onto CartPole. This protocol tests one-step backup of frozen CartPole H=3 open-loop value versus H=3 receding on unused CartPole physics, margin 25. Collection unauthorized. Report `NEXUS_CARTPOLE_LOOKAHEAD_PROTOCOL.md`.

## Latest — H-lookahead-transfers-to-new-physics passed on one Pendulum holdout; not L2L

The complete transfer screen passed the 25-point episode rule: lookahead minus frozen H=16 **98.608 [43.258, 153.957]**. Label `lookahead_transfer_established`. Successor value remained open-loop H=16 from s'. Student-minus-zero includes 0 and is a separate estimand. This is not cross-family transfer, learning-to-learn, or AGI. Do not retune from these outcomes. Report `NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_RESULTS.md`.

## Latest — H-lookahead-transfers-to-new-physics is implemented, not yet tested

Development lookahead versus H=16 passed. Transfer uses a new holdout (`73844661addfa11b`), not historically exposed confirmation physics. Primary: lookahead minus H=16 200-step return, margin 25. Student-versus-zero is secondary and cannot upgrade. Collection unauthorized. Report `NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_PROTOCOL.md`.

## Latest — H-lookahead-beats-h16 passed on development; Bellman consistency is not isolated

The complete development screen passed the 25-point episode rule: lookahead minus frozen H=16 **155.647 [109.825, 201.469]**. Label `bellman_backup_improves_episode_return`. Successor value was frozen open-loop H=16 from s', not receding-policy Q. H1 remains the supported mechanism class; this result does not prove Bellman consistency. Confirmation transfer is untested. Report `NEXUS_BELLMAN_BACKUP_CONTROL_RESULTS.md`.

## Latest — H1 planning-objective mismatch is best supported; H-bellman-backup-beats-h16 is unimplemented

Offline receding-value audit: H1 (open-loop plan value ≠ first-action+replan value) is the strongest supported explanation of long-horizon control failure. H2 (Q coverage/representation) explains closed 64-step Q/V failures, not the deployed rule. H3 (policy-induced distribution shift) is not isolated. Nested H=8, score-correction, and fitted Q/V stay closed. One locked test: parameter-free Bellman backup of frozen H=16 open-loop value versus frozen H=16 receding on 200-step development return, margin 25. Collection unauthorized. Report `NEXUS_RECEDING_LONG_TERM_VALUE_AUDIT.md`.

## Latest — H-shorter-horizon-improves-episodes was rejected; nested H=8 hurt return

The complete development screen failed the improvement rule and met the hurt rule: H=8 minus H=16 **−174.178 [−265.830, −82.527]**. Label `shorter_horizon_hurts_episode_return`. Executed one-step MAE stayed small. Do not retune H∈{4,8,16,32} on this sample. Report `NEXUS_HORIZON_OBJECTIVE_CONTROL_RESULTS.md`.

## Latest — H-multi-step-error-accumulates-on-live-actions is descriptively large; H-shorter-horizon-improves-episodes is unimplemented

Teacher-forced H=16 angvel MAE on recorded development actions is **1.935 / 2.030** (student / zero own-path). Isolation **−0.095 [−0.515, +0.325]** includes 0. H=1 isolation excludes 0 favoring the student. Exact H=16 sequence-versus-64-step objective mismatch stays demonstrated and closed. Nested H=8 200-step control is locked and unauthorized. Report `NEXUS_MULTISTEP_ROLLOUT_CONTROL_AUDIT.md`.

## Latest — H-student-late-executed-error-grows-faster was not established

The complete development screen failed the 0.05 practical margin: growth_diff **+0.016 [+0.003, +0.029]**. Label `late_error_growth_not_established`. The lower bound is above 0 but the mean is too small. Student executed MAE did not rise late; zero improved more. Episode return includes 0. First mismatch mean 9.6 steps. Do not retune. Report `NEXUS_LATE_EPISODE_DECISION_TRAJECTORY_RESULTS.md`.

## Latest — H-student-late-executed-error-grows-faster is implemented, not yet tested

Archives cannot reconstruct per-step scores or executed one-step errors on 200-step episodes. The locked development experiment logs paired H=16 receding traces with shared candidate seeds. Primary: differential late-minus-early executed angular-velocity error, margin 0.05. Same-state prefix until first mismatch; later steps are different-state. Three-action late-state forks stay closed. Collection unauthorized. Report `NEXUS_LATE_EPISODE_DECISION_TRAJECTORY_PROTOCOL.md`.

## Latest — H-episode-loss-is-a-first-horizon-ranking-miss is not supported by recorded traces

Exploratory decoder-level splits of closed return-phase rewards (not a new primary, `primarily_late` unchanged): steps 16–63 **+0.307 [−4.144, +4.759]** include 0; steps 64–127 and 128–199 exclude 0. Combined with strong source H=16 ranking and PCG ranking-without-control, further initial-state ranking screens are lower information than episode-level diagnosis. Report `NEXUS_NEXT_DIRECTION_ASSESSMENT.md`.

## Latest — H-decision-relevant-score-error was not established on source

Independent recomputation of frozen `planning_value` prefixes and scores found student near-best minus dominated H=16 absolute error **+0.577 [−0.233, +1.387]**, n=10 decoder units, τ=1. Label `source_h1_not_established`. 16-step ranking is already strong (Spearman **0.923 [0.874, 0.973]**). Closed prediction-control-gap fresh ranking gains with episode loss stay closed and already reject “better prediction, worse ranking” on that split. Decision-aware training is not justified. A development diagnostic is locked and unauthorized. Report `NEXUS_DECISION_AWARE_WORLD_MODEL_AUDIT.md`.

## Latest — H-decision-relevant-score-error is implemented, not yet tested

The remaining open measurement is whether development physics with fresh seeds show concentrated H=16 score error on near-best candidates. Primary: student near-best minus dominated absolute score error, mean ≥ 1 and lower bound > 0. Episode return is a separate secondary and cannot pass the screen. Collection unauthorized. Report `NEXUS_DECISION_AWARE_WORLD_MODEL_PROTOCOL.md`.

## Latest — H-remaining-horizon-beats-fixed-H16 was not established on episodes

The complete development screen failed the 25-point full-episode rule: remaining-horizon minus fixed H=16 **+0.523 [−0.077, +1.123]**. Label `boundary_specific_alignment`. The 16-step diagnostic passed its own margin and all episode difference was in the last 15 steps. Close general horizon alignment rather than retuning. Report `NEXUS_HORIZON_ALIGNMENT_RESULTS.md`.

## Latest — H-remaining-horizon-beats-fixed-H16 is implemented, not yet tested

The previous 16-step H=16 loss is an artificial cutoff, not episode termination. The locked experiment compares remaining-horizon `H=min(16, remaining)` with fixed H=16 on complete 200-step development episodes (primary, margin 25) and a 16-step diagnostic (cannot upgrade). Shared per-step seeds must match actions on steps 0–184. Collection unauthorized. Report `NEXUS_HORIZON_ALIGNMENT_PROTOCOL.md`.

## Latest — H-same-set-beats-equal-horizon-fresh was not established

The complete development screen failed its registered pass rule: same-set minus equal-horizon fresh **+0.834 [−0.955, +2.623]**. Label `same_set_advantage_not_established`. Remaining-horizon methods beat production H=16 only as secondaries and cannot upgrade the primary. Do not retune same-set versus equal-horizon fresh. Report `NEXUS_SAME_SET_PLANNING_RESULTS.md`.

## Latest — H-same-set-beats-equal-horizon-fresh is implemented, not yet tested

Retrospective source evidence that same-set suffix receding beat recede-fresh and commit-16 is decoder-consistent but confounded by remaining-horizon mismatch. The locked development experiment equalizes candidate count and scored horizon for same-set versus fresh draws; production H=16 receding is a separate unequal-budget baseline. Collection unauthorized. Reports `NEXUS_SAME_SET_PLANNING_AUDIT.md` and `NEXUS_SAME_SET_PLANNING_PROTOCOL.md`.

## Latest — H-commit-beats-replan was not established

The complete source screen failed both registered pass rules: commit-16 minus recede-fresh **−1.787 [−4.324, +0.751]**. Label `replan_consistency_not_established`. Recede-same-set beat both open-loop commitment and recede-fresh as a secondary only and cannot upgrade the primary. Report `NEXUS_RECEDING_POLICY_CONSISTENCY_RESULTS.md`.

## Latest — H-commit-beats-replan is implemented, not yet tested

After score-correction closed, the remaining control question is whether receding replanning loses 16-step return relative to executing the H=16 selected sequence from the same restored source state. Search noise at that state is measured separately from state-driven re-ranking of the same 16 suffixes. Collection unauthorized. Archived live suffix mismatch is confounded and is not this test. Report `NEXUS_RECEDING_POLICY_CONSISTENCY_PROTOCOL.md`.

## Latest — H-action-conditioned-Q did not establish a first-action gain

The resumed complete 60-cell development screen failed its registered pass rule: conditioned−H=16 **−4.293 [−15.751, +7.165]**. Label `action_conditioned_gain_not_established`. H-additive-enough is not supported as a decision upgrade (conditioned−additive includes 0). Close score-correction rather than enlarging the readout. Report `NEXUS_ACTION_CONDITIONED_Q_RESUME_RESULTS.md`.

## Latest — H-resume-valid is implemented, not yet tested

The incomplete 59/60 action-conditioned grid can be completed only if the missing zero-visitor cell (decoder 9, development task 2) is independently generated from locked seeds and frozen fits, the 59 cells reconstruct, and assembly refuses to replace completed outcomes. If reconstruction fails, the hypothesis is rejected in favor of a fresh full run. Collection unauthorized. Report `NEXUS_ACTION_CONDITIONED_Q_RESUME_PROTOCOL.md`.

## Latest — H-action-conditioned-Q execution incomplete

The registered development screen did not complete: timeout at 240 s, 59/60 evaluation cells. That is not a pass, fail, or equivalence result for first-action return versus H=16. Source labels and both Q fits were frozen before the timeout. A new approval is required to finish or rerun. Report `NEXUS_ACTION_CONDITIONED_Q_RESULTS.md`.

## Latest — H-action-conditioned-Q is implemented, not yet tested

Additive first-action Q, including the unexecuted 81-coefficient polynomial, cannot change preferred action across states. A compact action×observation family (16 weights) can, on synthetic data. Source-only cross-task identification on 24 historical unique labels is 0.463 versus additive 0.312; action×context was not justified. The locked experiment collects two distinct source states per task and compares action-conditioned Q, additive Q, frozen sequence-value and H=16 on new development visited states. Collection unauthorized. If that screen fails, close score-correction rather than enlarging the readout. Reports `NEXUS_ACTION_CONDITIONED_Q_PROTOCOL.md` and `NEXUS_CAPACITY_MATCHED_Q_PROTOCOL.md`.

## Latest — H-capacity-matched-Q is implemented, not yet tested

The 15-coefficient miss left open whether aligned first-action labels fail because of capacity. The locked 81-coefficient protocol reuses V's 77 polynomial coordinates plus three action dummies, ridge λ=1. Offline diagnostics show only 24 unique source labels versus 81 weights, rank 50, and state-independent action ranking. That does not answer the decision question. Collection is unauthorized until a fresh 150 s / 29,880-step approval. If the complete run fails the registered first-action screen, close this score-correction branch. Report `NEXUS_CAPACITY_MATCHED_Q_PROTOCOL.md`.

## Latest — H-aligned-Q not established for the 15-coefficient linear readout

A source-trained linear Q(s,z,a) with 15 coefficients did not raise development first-action 64-return versus frozen H=16: **−3.535 [−9.840, +2.769]**, n=10 decoder units. The registered gain screen failed. Source RMSE remained ~70, so the aligned-label hypothesis was not given a capacity-matched test against sequence-value V. Sequence-value itself also did not beat H=16 on this sample. No architecture change is justified. Unknown: whether the same first-action labels become useful with the 77-coordinate polynomial feature class already used by V. Report `NEXUS_FIRST_ACTION_VALUE_RESULTS.md`.

## Latest — H-objective alignment gap supported on the recorded suite

The best actual64-value sampled sequence's first action loses **20.254 [11.382,29.127]** under forced-first-action+63zero replanning versus the best measured action, across ten decoder units. All60 states cover all3first actions, so the gap is not absent-action coverage. Represented-action and total regret are identical here and are dependent evidence. The exploratory screen passed. However, this is not the globally best sequence, limited future-suffix search is not excluded, and the zero continuation is not a student full-policy value. Learned-baseline versus sequence-reference first-action comparisons remain inconclusive. Further work justified: a source-only readout trained to the actual replanning intervention and evaluated on fresh states, not more scalar tuning. Report `NEXUS_ACTION_VALUE_ALIGNMENT_RESULTS.md`.

## Latest — H-magnitude source-scalar screen failed

The prespecified source-only covariance rule selected common beta0.823947 before fresh visited outcomes. It improved centered prediction error by **+221.281 [73.560,369.002]** but did not establish chosen64 return improvement: calibrated−base **−9.228 [−22.358,+3.901]**, calibrated−original **+1.194 [−0.102,+2.489]**. Both primary return intervals include zero, and no task/visitor subgroup establishes a gain. No claim that all calibration fails or that a scaling-only cause is disproven. Decoder intervals are conditional on the shared source-fitted scalar; uncertainty in fitting beta is not included. Further scalar tuning on this closed data is unjustified. One next question: does even perfect full-sequence value ranking align with executing its first action then replanning? Existing16-sequence and three first-action outcomes can support a separate exploratory offline audit. Report `NEXUS_SOURCE_SCALAR_RESULTS.md`.

## Latest — visited-state value information is mixed

The exploratory intersection screen failed: centered tail benefit **−1,194.516 [−2,025.559,−363.473]** despite tail pair-ordering advantage **+0.05597 [0.00432,0.10763]**, ten decoder units. Label `tail_centered_error_worse_than_constant`. Thus this finite suite supports poor candidate-relative error magnitudes, but contradicts a blanket claim that no ordering information survives. Fixed-source-constant absolute MSE benefit includes zero, so do not claim reliably worse absolute calibration. Prefix/tail combination remains unresolved: research-only actual-prefix substitution is descriptive, not a causal intervention on a learned controller. No new environment data, neural inference or training; parent return effects are duplicate evidence. Further work justified: a source-only scalar calibration test on separately registered visited-state data, not larger encoders or tuning on this sample. Report `NEXUS_VISITED_VALUE_RANKING_RESULTS.md`.

## Latest — H-persistence, complete but not established

The initial-state correction×commitment benefit did not establish a positive replication at phase50 visited states: interaction **−5.999 [−22.293,+10.295]**, n10 independently pretrained decoders, all five scoring students and both visitors averaged inside decoders. Full-sequence gain **−7.784 [−22.369,+6.800]**. Both registered screen conditions failed. This is inconclusive regarding a nonzero effect, not equivalence or a universal negative. Visitor/task intervals also include zero. The posthoc paired decline relative to the old initial-state sample is **−45.365 [−72.104,−18.625]**, but states, candidates and resets differ, so it does not isolate a causal distribution effect. No controller modification is justified. Unknown: whether the fixed readout loses within-state candidate discrimination at visited states. A separately registered offline audit can use already recorded outcomes without training or new data. See `NEXUS_VISITED_COMMITMENT_RESULTS.md`; all earlier claims/results are retained.

## Latest — H-commitment, completed development diagnostic

The same-state experiment supports sensitivity to commitment length: corrected-minus-original return gain16 minus gain1 is **+39.366 [26.247,52.484]** across ten independent decoders. Gain16 **+36.710 [26.599,46.821]**; gain1 **−2.656 [−7.215,+1.904]**. Both registered screen conditions passed. This distinguishes a commitment interaction from the earlier unmatched-state comparison. All three task-level interactions are positive, but only two initial states per known development physics were sampled. Zero-context correction also has a positive interaction, so student context is not established as necessary. Corrected sequence commitment remains descriptively below original first-action return. Full-episode usefulness and late-state persistence remain unknown. No model training, confirmation reuse, or control-generality claim. Raw artifact `artifacts/commitment_value.json`, SHA1844bf2a97316cf8a2c5e4a00ef145c03c88bb693632c5fc3b13181865975623; report `NEXUS_COMMITMENT_VALUE_RESULTS.md`.

Evidence is from committed artifacts unless marked *reproduced this checkpoint*. CIs are seed-clustered Student-t 95% where that protocol existed. Completing a version tag is not AGI.

| ID | Hypothesis | Support | Contradiction | Failure modes | Unresolved | Further work? |
| --- | --- | --- | --- | --- | --- | --- |
| H-V05 | A contextual bandit (LinUCB) can select PPO experiments better than random on independent return | Synthetic bandit: LinUCB beats random/frozen, CI excludes 0 | CartPole/Acrobot independent champion CIs all include 0; frozen point estimate > updating LinUCB | Inner PPO 8k steps too weak; Acrobot all −500 | Would a 250k inner loop change selection? (costly, not learning-to-learn) | **No** as a path to L2L. Keep as a cheap scheduler only |
| H-V06 | Sequential CL (naive/replay/EWC/multi-head) beats specialists on CartPole variants | — | No method beat specialists **and** naive with non-overlap; V0.6.1 FWT **−45 [−85, −5]** | Unsolved source policies; 2–16k steps | Solved specialists + larger replay | **No** on unsolved 8k PPO. Closed in V0.6.6 |
| H-V064 | Encoder transfer (new head) beats scratch | V0.6.4 confirm **+300 [224, 376]** vs scratch | V0.6.5: random encoder + source RMS beats pretrained encoder (**D−B = −110**) | Confounded with RMS; encoder can hurt | When do features transfer after RMS is controlled? | **No** as “representation learning” until RMS is not the whole effect |
| H-V066 | RMS-only reuse is the useful mechanism | B vs A **+222 [173, 272]** | LinUCB choosing `rms_only` did not beat fixed B (CI includes 0) | Normalization ≠ task intelligence | RMS + tiny adapter? | Optional control, not a research engine |
| H-V07 | A residual WM supports planning better than greedy / random | V0.7.3 H=3 **+225 [206, 245]** vs greedy | Ridge one-step can have **worse** MPC if RNG is reset every step (V0.7.1) | Too few candidates at long H; ridge≠residual | Calibrated uncertainty unused | **Keep** as the only reliably positive WM result — on CartPole |
| H-V08 | Fine-tuning the WM on a shifted CartPole lowers error **and** raises return | FT@128 MAE 0.017 vs frozen 0.035 | Planning already 500; no control headroom. V0.8.1: MAE↓ return **263 vs 290** | MAE ≠ control; ceiling tasks | Off-policy error vs planner-state error | **Stop** treating one-step MAE as the objective |
| H-V081 | Residual-error detector finds physics/noise shifts | FPR 0, delay ~31, miss 0 (V0.8.1–V0.8.9, *reproduced delay 31*) | PH/window TPR CIs overlapped in V0.8 | Alarm ≠ useful update | Recalibration vs fixed: no delay difference in V0.8.9 | Detector is adequate; not the bottleneck |
| H-V082 | Belief estimators (Kalman/GRU) improve noisy MPC | — | Identity ≥ Kalman on noisy; Kalman **hurts** clean (281 vs 500); GRU unusable in MPC | Filter mismatch; GRU not in planner | Learned beliefs with training in the loop | **No** until a belief is in the actual planner and wins a paired CI |
| H-V083 | Gated online learning beats never-adapt | — | MAE +12 CI includes 0; always-adapt harmful-commit 0.50 | Wrong control comparison (later fixed) | — | Historical; superseded by V0.8.4+ |
| H-V084 | Fair H=32 control gate selects better models | Engineering: matched seeds, observe-once | **0 accepts** (`tie_or_small_diff`); cartpole saturates at H=32 | Horizon too short | Longer matched H still ceiling in V0.8.5 | **No** as a CartPole gate |
| H-V085 | MAE gate on a shared candidate bank has decision value | Confirm MAE vs never **+50.5 [8.7, 92.2]** excludes 0 | Seed-mean pair Δ vs never includes 0; 6 harmful accepts; later versions do not replicate this gain | Bank ≠ online collection | Was +50.5 luck + ceiling? | **Do not retune**; treat as one unreplicated positive |
| H-V086 | Low-LR candidates are safer than standard FT | Harm 0.25 vs 0.60 on the bank | MAE choice vs never **+5.6** includes 0; online MAE **0** accepts | Too-small updates (see checkpoint audit) | Larger LR + early stop on **independent** val | Only if control CI excludes 0 |
| H-V087 | Online MAE accepts once collection matches the bank (128/64) | Accept rate 0.25 vs 0 for 64/32 split | Δ **+7.5 [−3.5, +18.5]** includes 0 | Size ≠ usefulness | Persistent vs chunked collect | Diagnostic only |
| H-V088 | Change-triggered multi-cycle learning improves control | Detector works; ~0.95 accepts / 3 cycles | Δ **+3.3 [−35, +42]** includes 0; retrieval = gated, not > never | Accepts don’t move MPC | Deployed-data vs frozen pool | **No** further cycles on CartPole without better candidates |
| H-V089 | Past tasks reduce data needed on a new task D | Persistent episodes work | Frozen **384** vs scratch **43**; ABC-then-D Δ **0**; MAE-gated 4/4 rejects | Gate never commits; frozen already strong | If we forced always-adapt on D after ABC | **Falsified** under the frozen protocol |
| H-V089b | Low-LR proposals fail the MAE gate because they are tiny, not because the gate is blind to huge gains | *Reproduced:* ratio 0.996, L2 Δ 0.10, disagreement 2%; 0/40 ≤ 0.97 | 13/40 1-ep Δ≥10 but 13/40 Δ≤−10; seed Δ includes 0 | 1-ep control is a weak audit | Multi-episode matched control on the same 40 pairs | **Do not retune 0.97** |
| H-V089c | Frozen H=3 residual MPC beats random on Pendulum | — | Default-g confirm Δ **+143 [−84, +370] includes 0** | Horizon too short vs dt=0.05 s swing-up | New g/eval later showed H=3 Δ>0; do not overwrite H1 | **H1 failed**; keep the artifact |
| H-V089d | A longer development-selected horizon of the **same** planner beats random on new Pendulum physics | Confirm H=16 Δ **+524 [443, 605]**; CartPole H=3 still 500 | Oracle-on-dev **−128** vs learned **−621**; not swing-up | Search and WM error remain | — | Diagnostic closed |
| H-V089e | MAE-gated low-LR beats frozen H=16 MPC on shifted Pendulum | Always-adapt **+211 [134, 288]**; low-LR **+106 [39, 173]** vs frozen | **Primary MAE-gated +29 [−28, +86] includes 0** | Gate rejects useful updates / accepts mixed harm | Control-based gate as a **new** pre-register, not 0.97 retune | **No** meta-learning on the MAE inner loop |
| H-V089f | A→B→C reduces data needed on Pendulum D | — | ABC vs naive **+22 includes 0**; vs matched **−6 includes 0** | Same as CartPole V0.8.9 | Different inner adapter | **L2L not shown** |
| H-V089g | First-order Reptile init adapts faster than matched-data multitask on new Pendulum physics | Multitask beats source AUC **+163k [70k, 257k]** | Reptile − multitask AUC **−765k** excludes 0 (worse); Reptile ≈ scratch | Reptile interpolation destroyed useful init; inner k/ε not tuned on confirm | MAML / more outer steps would be a **new** pre-register | **No.** Do not scale meta-learning from this. This does not disprove Reptile in general |
| H-V089h | Transition-context FiLM adapts with fewer Pendulum steps than multitask fine-tuning | Encoder L2 Δ **1.52**; returns finite | Dev primary AUC real **−755** vs fine-tune **−454**; real−zero **−103**; real−wrong **−30**. All gate signs negative | Weaker (48, 48) trunk; z poorly separated; real context hurt control | Diagnosis below. Do not open the unused confirmation tuples | **Inconclusive** on the locked confirm test (not run). Development screen **failed** |
| H-length / H-context | Varied support length helps short histories; real context lowers held-out prediction error | Variable−fixed control point estimate **+22**; source real MAE does not beat zero for the fixed trainer | Source fixed real MAE **0.0703** vs zero **0.0700** at budget 128; dev real **0.084** vs zero **0.077**. Control intervals include 0 | Context raises angular-velocity error; ‖z_real−z_wrong‖ ~0.2. Zero-context control still ~146 below the MLP | Optimization diagnostic below. The old artifact key name is unchanged | **H-context not supported** on the fixed trainer. **H-length not established** (interval includes 0) |
| H-optimization | More Adam updates make real context beat zero and wrong context on held-out source prediction | First 300 updates reproduce the diagnosis. Selection angvel falls from **0.150** at 300 updates to **0.136** at 3000 | Audit at 3000: real angvel **0.1264** vs zero **0.1256** vs wrong **0.1234**. Benefits **−0.0008** and **−0.0030**, intervals include 0. Screen failed (1/3 seeds) | Extra updates improved the shared dynamics. Real context stayed worse than zero | Freeze the 3000-update trunk and train only the encoder/FiLM. Do not add updates or open confirmation | **Not supported.** Dynamics improved. Context use did not |
| H-frozen | With the trunk frozen, encoder and FiLM training makes real context beat zero, wrong, and a constant context on a fresh source audit | Checkpoint 0 reproduces the 3000-update selection angvel **0.1363**. Selection real angvel falls to **0.118** at 1000. Frozen hashes unchanged. Encoder L2 **1.60–2.32** | Audit real **0.1484** vs zero **0.1159**, wrong **0.1207**, constant **0.1127**, start **0.1482**. Positive seeds **0**. MAE and horizon 16 exceed the 5% harm limit. Screen failed | Real context is worse than the same model's zero context. The history-free vector is near the MLP; the encoder is not | Directly optimize a latent context with no history encoder. Do not add encoder updates or open confirmation | **Not supported.** History use is absent |
| H-latent | With all network weights fixed, a latent vector optimized from a task's support transitions improves held-out query angular-velocity MAE over zero context, a global task-independent vector, and a vector optimized from wrong-task support | Fresh source audit, rule Adam 0.1 × 256 from the global vector. Task angvel **0.0628** vs zero **0.1151**, global **0.1109**, wrong **0.1762**. Paired control−task intervals exclude 0. Positive seeds **3/3**. Support loss **0.00114 → 0.00030**. Frozen hashes unchanged. Screen passed | Cos and sin point estimates are slightly higher than the global vector; those paired intervals include 0. The frozen encoder on the same rows is **0.1256**, worse than zero. Wrong-support optimization raises query error | Source physics only. Three seeds. Bounded search, not a globally optimal code | Confirmation of the locked rule on hash `87b83c41be34aa1a` | **Supported on this source audit.** Encoder inference is still the weak step. Not control, not L2L |
| H-latent-confirm | The locked support-only latent rule lowers held-out query angular-velocity MAE on the reserved confirmation physics versus zero, the global vector, and a cyclic wrong-support vector | Hash `87b83c41be34aa1a`. Task angvel **0.152** vs zero **0.308**, global **0.314**, wrong **0.398**. Paired intervals exclude 0. Positive seeds **3/3**. All four tasks met the 5% point bar. Frozen hashes unchanged. Screen passed | c2 (m=0.35) remains high at **0.335**, only about 10% below zero. Frozen encoder **0.307**, level with zero. Sine paired difference vs global includes 0 | n=3 exploratory. Four physics tuples, not every pendulum. Support-loss drop is not the claim | Can a history encoder be trained to predict this support-fit latent and keep the query gain? | **Supported on this confirmation set.** Not amortized inference, not control, not L2L |
| H-amortized | The existing history encoder, trained to match support-fit teacher latents, lowers held-out query angular-velocity MAE below zero context and below that frozen encoder | Student is slightly below the frozen encoder: paired difference **+0.0026 [0.0015, 0.0037]** | Best development cell, λ 0 / epoch 120 / 128 rows, angvel **0.1747** vs zero **0.1587**. Paired zero−student **−0.0159 [−0.0170, −0.0149]**. All 48 cells lose to zero. Teacher **0.0781**. Recovery **−0.39**. Training latent distance still **1.27** at epoch 400. Gate failed. Hash `d1fa621351d286cf` not collected | Ten student seeds share three decoders. Epoch 400 was worse on the development metric. One decoder's student beat its own zero context; the pre-registered mean did not | Whether this encoder can be driven onto the eight saved teacher codes without reading development queries | **Not supported.** Not control, not L2L |
| H-represent | The existing 584-parameter mean-pooling encoder can reproduce the eight saved meta-training teacher latents on the support that defined them | Rate **0.01**, step 2000: mean latent distance **0.0074, 0.0021, 0.000024**. Worst tasks **0.0089, 0.0026, 0.000030**. Constant baselines **1.31, 1.75, 1.51**. Output spread matches the teachers. Threshold passed on all three decoders | Rate **0.001** misses the bar (decoder 1 mean **0.252**, worst task **0.534**). A second support of the same task has median distance **1.42, 1.43, 0.87** and is usually not prediction-equivalent | Eight pairs on the support that defined the label. Full batch, not a new task. Decision is the final step, not the best checkpoint | Does a student trained at 0.01 on more source tasks lower development query error below zero and the frozen encoder? | **Supported as a training-set fit.** Not generalization, not control, not L2L |
| H-generalize | The existing 584-parameter encoder, trained at learning rate 0.01 on a broader grid of support-specific teacher codes, lowers held-out development angular-velocity error below zero context and below the frozen encoder | Epoch 200: **0.0913** versus zero **0.1587** and the frozen encoder **0.1773**. Paired gaps exclude 0. The teacher remains lower at **0.0781**. Validation mean **0.0832** versus zero **0.0972** and encoder **0.0951** | Training latent distance **0.648**. Held-out history distance **1.752**. Teacher pairs of the same physics have median distance **1.52**. Validation task va3 is worse than zero, and the teacher is too | Five student seeds share three decoders. Checkpoint chosen on development angular velocity only | A separate confirmation on newly registered physics, retraining these seeds. Do not reopen either reserved split | **Supported on the prediction screen.** The encoder did not reproduce the teacher vectors. Not control and not L2L |
| H-gen-confirm | The same encoder, retrained on the twelve source physics, lowers confirmation angular-velocity error at least 0.01 below zero context, the frozen encoder, and the global vector | Epoch 200: **0.1016** versus zero **0.2729**, frozen encoder **0.2660**, and global **0.2742**. Decoder-level gaps **+0.171, +0.164, +0.173**, each interval above 0.01. Teacher **0.0876**, and that interval includes 0 | Latent distance **1.558**. Sine MAE **0.0098** versus zero **0.0080**. All four tasks cleared the three primary controls | Three frozen decoders. Five student seeds are averaged inside each decoder | Ask whether the saved student context improves H=16 MPC return. Do not retune this split | **Supported on the prediction screen.** Not control and not L2L |
| H-control | The epoch-200 student context raises H=16 MPC return by at least 25 points above zero context and the frozen encoder on the four confirmation physics | Student **−683.0** versus zero **−768.4** and the frozen encoder **−773.2**. Paired gaps **+85.4 [−109.4, +280.3]** and **+90.2 [−5.7, +186.1]**. Both intervals include 0 | Decoder 1 is only **+11.0** above zero. High-gravity and heavy-mass returns stay below **−1000**. The 16-step imagined score does not separate the controllers | Three frozen decoders. Five student seeds are averaged inside each decoder | Keep these episode seeds closed. Do not retune the encoder from this return | **Inconclusive.** The point estimate is positive and the interval includes 0 |
| H-control-replication | Across ten independently trained decoders, the same student raises H=16 return by at least 25 above zero and the frozen encoder, on new episodes of the previous physics and on disjoint physics | Replication return **−636.4** versus zero **−708.6** and encoder **−699.2**. Gaps **+72.2 [+45.6, +98.8]** and **+62.8 [+31.3, +94.3]**, both lower bounds above 25 | Fresh physics **−716.0** versus zero **−696.6** and encoder **−705.7**. Zero gap **−19.4 [−35.4, −3.3]** lies below 0. Visited prediction still improved on both sets | Ten decoders. Seeds 0–2 are the old weights on new episodes. Episode SD exceeds decoder SD because tasks are pooled inside the decoder | Do not retune this sample. The return gain did not transfer | **Negative transfer.** Replication passed. The new physics did not. Not L2L |
| H-prediction-control | On the fresh physics, better one-step prediction comes with worse ranking of shared H=16 candidates | One-step angular velocity improves **0.1148 [0.1030, 0.1266]**; open-loop and recorded error improve too | Regret improves **1.313 [0.507, 2.118]** and H=16 score error falls **6.386 [5.450, 7.322]**. The closed episode gap remains **−19.4 [−35.4, −3.3]** | `rp1` and `rp2` regret intervals include 0. Forecast error stays about **12.8**. Open-loop error stays about **1.16** | How a better one-shot score loses a 200-step episode | **Ranking improved.** The planner audit is H-receding. Not a control claim |
| H-receding | On fresh visited states, the one-shot regret advantage reverses, or the matched next-16 continuation reverses it, or live replay fails | Replay **1920/1920**. Selected-score error falls **4.751 [3.023, 6.480]** and reward-forecast error falls **6.539 [4.548, 8.529]**. Step-0 regret is **4.303 [1.276, 7.330]** | Pooled regret **0.812 [−0.038, 1.662]** and next-16 **−0.528 [−1.139, 0.083]** both include 0. Spearman **−0.013 [−0.067, 0.041]**. `rp2` regret favors zero | Task signs differ. Step-0 continuation **−2.221 [−4.622, 0.181]** includes 0. Next-16 is not a 200-step value | Which mechanism produces the closed **−19.4** episode gap | **Inconclusive.** Do not change the architecture or the planner |
| H-return-phase | On new fresh episodes, the student-minus-zero return difference arises in steps 0–15 or in steps 16–199 | Total **−30.671 [−41.540, −19.801]**. Late **−29.441 [−40.706, −18.175]**. Late share **0.928 [0.836, 1.020]** | Early **−1.230 [−2.583, 0.123]** includes 0. `rp1` total includes 0. `rp2` late is **−98.6** and dominates | New seeds, not the closed **−19.4** sample. Observation distance grows to **2.86** by step 199 | Why the paired trajectories separate after step 15 | **Primarily late on this sample.** Not a general control claim |

## Mechanisms that have never shown useful transfer

These produced no paired control/sample-efficiency gain that survived an independent confirm:

1. Sequential naive fine-tune / replay / EWC / multi-head on CartPole variants (V0.6).
2. Learned experiment selection on real PPO (V0.5).
3. Encoder-only reuse after RMS is controlled (V0.6.5).
4. GRU/stack beliefs in the planner (V0.8.2).
5. Uncertainty-directed collection (V0.8).
6. Fair H=32 control gate (V0.8.4).
7. Probe-MAE snapshot retrieval without task labels (V0.8.8–V0.8.9).
8. ABC experience as initialization for D under MAE (V0.8.9).
9. Always-adapt online (often negative point estimates).
10. Transition-context FiLM on Pendulum prefixes (development gate failed; confirmation physics not evaluated). The Reptile loss in H-V089g is specific to that configuration.

**Normalization reuse (RMS)** transferred vs scratch. That is a statistics-copy, not an improving learner.

## Unresolved scientific questions

1. Can any CartPole WM update improve H=3 MPC return vs frozen with a CI excluding 0 **and** without retuning 0.97?
2. Does the V0.7 residual+H=3 recipe plan at all off CartPole?
3. Is one-step MAE on incumbent actions the wrong proxy for planner-relevant error (multi-step / near-failure)?

## Current late-control hypotheses (later than the historical register above)

H-late-action: on the registered late states, the student-selected first action loses at least one return point under shared zero-context next-16 continuation. **Not established**: +0.0312 [−0.0827,+0.1452], ten decoder units, complete grid. Full-policy next-16 is also inconclusive. This is not equivalence and not a general control result.

H-long-policy: full-policy continuation from identical late states loses at least five points in local steps 16–63. H-long-first-action: the selected first action alone has delayed adverse consequences under common-zero continuation. **Both are untested proposals**, locked in `docs/NEXUS_LONG_CONTINUATION_PROTOCOL.md`; no new data collected, budget not yet approved. A future negative/inconclusive outcome must not trigger automatic architecture expansion.

## H-policy-switch — predeclared bounded diagnostic

After the measured rp2-concentrated longer-continuation loss, compare SS with SZ tail return after identical student-controlled 16-step prefixes. The same frozen controllers, H=16/16 candidates and ten decoder units are retained. SZ-ZZ inheritance and ZS-ZZ suffix-after-zero are secondary. See `docs/NEXUS_POLICY_SWITCH.md`. The one bounded local run is authorized; no performance improvement is claimed from its design or tests.

## Latest bounded diagnostic: paired policy switching

The rp2 prefix/suffix experiment completed with SS-SZ tail **−18.733 [−27.271, −10.195]**, favoring zero-context continuation after identical student prefixes in all ten decoders. SZ-ZZ inheritance **−4.025 [−23.422, +15.373]** and SS-ZZ overall **−22.758 [−45.939, +0.424]** remain inconclusive. This isolates a continuation-policy disadvantage on the registered states; it does not establish a general switching controller or explain the whole historical episode loss. All checkpoints remain frozen. Details: `docs/NEXUS_POLICY_SWITCH.md`, artifact `artifacts/policy_switch.json`. No general control improvement, learning-to-learn or AGI claim follows.


## Latest source planning-value diagnostic

The frozen-model diagnostic completed all planned data in 238.48 s. An initial support-hash format validation bug was corrected offline without resimulation; the unchanged failed capture and separate complete validation record are both retained. Exact simulator H=16 selection still lost **34.685 [22.677, 46.694]** points to the best64 candidate under a shared zero-policy continuation. The source development screen passed. Student-minus-zero selected64 return **+1.507 [−2.870, +5.885]** is inconclusive. This supports short-objective truncation under a full-block intervention, not a causal explanation of the historical negative transfer or a controller improvement. Source suite: eight known physics, one fresh state each, ten decoder units; all weights fixed and 120 files verified. Costs: 64,512 environment steps, 15,851,520 imagined states. Final tests: 480 passed, plus explicit checkpoint audit. See `docs/NEXUS_PLANNING_VALUE.md`; primary summaries are in `artifacts/planning_value_validation.json`, tied to the unchanged raw capture. Prior pending entries below/above are chronological, not the current run status.


## Terminal-value pilot prepared — no experimental results

The next source-only score-correction experiment is implemented on `codex/terminal-value-pilot`, from base `03ae187`. It adds a 78-coefficient source-fitted terminal readout per decoder while preserving all existing neural weights, H=16 and sixteen candidates. Readout source fitting and development collection are separated by a saved, validated manifest. Primary outcome is corrected-student minus unchanged-student same-state common64 first-action return; ten independent decoders, one-point practical margin and a positive lower95% bound. Strong zero-context and corrected-zero comparisons remain explicit.

Readiness: 35 focused tests and 515 full-suite tests passed; the separate local audit verified120 binary files. The default runner performs preparation only; direct execution without exact budget/config approval fails before collection. **No registered source fitting or evaluation has run.** Proposed cap:600 seconds,28,800 real steps and7,050,240 imagined transitions; estimated2–4 minutes. See `docs/NEXUS_TERMINAL_VALUE_PROTOCOL.md` and `artifacts/terminal_value_preparation.json`. Existing measured findings remain unchanged. This prepared implementation is not evidence of a control gain.


## Completed terminal-value correction pilot

The single approved run completed in109.68 seconds, all28,800 real steps and7,050,240 imagined transitions. The primary corrected-student minus unchanged-student common64 first-action difference is **−0.221 [−5.881,+5.438]**, n10 decoder units. The one-point improvement screen did not pass; label `local_first_action_inconclusive`. Corrected student versus unchanged zero is **−1.655 [−6.798,+3.489]**; corrected zero versus unchanged zero **−1.540 [−6.582,+3.502]**; all secondary intervals include zero.

The correction changed154/300 student first actions. Source-fit RMSE improved versus a training-mean constant, but held-out terminal-value accuracy was not measured by these first-action counterfactuals. All110 six-model groups preserved weights/context/normalization;120 checkpoint files verified before/after and independently afterward. Full suite516 passed; no further training, repeat experiment or confirmation/control sweep. The earlier pending-approval entries are preparation history, superseded by this completed result. See `docs/NEXUS_TERMINAL_VALUE_RESULTS.md`. One next proposal: frozen readout calibration on new states using actual versus imagined endpoints, before changing capacity.


## Frozen terminal-value calibration — registered, not executed

H-readout: fixed source-fitted terminal readouts lack held-out state calibration. H-endpoint: imagined endpoint error changes their calibration. These competing explanations may coexist. The locked primary screen instead tests the positive alternative: student-context imagined-endpoint RMSE beats the fixed source mean by at least10%, with paired95% benefit lower bound>0 across ten decoder units. Actual-versus-imagined errors and source results are secondary exploratory diagnostics. One state per known physics, four candidate labels per state; these are not independent decoder replications. No new outcomes exist and the earlier inconclusive control result is unchanged. Protocol: `NEXUS_TERMINAL_VALUE_CALIBRATION_PROTOCOL.md`. Execution awaits separate exact-budget approval; no controller change, learning-to-learn or control-success claim.


## Completed frozen terminal-value calibration

All registered data completed in83.48 seconds:21,824 real steps and5,448,960 imagined transitions; no support collection, fitting or model updates. Student imagined-endpoint development RMSE85.437 versus source-mean128.324 gives **+42.887 [34.451,51.323]** paired error reduction,33.42%; the registered10% screen passed. Actual endpoints did not improve error reliably: imagined-minus-actual **−2.649 [−7.169,+1.871]**. Source reduction was7.81%, a secondary result. This is value calibration versus a constant, not control improvement or evidence of accurate within-state ranking. Earlier control findings remain closed.

The original full raw capture retained its final exact-sum validation failure (maximum Python/NumPy difference1.7e−13). A separate complete offline validation and independent arithmetic audit recover the grid without any replay. Original capture SHA419a07b95881aaeae1a61c57e194acd75d37a73031e23990a4ca315ca7245d4d; execution40bc1e3; validator204b463. All120 checkpoint files and110 groups preserved. Focused35 passed; full **551 passed,1 deselected** in126.35s; standalone120-file verification passed. See `NEXUS_TERMINAL_VALUE_CALIBRATION_RESULTS.md` and `artifacts/terminal_value_calibration_validation.json`. Earlier pending statuses are retained preparation history. The two-hour session's wall-clock window elapsed during a later pause; no additional simulation was started afterward. Next: a separately registered exploratory within-state analysis using only recorded data.


## Completed recorded-data candidate discrimination

The frozen scoring replay completed in8.01 seconds, **zero new environment steps**,337,920 imagined transitions, all110 cells and all120 checkpoint checks. On the same four labeled candidates, committing the complete16-action sequence plus zero48 continuation improved chosen64 return by **+24.030 [1.279,46.781]** on development, n10 decoder units; source +6.951 [2.576,11.325]. This is explicitly exploratory reanalysis of inspected data, not independent control confirmation or first-action replanning performance. The earlier −0.221 first-action result stays inconclusive and closed.

Development gain is concentrated in dev0 (+71.520); dev1 and dev2 intervals include zero. Centered prediction benefit +106.993 [−42.133,256.119] is inconclusive despite absolute calibration success. Constant correction changed0/660 choices, so its identical contrast and regret reduction are dependent evidence, not corroborating replications. A separately labeled posthoc uniform-in-set reference also favors correction (+16.750 [1.181,32.319]); it is not a preregistered randomized-controller result. All models/readouts/normalizers/contexts remain frozen. Before analysis566 full tests passed; final **567 passed,1 deselected**,132.08s, and51 combined focused tests passed. Independent selected-index arithmetic agrees. See `NEXUS_VALUE_CANDIDATE_DISCRIMINATION_RESULTS.md`; raw analysis SHA4de98e582129067a4d18c9012c5b053fe5d7361fb295370e5b5d6add2da412ed, execution438bacea9fd327c5d56e2ad8128baaa20679d897.

One next experiment is designed, not executed: same-state correction×commitment-length interaction (1 versus16 actions), then common zero continuation to64; ten decoders/five students, unchanged H16/16 candidates, fresh registered states. Proposed59,136 real steps,14,883,840 imagined transitions, estimated4–6 minutes, cap900s. See `NEXUS_COMMITMENT_VALUE_PROPOSAL.md`. No extra simulation was started after the prior two-hour wall-clock window elapsed during an interruption. No general control improvement, learning-to-learn or AGI claim.


## Same-state commitment diagnostic prepared — not executed

The next hypothesis is now a locked executable comparison of correction×commitment length, using identical states,16×16 candidate arrays and action-independent common-zero continuation. Primary gain16-minus-gain1 is averaged inside ten independent decoder units, preserving all previous scores, weights, readouts and normalizers. Complete source reconstruction verified120 files and30 decoder/task context groups, with no new registered environment data. Budget59,136 real steps/14,883,840 imagined transitions, estimated4–6 minutes, hard cap900s. Actual research outcomes remain unknown; readiness/tests are not improvement evidence. See `NEXUS_COMMITMENT_VALUE_PROTOCOL.md` and the preparation record for exact revision, hashes and executed tests. Prior candidate-discrimination/first-action results remain closed and unchanged. Execution awaits new exact-budget approval.
