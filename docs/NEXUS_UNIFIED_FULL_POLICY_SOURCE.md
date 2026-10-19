# Frozen-model full-policy source return screen

Protocol v1. Starting revision: `5221d7f46650f99f453288c7e3482fc5ba21e55a`.
Branch: `codex/unified-full-policy-source-screen`. Prepared before any outcomes.

## Question and boundaries

Does repeatedly executing one fixed switch or ranking composition create useful
episodic return differences beyond both anchors, where the prior first-action
neutral-tail proxy had no grammar-over-anchor headroom? Competing explanations:
the proxy erased useful long-run behavior; or these fixed compositions provide
no robust advantage. A negative result cannot reject every strategy in the grammar.
This is exploratory source-physics controller development, not held-out transfer,
confirmation, useful proposal learning, or learning-to-learn.

Explicit user instruction to actually continue execution plus AGENTS standing
local authority dated 2026-10-16 authorize this separate bounded development run.
The former 50-step/1600-step estimate was a proposal, not a locked experiment.
Here complete episodes are fixed at 200 steps: 32 episodes, 6400 real steps,
9,830,400 imagined-state upper cap, 180-second wall/CPU cap, local CPU only.
Session starts at 335.40020462500377 seconds used; actual runtime, including
preflight and partial failures, is added without resetting the ledger. No retry.
No E2.17 grant reuse, H17 unlocking, confirmation access, fitting or online updates.

## Models, methods and resources

Use the four existing E2.9 disposable residual MLPs: Pendulum/Acrobot bundles
0 and 1, hash-verified against `evolution2_fit_clock_run.json`. Verify original
source NPZ hashes too. All weights, buffers and observation-normalizer statistics
are fingerprinted before/after; files remain outside tracked binaries. Original
fit manifest lacks an execution SHA: retain that provenance limitation.

Reuses `generated_strategies.execute`, catalogue/plan_bound, `planner_adapter`,
`TaskSpec`/existing wrappers and `ReservationLedger`; replaces none of these.
No new proposer, learner, memory or meter. Four policies chosen before scoring:

1. Existing IID flat H16 anchor.
2. Existing IID successor H16 anchor.
3. Switch: successor when abs(observation[0]) > .25, otherwise flat.
4. Sum of the two anchors' per-action midranks, ties lowest action index.

Catalogue budget is 1536 imagined states per decision; this is **not** the old
H16×16-candidate controller. Flat gets96 sequences; successor gets31 tails per
first action (1491 states). Rank blend divides budget768/768 (48 flat sequences
and15 successor tails;1491 states). Switch uses its active branch's budget.
Equal ceilings do not imply identical inference calls or actual work. Disclose
actual work by policy. Same explicit planner seed each tick across paired policies;
no retained planner state. No teacher, learned context or new policy fitting.

## Source tasks, pairing and freshness

Only known family-default source physics: Pendulum(g,m,l)=(10,1,1), torques
(-2,0,2); Acrobot masses=(1,1), link1 length=1, other Gym defaults. Existing
Pendulum current-state cost and Acrobot dense successor-height reward, goal
termination disabled, TimeLimit200. Family raw return units are not pooled.

Executable configuration is `configs/unified_full_policy_source.json`, validated
against immutable runtime settings. Family index f=0,1; bundle b=0,1; episode e=0,1:
reset seed=2103000000+10000f+100b+e;
planner seed at tick t=2104000000+10000f+1000b+200e+t.
Eight distinct reset seeds and1600 distinct planner seeds, paired across methods.
Before environment construction scan integer seed metadata in existing artifact
JSON and preserved H17 conservative ranges for collisions. This does not claim
coverage of inaccessible external runs. No outcomes inform seed/task selection.

## Analysis and failure rules

Record every observation, action, next observation, actual reward, termination,
planner seed and latency. Check wrapper reward against published reward function
at every step. Validate exact 2families×2models×2episodes×4policies×200steps grid,
finite returns, episode continuity, paired starts, no unplanned early endings,
6400 completed real steps and zero unknown costs before analysis is complete.

For each generated policy minus each anchor, average the two paired episode
differences within each independent source model; report both model differences
and their mean separately in each family. Exploratory practical screen: mean>=1
raw return point and both model differences positive for both anchors in both
families. No inferential control-success label, confidence/generalization claim
or ten-decoder analysis with n=2 models/family. Report every contrast regardless
of screen. No selection/retraining on this sample; close these seeds after use.

Trusted host reserves every neural call and real step before dispatch, checks
deadline, and persists hash-chained decision journals in gzip. It is not an OS
sandbox. Partial/interrupted work is charged; missing/unknown work prevents a
complete label. All previous JSON byte hashes checked after execution. Missing
checkpoint, hash mismatch, reused seed, cap exhaustion or invalid grid produces
an incomplete/invalid result, never a scientific negative by default.

## Tests and reproducibility

Before execution: source-only complete-grid, omission, nonfinite/type checks,
seed pairing, continuity, termination, checksum rejection, synthetic composed
model-call shapes, interrupted-resource accounting and journal serialization.
Synthetic tests construct no environments and use no learned-model inference.
Commit implementation, protocol and exact-hash allocation before the one run.
Run `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3
scripts/run_unified_full_policy_source.py`. Save execution SHA, dependency versions,
source/model/configuration hashes, raw trajectories, actual resource consumption,
and separate saved-data verification. No additional simulator smoke trial.

## Results

Not yet executed at protocol commit. Results will be appended separately;
protocol sections above remain frozen.
