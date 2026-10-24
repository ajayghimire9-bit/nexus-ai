# API apply modes — protocol

Isolated branch `cursor/seed-api-apply-modes` from reviewed
`cursor/seed-named-api-id` `711549e`. Protocol committed before scoring.
Opened named (`api_nb_*`) and positional API cells are not rescored.
Not confirmation. Not learning-to-learn. Ranking stays paused. Do not
merge `main`.

## Questions

On a fresh frozen grid with an explicit apply mode:

1. Structural validity: does the request satisfy the schema (named
   bindings plus `apply`, or an `ask`)?
2. Type validity: do bound fields match parameter shapes, and is the
   apply mode compatible? A well-formed `field.list` on a scalar is
   structurally valid and type-invalid.
3. Correct bindings: named fields and apply mode match gold, or the
   model asks on the ambiguous cell.
4. Final behavior: assembled program passes private tests, or the
   ask cell asks.

Direct receives the same interface brief, apply rules and one-call
budget.

## Grid

Two different APIs and distinct fields in each role. Decoy same-type
fields sit beside the gold field. Renamed IDs alone are not
independence.

| Role | IDs | APIs |
| --- | --- | --- |
| Optional omitted | `api_ap_omit_badge`, `api_ap_omit_wrap` | `labels.badge`, `notes.wrap` |
| Optional supplied | `api_ap_use_tone`, `api_ap_use_bonus` | `paint.tint`, `mathx.shift` |
| Whole-list | `api_ap_list_stretch`, `api_ap_list_join` | `stats.stretch`, `bags.join_all` |
| Element-wise | `api_ap_elem_tall`, `api_ap_elem_wide` | `gate.over`, `check.wide` |
| Ambiguous ask | `api_ap_ask_limit` | `gate.over` on scores; loft vs width |

Optional parameters may be absent. The assembler never fills them.
`apply` is `direct`, `whole_list` or `element`. Incompatible proposals
do not assemble. When two type-compatible fields remain and the
request does not name one, the gold act is ask.

## Budget

9 tasks × 2 methods = 18 calls. Standing local-CPU grant. Cap 80 /
900 s. Frozen ledger, product chat and Metal unused.

## Verifier

Replay non-ask saved programs. Do not trust success flags.
