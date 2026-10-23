# v3_headroom Set A → Set B transfer — development results

Branch `cursor/seed-v3-headroom`. Protocol `3190714` committed before
scoring. This results commit is separate. Base `86836cb`. Zero neural
calls. Not open-domain coding. Not conversation capability. Not
learning-to-learn. Not AGI.

Verifier `valid: true` (48 Set B episodes, every call replayed,
`n_candidate_calls <= 35`, φ hash frozen, three tampers rejected).
Wall **2.281102 s**. Ledger after this run:
**3128.309460455996 used / 471.690539544004 remaining**.

`local_model_runtime.py` and `apply_primitive_op` were not edited.
Depth 1–2 and v1/v2 artifacts were not rescored. `name_indexed_ranker`
matched `untrained_default` exactly (Set B names score 0).

## Equalized Set B (`B = 35`, eight tasks)

| Method | Solved | Mean calls (capped) | Mean untruncated | Hit cap |
|---|---:|---:|---:|---:|
| `untrained_default` | 2 / 8 | **31.000** | 394.25 | 5 |
| `simple_frequency_interleaved` | 4 / 8 | 32.875 | 30.75 | 4 |
| `name_indexed_ranker` | 2 / 8 | 31.000 | 394.25 | 5 |
| `invariant_phi_frozen` | 4 / 8 | **31.625** | 96.375 | 3 |
| `higher_order_skeletons_only` | 2 / 8 | 30.875 | 48.25 | 5 |
| `combined_invariant_phi_plus_skeletons` | 4 / 8 | 32.625 | 32.25 | 4 |

## Gates

**Gate 1 (specialist separation): FAIL.** Per-cluster support checks
for `invariant_phi_frozen` versus `simple_frequency_interleaved`:
filter 46 vs 70, mod 70 vs 70, order 43 vs 45, group 70 vs 70. Probe
construction: filter 16 vs 0, mod 0 vs 0, order 8 vs 8, group 0 vs 0.
φ did not strictly reduce both tallies on every cluster. Frequency
often spent the whole budget on failed support checks and never built
a specialist probe; φ sometimes did, so probe counts rose.

**Gate 2 (primary transfer): FAIL.**
`mean_calls(φ) = 31.625` is not `<= 0.5 * 31.000 = 15.5`.
Solve rate 0.50 does beat untrained and name-index (0.25 each), but
the registered call criterion failed. Untruncated call-to-first-support
match is 96.375 versus 394.25 — a cheaper search if the cap is removed —
and that is **not** a pass. Transfer is not established.

**Gate 3 (depth 3–4 skeletons):** depth-3 solve 0.75 vs 0.75; depth-4
solve 0.25 vs 0.25 (`invariant_phi_frozen` vs combined skeletons).
Raw φ did not sit alone on the 35-call ceiling while skeletons solved
4-step tasks. Combined φ+skeletons solved `b_group_d3` (untruncated 22)
where raw φ needed 313; it also missed `b_filter_d3` that raw φ solved.
No clean depth-4 skeleton necessity.

## Claims

Investigation transfer on v3_headroom is **not** established. Ranking
stays unpromoted. `fixed_boundary` remains the default. Do not merge
`main`.
