# v3_headroom stepwise residual search — development results

Branch `cursor/seed-v3-stepwise-residual`. Protocol `f8c4c83` committed
before scoring. This results commit is separate. Base `9b4468b`. Zero
neural calls. Zero LLM-ledger debit. Not open-domain coding. Not
conversation capability. Not learning-to-learn. Not AGI.

Verifier `valid: true` (32 Set B episodes, every call replayed,
`n_candidate_calls <= 35`, φ and φ_step hashes frozen, three tampers
rejected). Wall **2.139212 s**. Ledger unchanged:
**3128.309460455996 used / 471.690539544004 remaining**.

`local_model_runtime.py` and `apply_primitive_op` were not edited.
The `9b4468b` artifact was not overwritten (sha256
`4324e5d51f085c9738c1867002da10ef6f5daa47ea664377b66e7e33a62dd596`).
Depth 1–2 and v1/v2 artifacts were not rescored. Flat re-runs matched
the locked `9b4468b` means (untrained 31.0, frequency 32.875, φ 31.625).

## Equalized Set B (`B = 35`, eight tasks)

| Method | Solved | Mean calls (capped) | Depth 3 | Depth 4 | Hit cap |
|---|---:|---:|---:|---:|---:|
| `untrained_default` | 2 / 8 | **31.000** | 0.00 | 0.50 | 5 |
| `simple_frequency_interleaved` | 4 / 8 | 32.875 | 0.00 | 1.00 | 4 |
| `invariant_phi_frozen` | 4 / 8 | **31.625** | 0.75 | 0.25 | 3 |
| `stepwise_residual_phi_frozen` | 3 / 8 | **23.250** | 0.00 | 0.75 | 0 |

Stepwise never hit the 35-call cap. It solved `b_filter_d4`,
`b_mod_d4`, and `b_order_d4`. The locked `b_order_d4` target is
I/O-identity on the frozen support and assessment payloads, so a
foreign-cluster no-op also counts as solved. All four Depth 3 tasks
missed: filter/mod stopped on a 2-op support prefix that failed
assessment; order and group found no support match.

## Gates

**Gate 1 (integrity): PASS.** No Set A → Set B name overlap. φ and
φ_step hashes unchanged. Every call replayed. All episodes
`n_candidate_calls <= 35`.

**Gate 2 (primary transfer): FAIL.**
`mean_calls(stepwise) = 23.250` is not `<= 0.5 * 31.000 = 15.5`.
Solve rate 0.375 beats untrained (0.25) and loses to flat φ (0.50).
Transfer is not established.

**Gate 3 (depth report):** stepwise Depth 4 0.75 vs flat φ 0.25;
Depth 3 0.00 vs flat φ 0.75. Cheaper search did not recover the
Depth 3 programs that flat φ already found.

## Claims

Investigation transfer on v3_headroom is **not** established. Ranking
stays unpromoted. `fixed_boundary` remains the default. Do not merge
`main`.
