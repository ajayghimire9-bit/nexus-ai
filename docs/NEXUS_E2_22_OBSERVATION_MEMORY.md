# NEXUS Evolution-2.22 — Observation-conditioned strategy memory

Development source-only screen. Not a scientific result, not
learning-to-learn, and not AGI. E2.17 remains inconclusive. H17 is
untouched. Scores are `decide()` + `FakeStepModel` **proxies**, not
real control returns.

## What was implemented

`ObservationAwareAdaptive` wraps `AdaptiveProposer`. It does not
replace that proposer, `PersistentAdaptive`, or
`ContextualStrategyMemory`.

Each memory entry stores planner fingerprint, permitted unit score,
family-normalized observation embedding, observation schema,
provenance, and a support digest. Retrieval uses only same-family,
same-schema embeddings. Current-task provenance is excluded so the
two anchors cannot open the gate by writing the query observation
before the first free slot.

Family z-scores and the gate (kernel length 2.549, threshold 0.491)
are fitted on E2.8 `bundle{0,1}_train` observations only (2048 per
family). The far shift is mean + 4σ of that fit. Shifted evaluation
outcomes were not used to set thresholds.

## Protocol

Branch from local HEAD `0d8ebd566da6c49d25404876db9e83d85cfd571a`.
Six proposals, two anchors, four free slots. Seed 7. Permitted E2.8
arrays + `FakeStepModel` only. 60 matched lookups per method. Grant
stays consumed. Wall 0.123 s. CPU 0.123 s. 0 env steps.

| Situation | Tasks |
|---|---|
| Familiar stored-obs | `pend_store_2`, `acro_store_1` |
| Ranking-changing shift | `acro_zero_1` (zero start; also in train as `acro_zero_0`) |
| Distribution shift, same oracle | `pend_far_2`, `acro_far_1` |
| Conflict | `acro_zero_collision` (stored support, zero decide() obs) |

Oracles: stored-obs and both far tasks are flat H=4 (`4e697425…`).
Zero-obs Acrobot is successor H=16 (`c01e7ee7…`). Collision oracle is
`e04f4ef2…`. Far-σ=4 is a real embedding shift (causal nearest 9.06)
but **not** a planner-identity shift on this proxy.

## Results

| Method | Dev FF | Shift FF | Collision FF | Dev retrieve | Shift fallback |
|---|---:|---:|---:|---:|---:|
| reset | 0.915 | 0.617 | 0.110 | 0 | 0 |
| persist | **0.000** | 0.063 | 0.110 | 0 | 0 |
| gated memory | **0.000** | **0.000** | 0.110 | 0 | 2.67 |
| ungated memory | **0.000** | **0.000** | 0.110 | 4 | 0 |
| shuffled memory | **0.000** | 0.635 | 0.950 | 0 | 2.67 |
| evolution | 0.459 | 0.063 | 0.110 | 0 | 0 |
| random | 0.655 | 0.460 | 0.789 | 0 | 0 |

On `acro_zero_1` gated memory retrieves the train zero-obs winner
(`c01e7ee7…`, first-free regret 0). Persist still pays the historical
0.188 first-free cost on that task (pooled shift 0.063). Far tasks
fallback and match persist. Familiar development also fallbacks
(inter-bundle stored-obs distance 1.216 > gate 0.491); first-free 0
there is the inner proposer’s persist-like weights, not retrieval.

Causal (memory and weights frozen; only the query observation changes):

| Query | Action | Nearest | Choice |
|---|---|---:|---|
| stored Acrobot | fallback | 1.216 | `fde871fd…` |
| zero | retrieve | 0.000 | `c01e7ee7…` |
| far +4σ | fallback | 9.059 | `fde871fd…` |

Shuffle destroys the shift (0.635) and collision (0.950). Ungated
also reaches shift first-free 0 by always retrieving.

**Development success: false.** Shift first-free beats persist, but
familiar retrieval is not shown (global fallback on stored-obs
development). Falling back everywhere except an exact zero match is
not yet useful general memory.

## Research answers

1. **Decisions vs scores.** Best-of-six is already 1.0 for persist on
   familiar and far tasks. The measurable change is first-free:
   gated memory picks the zero-obs oracle immediately; persist does
   not. That is a real `choose()` change, still a proxy score.
2. **Negative transfer.** The earlier un-isolated gate transferred
   current-task anchor writes and lost to persist (shift 0.315).
   After provenance isolation, gated memory no longer loses the
   shift. Shuffle reintroduces harm. Collision first-free ties
   persist (0.110); it does not beat the collision oracle.
3. **Positive transfer.** Exact-match zero-obs reuse works.
   Same-family stored-obs reuse does not pass the source-calibrated
   gate. Familiar first-free 0 is proposer persistence, not memory.
4. **Observation-conditioned.** Yes, by the frozen-memory obs swap
   and by shuffle. The gate is not a hardcoded zero test: far (+4σ)
   also fallbacks, and zero retrieves because train wrote that
   embedding.
5. **Next experiment.** Recalibrate the gate from *inter-bundle*
   source planning-obs distances (bundle 0 vs 1), still without
   shifted labels, so typical stored-obs neighbors retrieve. Do not
   loosen the threshold on `acro_zero_1`. Separately, this FakeStep
   landscape does not change planner identity under +4σ; a later
   residual/`decide()` landscape that does would make far-shift
   identifiable. No collection. No E2.17 reuse. No n=10 science.

Failure source: **source-NN gate tighter than inter-bundle stored-obs
distance**. Smallest correction: inter-bundle source calibration, not
another selector stack.
