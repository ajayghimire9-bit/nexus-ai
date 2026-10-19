# E3.8 — Compact Observation–Support Interaction and Learning Interfaces

## One targeted experiment, locked before outcomes

Base4c31881209467cafb1ecc92b182702b366f4f854 verified against GitHub; branch codex/e3-8-interactions-and-learning-interfaces. User supplied seven proposed milestones and explicitly requested implementation. Existing standing2026-10-16 grant permits this bounded source-only experiment. These are proposed capabilities, not already demonstrated successes. Preserve the two unrelated untracked Evolution-1 adapter files.

Hypothesis: source context needs to modulate the observation-to-strategy relationship. Reuse AdvantagePredictor, existing ridge=1/RMS, feature_informativeness blocked-reset/permutation adapter, source-support preprocessing and SAME one-run audit host. No replacement learner, memory, planner or resource meter. Exactly ONE new representation, no feature/regularization search and no further feature-selection rounds on these36 pairs.

Feature version compact_observation_support_v1: z has six padded source-normalized/tanh observation coordinates; c has the two nonconstant source-transition summaries from E3.7 (normalized mean absolute state change, normalized linear residual MAE). Drop action coverage, which is1 in all four sources, and remove repeated strategy-descriptor coordinates. Extract and certify the factorization of the existing cached outer-product features; no new source-normalizer fit or query-dependent preprocessing.

Compact additive features: [1,z6,c2],9 coefficients. Compact interaction: [1,z6,c2,flatten(z6 outer c2)],21 coefficients. Estimate d_hat=mu_model+ridge(features) with residual training labels d−mu_model. This implements a learned observation slope plus context offsets plus bilinear interaction. Coefficients are ridge/RMS scaled; the displayed formula is in those coordinates. Native feature vectors have9/21 dimensions, NOT padded192. Packed414-value audit storage includes preserved old layouts for provenance but is never a414-coefficient learner.

Compression removes duplicates and CHANGES the effective penalty relative to old192 features even though numerical ridge remains1. We explicitly do not preserve that old penalty or claim equal effective capacity. The first nine shared coordinates have the same training RMS in the compact additive/interaction comparison; interaction adds12 parameters. Compare both, disclose capacity and do not attribute any improvement solely to interaction unless its added value exceeds additive.

## Permitted data and resource ceiling

Only original E3.4 TRAINING manifest e3_4_predictor_b9.json, hash5bc051a2effe1fb2c9220393881fe4a1f8ec77f08c28f9660d5d6cb8418c743a:36 training pairs/features plus frozen source normalizers/support receipts. Four pinned original TRAIN NPZs, first32 rows/model, already specified in E3.7/config: verify complete file hashes and original prefix receipts. Reuse exactly the E3.7 support summaries; one descriptor least-squares diagnostic per source. No validation/bundle2/E2.17 arrays or checkpoint loading, no new simulator collection, no neural inference/training or imagined environment rollout in the registered scientific run. Other interface tests use authored deterministic fixtures only.

Nine blocked-reset folds each train32 rows/eight per model, query4; recompute model means, residual labels and fit-only RMS. No query returns in fitting or feature construction. Model means are legitimate training-only priors for these KNOWN source models, not an oracle available on unfamiliar models.

Conditions: model means; compact additive; compact interaction. For both feature maps,19 within-model TRAINING-feature permutations using the same locked E3.6/E3.7 map613000+held*10000+p*10+k, labels and means unchanged, query untouched. Forty coefficient fits/fold,360 total;64 antisymmetric numerical rows/fit are not new contexts. Freeze coefficients/designs/targets/predictions before scoring. No fitting after outcomes.

One run,30s CPU-local wall cap,360 ridge attempts,4 support least-squares attempts,0 real/imagined/neural scientific work. Carry ledger785.453092043025 used/2814.546907956975 remaining. Single-thread BLAS/OMP/VECLIB, no paid resources, retries or cap extensions. Allocation cites standing grant/user attachment and exact config/protocol/prior validation hashes. Commit tested implementation/protocol/allocation before fitting. Exclusive artifacts, deadline guard and SIGALRM, save partials honestly.

## Primary decision and supporting diagnostics

Primary: out-of-fold selected cached return versus model means. Average nine queries inside each existing pretrained model, then two models per family. Require:
- >=1 return-point mean interaction-minus-model-mean gain in EACH family.
- Strict positive gain in ALL four individual pretrained models.
- Interaction family mean return no worse than compact additive in BOTH families.

Otherwise label compact_interaction_selection_not_established; if all pass, compact_interaction_selection_passed, still exploratory source reuse only. No cross-family raw-unit pooling, CI or significance from two models/family/shared ridge fits. Query resets and permutations are not model replications. No threshold changes, winning regularization or support-feature changes after inspection.

