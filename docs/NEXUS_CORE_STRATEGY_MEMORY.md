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

## Next research experiment

Development-only: score `ContextualStrategyMemory` against persist/reset
with `decide()`-owned FakeStepModel returns and more than two free
slots. Do not collect. Do not start an n=10 scientific run. Do not
reuse E2.17 development as confirmation.
