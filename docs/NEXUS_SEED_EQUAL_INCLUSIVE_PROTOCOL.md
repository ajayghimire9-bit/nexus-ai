# Equal inclusive baseline and fresh API-ID — protocol

Isolated branch `cursor/seed-equal-inclusive` from reviewed
`cursor/seed-acquired-experience` `90eef6b`. Protocol committed before
scoring. Opened acquired-experience and routes cells are not rescored.
Not confirmation. Not learning-to-learn. Ranking stays paused. Do not
merge `main`.

## Questions

1. After giving the ordinary baseline the same applicability checks and
   the same `</>` inclusive repair (`apply_make_inclusive`), does
   acquired experience contribute anything beyond invoking that tool?
2. On a fresh API-ID grid, do named/validated bindings prevent the extra
   `elem.*` miss from becoming an executable call, and does selection or
   binding still fail separately?

Broader learning research stays paused unless a reusable procedure beats
this equally capable simple baseline.

## Experience methods

Same frozen 1.5B model, prompt, contracts, tools and revision limits.

| Arm | Mechanism |
| --- | --- |
| A scratch | `generate_direct` |
| B exact cache | hit or miss→scratch fallback |
| C inclusive tool | `propose_inclusive_tool`: same gates as memory, Lt or Gt rebound |
| D acquired | captured schema + `propose_retrieved_repair` |
| E reset | empty store + scratch |
| F irrelevant | null-default store only; miss→scratch fallback |

Refuse and ask are complete assistant acts. Only `abstain` (retrieval
miss) falls back to `generate_direct`. Cache and memory therefore cannot
look cheaper merely by stopping without solving.

C is no longer the Lt-only template from the prior study. That older
arm understated the ordinary tool. If C and D match, report a tool-tie
rather than inventing a distinction.

## Fresh splits

Closed IDs include the opened acquired-experience and routes API cells.
Roles are the same; names and paths are new.

| ID | Role |
| --- | --- |
| `src_eq_span` | acquire Lt→LtE |
| `src_eq_null` | irrelevant family |
| `dev_eq_lt` | freeze representation |
| `tgt_eq_rename` | related rename/layout |
| `tgt_eq_gt` | related `>` rebound |
| `tgt_eq_exclusive` | refuse; starter already correct |
| `tgt_eq_unrelated` | miss then fallback |
| `tgt_eq_ask` | ask; no fallback |
| `tgt_eq_repeat` | exact repeat, separate |

## Fresh API-ID

`api_eq_ceil` (`clip.cap_high`) and `api_eq_glue` (`tape.glue_bits`).
Methods: `direct` and `id_select_assemble`. Score selection, binding
validity, binding correctness, assembly and private execution
separately. Extra bindings must not assemble. Selection is not
generally solved. Opened `api_id_floor` / `api_id_stitch` unused.

## Metrics (reported separately)

- correct solutions (private pass)
- correct clarification or refusal
- harmful changes (changed a privately correct starter and then failed)
- model calls
- wall time / retrieval tokens

Exact-repeat caching is separate from later-task transfer.

## Decision rule

Tool-tie: D matches C on later solutions and on clarification/refusal,
with no extra harmful change. Useful acquired: D beats C and scratch
and reset on later solutions without worse harm. Negative: D introduces
harm. Otherwise inconclusive. Memory persistence is not
learning-to-learn.

## Budget

Standing local-CPU grant. Cap 80 calls / 900 s. Expected live load is
about 28 completions (experience fallbacks plus 4 API cells). Frozen
research ledger, product chat and Metal are not charged.

## Verifier

Replay saved programs. Do not trust success flags. Check isolation,
reset emptiness, frozen debit 0.