Report every model/family, helpful and harmful override counts AND summed gain/loss, MAE/RMSE/sign, within-model permutation ranks, variability/ranks and resource costs. Magnitude error and permutation checks are supporting diagnostics, not hidden primary gates. Old5%/18-of19 config fields are retained for labeled MAE diagnostics only. Return improvement equals regret reduction on this same two-arm table; not independent evidence. Forecast advantage is not observed feedback, and cached-return improvement is not a new environment/control-generalization result.

Independently verify360 ridge solutions without ridge fitting, recompute4 pinned source descriptors (count these LS recomputations), exact grids/normal equations(abs1e−6)/predictions(abs1e−10,rel1e−12), original historical JSON bytes and code SHA. Save raw predictions, source/config/checkpoint-parent receipts, runtime/CPU/dependencies/ledger. No historical result edits.

## Parallel engineering milestones — no scientific capability claims

1. EpisodeContext interface: observe only completed chronological transitions, optional pre-action prediction, rolling history<=128, reset clears episode evidence but preserves immutable source context. No future-row context construction. No cached episode-prefix evaluation is authorized here: existing reset-choice labels precede the needed history.
2. planner_evidence alongside existing planner_adapter: same horizon/candidate shape/reward definition for incumbent/challenger, score_open_loop reuse, ReservationLedger reserves before each model call; forecast traces/actions/rewards/termination logged. Proposal generation/planning costs are EXTRA, never silently free. Disagreement is not calibrated failure probability. Real frozen-model evidence evaluation requires its own scoped protocol; current tests use FakeStepModel only.
3. StagedStudy coordinator: separate source fit/freeze, chronological charged probe adaptation and final evaluation. Shared probe cost counted once physically, logical prefix shared equally; remaining horizon192 after8-step probe. Trusted host must provide completed existing-ledger receipts; policy/context frozen during final scoring. Known-model SourcePrior versus source-family fallback for unfamiliar models; never supply true target means. Production config remains registered=false/authorized=false, no new seed registration or environment worker bound.
4. Opt-in parent–child mutation credit in EXISTING StrategyGenerator: single structural mutation of a parent leaf, exact matched pair context/reset/planner/horizon/cap, training full-policy observed returns only. Credit=tanh((child−parent)/registered_scale)/(1+paired_CPU_seconds); average by mutation type, softmax preferences changes future kind proposals. No leaf credit from this path; original coarse update remains historical/default. Return scale fixed100 for engineering examples, not tuned. Random adaptive=false baseline, withheld/final/forecast/replay rejected. Trusted Python host attestation is NOT a cryptographic evaluator sandbox.
5. TaskStream bounded A→B→A→C state machine: same generator/AdaptiveProposer and Journal, existing meta.controller.EpsilonGreedyController statistics reused; no duplicate RL/memory framework. Retained mutation evidence/provenance, persistent/reset/shuffled memory controls and adaptive/random/fixed schedules. Reward only observed return improvement per measured CPU, not prediction error. Noisy zero gain stops after bounded exploration; fixed logical step bound is not a replacement for physical resource ledger.
6. Learning Lab: offline hash-verified read-only HTML artifact replay, predicted versus observed advantage, cached selected return/regret/mistakes. Synthetic lineage/task-memory illustrations visibly separate from scientific evidence. No live animation, evaluator/training access or network calls.

Protocol tests are deterministic engineering evidence only. Source-only experimental claim concerns compact selection; no claim that episode context, planner evidence, continual learning or mutation learning improves real control. Interface implementations may proceed regardless of compact screen, but fresh control/promotion remains blocked.

## Independent study and stopping boundary

The larger evidence milestone needs a NEW concrete study with fresh resets and frozen selected recipe, then a separate unfamiliar-model/dynamics study. Production collection is not registered/allocated here and E3.4 evaluation/E2.17 grant remain closed. The staged engine supplies contracts; reviewed worker integration, resource/seed review, model counts, costs and independent outcome criteria remain necessary. No repeated validation on this bank counts as independent evidence.

If compact selection fails, stop source-bank representation search; recommend one fresh-data/evidence-readiness step based on the actual result. If it passes, freeze recipe for separately registered fresh-reset validation, not retrospective promotion. Do not run another experiment or automatically enlarge the model from these results. Preserve negative outcomes, main and all historical checkpoints. Commit results separately and push the branch.

## Research precedents

PEARL separates task inference and control with probabilistic latent inference; this interface is transparent rolling statistics, not an implementation or replication of PEARL: https://arxiv.org/abs/1903.08254 . PETS combines uncertainty-aware models with trajectory sampling; NEXUS forecast disagreement remains diagnostic and is not calibrated failure probability: https://arxiv.org/abs/1805.12114 . No performance claim is transferred from either paper.
