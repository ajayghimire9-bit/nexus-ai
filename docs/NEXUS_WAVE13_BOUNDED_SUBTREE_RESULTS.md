# Wave-13 bounded subtree and opcode accounting results

**Status: developmental / invalid.** Single-shot Commit 2 failed its
pre-registered gates. Commit 1 files were not edited. The `w13f_*`
suite is closed and must not be reused.

Branch `cursor/seed-wave13-mdl-guarded-subtree-and-bounded-macro-beam`
from `6bdf9ae`. Protocol freeze `460a04a`. Artifact hash
`f35215d7ba5a509e5a68c636a34f98d23d68ee4b9e9dcd13266a68da8b240ab6`.
`270` cells (`3` seeds × `5` methods × `18` tasks). Track B closed.
`0` model calls. Frozen debit **0**. Wall **1.652 s**. Grammar prior
was not retrained. Not general learning-to-learn. Not AGI.

`git ls-tree 460a04a` contains no `mechanism_wave13_fresh_assessment.py`.
`git diff 460a04a -- src/nexus/seed/wave13_bounded_subtree_learner.py scripts/run_wave13_bounded_subtree_assessment.py scripts/verify_wave13_bounded_subtree_enumerator.py tests/test_seed_wave13_bounded_subtree.py` is empty.
Verifier replayed `270` rows with both cost identities intact.

Wave 12 (`e940b82` → `6bdf9ae`) remains **Closed Developmental / Invalid
(Blind Holdout Failed Gates; Preserved Unamended)**.

## Suite totals

| Method | Map | Priv | False unique | Work | Primitive steps |
| --- | ---: | ---: | ---: | ---: | ---: |
| equal_typed_scratch | 45/54 | 45/54 | 0 | 155868 | 419256 |
| ordinary_persistent_memoization | 45/54 | 45/54 | 0 | 155635 | 419896 |
| nexus_whole_macro_only | 51/54 | 51/54 | 0 | 141795 | 359886 |
| nexus_typed_without_pruning | 53/54 | 53/54 | 0 | 90142 | 221765 |
| nexus_typed_full | 53/54 | 53/54 | 0 | **85339** | **208076** |

`nexus_typed_full` was cheapest on both identities and beat
`nexus_whole_macro_only` on the subtree split (`25522` vs `34749` work).
That does not pass the run: two gates failed.

## Split totals (`nexus_typed_full` / scratch work)

| Split | Full map | Full work | Scratch work | Whole-macro work |
| --- | ---: | ---: | ---: | ---: |
| base | 9/9 | 1533 | 1344 | 1533 |
| analogy | 6/6 | 1025 | 831 | 1009 |
| subtree | 15/15 | 25522 | 92715 | 34749 |
| piecewise | 5/6 | 48633 | 54780 | 96265 |
| archive | 12/12 | 2216 | 1587 | 2072 |
| oog + ambiguous | 6/6 | 6410 | 4611 | 6167 |

## What failed

1. **`full_accuracy`:** seed-2 `w13f_piece_rot_odd` abstained
   (`53/54` map and private). Seeds 0 and 1 solved that cell.
2. **`archive_reactivation`:** delayed palindrome was solved uniquely
   on all 3 seeds, but `cold_archive_reactivated = 0`. The once-used
   palindrome operators were not evicted into the Tier-2 archive
   before the delayed task, so the O(1) reactivation counter never
   fired.

## What held on this grid

- `0` false unique locks. Elementwise-dup OOG abstained `3/3`.
- Identity field collision declared `ambiguous` `3/3`.
- Dual identities reconstructed on every row.
- Unassisted right-rotation subtree: after two wraps, full reused an
  internal `L1` on `w13f_sub_rot_plus` and reached `max_hierarchy_depth
  = 2` on the L2 tasks. `subtree_macro_invented = 3` (one per seed).
- Suite work/primitive domination vs all four baselines.

## Gates

| Gate | Result |
| --- | --- |
| Isolation / OOG / 0 false unique / ambiguous | **pass** |
| Dual cost identities | **pass** |
| Full accuracy | **fail** |
| Full dominates suite + subtree vs whole-macro | **pass** |
| Archive reactivation `3/3` | **fail** |

## Why this is closed

The no-amend rule forbids editing `460a04a` files or rerunning the same
`w13f_*` suite. Local subtree and opcode-accounting signal is real and
still short of a passed blind holdout.
