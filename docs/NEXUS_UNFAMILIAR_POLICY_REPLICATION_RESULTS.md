# Unfamiliar policy-only replication results

Branch `cursor/seed-unfamiliar-policy-replication`.
Protocol `18093a1`. This results commit is separate.
Base `b357b01`. Artifact hash
`6f7437ede1a0b5f582a0b1e71bdf83881fa2067011b0ee902740c20512f532ff`.
Verifier `valid: true` on 54 assessment cells; opened prior IDs
rejected. Track B not run. Skill memory paused and cleared between
tasks. 0 model calls. Frozen debit **0**. Pilot, not confirmation.
Not general learning-to-learn. Not AGI.

## Bounded claim

NEXUS learned an investigation strategy from source tasks that
reduced the cost of acquiring unfamiliar mechanisms within the
tested setting.

The continual 84 vs 105 comparison is not rescored. This study is an
independent replication on a fresh exclusive-or suite against both
the untrained diagnostic checklist and a source-distilled static
order, with full work accounting.

## Suite

After `ACT_1`, Branch A (`y_1 = 3`) makes `ACT_2` informative and
`ACT_NEG` redundant (0 splits). Branch B (`y_1 = 0`) does the reverse.
Held-out IDs `up_hold_*` are disjoint from source and from every
opened prior cell. Reserved retest: `up_ret_add1`, `up_ret_if_pos`.

Source seeds `0, 1, 2` shuffle the same eight source tasks and retrain
`fit_acquire`. Distilled orders were
`ACT_NEG, ACT_1, ACT_0, MEASURE, ACT_2, RESET` (seeds 0 and 2) and
`ACT_NEG, MEASURE, ACT_1, ACT_0, ACT_2, RESET` (seed 1).

## Gates

| Gate | Result |
| --- | --- |
| 1 Accuracy and reserved-retest parity | **pass** — all three methods 12/12 holdout useful and 6/6 reserved |
| 2 Learned env interactions < untrained and < distilled, every seed | **pass** — 7 < 14 and 7 < 14/15 |
| 3 Learned total acquisition work < both baselines, every seed | **pass** — 233 < 286 and 233 < 296/316 |

Exact identity never awarded.

## Holdout totals (4 mechanisms × 3 seeds)

| Method | Useful | Env | Hyp evals | Policy evals | Total work |
| --- | ---: | ---: | ---: | ---: | ---: |
| untrained_default_policy | 12 | 42 | 816 | 0 | 858 |
| source_distilled_fixed_order | 12 | 43 | 865 | 0 | 908 |
| source_learned_adaptive_policy | 12 | **21** | 432 | 246 | **699** |

Reserved retest: all three methods 6/6 useful. Learned 6 env vs 12
for each static method; total work 249 vs 252.

## Source-seed consistency (holdout)

| Seed | Untrained env / work | Distilled env / work | Learned env / work |
| ---: | ---: | ---: | ---: |
| 0 | 14 / 286 | 14 / 296 | **7 / 233** |
| 1 | 14 / 286 | 15 / 316 | **7 / 233** |
| 2 | 14 / 286 | 14 / 296 | **7 / 233** |

## Per-task breakdown

`ret` is reserved-retest useful; holdout cells leave it blank.
Source-training seed is 0, 1, 2.

