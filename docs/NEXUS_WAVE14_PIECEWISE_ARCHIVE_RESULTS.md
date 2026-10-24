# Wave-14 piecewise probe allocation and cold archive routing results

**Status: developmental / invalid.** Single-shot Commit 2 failed its
pre-registered suite-cost gates. Commit 1 files were not edited. The
`w14f_*` suite is closed and must not be reused.

Branch `cursor/seed-wave14-piecewise-probe-allocation-and-cold-archive-routing`
from `a48001e`. Protocol freeze `53e5317`. Artifact hash
`a68e1c552dc74a5d4a028c75929b95c45ad38e913dfb38ef7a676581c963f80f`.
Payload digest
`0d197e373679e658614d91ff6ef9c899bbac89401ca8bd994a1c6a239dcf4664`.
`270` cells (`3` seeds × `5` methods × `18` tasks). Track B closed.
`0` model calls. Frozen debit **0**. Wall **5.155 s**. Grammar prior
was not retrained. Not general learning-to-learn. Not AGI.

`git ls-tree 53e5317` contains no `mechanism_wave14_fresh_assessment.py`.
`git diff 53e5317 -- src/nexus/seed/wave14_piecewise_archive_learner.py scripts/run_wave14_piecewise_archive_assessment.py scripts/verify_wave14_piecewise_archive_enumerator.py tests/test_seed_wave14_piecewise_archive.py` is empty.
Verifier replayed `270` rows with both cost identities intact and
Commit-1 blindness valid. It reports `gates_not_passed` only.

Wave 12 (`e940b82` → `6bdf9ae`) and Wave 13 (`460a04a` → `a48001e`)
remain **Closed Developmental / Invalid (Preserved Unamended)**.

## Suite totals

| Method | Map | Priv | False unique | Work | Primitive steps |
| --- | ---: | ---: | ---: | ---: | ---: |
| equal_typed_scratch | 45/54 | 45/54 | 0 | **276378** | **758274** |
| ordinary_persistent_memoization | 45/54 | 45/54 | 0 | **241527** | **662359** |
| nexus_whole_macro_only | 54/54 | 54/54 | 0 | 439930 | 1126232 |
| nexus_typed_without_pruning | 54/54 | 54/54 | 0 | 779380 | 1949381 |
| nexus_typed_full | 54/54 | 54/54 | 0 | 414925 | 1051271 |

`nexus_typed_full` solved every unique cell and beat
`nexus_whole_macro_only` and `nexus_typed_without_pruning` on both
identities. It lost the suite-cost gate to scratch and memoization,
which abstained on the two size-9 L2 tasks and on
`w14f_piece_wrap_odd_caret` (`9` unique abstentions, `45/54`).

## Split totals (`nexus_typed_full` / scratch work)

| Split | Full map | Full work | Scratch work | Whole-macro work |
| --- | ---: | ---: | ---: | ---: |
| base | 9/9 | 18081 | 24252 | 18048 |
| analogy | 6/6 | 752 | 549 | 730 |
| subtree | 15/15 | 40125 | 133077 | 56683 |
| piecewise | 6/6 | 79130 | 49020 | 87731 |
| archive | 12/12 | 16569 | 25080 | 16470 |
| oog + ambiguous | 6/6 | 260268 | 44400 | 260268 |

The OOG pairwise-swap cells dominate suite cost: full and whole-macro
each spent `260268` work after the active macro beam entered two-branch
search, versus scratch `44400`. That single split (`+215868` vs scratch)
exceeds the subtree savings (`−92952`).

## What failed

1. **`suite_work` / `suite_prim` vs `equal_typed_scratch` and
   `ordinary_persistent_memoization`.** Full `414925` / `1051271`
   exceeded scratch `276378` / `758274` and memo `241527` / `662359`.
   Scratch and memo abstained on `w14f_sub_revlast_l2_form`,
   `w14f_sub_revlast_l2_reuse`, and `w14f_piece_wrap_odd_caret` on
   every seed.

## What held on this grid

- **Full accuracy `54/54`.** The Wave-13 seed-2 piecewise abstention
  did not recur. Both piecewise tasks locked uniquely on all 3 seeds
  after the full-budget drain and implication-sound branch test.
- **Archive reactivation `3/3`.** Delayed bookend
  (`w14f_arc_delayed_bookend`) set `cold_archive_reactivated` on every
  seed. Full delayed gate+synth `497+7` beat without-pruning `827+14`.
- `0` false unique locks. Pairwise-swap OOG abstained `3/3`.
- Identity field collision declared `ambiguous` `3/3`.
- Dual identities reconstructed on every row.
- Unassisted `APPEND_TOK(REVERSE(x), LAST(x))` subtree: full invented
  an internal `L1` once per seed (`subtree_macro_invented = 3`) and
  reached `max_hierarchy_depth = 2` on the L2 tasks. Subtree work
  `40125` beat whole-macro `56683` and scratch `133077`.

## Gates

| Gate | Result |
| --- | --- |
| Isolation / OOG / 0 false unique / ambiguous | **pass** |
| Dual cost identities | **pass** |
| Full accuracy | **pass** |
| Full dominates suite + subtree vs whole-macro | **fail** (suite vs scratch/memo) |
| Archive reactivation `3/3` + cheaper than no-prune | **pass** |

## Why this is closed

The no-amend rule forbids editing `53e5317` files or rerunning the same
`w14f_*` suite. The two Wave-13 surgical targets (piecewise seed
invariance and cold-archive routing) held. Suite-cost domination did
not, because a true OOG task still paid a full macro-augmented
two-branch search.

## Recommended next experiment

Wave 15 should add a residual-coverage abort *before* piecewise search
when no transform in the T0/T1/T2/T3 pool covers at least
`min_branch_support` strict residuals, so a true OOG task abstains
without a two-branch explosion. Do not reuse `w14f_*`. Do not amend
`53e5317`.
