# Bounded source correction comparison

Starting base: b6926a0ea677b82e6565af52dedf78c222fc537f.
Branch: codex/seed-bounded-correction. This is reusable-source exploration,
not validation, control evaluation or a learning-to-learn claim.

## Hypotheses and intervention

H-bound: constraining the output change of each existing protected update
reduces source query error and later-prefix instability. A competing explanation
is that its update direction or support coverage is the problem, so bounding
magnitude will not beat scaled replay. A generic improvement shared by learned,
static and fixed protection is not evidence for learned plasticity.

Use the existing original 12 source tasks and source-fitted frozen controllers
for 6401/6402/6403. Keep the 33-dimensional features, source normalization,
original initialization, original protected candidate update and labels fixed.
Do not read the old development/audit/control outcomes into the worker.

Compute one source-only scale: RMS of the 96 support residuals at the original
old-anchor initialization (eight rows per task), using no query outcomes.
Set tau = max(1e-6, 0.25 * this RMS), with no grid search or retuning. Given an
original candidate delta, let B contain the four old anchors and the observed
support prefix. Set alpha = min(1, tau / max(RMS(B delta), 1e-12)), and apply
theta_new = theta + alpha * delta. Only permitted old/current-prefix rows enter
this bound. It limits prediction changes on B, not globally on unseen inputs.

Add learned_bounded, static_bounded and fixed_bounded. These call the existing
update function then apply this same bound. No parameters are trained, including
the original frozen GRU/readout and all stored protection-controller weights.
The disposable per-task theta vectors do adapt; this is not zero computation.

## Controls, cached reuse and expected grid

The hash-verified preceding source diagnosis supplies unchanged learned, static,
fixed, replay and none trajectories. Reuse these cached baselines exactly;
do not charge them again as executed updates. Verify their source fingerprint,
grid and arithmetic. New and cached arms share identical source arrays, initial
fits, weights and budgets. Never use cached query scores to set alpha or tau.

Record all prefixes 0–8 for 3 seeds × 12 tasks × 8 methods: 2592 snapshots,
1620 cached and 972 newly evaluated. Save theta, query/retention errors, update
norms, support residuals, alpha, candidate RMS and actual bounded RMS. Check
every bound numerically, prefix-zero equality and frozen weights. Missing or
nonfinite cells mean incomplete/invalid execution, not a scientific failure.

## Locked metrics and decisions

Primary metric: equal mean source query MSE over budgets 1,2,4,8. Average the
three controller seeds inside each task, then average the 12 source tasks.
Report paired exploratory 95% t intervals, df11, conditional on these reused
training tasks and ONE world-model core. These are not independent pretrained
model replications or untouched evidence; multiple contrasts are exploratory.

Report three decisions separately:

1. Stabilization: learned_bounded lowers mean curve MSE by at least 10% versus
   unchanged learned, paired benefit interval lower bound >0, and mean final
   retention MSE no more than .01 worse than unchanged learned.
2. Strong-baseline screen: learned_bounded lowers curve MSE by at least 5%
   versus scaled replay, with paired benefit interval lower bound >0.
3. Learned-specific screen: learned_bounded lowers curve MSE by at least 5%
   versus fixed_bounded, with paired benefit interval lower bound >0.

Also report all static/fixed curves, task sensitivity, worst-prefix query MSE,
clamp rates and costs. Do not replace these rules after seeing results. Passing
any source screen permits only proposing fresh validation; no runtime promotion,
control claim or confirmation is executed here. If only generic bounding helps,
say so. If it fails, preserve failure without widening the bound/search budget.

## Budget, reuse and provenance

Reuse the EXPERIMENTAL host/worker, LessonTask, initial/update/scaled,
PlasticityController and the preceding trace/arithmetic helpers. No separate
meter, optimizer or learning framework. Commit protocol, configuration and
tested implementation before running once. Preserve all historical artifacts.

Standing grant: local CPU, 30-second wall and CPU limits, 2048 MiB sampled RSS
(not exact kernel enforcement on macOS), 0 real/imagined steps, 0 outer updates,
0 world-model forwards. New work: 864 protected updates, 576 tiny-controller
forwards, 120 initial solves (12 scale fits + 108 trajectories), 7344 additional
bound-design rows, and 96 source residual-scale examples. Cached baseline
operations are separately labeled. Each new trajectory scores 27 query and 27
retention rows at nine prefixes: 26244 of each. No new scientific interaction.

Carry 1919.6321034559958 seconds used / 1680.3678965440042 remaining. Startup,
failures and interruptions count. Persist honest partial/invalid status on a
cap or integrity failure. Record execution SHA, source/config/protocol hashes,
runtime versions and host receipt. Commit results separately and push; no main
merge, historical checkpoint replacement or second study in this branch.
