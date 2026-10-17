# H16 same-state library — results

## Decision

**`h16_same_state_library_effect_not_established`.** The predeclared
primary — per-seed mean

`D_same = (S_mt_L0 − S_sc_L0) − (S_mt_redraw − S_sc_redraw)`

over eight nested later states (four resets × t=8,12) — was
**+0.023 [−0.014, +0.060]** (student-t 95%, df 9, n = 10). The
interval includes 0. Six of ten seeds were positive.

Mean selected returns: multitask L0 **−15.504**, scratch L0
**−15.682**, multitask redraw **−15.513**, scratch redraw
**−15.668**. The point estimate is a small L0-relative multitask
advantage, but it is not established under the locked rule.

This is a same-state ranking contrast on unused MCC
**(0.0015, 0.0014, 0.055)**. It does not establish the cause of the
closed H14/H15 trajectory-return interaction. It is not a 200-step
control claim. H14/H15 cells were not pooled. Not learning-to-learn,
not AGI.

## Cost

**2.065 s wall** (300 s cap), **84,000 fresh real steps**, **81,920
imagined transitions** exactly, local CPU, one valid execution after
authorization commit `834bb63` (no invalid attempts). Session ledger:
303.777 + 2.065 = 305.842 s of 3600 s consumed; 3294.158 s remain.

## Integrity

Saved label rebuilds from the raw cells. Ten-seed eight-later-state
grid, execution totals, `same_state_is_primary: true`,
`closed_loop_is_primary: false`, and forbidden-claim flags match.
Rule `mcc_same_state_library_v1` reproduced **(0.0015, 0.0014, 0.055)**.
Locked config SHA256
`e71b0053331afa39db5b368510c8524d23e454fb490a2bde57e72ac39f32834c`
and protocol SHA256
`f757e8a8e1f08d0b5abeb7cffa84071a79e1c5e93ded89b6817fe25e8f7fcea7`
are unchanged. Raw SHA256
`96be8b401a06f48e8eab190058f58a82f6dc1f2eebc6c2fe46f31da1e4bc4625`.
Oracle cancellation held on all 160 library cells. This run’s
reset-plus-prefix reconstructions passed the locked float32
`np.array_equal` gate; that is an execution fact for this stack, not
a general Gymnasium guarantee. Further collection on this
configuration is not authorized. The one-run allocation is consumed
and closed.

## Secondaries (not label-deciding)

- Oracle opportunity L0−redraw: **+0.007 [−0.028, +0.042]** includes 0.
- Multitask L0 regret: **+0.005 [−0.002, +0.012]** includes 0.
- Multitask L0 Spearman: **+0.902 [+0.814, +0.989]**.
- Multitask L0 first-action regret: **+0.004 [−0.001, +0.009]** includes 0.
- L0 sequence diversity: **16.0** (all 16 sequences distinct).

## What this can and cannot say

A CI that includes 0 does not prove D_same is zero. It means this
locked same-state design did not establish that reused L0 changes
multitask-versus-scratch selection quality relative to redraw. The
closed H14/H15 primaries remain. Occupancy after the comparison
state is still a candidate explanation for those closed-loop
returns. This result does not authorize a retune, a larger library,
or a new holdout search.
