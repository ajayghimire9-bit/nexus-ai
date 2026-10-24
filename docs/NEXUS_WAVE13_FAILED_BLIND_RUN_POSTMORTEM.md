# Wave 13 failed blind-run postmortem

**Classification: Closed Developmental / Invalid (53/54 Accuracy & 0/3 Archive Reactivation; Preserved Unamended).**

Wave 13 (`460a04a` → `a48001e`) is permanently closed. Do not amend
either commit. Do not rerun or edit `mechanism_wave13_fresh_assessment.py`
(`w13f_*`).

## Provenance

| Item | Value |
| --- | --- |
| Parent | `6bdf9ae` (Wave 12 closed) |
| Commit 1 | `460a04a` — pre-assessment freeze |
| Commit 2 | `a48001e` — failed artifact + close |
| Artifact | `artifacts/seed_wave13_bounded_subtree_enumerator.json` |
| Payload SHA-256 | `f35215d7ba5a509e5a68c636a34f98d23d68ee4b9e9dcd13266a68da8b240ab6` |
| Cells | 270 (`3` seeds × `5` methods × `18` tasks) |
| Track B | `0` model calls, `0 s` frozen debit, wall `1.652 s` |

`git ls-tree 460a04a` contains **zero** `mechanism_wave13_fresh_assessment.py`.
Frozen learner / runner / verifier / tests vs `460a04a` are empty.
Both identities reconstructed on `270` rows.

## Five-method suite table

| Method | Map | Priv | False unique | Work | Primitive steps |
| --- | ---: | ---: | ---: | ---: | ---: |
| equal_typed_scratch | 45/54 | 45/54 | 0 | 155,868 | 419,256 |
| ordinary_persistent_memoization | 45/54 | 45/54 | 0 | 155,635 | 419,896 |
| nexus_whole_macro_only | 51/54 | 51/54 | 0 | 141,795 | 359,886 |
| nexus_typed_without_pruning | 53/54 | 53/54 | 0 | 90,142 | 221,765 |
| nexus_typed_full | **53/54** | **53/54** | 0 | **85,339** | **208,076** |

Full was cheapest and beat whole-macro on the subtree split. Gates
`full_accuracy` and `archive_reactivation` still failed.

## Failed gate (a): seed-2 `w13f_piece_rot_odd` abstained

`SEED_ORDERS[2]` placed both piecewise tasks *before* the five subtree
tasks. Seeds 0 and 1 therefore arrived at `w13f_piece_rot_odd` with an
evolved right-rotation macro; seed 2 did not.

On 2-token evens, `ROT_RIGHT(x) == REVERSE(x)`. Wave 13's two-branch
search required biconditional residual masks (`G <=> T-hits`) and
`>= 3` leftover residuals *before* drawing leftover public probes.
Seed 2 therefore searched a 13-example window (no hold-slot drain)
instead of the 16-example window seeds 0/1 used after confirmation
reads. Implication-unsound collision plus unequal public sets produced
a seed-dependent abstention (`53/54`).

Wave 14 Fix 2: drain every remaining public probe before piecewise,
and accept implication `G1 => T1(x)==y` rather than biconditional
equality.

## Failed gate (b): delayed palindrome `cold_archive_reactivated == 0/3`

`SEQ_EQ(x, REVERSE(x))` has AST size 4. Wave 13 put every size-`<=5`
relational guard in the first beam, including palindrome. Delayed
palindrome was therefore re-solved in that first beam. The once-used
palindrome macro *was* evicted into `cold_archive` after the
distractors (`bool_macro_15` appears in the pruned list), then
`promote_ast_subtree` restored the same body from the archive after
Tier-0 already locked the program. The Tier-2 flag never fired.

Wave 14 Fix 1: Tier-0 is only EVEN/ODD plus size-1..2 transforms.
Size-4+ guards go through active macros, then the cold archive, and
only then Tier-3. Once-used macros with `inactive_age >= 3` are
evicted before the delayed task's search.

## What still worked

- `0` false unique locks; elementwise-dup OOG abstained `3/3`.
- Identity field collision declared `ambiguous` `3/3`.
- Unassisted right-rotation subtree and L2 depth `2` on seeds 0–1.
- Suite work/primitive domination vs all four baselines.

Those local signals do not reopen `w13f_*`.
