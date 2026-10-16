# Same-state value × commitment length — locked protocol v1

Status: implementation preparation only, no registered outcomes. Base c458803d820902e4d1eeb3c3208db1ce40fb50f7 matched GitHub with a clean tree before creating `codex/commitment-value-diagnostic`. Config `configs/commitment_value.yaml`, SHA256 **ebd9b2b5ebf4eff5d7c2248176da89a343b86898e7302bd2d13d7b7726e1f16c**. Original design `NEXUS_COMMITMENT_VALUE_PROPOSAL.md` is unchanged and its hash is bound by config. This protocol finalizes implementation details without changing that design's estimand, sample size, thresholds or budget.

## Why this experiment

The existing terminal readout improved absolute held-out calibration, and exploratory reanalysis favored corrected selection when committing complete16-action sequences among four labeled candidates. A different first-action sample stayed inconclusive. Those studies cannot estimate a commitment-length interaction because their states/candidate sets differ. H-commitment: honoring the planned sequence makes the correction more useful. H-sampling: the apparent contrast arose from the different sampled states/candidates. Both can coexist; the historical184-step negative transfer remains closed.

## Locked methods, inputs and participants

Ten independently pretrained decoders, five broad student seeds each, original zero-context comparator, same source-normalization statistics, saved student latent contexts, frozen ten source readouts, original published reward and torque actions. Preserve encoder/decoder/FiLM/heads/readout hashes and all original checkpoint binaries. No fitting, context inference from new experience, source retraining, network/architecture change, longer planning horizon or additional search candidates.

Reuse exact recorded128-row development contexts, from the prior terminal-value source/evaluation records, checking vector and model/normalizer fingerprints before/after. Unique previous target support384 steps is inherited, not newly collected and not counted repeatedly per decoder/student. Zero new support or teacher data. This is a conditional control mechanism test, not a new support-adaptation or learning-to-learn experiment.

Physics are exactly existing pendulum_ctx_dev0=(g6,m1,l1), dev1=(g10,m2,l1), dev2=(g10,m1,l1.55), checked against the registry. These are inspected development physics, not untouched confirmation. Initial-state seeds2400000+10*t+j; candidate seeds2410000+10*t+j; t0..2,j0..1. At future local step k0..63, candidate seed2420000+256*t+128*j+k. All exact sets are checked against prior closed experiments, including the calibration run. No seed depends on action, method, decoder, student, outcome or commitment length. Candidate generation remains16 sequences, each16 discrete actions, existing chunk size4.

## Intervention, caching and outcome isolation

At each new state generate one shared16×16 candidate set. Each frozen model produces original H16 scores and original+survival16×frozen terminal value scores using observations and saved z only. Outcomes are never passed to scoring, context or any optimizer.

For each selected candidate compare:

1. Force its first action then unchanged corresponding decoder zero MPC for63 steps.
2. Commit all16 actions then unchanged same zero MPC for48 steps.

Both returns cover exactly64 steps. Restore identical true state and simulator clock before every branch. True state/physics are research-only simulator restoration data, never model inputs. At future step k use the same registered planning randomness; branch2 resumes at local clock16 while branch1 replans at1. The continuation interface rejects nonzero context in both arms, including unforced suffixes. Keep context fixed throughout. Record all per-step rewards/actions/termination flags/decision seeds and terminal observations. Published reward timing is checked during collection; prefix traces also permit offline checking.

Cache all three first-action64 trajectories per decoder/state. Cache each actual16-action prefix once per task/state across decoders/context methods. Collect all16 full-block48-step suffixes per decoder/state. This removes the previous four-labeled-candidate restriction while preserving the deployed16-candidate search budget. Cache reuse is accounting, not additional real interactions. Readout/model scoring and actual outcome computation remain separate interfaces.

End-state divergence is the Euclidean distance between commit1 and commit16 end **observations** for each fixed context/scoring rule, computed per student before averaging. It is not the distance between student-mean and zero-mean observations; those are different quantities. Angular observation uses cos/sin coordinates; velocity remains in raw units. Report as descriptive divergence, not causal proof.

## Primary analysis and statistical decision

