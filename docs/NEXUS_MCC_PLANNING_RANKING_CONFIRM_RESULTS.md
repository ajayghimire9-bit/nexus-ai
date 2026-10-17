# MCC same-state planning-ranking confirmation — results

## Decision

**`mcc_planning_ranking_confirm_multitask_better`.** The predeclared
primary — per-seed mean sequence regret over four reset states, paired
`scratch − multitask` — was **+0.156 [+0.086, +0.226]**
(student-t 95%, df 9, n = 10). The lower bound is above 0. Ten of ten
seeds were positive.

Mean sequence regret: multitask **0.002** versus scratch **0.158**.
First-action regret (secondary) was **+0.120 [+0.071, +0.169]** and is
not label-deciding. Closed-loop 16-step recede
(`multitask − scratch`) was **−0.253 [−0.431, −0.074]**; the upper
bound is below 0. Recede stays secondary and does **not** decide the
label.

The frozen H12 ranking recipe **replicated** on unused MCC
**(0.0039, 0.002, 0.075)**. This is still a same-state ranking result,
not a 200-step episode-return study. It does not reopen H10, H11, or
H12, and it does not convert the recede interval into a control claim.

This configuration only — not learning-to-learn, not AGI.

## Cost

**2.857 s wall** (300 s cap), **28,480 fresh real steps**, **348,160
imagined transitions** exactly, local CPU, one valid execution after
authorization commit `c600e11` (no invalid attempts). Session ledger:
292.198 + 2.857 = 295.055 s of 3600 s consumed; 3304.945 s remain.

## Integrity

The independent Git-only results audit passed: saved label, ten-seed
four-state grid, execution totals, forbidden-claim flags,
`full_episode_primary: false`, and `closed_loop_is_primary: false`.
Rule `mcc_planning_ranking_confirm_v1` reproduced **(0.0039, 0.002, 0.075)**.
Locked config SHA256
`30a6f3da0a550e1a3be079fe4183398a72d91200e5837cd10c9795ce3954dfb4`
and protocol SHA256
`6e3f32b629e8f698ffdd7ec527e9541eb115ba3c44ae5bfbcf6bc39eb635ef43`
are unchanged. Closed H12 raw SHA256
`c65bc9f42e3fbfe99b5b7dc4d68f8a08fb63fc04e08d374e619dba2f35bbcb8f`
is unchanged.

## Provenance

Branch `cursor/mcc-planning-ranking-confirm`: lock `6585c3f`,
authorization `c600e11`, executed once with a clean tree. Raw artifact
`artifacts/mcc_planning_ranking_confirm.json` SHA256
`e1083da8fecccffa140b2051744c9c3bd8c0398ffa8fd5a9ebc36c2a079afdc8`.

## One next recommendation

Leave this confirmation closed. Do not retune physics, candidates, or
the H12 recipe after seeing these outcomes. H12 ranking is now a
two-holdout ranking screen; H10 remains a single-holdout 200-step
screen; H11 remains not established. The recede interval favored
scratch and is unresolved, but it is not a registered primary. A new
locked protocol would be required before treating recede or 200-step
return as the question. Nothing is pre-authorized.
