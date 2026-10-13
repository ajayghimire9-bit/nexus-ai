# Context-adaptation diagnosis

Starting SHA `b86baf4e23e29761ec34e29b2a8d67f3a24ae207` on `cursor/context-adaptation-diagnosis`. Config: `configs/context_adaptation_diagnosis.yaml`, which the runner loads and checks against the locked settings.

Not AGI. Development only. The unused confirmation physics are not evaluated. This does not replace the original 0–256 confirmatory result.

## Preserved negative result

The context-adaptation development screen stands:

| Method | Primary AUC (0–256) |
| --- | ---: |
| Multitask fine-tune | −453.6 |
| Real context | −755.3 |
| Zero context | −651.9 |
| Wrong-task context | −725.3 |

## Diagnostic hypotheses

These are exploratory. They are not the original confirmation hypothesis.

**H-length.** Training on varied support lengths improves short-history adaptation compared with training only on empty or 128-transition histories.

**H-context.** Real task context improves held-out prediction over zero context and wrong-task context.

A correlation between prediction error and return is not, by itself, a causal claim.

## What stays fixed

Source and development physics, source-only normalization, context dimension 8, encoder hidden size 32, trunk (48, 48), the existing prediction loss and Adam step, 300 source updates, query batch 64, MPC horizon 16 with 16 candidates, the target-prefix collection policy, and the development evaluation seed `193000`.

Fine-tuning stays at 4 epochs and learning rate 5e-4. It is not retuned. The MLP still returns its best source-validation checkpoint. Both context models return their final update. That asymmetry is disclosed. `mlp_final_secondary` records the last MLP epoch and is not used as the primary baseline.

No task-separation loss, Reptile, ensemble, GRU training, architecture search, or meta-controller. The trunk is not enlarged.

## The comparison

**A. Fixed length.** Empty context with probability 0.2, otherwise 128 support transitions. This is the previous training rule.

**B. Variable length.** Empty context with probability 0.2, otherwise a length drawn uniformly from {16, 32, 64, 128}.

A and B share initial weights, the sampled task, the support/query episode split, and the query minibatch. Length uses a separate random stream. B's support is a prefix of the same eligible support history A uses. Support-example counts are reported separately. Total compute is not claimed to match.

Three paired training seeds. The previous development artifact is not overwritten.

## Prediction

Diagnostic query episodes are separate from source training data, source validation, target prefixes, and control-evaluation episodes. The same query rows are scored for every model and context condition.

Source physics and the existing development physics are both scored. Confirmation physics are not.

Budgets 0, 16, 32, 64, and 128. Conditions: real context, zero context, wrong-task context, frozen multitask MLP, fine-tuned multitask MLP.

Donor rule, fixed before any diagnostic return:

- On source task `i`, the prediction donor is source task `(i + 1) mod 8`, using that task's diagnostic support prefix.
- On every development task, the prediction donor is source task 0 `(g=8, m=1, l=1)`, using its diagnostic support prefix.
- Control-evaluation wrong-task context stays the original rule: the first rows of source-training task 0 for that seed.

Metrics: held-out one-step MAE and RMSE, including per-dimension errors; open-loop error at horizons 3, 8, and 16 on recorded actions inside one episode; real-minus-zero and real-minus-wrong prediction gaps; encoder gradient norms and parameter change; context-vector distances. Distances alone are not evidence of task identification. Context stays fixed during each rollout.

## Control

Same development tasks and shared target prefixes. Budgets 0, 16, 32, 64, 128. Three seeds. Three evaluation episodes. Paired environment and planner seeds.

Primary diagnostic metric: trapezoidal return AUC from 0 to 128, divided by 128. This window exists because both context conditions use at most 128 transitions. It is not the original 0–256 metric.

Report raw curves, per-task and per-seed values, variable-minus-fixed AUC, each condition minus its own budget-zero return, and real-minus-zero and real-minus-wrong. Intervals across three training seeds are exploratory. Episodes are not training replicates.

## How a pattern becomes the next experiment

If several patterns are present, the earliest one is the single recommendation:

1. Real context fails held-out source prediction: representation, optimization, or amount of training.
2. Real context helps source prediction but not development physics: task-distribution generalization.
3. Variable-length training helps budgets 16 and 32: the support-length mismatch contributed.
4. Context improves held-out prediction and worsens control: rollout error and planner sensitivity.
5. Zero-context return stays more than 50 points below the frozen MLP: a later trunk-capacity experiment.

## Confirmation

The confirmation entry point rejects a run unless the development artifact is complete, non-smoke, passing, hash-matched, and tied to a clean implementation revision. Later commits that touch only documents or artifacts can preserve that revision. Source-tree changes cannot. This diagnosis does not unlock confirmation.

## Results

Not run yet.