For each decoder/task/state/student, define `gain1=R_corrected,commit1−R_original,commit1`, `gain16=R_corrected,commit16−R_original,commit16`, and **interaction=gain16−gain1**.

Average five students, two states and three tasks equally inside each decoder. Ten independent decoder values, paired two-sided t95% interval, df9/critical2.262. Student seeds/states/tasks are not independent decoder replications. Primary practical threshold1point and interval lower bound>0. Label `commitment_sensitive_gain` requires both that primary rule and full16 gain interval lower>0. If only the interaction passes, label `relative_commitment_sensitivity_without_established_gain`; all other cases `commitment_interaction_not_established`, with numerical signs/intervals reported. Negative interaction is not suppressed; it favors relative first-action effect descriptively. A favorable interaction with two harmful component effects is not a control benefit.

This matches the original design's conjunctive sensitivity-and-gain screen, not a new posthoc criterion. The final label is one intersection claim; individual component/task/zero-context95% intervals remain unadjusted exploratory measurements. Do not infer an interaction from significant16 versus nonsignificant1 results. An interval including zero is not equivalence. Report zero-context correction, all task/decoder results, selection/action disagreements, end-observation distances, and in-set regret. Regret reduction repeats return gain algebraically, not independent evidence.

These64-step common-zero counterfactuals are not unbiased values of full receding-horizon student/corrected policies. Nor is this an independent unseen-physics generalization test or an explanation of the old full-episode loss. The states are sampled initial states, so late visited-state distribution shift remains outside scope.

## Budget, authorization and execution integrity

Exact real steps:1536 cached prefixes +46,080 full-block suffix steps +11,520 first-action common steps = **59,136**. Imagined transitions:46,080×256 +180×63×256 +360×512 = **14,883,840**. The forced first action requires no model-planning call. Zero network/readout updates, zero new support collection. Prior source/support costs remain inherited.

Estimated4–6 minutes single-thread local CPU, cap **900 seconds**; enforce real and imagined caps before each step. Save incomplete captures on any exception or timeout; never reduce the grid or rerun quietly. Expect six prefix groups,60 decoder/task/state cells, each3 first-action traces,16 full-block tails, six contexts, both score conditions and all required finite metrics. Complete=true only after exact grid, typed metrics, raw scoring arithmetic, reward accounting, frozen fingerprints and120-file before/after audits pass. Stable builtin-float summation and explicit tolerances avoid exact NumPy/Python numeric-type mismatches. Missing cells or invalid execution are not an inconclusive scientific result.

A fresh exact-config approval record and clean committed implementation are required before any environment construction. The previous wall-clock authorization expired and is not reused. Default preparation and `--verify-inputs` create no environment. The latter fails clearly if any binary file/hash or reconstructed group is missing; all30 decoder/task groups must verify before execution collection starts. Repository result arithmetic remains possible without `.pt` files. Never overwrite historical results, configs, protocols, checkpoints, or an existing output. No paid services or main merge.

## Checks and commands

Focused tests must cover reward timing and exact restoration, same candidate arrays, action-independent continuation seeds, invariant zero-policy future, cached counts, context immutability, pairwise endpoint-distance aggregation, gain/interaction arithmetic, decoder CIs, full-grid/type rejection, termination/clock checking, missing binary failure and stale approval before environment access. A synthetic complete capture exercises every raw cell without registered simulation.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_commitment_value.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_commitment_value.py
PYTHONPATH=src:.deps python3 scripts/run_commitment_value.py --verify-inputs
PYTHONPATH=src:.deps python3 -m pytest -p no:cacheprovider
# Only after exact-budget approval is recorded and committed:
PYTHONPATH=src:.deps python3 scripts/run_commitment_value.py --approved-config-sha256 ebd9b2b5ebf4eff5d7c2248176da89a343b86898e7302bd2d13d7b7726e1f16c
PYTHONPATH=src:.deps python3 scripts/run_commitment_value.py --audit
```

Commit implementation/tests/protocol before outcomes, results separately. No other experiment is authorized. If the screen fails or is inconclusive, retain that finding and do not automatically modify architecture or retune these states.
