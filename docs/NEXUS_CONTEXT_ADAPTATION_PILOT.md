# Context-adaptation pilot

Branch `cursor/context-adaptation-pilot`. Starting SHA `a9c184c85c2a22317098d0c3637812386f4207e6`. Protocol: `docs/NEXUS_CONTEXT_ADAPTATION_PROTOCOL.md`. Development artifact `artifacts/context_adaptation_dev.json`. Plot `artifacts/context_adaptation_dev.svg`.

Not AGI. Not autonomous online learning. Not continual learning. An offline target-prefix comparison. Confirmation physics were **not** evaluated.

## Hypothesis

H1: a world model with context inferred from observed transitions has higher low-budget control-return AUC on unseen Pendulum physics than multitask fine-tuning, and real context beats constant and wrong-task context.

Null: the context model fails to beat the strong baseline or its context controls.

**Development gate: failed.** Confirmation was not run. The locked confirmation test of H1 is **inconclusive**. The development point estimates go against H1. Success was not redefined after seeing the curves.

## What was tested

FiLM context, dimension 8, encoder hidden 32, residual trunk (48, 48). `z` is the mean encoder of normalized state, action one-hot, and normalized next-state change. Maximum history 128. Empty context during training with probability 0.2. Normalization fit on source-training observations only.

GRU was excluded. The old Reptile result stays a negative result for that configuration, not a general disproof.

Methods: frozen multitask MLP, ordinary fine-tune (lr 5e-4, no target validation), real context, zero context, wrong-task context from source task 0, and a development-only random encoder. Fine-tune epochs were chosen on development task 0, budget 64, one episode, among {2, 4}. Four epochs won (−146.8 vs −147.6) and were used for the development grid.

Source data: 400 transitions × 8 tasks (3200 env steps) plus 256 disjoint validation steps. 300 optimizer updates and 19200 query examples for both the MLP and the context model. Support encoding processed about 30720–31104 extra examples. That extra compute is disclosed. It is not a matched-FLOP claim.

Budgets 0, 16, 32, 64, 128, 256, 512, 1024. Primary metric: trapezoidal return AUC on 0–256, divided by 256. Two model seeds, two evaluation episodes. Planner H=16, 16 candidates, torques {−2, 0, +2}.

Split hashes: train `c61358588a9da3b5`, development `e3d6d6dd1a08cf4f`, confirmation `87b83c41be34aa1a` (hash only).

## Development results

Wall clock **312.7 s**. Run complete (`incomplete: false`). All returns finite. Encoder L2 change **1.50** and **1.54** (mean **1.52**). Mean encoder gradient norm about **0.013–0.016**. Random-encoder L2 change **0**.

Parameter counts: MLP **4868** (19524 bytes), context model **4332** (17328 bytes). These are not equal capacity. The context trunk is (48, 48); the MLP is (64, 64).

Primary AUC, mean across the three development tasks, then across two seeds (return units). The n=2 Student-t intervals have 1 degree of freedom and are **not** the gate.

| Method | Mean primary AUC |
| --- | ---: |
| Multitask MLP, frozen | −470.5 |
| Multitask MLP, fine-tune | −453.6 |
| Context, real target prefix | −755.3 |
| Context, zero | −651.9 |
| Context, wrong source task | −725.3 |
| Context, random encoder | −723.8 |

Gate contrasts (means of seed-level task averages):

| Contrast | Mean |
| --- | ---: |
| Real − fine-tune | −301.7 |
| Real − zero context | −103.5 |
| Real − wrong-task context | −30.0 |
| Real − frozen MLP | −284.8 |
| Real − random encoder | −31.6 |

The gate required all of real−zero, real−wrong, and real−fine-tune to be positive. All three are negative.

Budget zero is already a large gap. Frozen MLP and fine-tune start near **−470**. Zero context starts at **−652**, which is also its whole curve, because zero context does not depend on the prefix. Real context’s primary AUC (**−755**) is worse than its own budget-zero return. The deficit is not only a weaker starting model. Conditioning on the target prefix made average control worse.

On the near-source development task `(g=6, m=1, l=1)`, the frozen MLP holds about **−73**. Real context moves from about **−403 / −518** at budget 0 to about **−800 / −628** once the prefix is used. Wrong-task context moves the same direction.

Context vectors are not well separated. `‖z_real − z_wrong‖` on the three development tasks was about **0.10 to 0.72**, while `‖z‖` itself was about **2.2 to 2.8**. In-prefix one-step MAE at budget 256 was about **0.05–0.11** for real context and about **0.016–0.030** for the fine-tuned MLP. That MAE is diagnostic and in-sample.

Returns for every context method are identical from budget 128 through 1024 because the encoder keeps at most 128 transitions. Fine-tuning still uses the longer prefixes. The primary window therefore gives fine-tuning extra data between 128 and 256. The curves are already worse for real context at budgets 16 and 32, so the cap does not explain the gate failure.

Evaluation used 400 environment steps per method, task, and budget (two episodes of length 200). Imagined model states at a non-cached evaluation were 102400. Frozen MLP and zero context were cached across budgets. Source training walls were under 1 s per seed. The 313 s are almost all planning.

## Diagnosis

The encoder’s weights moved, and different prefixes change `z`. That is not enough. On these development tasks:

1. The smaller trunk is a weaker planner at budget zero than the multitask MLP, especially on the easy `(g=6)` task.
2. Real context and wrong-task context stay close, and using either one tends to hurt control relative to a constant zero context.
3. In-prefix prediction error stays higher than the fine-tuned MLP.
4. A frozen random encoder was not worse on average than the learned encoder (primary AUC −724 vs −755). Learned context is not showing a control benefit over random features in this run.

No leakage check failed. No NaNs. The negative result is about usefulness, not a crashed run.

## What was not done

Confirmation (10 seeds, 5 episodes, four fresh physics tuples) was not started. Those tuples remain unused as evidence. Do not retune this architecture against them.

## Next experiment

See `docs/NEXUS_NEXT_EXPERIMENT.md`. One development-only follow-up: match the MLP trunk, require budget-zero control to be close to that MLP, and require true-task context to beat wrong-task context on held-out source prediction before any new control curve or confirmation run.
