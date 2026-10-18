# NEXUS Core — Task-Conditioned Strategy Memory

Development algorithm and synthetic benchmark. Not a scientific result,
not learning-to-learn, and not AGI. E2.17 remains inconclusive.

## Architecture

`ContextualStrategyMemory` sits beside `AdaptiveProposer`. It does not
replace residual world models, the twelve-variant catalogue,
`TrustedEvaluator`, or Evolution-2 persist/reset methods.

1. **Task descriptor.** 12-d public vector from support observations,
   rewards, action statistics, residual prediction error, and
   observation/action/horizon dimensions. No family names, hidden
   weights, or holdout identifiers.
2. **Persistent memory.** Kernel store of `(descriptor, variant, score)`
   with running means and a conflict flag when neighbor scores disagree.
3. **Active selection.** LinUCB over catalogue arms. Retrieved mean,
   uncertainty, and conflict enter the features. High conflict
   downweights reuse and raises exploration.
4. **Adaptation.** `observe_support` refreshes the descriptor on a new
   task. Retrieval is nearest-descriptor, not last-task copy.

The memory-ablated control uses the same LinUCB without retrieval and
without a retained store.

## Development benchmark

Synthetic Evolution-2 families, seed 7, four matched proposals per task
(two forced anchors + two free), `TrustedEvaluator`-owned scores.
`holdout_horizon` is not consumed. No environment collection. Grant
stays consumed. Permitted `bundle0_train.npz` only exercises the
descriptor.

| Method | Train regret | Dev regret | Shifted regret | Dev first-free | Shifted first-free | Dev evals to strong |
|---|---:|---:|---:|---:|---:|---:|
| random | 0.0450 | 0.0700 | 0.1375 | 0.4298 | 0.2400 | 4.00 |
| reset_adaptive | 0.0000 | 0.0000 | 0.2625 | 0.7335 | 0.0000 | 3.00 |
| persistent_adaptive | 0.0200 | 0.0000 | 0.2625 | 0.7335 | 0.0000 | 3.00 |
| evolutionary | 0.0000 | 0.0350 | 0.0000 | 0.6573 | 0.1863 | 3.50 |
| contextual_strategy_memory | 0.0100 | 0.0000 | 0.2625 | 0.7060 | 0.0000 | 3.50 |
| memory_ablated | 0.0283 | 0.0000 | 0.2625 | 0.6510 | 0.0000 | 4.00 |

Lookups: 40 per method. Wall 0.036 s. CPU 0.036 s. Memory records: 40.

## What the numbers say

- **Memory changes decisions.** After the same training, toggling
  retrieval on a frozen weight matrix changes the first free choice on
  `successor_dev:0` (`8b9d187b…` vs `c01e7ee7…`).
- **Equal-budget selection does not improve.** Development regret ties
  persist and reset at 0. Persist/reset first-free 0.7335 beats memory
  0.7060. Retrieval does beat the ablated controller on first-free
  (0.7060 vs 0.6510).
- **Negative transfer is not avoided.** `inverted_successor` shares the
  public context of `successor_scale` and inverts hidden scores. Memory,
  persist, reset, and ablated all have shifted regret 0.2625 and
  first-free 0. Evolution finds a usable planner (shifted regret 0).
- Descriptor on permitted Pendulum arrays is 12-d and finite.

## Decide()-owned follow-up (four free slots)

Permitted E2.8 source arrays + `FakeStepModel` + `fixture_hidden_return`.
Six matched proposals (two anchors + four free). Seed 7. 48 lookups
per method. Wall 0.063 s. CPU 0.060 s. E2.17 science arrays unused.

Stored-obs Pendulum/Acrobot: flat-H=4 wins. Zero-obs Acrobot:
successor-H=16 wins. Collision reuses stored-Acrobot support on a
zero-obs landscape.

| Method | Train | Dev | Shifted | Collision | Dev first-free regret | Shifted first-free | Collision first-free |
|---|---:|---:|---:|---:|---:|---:|---:|
| random | 0.0390 | 0.0401 | 0.0000 | 0.0000 | 0.6549 | 0.0000 | 0.7892 |
| reset | 0.2349 | 0.3114 | 0.0000 | 0.0000 | 0.9152 | 0.0000 | 0.1096 |
| persist | 0.0775 | 0.0000 | 0.0996 | 0.0000 | 0.0000 | 0.1882 | 0.1096 |
| evolution | 0.0000 | 0.0000 | 0.0996 | 0.0000 | 0.4586 | 0.1882 | 0.1096 |
| memory | 0.0360 | 0.0000 | 0.0996 | 0.0000 | 0.0000 | 1.0000 | 1.0000 |
| ablated | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.9498 |

Collision best-of-six regret is non-identifying: the second forced
anchor is a zero-obs winner. First-free is the valid contrast.

## What the decide() numbers say

- **Causal retrieve-on/off did not change the first free choice** on
  `pend_store_2` (both `fde871fd…`). The earlier synthetic causal
  effect does not appear on this landscape.
- **Equal-budget development ties persist** at regret 0 and first-free
  regret 0. Memory and persist both beat reset (0.3114). That is
  retained-weight transfer, not a memory-retrieval win.
- **Retrieval hurt the start-state shift.** On fair zero-obs Acrobot,
  memory first-free regret is 1.0 (reuses stored-obs flat-H=4). Persist
  is 0.1882. Ablated best-of-six regret is 0; memory is 0.0996.
- **Collision first-free is worse for memory than persist** (1.0 vs
  0.1096). Misleading support pulled the stored-obs winner.

## Observation-aware descriptor (same eight tasks)

8-d `tanh` sketch of the `decide()` observation is concatenated onto
the 12-d support vector (`mode=combined`, dim 20). Write and query
use the same construction. No hidden returns enter the descriptor.

Support-only collision vs stored-Acrobot: distance 0.128, kernel
weight 0.990. Observation sketch: 1.440 / 0.265. Combined: 1.446 /
0.262. The missing information was the planning observation; adding
it separates the embeddings.

| Config | Dev best / first-free | Shifted first-free | Collision first-free |
|---|---:|---:|---:|
| persist | 0.000 / 0.000 | **0.188** | **0.110** |
| support memory | 0.000 / 0.000 | 1.000 | 1.000 |
| obs-only memory | 0.000 / 0.039 | 0.944 | 1.000 |
| combined memory | 0.000 / 0.000 | 1.000 | 1.000 |
| combined, no retrieve | 0.000 / 0.000 | 1.000 | 1.000 |

Causal (same support, store, RNG; only planning obs changes):
support-only choice stays `fde871fd…`. Combined neighbors move
(distance 0 → 0.888) but the selected planner does not. Zero-obs
query still picks the stored-obs winner (zero-landscape unit 0).
Shuffle/replace do not produce a better zero-landscape choice for
combined.

Held-out val/synthetic fixtures stayed separate. Combined first-free
0.178 vs persist 0.395 there is not a locked-split transfer claim.

**Development success: false.** Failure source:
`strategy_value_prediction`. Observation information now separates
tasks and retrieval neighbors move; LinUCB does not follow the
retrieved values. Persist remains better on the genuine shift.

## Next research experiment

Development-only: keep the observation-aware descriptor and replace
the LinUCB argmax with a retrieved-mean / gated selector when
neighbor mass is high. Same eight tasks, persist baseline, no
collection, no n=10 science. Do not reuse E2.17 development.
