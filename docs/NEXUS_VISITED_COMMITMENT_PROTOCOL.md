# Phase-50 visited-state commitment diagnostic — protocol v1

Registered before outcomes, from clean GitHub-matched `f7dd7239cc13ad6b02bdee89c4c41010af1c83e5`. Executable source of truth: `configs/visited_commitment.yaml`; the allocation binds exact config and protocol hashes before collection. New research branch `codex/visited-commitment-diagnostic`. Previous artifacts, weights and closed seeds remain unchanged.

## Hypotheses and scope

H-persistence: the positive frozen-correction×commitment interaction measured at fresh initial states persists on states visited during control. H-distribution: that benefit does not persist under the sampled visitor distributions. Failure to reject zero is inconclusive, not evidence that the effect disappears. A changed mean across these separately sampled studies is descriptive, not a causal state-distribution effect. This is known-development-physics mechanism research, not unseen-physics confirmation or full-episode controller selection.

## Frozen inputs and visited states

Reuse the ten original independent decoders, all five student encoders/contexts, zero context, frozen terminal readouts, source normalization, H=16,16 candidates, published reward and torque actions. No fitting or new support. Same three inspected development physics as the initial-state diagnostic; exact tuples in config. All120 binary hashes and30 decoder/task context groups must verify before data collection. Weights, contexts, normalization and readouts must match before/after.

For each decoder d0..9 and task t0..2, collect exactly50 live actions under each of two unchanged visitors: student seed `(d+t) mod5` and zero context. This balanced prespecified assignment uses each student seed six times across30 decoder/task groups. This is one student visitor per decoder/task, not the distribution of all five student visitors. All five student models score every collected state. No visitor is chosen using return. Both visitors share reset seed2500000+100*d+t and collection candidate seeds2510000+10000*d+100*t+k for k0..49. Store every action, reward, observation/next observation, true simulator state, candidate score and selected index, termination flags and RNG seed. Re-score the final live decision without another environment step; reject mismatched live replay before interpreting counterfactuals.

Use the phase50 endpoint as the registered state. True state is for restoration/measurement only, not model input. Restore simulator state and original episode clock50 for first-action branches and candidate prefixes; full-block suffix starts at66. Every counterfactual finishes at original step114, below truncation200. Context stays fixed during collection, scoring and rollouts. Model inputs never include task ID, physics or actual future outcomes.

## Same-state intervention

For each of60 decoder/task/visitor states generate exactly16 shared H16 candidate sequences with seed2700000+100*d+10*t+v (v0 student-visitor, v1 zero-visitor). All frozen contexts score the identical candidates with original score and original+survival×terminal-readout score. Outcomes cannot enter scoring.

For each selected candidate, compare forcing its first action then zero-context replanning for63 steps, versus executing all16 actions then zero replanning for48 steps. Both measure64-step return. Planning seeds are2800000+10000*d+1000*t+100*v+k, k0..63: they depend on local time, not action or scoring rule. Cache the three possible first-action outcomes and all16 sequence outcomes per state. Six scoring contexts and two rules reuse those outcomes; they do not add environment interactions. Exact sets are disjoint from historical closed suites and each other. Diagnostic prefixes cannot be shared across decoders because visited states differ.

## Primary analysis and decisions

Per state and student define gain1=corrected−original return under first-action commitment; gain16=corrected−original return under full-sequence commitment; interaction=gain16−gain1. Average five scoring students within decoder/task/visitor, then weight both visitor groups equally, then average three tasks equally within each decoder. There is only one phase,50. Use the ten independent decoder values for two-sided paired95% t intervals, df9,critical2.262. Episodes, visitors, students and candidates are not independent decoder replications.

Keep the prior practical screen unchanged: interaction mean≥1 and interval lower>0. `commitment_sensitive_gain` additionally requires gain16 interval lower>0. If interaction alone passes, label `relative_commitment_sensitivity_without_established_gain`; otherwise `commitment_interaction_not_established`. Report negative directions and uncertainty. A failed/incomplete integrity grid has label `incomplete`, never an inconclusive scientific result. This conjunction is one registered screen; task and visitor intervals are exploratory, unadjusted sensitivity measurements.

Report both visitor groups separately, all tasks/decoders, absolute four-arm returns, selection/action disagreements, regret and pairwise endpoint distances. Regret reduction repeats the return contrast and is not independent corroboration. An interaction does not show block commitment is better than original one-action control: show that absolute comparison descriptively. Report comparison to the closed +39.366 initial-state estimate without treating different samples as a randomized distribution intervention. No posthoc reweighting, seed exclusion, tuning or rerun.

## Budget and stopping

Estimated4–6 CPU minutes based on the prior225.528-second run, with added collection and separate prefixes; **hard cap600seconds**, inside the remaining674.472-second standing session allowance. Exact planned real steps: collection3000 + prefixes15360 + block tails46080 + first-action branches11520 = **75,960**. Imagined transitions: prior counterfactual/scoring14,883,840 + live collection768,000 +60 live-decision replay calls×256=15,360 = **15,667,200**. Zero new support/model/readout updates. Preserve inherited training/support accounting separately.

Enforce caps before each environment/model step. Save partial raw data on exceptions/timeouts; do not shorten the declared grid or silently rerun. Protocol, implementation, focused tests and exact standing-grant allocation must be committed before constructing registered environments. Preserve clean execution SHA, config/protocol/allocation/parent hashes, dependencies, typed finite metrics, raw per-step rewards and complete60-cell grid. Explicit binary checks fail on missing files; repository-only arithmetic checks do not need .pt files. Before/after120-file verification and fingerprint equality are mandatory for completeness.

## Tests and commands

Tests must verify visitor assignment and equal weights, episode clocks/restoration, deterministic live replay and candidate streams, common-zero context rejection, complete seed/task/visitor/context/arm grid, finite metrics, saved reward sums including unselected actions, context immutability, exact budgets, missing/stale allocation, and rejection of closed seeds before collection. Synthetic complete captures permit strict validation without running the registered experiment.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_visited_commitment.py tests/test_commitment_value.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_visited_commitment.py
# Once only, after clean preregistration commit:
PYTHONPATH=src:.deps python3 scripts/run_visited_commitment.py --execute
PYTHONPATH=src:.deps python3 scripts/run_visited_commitment.py --audit
PYTHONPATH=src:.deps python3 -m pytest -p no:cacheprovider
```

If the screen passes, the next question is practical policy value under an explicitly bounded controller comparison, not immediate deployment. If inconclusive, retain uncertainty and visitor/task sensitivity rather than changing architecture. If negative, investigate state-distribution dependence without claiming it caused the earlier full-episode loss. No controller changes, confirmation access, architecture search or further experiment are part of this run.
