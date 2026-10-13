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

Implementation revision `5c636093a8fe25edb6005d2e504ee60015ad1064`. Source tree was clean. A later commit keeps the final-epoch MLP weights off the training log so they are not written into JSON; it does not change this run. Artifact `artifacts/context_adaptation_diagnosis.json`. Plots `artifacts/context_adaptation_diagnosis_prediction.svg` and `artifacts/context_adaptation_diagnosis_control.svg`. Wall clock **520.9 s**. Declared run complete. Confirmation evaluated: **no**.

Three training seeds, three development tasks, three evaluation episodes. Intervals below are exploratory Student-t intervals across seeds (2 degrees of freedom). Episodes are not training replicates. The metric is the 0–128 AUC, not the original 0–256 result.

### Training

Both context models used 300 updates and 19,200 query examples. Fixed-length support examples were 30,720 / 31,104 / 31,360. Variable-length support examples were 15,152 / 15,280 / 14,752. The same query schedule was used. Compute is not matched.

Encoder L2 change was about **1.50–1.57** (fixed) and **1.44–1.49** (variable). Mean encoder gradient norms were about **0.013–0.017**. Parameters: context model **4332**, multitask MLP **4868**.

The final-epoch MLP, scored only as a secondary check, matched the best-validation MLP at budget zero on every development task (returns agreed to about 0.1). Checkpoint selection is not what makes the MLP baseline stronger in this run.

### Held-out prediction

One-step MAE, mean over tasks and seeds.

Source physics, fixed-length model:

| Budget | Real | Zero | Wrong | MLP frozen | MLP fine-tune |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 0.0700 | 0.0700 | 0.0700 | 0.0484 | 0.0484 |
| 16 | 0.0704 | 0.0700 | 0.0705 | 0.0484 | 0.0414 |
| 128 | 0.0703 | 0.0700 | 0.0702 | 0.0484 | 0.0317 |

Real context does not beat zero or wrong-task context on source data for the original fixed-length trainer. The gap is small, and both sit well above the MLP. Fine-tuning lowers source MAE from 0.0484 to 0.0317 at 128 transitions.

The variable-length model is slightly different on source data: zero MAE **0.0693**, real **0.0682**, wrong **0.0679** at budget 128. Real beats that model's own zero context by a small margin and does not beat wrong-task context.

Development physics, fixed-length model: zero MAE **0.0774**; real and wrong rise to about **0.084**. Variable-length real is about **0.0825**, still worse than zero. Fine-tuning lowers development MAE from 0.0646 to **0.0336** at budget 128.

The error is concentrated in angular velocity. At development budget 128, fixed real context has per-dimension MAE about **0.027 / 0.038 / 0.187**, versus zero context **0.041 / 0.047 / 0.144**. Context slightly reduces the angle error and increases the velocity error. Fine-tuning reduces that velocity term to about **0.063**.

Open-loop error agrees. On development physics at budget 64, fixed real-context MAE at horizons 3, 8, and 16 is **0.267 / 0.541 / 0.821**, versus zero context **0.204 / 0.474 / 0.513**. Real and wrong-task rollouts are close. Mean `‖z_real − z_wrong‖` is about **0.25** on source tasks and **0.17** on development tasks, while `‖z‖` is about **2.7**. That distance is not evidence that the vector identifies the task.

### Control

Mean 0–128 AUC:

| Method | Mean | Exploratory 95% interval |
| --- | ---: | --- |
| MLP frozen | −490.0 | [−533.3, −446.6] |
| MLP fine-tune | −505.7 | [−708.3, −303.1] |
| Fixed, real context | −647.0 | [−1004.9, −289.1] |
| Fixed, zero context | −635.7 | [−835.2, −436.1] |
| Fixed, wrong context | −637.7 | [−998.0, −277.5] |
| Variable, real context | −624.6 | [−1007.2, −242.0] |
| Variable, zero context | −633.9 | [−866.4, −401.4] |
| Variable, wrong context | −624.3 | [−973.4, −275.2] |

Seed-level contrasts, all with intervals that include 0:

- Variable real minus fixed real: **+22.4 [−65.4, +110.3]**
- Fixed real minus fixed zero: **−11.4 [−246.5, +223.8]**
- Fixed real minus fixed wrong: **−9.3 [−100.9, +82.4]**
- Variable real minus its own zero: **+9.3 [−170.3, +188.9]**
- Variable real minus wrong: **−0.3 [−49.3, +48.7]**

Relative to each method's own budget-zero return, fixed real context is **11** points worse, variable real context is **9** points better, and fine-tuning is **16** points worse on this 0–128 window. The short-budget (16 and 32) point estimate favors variable length by about **22** return points. That estimate pools tasks and seeds; the seed-level AUC interval still includes 0. H-length is not established.

Individual tasks disagree. On seed 2, development task `(g=10, m=1, l=1.55)`, fixed real context reaches AUC **−414** against its zero-context **−640**. On seed 0, `(g=6, m=1, l=1)`, fixed real context falls from **−407** at budget zero to an AUC of **−623**. The average is not a uniform failure mode.

### What the patterns say

Real context fails held-out source prediction for the fixed-length trainer, including a higher development rollout error. It does not help source prediction and then fail only on new physics. Variable length has a positive short-history point estimate and a small source-MAE improvement, without a seed-level control interval that excludes 0. Zero-context control remains about **146** points worse than the frozen MLP at budget zero, so trunk capacity is still unresolved. Because prediction does not improve, this run does not isolate a planner-only failure.

The predeclared priority therefore selects representation or optimization, not a wider trunk and not a new control sweep. The coexisting length and capacity patterns stay on the record.

### Resources

Source training interactions **9,600**. Source validation **768**. Diagnostic support **1,408**. Diagnostic query **4,400**. Target prefixes **9,216**. Executed evaluation interactions **129,600**. Imagined model states **33,177,600**. Cached evaluations were not added again. Training walls: MLP **0.63 s**, fixed context **0.48 s**, variable context **0.46 s**. Almost all of the 521 s is planning.

### Next experiment

Keep the (48, 48) trunk and the fixed-length schedule. Train longer, or with a learning rate chosen for the small encoder gradients, and stop on held-out source one-step error by state dimension. Require real context to beat both zero and wrong-task context on source angular velocity before any new control curve, trunk change, or confirmation run.
