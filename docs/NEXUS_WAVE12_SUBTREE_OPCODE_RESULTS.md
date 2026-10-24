# Wave-12 subtree invention and opcode accounting results

**Status: developmental / invalid.** Single-shot Commit 2 failed its
pre-registered gates. Commit 1 files were not edited. The `w12f_*`
suite is closed and must not be reused.

Branch `cursor/seed-wave12-subtree-invention-and-opcode-accounting`
from `5777ea2`. Protocol freeze `e940b82`. Artifact hash
`a6b8ba055930c36b9302aba9eae11d89d7b3c1df2879a6f80e883a5cfb037da0`.
`270` cells (`3` seeds × `5` methods × `18` tasks). Track B closed.
`0` model calls. Frozen debit **0**. Wall **1.942 s**. Grammar prior
was not retrained. Not general learning-to-learn. Not AGI.

`git ls-tree e940b82` contains no `mechanism_wave12_fresh_assessment.py`.
`git diff e940b82 -- src/nexus/seed/wave12_subtree_opcode_learner.py scripts/run_wave12_subtree_opcode_assessment.py scripts/verify_wave12_subtree_opcode_enumerator.py tests/test_seed_wave12_subtree_opcode.py` is empty.

## Wave-11 audit disclosures carried

- `w11a` (`c72a690` → `ffa43de`): runner `suite_totals` vs `totals["suite"]`.
- `w11b` (`b19b69a` → `1d6a946`): verifier `output` vs `observed_output`.
- Wave-12 Commit 1 tests replayed those exact keys on a synthetic payload
  before the assessment module existed.

## Suite totals

| Method | Mapping | Private | False unique | Work | Primitive steps | Synth evals |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| equal_typed_scratch | 33/54 | 27/54 | 3 | **26793** | **284967** | 25080 |
| ordinary_persistent_memoization | 33/54 | 27/54 | 3 | 26991 | 285566 | 25278 |
| nexus_whole_macro_only | 33/54 | 27/54 | 3 | 30249 | 348139 | 27490 |
| nexus_typed_without_pruning | 33/54 | 27/54 | 3 | 33370 | 476548 | 30666 |
| nexus_typed_full | 33/54 | 27/54 | 3 | 31955 | 391339 | 29160 |

`nexus_typed_full` did **not** win `total_work` or `total_primitive_op_steps`.

## What failed on seed 0 for `nexus_typed_full`

| Task | Status | Map / priv | Notes |
| --- | --- | --- | --- |
| w12f_base_even_dollar | unique | yes | `$` extracted |
| w12f_base_odd_at | unique | yes | `@` extracted |
| w12f_base_even_reverse | unique | private no | reverse on empty/even mismatch |
| w12f_ana_even_dup | unique | private no | |
| w12f_ana_odd_rev | ambiguous | no | field collision |
| w12f_sub_rot_* (4 tasks) | abstain | no | ROT wrap not found within size 7 |
| w12f_piece_even_odd / len0_odd | unique | yes | 2-guard path fired |
| w12f_piece_rot_odd | abstain | no | |
| w12f_arc_* | unique | yes | delayed palindrome reactivated archive |
| w12f_oog_caesar | abstain | yes | clean |
| w12f_oog_interleave | unique | false unique | enumerator locked a lookalike |

## Gates

| Gate | Result |
| --- | --- |
| Isolation / OOG / 0 false unique | **fail** |
| Dual cost identities | **pass** |
| Full accuracy | **fail** |
| Full dominates scratch / memo / whole-macro | **fail** |

## Why this is closed

The Part-3 no-amend rule forbids editing `e940b82` files or rerunning
the same `w12f_*` suite. Dynamic constant extraction and archive
reactivation showed local signal; unassisted ROT-left subtree invention
and OOG interleave abstention did not hold on this grid.
