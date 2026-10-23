# v3_headroom Set A → Set B transfer and depth 3–4 ablation — protocol

Base: reviewed tip `86836cb` of `cursor/seed-v3-headroom`. Development
only. Do not rescore the design-lock certificate, Depth 1–2 grids, v1/v2
investigation artifacts, or conversation-capability tools /
`ordinary_cache` / `simple_frequency` results. Do not edit
`apply_primitive_op` or `src/nexus/seed/local_model_runtime.py`.
Zero live neural calls. Runner wall must stay under 15 s. Standing
grant: 900 s this experiment, carried session
**3126.028358455996 used / 473.9716415440039 remaining**, local CPU.

Commit this protocol and the tested runner **before** writing the
scored artifact.

## Equalized controller (every method, every Set B episode)

- `max_episode_candidate_calls = B = 35`
- `shortlist_limit = 8`
- `allow_questions = True`
- `max_questions_per_task = 2`
- Widening stop is the same call/question ceiling. Skeleton methods
  may expand abstract templates; other methods use raw primitives.
  Stopping rules do not change.

A candidate call is one `execute_v3(program, input)`. Oracle answers
are not candidate calls. Training calls on Set A are charged separately
and are not part of Set B means.

## Disjoint train / transfer

Set A (train only): 12 named operators, eight authored tasks, two per
cluster (depth 3 and depth 4). φ and name-index weights and abstract
skeletons are fit on Set A support I/O only.

Then `freeze_weights = True`. Set B episodes must not write φ.

Set B (held-out): 12 **different** operator names, `|H| = 12³ + 12⁴ =
22 464`, eight authored tasks, two per cluster (depth 3 and depth 4).
Operator signatures used on Set B are the four automatic specialist-probe
fingerprints computed at registration. No hand map from Set A names to
Set B names.

Locked Set A targets: `keep_pos+keep_even+take_prefix_half` and the
depth-4 extension starting with a repeated first op; `res_mod3+add2_mod5+mul2_mod7`;
`rev+rot_l+sort_up`; `sum_by_parity+count_by_sign+first_per_mod2`; plus
the four matching depth-4 rows in the config.

Locked Set B targets: `keep_odd+drop_suffix_half+keep_neg` (depth 3,
3-ary index 19) and `keep_neg+keep_neg+keep_neg+keep_odd` (depth 4,
3-ary index 1); the analogous mid-depth-3 / early-depth-4 rows for
mod, order, and group in the config.

## Six equalized Set B conditions

1. `untrained_default` — uniform 12-ary catalogue order, raw primitives.
2. `simple_frequency_interleaved` — four-slice zipper, raw primitives.
3. `name_indexed_ranker` — Set A `op_name → score`. Disjoint Set B names
   must score 0.
4. `invariant_phi_frozen` — Set A `(Support_IO_Invariant,
   Operator_Algebraic_Signature) → score`, frozen, raw primitives.
5. `higher_order_skeletons_only` — untrained ranker; expand Set A
   signature templates (including `C_i(SLOT) -> C_j(SLOT)`) with Set B
   operators of the same automatic signature. No operator-ID leakage.
6. `combined_invariant_phi_plus_skeletons` — frozen invariant φ plus
   those templates.

## Gates (fixed; do not retune after scoring)

1. **Specialist separation.** On the eight full Set B episodes, summed
   per cluster, `invariant_phi_frozen` support-check calls **and**
   specialist probe-construction calls are each strictly below
   `simple_frequency_interleaved`.
2. **Primary transfer.** On Set B under B = 35:
   `mean_calls(invariant_phi_frozen) <= 0.5 * mean_calls(untrained_default)`
   **and** solve rate strictly above `untrained_default` **and**
   `name_indexed_ranker`. If both methods sit on the 35-call cap so that
   17.5 is unreachable, report the capped means, the untruncated
   call-to-first-support-match distribution, and **do not** mark
   transfer passed.
3. **Skeleton necessity.** Report depth-3 and depth-4 solve rates for
   `invariant_phi_frozen` versus `combined_invariant_phi_plus_skeletons`.
   If raw φ hits the cap on 4-step tasks while skeletons solve them,
   state that gap. This gate is a measurement, not a reason to change
   Gate 2.

A task is solved when the selected program matches the target on the
held-out assessment input after the episode stops.

## Verifier

Rebuild means, solve rates, and gates from raw episodes. Check Set A/B
name and task disjointness, φ hash unchanged on every Set B episode,
every logged call replay, `n_candidate_calls <= 35`, and three tamper
self-tests (call-count, φ mutation, A/B name overlap).

## Claims

If Gate 2 passes, report investigation transfer on this algebraic
grammar only. Open-domain coding and conversation remain unestablished.
`fixed_boundary` stays the default. Do not merge `main`.
