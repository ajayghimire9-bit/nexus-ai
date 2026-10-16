# Proposed next experiment — same-state value × commitment length

Status: design only; no data collection or execution authorized by this proposal. It follows the completed calibration and exploratory recorded-data discrimination analyses. A new experiment branch, executable configuration, focused tests, clean protocol commit and explicit unexpired budget allocation are required before collection. This document is an implementation-ready design, not a result.

## One scientific question

Does the frozen terminal correction improve complete-sequence commitment more than first-action commitment at **the same states with the same candidates**? Competing explanations: commitment/replanning mismatch versus state/candidate sampling variability in the two already closed studies. Previously, four-candidate complete-sequence selection improved but an independent first-action sample did not show improvement. Those different samples cannot estimate this interaction.

## Fixed ingredients

Ten existing independent decoders, five saved broad students each, original saved development contexts, ten frozen source readouts, source/feature normalization, torque actions, reward, H16 and sixteen candidate sequences. No fitting or architecture change. Reuse existing dev0/dev1/dev2 physics; no reserved confirmation physics or closed episode seeds. Reusing saved128-row contexts means this tests a conditional control mechanism, not adaptation to a newly collected support history. Prior support/pretraining costs remain explicitly inherited.

Proposed fresh initial-state seeds:2400000+10*t+j, t=0..2,j=0..1. Candidate seeds:2410000+10*t+j. Continuation seeds:2420000+256*t+128*j+k, k=0..63. Check exact sets against every previous closed config and proposal before locking the executable config; fail if any collision. Candidate randomness is independent of selected action, method or observed reward. Neither physics parameters nor simulator state enter the controller; true state is for exact research restoration only.

## Paired2×2 intervention

At each restored state, all contexts score the same16×16 array with original H16 and original H16+survival16×V. No candidate count/horizon increase. For each selected candidate compare:

- Commit its first action; then unchanged zero-context MPC for63 steps.
- Commit its complete16-action sequence; then unchanged zero-context MPC for48 steps.

Both returns cover64 real steps from the identical initial state. The common continuation is always the corresponding decoder's unchanged zero controller. At local future step k use the registered seed for k regardless of commitment/action/method; full-block continuation starts at clock16, first-action continuation at clock1. Record all rewards, actions, flags, seeds and exact state restoration checks. No outcome enters model scores or modifies the policy.

Cache all three first-action64 returns per decoder/state. Cache all16 actual16-action prefixes once per state across decoders and contexts. Measure all16 decoder-specific48-step suffixes, making every model-selected sequence's true64 return available. This removes the four-labeled-candidate limitation of the retrospective analysis. Contexts share identical actual counterfactual returns and candidate opportunities. No direct simulator planner is deployed.

## Primary estimand and interpretation

For decoder d/task t/state j/student s:

`interaction = (R_value,commit16 − R_original,commit16) − (R_value,commit1 − R_original,commit1)`.

Average five students, two initial states and three tasks equally **inside each decoder**. Use ten decoder values and a paired two-sided t95% interval, df9/critical2.262. Practical primary margin:1 return point, with lower95% bound>0. Report both component effects with paired intervals; never infer their difference merely because one interval excludes zero and the other does not.

A positive primary interaction supports **relative commitment sensitivity on these states**. Describe a commitment-sensitive benefit only if the complete16 effect is itself positive with its95% lower bound>0. If both effects are negative, a positive interaction means less harm at16, not a benefit. If the first-action interval includes zero, do not claim equivalence or absence of improvement. The joint sensitivity-plus-gain screen is an intersection of required conditions; report all intervals and label all task/zero-context analyses exploratory/unadjusted.

Zero-context original/corrected comparisons are secondary strong baselines. Report per-task/state/decoder effects, catastrophic outcomes, selected first-action/sequence changes and end-state divergence. Full-sequence regret relative to the best measured16 is secondary. This experiment is not full-policy receding-horizon value, full-episode return, or an explanation of the historical184-step gap. It cannot establish general control transfer or learning-to-learn.

## Estimated exact budget

Six initial states. Cached actual prefixes:6×16×16=**1536 real steps**. All full-block suffixes:10×6×16×48=**46,080**. First-action counterfactuals:10×6×3×64=**11,520**. Total **59,136 new real interactions**, zero new support.

Imagined transitions:46,080×256 + (10×6×3×63)×256 + (10×6×6×512) = **14,883,840**. The last term includes both base scoring and endpoint prediction. A selected first action is forced without a planning call at step0; do not count that as an imagined rollout. Total costs are once per cached trajectory, not once per student/context.

Expected local single-thread CPU runtime **4–6 minutes**, hard cap **900 seconds**, based on the completed83-second21,824-step calibration and prior238-second64,512-step diagnostic. This is an estimate, not a measured new run. Refuse exceeding either interaction or inference cap. Save partial outputs honestly and never silently reduce the grid. No paid compute or main merge. The previous two-hour wall-clock authorization elapsed during an interruption and is not carried forward as an unlimited simulation permission.

## Proposed implementation checks

Before execution test exact state/clock restoration, reward timing and action decoding; common continuation randomness independent of action/commitment; unchanged model/context/normalizer hashes; full16 candidate equality; original scoring replay; prefix/tail cache counted exactly once;64-step accounting for both commitment lengths; interaction arithmetic and equal-weight aggregation; complete-grid and invalid-numeric rejection; closed-seed guard; checkpoint verification failing on missing files; and rejection of absent/stale budget approval before any environment call. A synthetic case should show why significant16 and inconclusive1 effects do not automatically establish a significant interaction.

Commit implementation and protocol before data. Execute once under a new bounded allocation. Commit raw results and independent arithmetic audit separately. If the interaction is inconclusive or fails, preserve that finding; do not automatically change architecture or retune on these states. This is the one proposed next scientific experiment.
