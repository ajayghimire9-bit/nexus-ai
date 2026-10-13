# Next NEXUS experiment (minimal, falsifiable)

Not AGI. Do not retune MAE 0.97. Do not start finance, NAS, Reptile, MAML, or a meta-controller.

## Closed on measured runs

Pendulum H=16 planning beat random on its confirmation physics (`docs/NEXUS_PLANNING_GENERALITY.md`). MAE-gated adaptation did not (`docs/NEXUS_PENDULUM_TRANSFER.md`). Reptile lost to matched-data multitask in that configuration (`docs/NEXUS_META_LEARNING_PILOT.md`). That Reptile result is not a general disproof.

The context-adaptation development screen failed (`docs/NEXUS_CONTEXT_ADAPTATION_PILOT.md`). Real-context primary AUC **−755** versus fine-tune **−454**, versus zero context **−652**, versus wrong-task context **−725**. Confirmation physics hash `87b83c41be34aa1a` was not evaluated. Leave those four tuples unused.

## Why the next run is not confirmation

The (48, 48) context trunk (4332 parameters) was already far behind the (64, 64) MLP (4868 parameters) at budget zero. Real and wrong-task vectors were close (`‖z_real − z_wrong‖` about 0.10–0.72). Using the prefix made control worse than a constant zero context. A longer confirmation would spend the fresh tasks on a model that has not shown a context benefit.

## The one next experiment

**Matched-trunk source-separation check. Development tasks only.**

Question: with the same residual trunk as the multitask MLP, does context from the true source task reduce held-out one-step error relative to a wrong source task, and is budget-zero control within a predeclared gap of the frozen MLP?

Freeze before any new returns:

- Trunk **(64, 64)**, same residual MLP as the frozen baseline. FiLM stays the only added path. Context dimension 8. Max history 128.
- Same eight source physics and three development physics as the context pilot. Do not construct environments from `pendulum_context_confirmation`.
- Query next-state loss, plus one source-only term that increases distance between contexts of different source tasks (InfoNCE or a pairwise distance penalty). No physics parameters and no task IDs at inference.
- Same source transition budget as the failed pilot (400 per task) unless a smaller smoke is labeled incomplete.

Stop rules, in order:

1. **Budget-zero gap.** On the three development tasks, mean return of the zero-context model minus the frozen MLP is greater than **−50** (zero context is not more than 50 return points worse). If this fails, stop. The trunk still does not match, so an adaptation curve is not interpretable.
2. **Separation.** On the disjoint source validation split, mean distance between true-task and wrong-task contexts exceeds the distance between two disjoint histories of the same task, and one-step MAE with the true context is lower than MAE with the wrong context. If this fails, stop. Do not run MPC learning curves.
3. Only if both pass: repeat the development control curves (frozen MLP, fine-tune, real context, zero context, wrong-task context) on the three development tasks. Still do not open confirmation in that run. A confirmation protocol would be a later pre-register.

Success for this experiment is only (1) and (2). Control curves are a follow-on, not a way to rescue a failed separation check.

Out of scope: GRU training, Reptile, ensembles, architecture search, changing the confirmation tuples, and retuning MAE 0.97.
