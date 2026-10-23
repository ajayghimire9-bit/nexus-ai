# Slot-3 after a duplicated KeyError subscript — development results

Branch `cursor/seed-worker-div-confirm`. Baseline `307bd89`. Protocol
`f850122` committed before scoring. This results commit is separate.
Not confirmation of learning-to-learn. Not AGI. Not a 4/4 claim.

Verifier `valid: true` on 1 inspect / 1 audit / 4 supplied cells, 18
events (9 complete / 5 worker / 4 assessment). Replay of saved final
files matched reported public and private flags. Scored wall
**72.075918 s** (confirm block **70.058627 s**). The 70 s hard
deadline was reached on the last cell. Offline tests were **0.84 s**
wall with 0 model calls; they are engineering checks and are not
added to the scientific ledger. Ledger after this live debit:
**3451.157780455996 used / 148.842219544004 remaining** of 3600 s.

Artifact
`artifacts/seed_slot3_copy_confirm/seed_slot3_copy_confirm.json`
sha256 `8a00c479ed9faba17016a92910fa50f0214393ee51495bac41eb5c7b438b7caf`.
Model `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`.
`local_model_runtime.py` was not edited. Closed 1/5, 3/4, prior 2/4,
and `307bd89` artifacts were not rescored.

## Offline

Focused `not live_model` tests passed, including
`[C1 bare subscript KeyError] → [C2 identical copy] → [C3 .get]`
charges 3 completions with codes `duplicate_ast` and
`unchanged_subscript_on_keyerror`; the verifier reconstructs that
chain and replays public/private parity; an unguarded `item['post']`
fails the fresh private missing-key cases.

## Live cells (one run)

| Task | C1 | C2 | C3 | Public | Private |
|---|---|---|---|---|---|
| `py_crate_tally` | `sum(item['crates'] or [0])` TypeError int+dict | identical; unprojected-sum reject | same body (`behavior_reject`, not structural) | 1/3 | 0/3 |
| `py_post_slash` | `item['post'].lower()+'/'+item['desk'].lower()` KeyError | identical copy | structural slot fired (`duplicate_ast` + `unchanged_subscript_on_keyerror`); model recopied | 1/3 | 1/3 |
| `py_ratio_div` | `item['taken'] / item['total']` | none | none | **2/2** | **2/2** |
| `py_clear_pair` | empty placeholder | format repair still empty | none (server RSS dropped to ~25 MiB) | 0 | 0 |

Public **1/4**, private **1/4**. Completions charged **9**
(3+3+1+2), all ≤ 3. Combined RSS ~2031–2050 MiB on the first three
cells; ~25 MiB after `clear` (owned server gone). Slot 3 fired on
the tag task as designed. Private missing-key cases made the
unguarded subscript fail private as well as public. The 1.5B coder
did not change the expression after the structural reasons. No
`.get` was planted.

## Next

The copy / KeyError trigger is implemented and was used. Remaining
failures are model-semantic (same unprojected `sum`, same bare
subscript after slot 3) plus an empty last cell at the deadline.
Do not resume ranking, memory, or experience comparison. Do not
merge `main`.