| Seed | Task | Method | Env | Hyp | Policy | Total | Solved | Retained |
| ---: | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 0 | up_hold_pos_plus2 | untrained_default_policy | 3 | 58 | 0 | 61 | yes | — |
| 0 | up_hold_twice_plus1 | untrained_default_policy | 3 | 58 | 0 | 61 | yes | — |
| 0 | up_hold_neg_gate | untrained_default_policy | 4 | 78 | 0 | 82 | yes | — |
| 0 | up_hold_neg_twice | untrained_default_policy | 4 | 78 | 0 | 82 | yes | — |
| 0 | up_hold_pos_plus2 | source_distilled_fixed_order | 5 | 100 | 0 | 105 | yes | — |
| 0 | up_hold_twice_plus1 | source_distilled_fixed_order | 5 | 100 | 0 | 105 | yes | — |
| 0 | up_hold_neg_gate | source_distilled_fixed_order | 2 | 40 | 0 | 42 | yes | — |
| 0 | up_hold_neg_twice | source_distilled_fixed_order | 2 | 42 | 0 | 44 | yes | — |
| 0 | up_hold_pos_plus2 | source_learned_adaptive_policy | 2 | 40 | 22 | 64 | yes | — |
| 0 | up_hold_twice_plus1 | source_learned_adaptive_policy | 1 | 24 | 16 | 41 | yes | — |
| 0 | up_hold_neg_gate | source_learned_adaptive_policy | 2 | 40 | 22 | 64 | yes | — |
| 0 | up_hold_neg_twice | source_learned_adaptive_policy | 2 | 40 | 22 | 64 | yes | — |
| 0 | up_ret_add1 | untrained_default_policy | 2 | 40 | 0 | 42 | yes | yes |
| 0 | up_ret_if_pos | untrained_default_policy | 2 | 40 | 0 | 42 | yes | yes |
| 0 | up_ret_add1 | source_distilled_fixed_order | 2 | 40 | 0 | 42 | yes | yes |
| 0 | up_ret_if_pos | source_distilled_fixed_order | 2 | 40 | 0 | 42 | yes | yes |
| 0 | up_ret_add1 | source_learned_adaptive_policy | 1 | 24 | 17 | 42 | yes | yes |
| 0 | up_ret_if_pos | source_learned_adaptive_policy | 1 | 24 | 16 | 41 | yes | yes |
| 1 | up_hold_pos_plus2 | untrained_default_policy | 3 | 58 | 0 | 61 | yes | — |
| 1 | up_hold_twice_plus1 | untrained_default_policy | 3 | 58 | 0 | 61 | yes | — |
| 1 | up_hold_neg_gate | untrained_default_policy | 4 | 78 | 0 | 82 | yes | — |
| 1 | up_hold_neg_twice | untrained_default_policy | 4 | 78 | 0 | 82 | yes | — |
| 1 | up_hold_pos_plus2 | source_distilled_fixed_order | 5 | 100 | 0 | 105 | yes | — |
| 1 | up_hold_twice_plus1 | source_distilled_fixed_order | 5 | 100 | 0 | 105 | yes | — |
| 1 | up_hold_neg_gate | source_distilled_fixed_order | 2 | 40 | 0 | 42 | yes | — |
| 1 | up_hold_neg_twice | source_distilled_fixed_order | 3 | 61 | 0 | 64 | yes | — |
| 1 | up_hold_pos_plus2 | source_learned_adaptive_policy | 2 | 40 | 22 | 64 | yes | — |
| 1 | up_hold_twice_plus1 | source_learned_adaptive_policy | 1 | 24 | 16 | 41 | yes | — |
| 1 | up_hold_neg_gate | source_learned_adaptive_policy | 2 | 40 | 22 | 64 | yes | — |
| 1 | up_hold_neg_twice | source_learned_adaptive_policy | 2 | 40 | 22 | 64 | yes | — |
| 1 | up_ret_add1 | untrained_default_policy | 2 | 40 | 0 | 42 | yes | yes |
| 1 | up_ret_if_pos | untrained_default_policy | 2 | 40 | 0 | 42 | yes | yes |
| 1 | up_ret_add1 | source_distilled_fixed_order | 2 | 40 | 0 | 42 | yes | yes |
| 1 | up_ret_if_pos | source_distilled_fixed_order | 2 | 40 | 0 | 42 | yes | yes |
| 1 | up_ret_add1 | source_learned_adaptive_policy | 1 | 24 | 17 | 42 | yes | yes |
| 1 | up_ret_if_pos | source_learned_adaptive_policy | 1 | 24 | 16 | 41 | yes | yes |
| 2 | up_hold_pos_plus2 | untrained_default_policy | 3 | 58 | 0 | 61 | yes | — |
| 2 | up_hold_twice_plus1 | untrained_default_policy | 3 | 58 | 0 | 61 | yes | — |
| 2 | up_hold_neg_gate | untrained_default_policy | 4 | 78 | 0 | 82 | yes | — |
| 2 | up_hold_neg_twice | untrained_default_policy | 4 | 78 | 0 | 82 | yes | — |
| 2 | up_hold_pos_plus2 | source_distilled_fixed_order | 5 | 100 | 0 | 105 | yes | — |
| 2 | up_hold_twice_plus1 | source_distilled_fixed_order | 5 | 100 | 0 | 105 | yes | — |
| 2 | up_hold_neg_gate | source_distilled_fixed_order | 2 | 40 | 0 | 42 | yes | — |
| 2 | up_hold_neg_twice | source_distilled_fixed_order | 2 | 42 | 0 | 44 | yes | — |
| 2 | up_hold_pos_plus2 | source_learned_adaptive_policy | 2 | 40 | 22 | 64 | yes | — |
| 2 | up_hold_twice_plus1 | source_learned_adaptive_policy | 1 | 24 | 16 | 41 | yes | — |
| 2 | up_hold_neg_gate | source_learned_adaptive_policy | 2 | 40 | 22 | 64 | yes | — |
| 2 | up_hold_neg_twice | source_learned_adaptive_policy | 2 | 40 | 22 | 64 | yes | — |
| 2 | up_ret_add1 | untrained_default_policy | 2 | 40 | 0 | 42 | yes | yes |
| 2 | up_ret_if_pos | untrained_default_policy | 2 | 40 | 0 | 42 | yes | yes |
| 2 | up_ret_add1 | source_distilled_fixed_order | 2 | 40 | 0 | 42 | yes | yes |
| 2 | up_ret_if_pos | source_distilled_fixed_order | 2 | 40 | 0 | 42 | yes | yes |
| 2 | up_ret_add1 | source_learned_adaptive_policy | 1 | 24 | 17 | 42 | yes | yes |
| 2 | up_ret_if_pos | source_learned_adaptive_policy | 1 | 24 | 16 | 41 | yes | yes |

The distilled checklist spends 5 probes on Branch A (family X is last
in its static order) and 2 on Branch B. Untrained walks
`DIAGNOSTIC_ORDER` and wastes `ACT_0` then `ACT_2` on Branch B.
The learned policy conditions on the first observation: Branch A
uses family X, Branch B uses family Y.

## Source training work and break-even

Source DAgger + own-source replay across three seeds:

| Env | Hyp evals | Policy evals | Total |
| ---: | ---: | ---: | ---: |
| 72 | 1572 | 522 | 2166 |

Holdout work saved versus untrained: 13.25 per task,
\(N_{\text{breakeven}} = 163.5\).
Versus distilled: 17.42 per task, \(N_{\text{breakeven}} = 124.4\).
Training cost is paid once; these N values are for this bank and
budget only.

## What this does not show

This is not a new learning algorithm, not skill-memory transfer, not
Track B, and not general learning-to-learn. The 84 vs 105 continual
cells stay closed. A later family that lacks an exclusive-or first
observation can still make a static checklist tie.
