# Next NEXUS experiment (minimal, falsifiable)

Not AGI. Do not retune MAE 0.97. Do not start finance, NAS, Reptile, MAML, a meta-controller, or the unused context-confirmation tasks.

## Closed on measured runs

Pendulum H=16 planning beat random on its confirmation physics (`docs/NEXUS_PLANNING_GENERALITY.md`). MAE-gated adaptation did not (`docs/NEXUS_PENDULUM_TRANSFER.md`). Reptile lost to matched-data multitask in that configuration (`docs/NEXUS_META_LEARNING_PILOT.md`). That Reptile result is not a general disproof.

The context-adaptation development screen failed (`docs/NEXUS_CONTEXT_ADAPTATION_PILOT.md`). Real-context primary AUC **−755** versus fine-tune **−454**, versus zero context **−652**, versus wrong-task context **−725**. Confirmation physics hash `87b83c41be34aa1a` was not evaluated. Leave those four tuples unused.

## Why the next run is not confirmation

The (48, 48) context trunk (4332 parameters) was already far behind the (64, 64) MLP (4868 parameters) at budget zero. Real and wrong-task vectors were close (`‖z_real − z_wrong‖` about 0.10–0.72). Using the prefix made control worse than a constant zero context. A longer confirmation would spend the fresh tasks on a model that has not shown a context benefit.

## Diagnosis that replaced the trunk-widening plan

The development diagnosis (`docs/NEXUS_CONTEXT_ADAPTATION_DIAGNOSIS.md`) kept the (48, 48) trunk. Fixed-length real context did not beat zero context on held-out source MAE (0.0703 vs 0.0700 at budget 128) and raised development MAE from 0.0774 to about 0.084, mostly in angular velocity. Open-loop horizon-16 error moved the same way. Variable-length training had a positive short-budget point estimate and a seed-level AUC interval that includes 0. Zero-context control stayed about 146 points below the frozen MLP. The final-epoch MLP matched the selected checkpoint, so that asymmetry is not the gap.

## Optimization diagnostic

More updates improved the shared dynamics and did not make real context useful (`docs/NEXUS_CONTEXT_OPTIMIZATION_DIAGNOSTIC.md`). At 3000 updates the source audit still had real angular-velocity MAE **0.1264** versus zero **0.1256** and wrong **0.1234**. The 5% screen failed. Do not continue to 10,000 updates.

## The one next experiment

**Train only the encoder and FiLM on a frozen 3000-update trunk.**

Question: with the dynamics trunk held at the 3000-update weights, can encoder and FiLM updates make real context beat zero and wrong context on held-out source angular-velocity error?

Freeze before any new returns:

- Start from the saved 3000-update context checkpoints. Freeze the trunk. Train the encoder and FiLM only, with the same loss, Adam learning rate, fixed support policy, and source data.
- Use a fresh source-audit split, disjoint from the optimization audit. Do not reuse that audit as the success set.
- Donor remains source task `(i+1) mod 8`.
- Same 5% screen: real angular-velocity MAE at least 5% below zero and wrong, positive in at least two of three seeds, and overall MAE and horizon-16 error no more than 5% worse than zero context.
- No MPC, no wider trunk, no extra joint-training updates, and no confirmation physics.

If the screen fails, mean-pooled FiLM context is not a useful dynamics code under this loss. Stop there.
