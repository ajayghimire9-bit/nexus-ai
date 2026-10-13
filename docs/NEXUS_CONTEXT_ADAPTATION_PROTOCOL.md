# Context-adaptation protocol (pre-registered)

Starting SHA `a9c184c85c2a22317098d0c3637812386f4207e6` on `cursor/context-adaptation-pilot`. This file states the rules before confirmation. It is not a results report.

Not AGI. Not autonomous online learning. Not continual learning. An offline target-prefix adaptation comparison.

## Hypothesis

H1: A world model whose context is inferred from observed transitions has higher low-budget control-return AUC on unseen Pendulum physics than a multitask MLP with ordinary fine-tuning, and real task context beats constant context and wrong-task context.

Null: The context model fails to beat the fine-tuning baseline or fails its context controls.

Prediction error is diagnostic. Control return is primary.

## Mechanism (frozen)

FiLM conditioning, context dimension 8, encoder hidden 32, residual trunk (48, 48).

`z = mean_i encoder(normalized state, action one-hot, normalized next − normalized state)`.

Support and query are episode-disjoint. Query loss trains the encoder and the dynamics model. Empty context is trained with probability 0.2. No physics parameters, task IDs, or simulator state enter the network.

Normalization is fit on source-training observations and not updated on target data.

At evaluation, weights are frozen. `z` is computed once from the allowed prefix (at most 128 rows) and held fixed for the episode and for imagined MPC rollouts. Evaluation does not update `z` or weights. Context is cleared between tasks.

GRU is excluded. Shuffled minibatches do not form a coherent recurrent trajectory. This is not a recurrent training rewrite.

The previous Reptile result remains a negative result for that configuration. It does not disprove Reptile in general.

## Methods

1. Multitask residual MLP, frozen.
2. Multitask residual MLP, ordinary fine-tuning (lr 5e-4).
3. Context model, frozen weights, real target context.
4. Same model, zero context.
5. Same model, wrong-task context from source-task 0, matched length. No other confirmation data.

Development only: fixed random encoder, dynamics trained, real target context.

Target fine-tuning uses no target validation. Epoch count is chosen on development task 0, budget 64, one episode, among {2, 4}, by higher return. That integer is then frozen.

## Data

Eight source, three development, and four confirmation physics tuples are in `pendulum_context_train/development/confirmation`. They are disjoint from every earlier Pendulum suite. Confirmation is not loaded until the development gate passes.

Budgets: 0, 16, 32, 64, 128, 256, 512, 1024. Nested prefixes from one random-policy collection per task and seed. Same prefixes for every method.

MPC: horizon 16, 16 candidates, torques {−2, 0, +2}, Gymnasium reward.

## Statistics

Primary metric: trapezoidal return AUC on budgets 0–256, divided by 256.

Primary comparison: real context minus multitask fine-tune. Tasks are averaged inside each training seed. The 95% interval is a Student-t interval across seeds. Episodes are not replicates.

Secondary, unadjusted (not a second primary, no Bonferroni): real minus zero context; real minus wrong-task context.

Development gate (point estimates, 2 seeds, not a CI): real−zero > 0, real−wrong > 0, real−fine-tune > 0, encoder L2 change > 0, all returns finite. If this fails, confirmation is not run.

Confirmation success requires the primary interval lower bound > 0 and both secondary interval lower bounds > 0. Otherwise the result is a failure if an interval lies entirely on the wrong side, and inconclusive if the primary interval includes 0 without that stronger contradiction.

## Compute disclosure

Source transitions match. Optimizer steps are logged. Context encoding of support is extra compute and is not claimed to match fine-tuning FLOPs. Target fine-tuning spends gradient steps; the context model does not update weights on the target prefix.

Time caps: 2 hours development, 4 hours confirmation. An overrun is an incomplete run.

## Development outcome

The development gate failed. See `docs/NEXUS_CONTEXT_ADAPTATION_PILOT.md`. Confirmation was not run. The rules above were not changed after the curves.
