# Wave 12 failed blind-run postmortem

**Classification: Closed Developmental / Invalid (Blind Holdout Failed Gates; Preserved Unamended).**

Wave 12 (`e940b82` → `6bdf9ae`) is permanently closed. Do not amend
either commit. Do not rerun or edit `mechanism_wave12_fresh_assessment.py`
(`w12f_*`).

## Provenance

| Item | Value |
| --- | --- |
| Parent | `5777ea2` (Wave 11c) |
| Commit 1 | `e940b82` — pre-assessment freeze |
| Commit 2 | `6bdf9ae` — failed artifact + close |
| Artifact | `artifacts/seed_wave12_subtree_opcode_enumerator.json` |
| Payload SHA-256 | `a6b8ba055930c36b9302aba9eae11d89d7b3c1df2879a6f80e883a5cfb037da0` |
| Cells | 270 (`3` seeds × `5` methods × `18` tasks) |
| Track B | `0` model calls, `0 s` frozen debit, wall `1.942 s` |

`git ls-tree e940b82` contains **zero** `mechanism_wave12_fresh_assessment.py`.
`git diff e940b82 --` learner / runner / verifier / tests is empty.
Both identities reconstructed. Gates failed.

## Five-method suite table

| Method | Map | Priv | False unique | Work | Primitive steps |
| --- | ---: | ---: | ---: | ---: | ---: |
| equal_typed_scratch | 33/54 | 27/54 | 3 | **26,793** | **284,967** |
| ordinary_persistent_memoization | 33/54 | 27/54 | 3 | 26,991 | 285,566 |
| nexus_whole_macro_only | 33/54 | 27/54 | 3 | 30,249 | 348,139 |
| nexus_typed_without_pruning | 33/54 | 27/54 | 3 | 33,370 | 476,548 |
| nexus_typed_full | 33/54 | 27/54 | 3 | 31,955 | 391,339 |

`nexus_typed_full` lost both cost identities to scratch.

## Four failure modes

### (a) Tier-3 macro-combinatorial explosion on unsolved / abstaining tasks

`TypedProgramEnumeratorSearch.expand` injected every active
`EvolvedMacroNode` into the bottom-up pool. Unsolved ROT wraps and
true OOG Caesar then paid macro branching at depths 4–7.

Seed-0 Caesar: scratch work `2,224` / `10,309` prims vs full `3,117` /
`15,045`. Suite OOG work: scratch `7,443` vs full `10,497`.
Subtree split work: scratch `7,374` vs full `8,348` vs no-prune `8,842`.

Wave 13 Fix 1: never inject evolved macros into Tier-3. Tier-1 is a
relevance-gated 1-wrapper beam only.

### (b) Size-7 cutoff on unassisted subtree wrappers (`ROT_LEFT`)

`APPEND_TOK(TAIL(x), HEAD(x))` is size 5. `PREPEND_TOK('@', ROT(x))`
and `APPEND_TOK(ROT(x), '$')` are size 7. Unconstrained size-6/7
enumeration hit the candidate cap; all four `w12f_sub_rot_*` tasks
abstained on every method (`0/12` mapping). No internal `ROT_LEFT`
macro was ever invented (`subtree_macro_invented = 0` on the subtree
split).

Wave 13 Fix 2: shared atomic cores through size 5, then
observation-guided outer affix/unary wrappers for sizes 6–7. Fix 3:
promote recurring internal size-4..6 subtrees after two wraps.

### (c) Under-constrained piecewise overfitting on OOG `interleave`

`seq_interleave_rev_w12` on the default public lengths `{0,1,2}` is
identical to in-grammar `CONCAT(x, REVERSE(x))`. All 15 interleave
cells locked unique (`false_unique = 3` suite-wide, one per seed ×
method). Caesar abstained cleanly.

Wave 13 Fix 4: confirmatory holdout probes and a minimum of 3
examples per piecewise branch. Length-3+ probes separate interleave
from `CONCAT(x, REVERSE(x))`.

### (d) Guard ambiguity / mislock on `even_reverse`, `even_dup`, `odd_rev`

Default public lengths `{0,1,2}` make `EVEN(LEN(x))` and
`INT_EQ(LEN(x), 2)` agree on every residual. The enumerator locked
the first exact-length guard. Private length-4 even sequences then
failed (`even_reverse` and `even_dup`: unique, `private_correct =
false` on all 3 seeds). `odd_rev` never reached synthesis: field
admission returned `ambiguous` because reverse collided with another
record field on the public series.

Wave 13 Fix 4: collect every 100% public guard, query up to 4
discriminating probes (lengths `2,3,4,5,6`), and declare `ambiguous`
only when distinct remaining guards still tie after the public bank
is exhausted.

## What still worked

- Dual identities passed (`gate2_identities = true`).
- Dynamic `$` / `@` / `%` extraction on base and archive tasks.
- Delayed palindrome reactivation (`cold_archive_reactivated = 3` on
  full and whole-macro).
- Two piecewise tasks unique + private on seed 0.

Those local signals do not reopen `w12f_*`.
