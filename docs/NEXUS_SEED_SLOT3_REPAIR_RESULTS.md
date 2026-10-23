# Unused third completion after a degenerate revision — development results

Branch `cursor/seed-worker-div-confirm`. Baseline `c94addb`. Protocol
`45bdbea` committed before scoring. This results commit is separate.
Not confirmation of learning-to-learn. Not AGI. Not a 4/4 claim.

Verifier `valid: true` on 1 inspect / 1 audit / 4 supplied cells, 16
events (6 complete / 6 worker / 4 assessment). Replay of saved final
files matched reported public and private flags. Per-task completion
identities reconstructed (`id:0` / `:behavior` / `:structural`).
Scored wall **64.114511 s** (confirm block **61.93452 s**). Hard
deadline 150 s was not hit. Offline tests were **0.59 s** wall with
0 model calls; they are engineering checks and are not added to the
scientific ledger. Ledger after this live debit:
**3379.081862455996 used / 220.918137544004 remaining** of 3600 s.

Artifact
`artifacts/seed_slot3_repair_confirm/seed_slot3_repair_confirm.json`
sha256 `a5ad6351e3218107adae69f0f3d5ee141e8d19fc329968b16bdf884ccb9e7fbc`.
Model `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`.
`local_model_runtime.py` was not edited. Closed 1/5, 3/4, prior 2/4,
and `c94addb` artifacts were not rescored.

## Offline

Focused `not live_model` tests passed, including:
`[C1 AttributeError] → [C2 {"body":"..."}] → [C3 valid]` charges 3
completions; `-lead` keeps C1 `AttributeError` and C2's structural
reason; prompts never write `{"body": "..."}`; the verifier
reconstructs a 3-completion chain and rejects a tampered private flag
or a changed historical fingerprint.

## Live cells (one run)

| Task | C1 | C2 | C3 | Public | Private |
|---|---|---|---|---|---|
| `py_lot_count` | `sum((item.get('lots', []).get('count', 0) for item in ...))` → `AttributeError` list has no `get` | `sum((item.get('count', 0) for item in item.get('lots', [])))` | not triggered (C2 parameterized and passed) | **3/3** | **3/3** |
| `py_job_slash` | `item['job'].lower() + '/' + item['unit'].lower()` → `KeyError` | identical parameterized body | not triggered (C2 references `item`, no unbound name) | 1/3 | **3/3** |
| `py_part_div` | `item['part'] / item['whole']` | none | none | **2/2** | **2/2** |
| `py_ok_pair` | `tenure >= min and grade >= cut` | none | none | **2/2** | **2/2** |

Public **3/4**, private **4/4**. Completions charged **6** (2+2+1+1),
all ≤ 3. Combined RSS ~2079–2082 MiB (`llama-server`). Slot-3 was
implemented and offline-proven; this live sample never produced a
placeholder, compile failure, or `item`-free constant after the
behavior revision, so the third completion stayed unused by design.

Lot-count repaired the `.get` on a list after public `AttributeError`.
Job-slash kept a structurally valid expression that still requires
both keys; missing `job` / `unit` public cases failed. Division and
the compound predicate succeeded on the first completion.

## Next

The unused-slot mechanical gap is closed. The leftover coding failure
is missing-field `KeyError` after a parameterized copy. Do not resume
ranking, memory, or experience comparison. Do not merge `main`.
