# v3_headroom stepwise residual search — protocol

Base: `9b4468b` on `cursor/seed-v3-headroom`. New branch
`cursor/seed-v3-stepwise-residual`. Development only. Do not overwrite
`9b4468b` or its artifacts. Do not edit `apply_primitive_op` or
`src/nexus/seed/local_model_runtime.py`. Zero live neural calls. Zero
LLM-ledger debit. Runner wall must stay under 15 s. Standing grant
is not charged for this symbolic study.

Commit this protocol and the tested runner **before** writing the
scored artifact.

## Why the flat search failed

`invariant_phi_frozen` computed `Support_IO_Invariant(x_0, y_final)`
once at `t = 0` and ranked all 22 464 whole 3-op and 4-op chains.
Inside one 3-operator cluster, `3³ + 3⁴ = 108` programs share that
tag. End-to-end chain testing cannot solve Depth 4 inside `B = 35`
(0.25 depth-4 solve rate; Gate 2 mean 31.625 vs `<= 15.5`).

## Equalized controller

- `max_episode_candidate_calls = B = 35`
- `shortlist_limit = 8`
- `allow_questions = True`
- `max_questions_per_task = 2`
- Stepwise beam: `beam_width = 3`, `ops_per_step = 3`, `max_depth = 4`

A candidate call is one `execute_v3` recorded through `EventMeter`
(`step_expand` or `probe_construction`). Assessment and Set A training
calls are not Set B candidate calls.

## Disjoint train / transfer

Same locked Set A / Set B tasks, payloads, and automatic specialist
probes as `9b4468b`. φ_step is fit on Set A support I/O only:

`(Residual_IO_Invariant(x_t, y_final), Operator_Probe_Signature) → step_score`

`Operator_Probe_Signature` is the fine-grained specialist-probe
profile (cluster class plus intra-cluster I/O class). It is never an
operator name. Then `freeze_weights = True`. Set B must not write
φ_step.

## Step-wise search

At depth `d = 1..4`, expand the top-ranked single-step operators
`x_{t+1} = op(x_t)` on the support input, drop any prefix that matches
an already seen support state (observational equivalence), and
recompute `Residual_IO_Invariant(x_{t+1}, y_final)`. Rank expansions
by residual progress. Stop at the shortlist or the call cap.

## Four equalized Set B conditions

1. `untrained_default` — flat 12-ary catalogue, same runner as `9b4468b`.
2. `simple_frequency_interleaved` — four-slice zipper, same runner.
3. `invariant_phi_frozen` — frozen flat φ from Set A, same runner.
4. `stepwise_residual_phi_frozen` — this study.

Do not rescore the six-method `9b4468b` artifact. Re-running the three
flat methods here is a new equalized grid.

## Gates (fixed; do not retune after scoring)

1. **Integrity.** No Set A → Set B name overlap. φ and φ_step hashes
   unchanged on every Set B episode. Every logged call replays.
   `n_candidate_calls <= 35`.
2. **Primary transfer.** On Set B under `B = 35`:
   `mean_calls(stepwise_residual_phi_frozen) <= 0.5 * mean_calls(untrained_default)`
   **and** solve rate strictly above `untrained_default` **and**
   `invariant_phi_frozen`. If both stepwise and untrained sit on the
   35-call cap so that 15.5 is unreachable, report the capped means
   and **do not** mark transfer passed.
3. **Depth report.** Publish Depth 3 and Depth 4 solve rates for all
   four methods. This is a measurement, not a reason to change Gate 2.

A task is solved when the selected program matches the target on the
held-out assessment input after the episode stops.

## Verifier

Rebuild means, solve rates, and gates from raw episodes. Check
disjoint names, frozen hashes, call replay, budget, and three tamper
self-tests (call-count, φ_step mutation, A/B name overlap).

## Claims

If Gate 2 passes, report investigation transfer on this algebraic
grammar only. Open-domain coding, conversation, and learning-to-learn
remain unestablished. `fixed_boundary` stays the default. Do not
merge `main`.
