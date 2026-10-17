# MCC same-state planning-ranking diagnostic — results

## Decision

**`mcc_planning_ranking_multitask_better`.** The predeclared primary —
per-seed mean sequence regret over four reset states, paired
`scratch − multitask` — was **+0.144 [+0.095, +0.193]**
(student-t 95%, df 9, n = 10). The lower bound is above 0. Ten of ten
seeds were positive.

Mean sequence regret: multitask **0.005** versus scratch **0.150**.
First-action regret (secondary) was **+0.076 [+0.046, +0.105]** and is
not label-deciding. Closed-loop 16-step recede
(`multitask − scratch`) was **+0.038 [−0.144, +0.220]** and includes 0;
it is not the primary.

This is a same-state **ranking** result on unused MCC
**(0.0027, 0.0015, 0.075)** at the frozen H10 recipe. It is not a
200-step episode-return study. It does not reopen H10 or H11, does not
establish general control improvement, and does not explain the H11
confirmation loss on different physics.

This configuration only — not learning-to-learn, not AGI.

## Cost

**2.913 s wall** (300 s cap), **28,480 fresh real steps** (15,360
source + 1,600 target + 10,240 shared open-loop + 1,280 recede),
**348,160 imagined transitions** exactly, local CPU, one valid
execution after authorization commit `4e4229e` (no invalid attempts).
Session ledger: 289.285 + 2.913 = 292.198 s of 3600 s consumed;
3307.802 s remain.

## Integrity

The independent Git-only results audit passed: saved label, ten-seed
four-state grid, execution totals, forbidden-claim flags,
`full_episode_primary: false`, and `closed_loop_is_primary: false`.
Rule `mcc_planning_ranking_v1` reproduced **(0.0027, 0.0015, 0.075)**.
Locked config SHA256
`17a48088591e8c9316f5b6bffd7cefac48ea2daf158cac98555204b47546feb6`
and protocol SHA256
`6acea6f51bdc8ec0ce0f72ce08996f38a333e2e68f854b8fb6c77e218a57148b`
are unchanged. Closed H10 code SHA256
`79a26fed3d0b4a852cd8194492ae67977af41965a56effc01d7441b006dfc701`
is unchanged.

## Provenance

Branch `cursor/mcc-planning-ranking-runner`: prep `b75417a`,
implementation `c67c300`, authorization `4e4229e`, executed once with
a clean tree. Raw artifact `artifacts/mcc_planning_ranking.json`
SHA256
`c65bc9f42e3fbfe99b5b7dc4d68f8a08fb63fc04e08d374e619dba2f35bbcb8f`.

## One next recommendation

Leave this ranking holdout closed. Do not retune physics, candidates,
or the H10 recipe after seeing these outcomes. H10 remains a
single-holdout 200-step screen; H11 remains not established. The
smallest untested follow-up is a same-design ranking confirmation on
new unused MCC physics. That run is not authorized.
