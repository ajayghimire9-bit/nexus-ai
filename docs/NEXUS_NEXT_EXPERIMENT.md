# Next NEXUS experiment (minimal, falsifiable)

Not AGI. Do not retune MAE 0.97. Do not start finance, NAS, Reptile, MAML, a meta-controller, or the unused context-confirmation tasks.

## Closed on measured runs

Pendulum H=16 planning beat random on its confirmation physics (`docs/NEXUS_PLANNING_GENERALITY.md`). MAE-gated adaptation did not (`docs/NEXUS_PENDULUM_TRANSFER.md`). Reptile lost to matched-data multitask in that configuration (`docs/NEXUS_META_LEARNING_PILOT.md`). That Reptile result is not a general disproof.

The context-adaptation development screen failed (`docs/NEXUS_CONTEXT_ADAPTATION_PILOT.md`). Real-context primary AUC **−755** versus fine-tune **−454**, versus zero context **−652**, versus wrong-task context **−725**. Confirmation physics hash `87b83c41be34aa1a` was not evaluated. Leave those four tuples unused.

## Why the next run is not confirmation

The (48, 48) context trunk (4332 parameters) was already far behind the (64, 64) MLP (4868 parameters) at budget zero. Real and wrong-task vectors were close (`‖z_real − z_wrong‖` about 0.10–0.72). Using the prefix made control worse than a constant zero context. A longer confirmation would spend the fresh tasks on a model that has not shown a context benefit.

## Diagnosis that replaced the trunk-widening plan

The development diagnosis (`docs/NEXUS_CONTEXT_ADAPTATION_DIAGNOSIS.md`) kept the (48, 48) trunk. Fixed-length real context did not beat zero context on held-out source MAE (0.0703 vs 0.0700 at budget 128) and raised development MAE from 0.0774 to about 0.084, mostly in angular velocity. Open-loop horizon-16 error moved the same way. Variable-length training had a positive short-budget point estimate and a seed-level AUC interval that includes 0. Zero-context control stayed about 146 points below the frozen MLP. The final-epoch MLP matched the selected checkpoint, so that asymmetry is not the gap.

## The one next experiment

**Longer fixed-length training, scored on source prediction only.**

Question: with the same FiLM encoder and (48, 48) trunk, do more optimizer updates make real context beat zero context and wrong-task context on held-out source one-step error, including angular velocity?

Freeze before any new returns:

- Same source physics, source-only normalization, context dimension 8, encoder width 32, trunk (48, 48), and the fixed-length schedule (20% empty, otherwise 128).
- Do not switch to variable length in the same run. That hint stays separate.
- Do not add a separation loss, widen the trunk, or run MPC.
- Do not construct environments from `pendulum_context_confirmation`.
- Hold out source episodes that are not the training set and not the checkpoint-selection set. Donor for task `i` remains source task `(i+1) mod 8`.

Stop rule: if real-context source MAE, and the angular-velocity component, are not lower than both zero and wrong-task context, stop. The context vector is still not a useful dynamics code. A later trunk-capacity run is allowed only after that prediction gap exists. Control curves and confirmation stay closed until then.

Out of scope: GRU training, Reptile, ensembles, architecture search, changing the confirmation tuples, and retuning MAE 0.97.
