# Next NEXUS experiment (minimal, falsifiable)

Not AGI. Do not retune MAE 0.97. Do not start finance, NAS, Reptile, MAML, or a meta-controller. The direct-latent confirmation protocol is closed; do not retune its learning rate or update count.

## Closed on measured runs

Pendulum H=16 planning beat random on its confirmation physics (`docs/NEXUS_PLANNING_GENERALITY.md`). MAE-gated adaptation did not (`docs/NEXUS_PENDULUM_TRANSFER.md`). Reptile lost to matched-data multitask in that configuration (`docs/NEXUS_META_LEARNING_PILOT.md`). That Reptile result is not a general disproof.

The context-adaptation development screen failed (`docs/NEXUS_CONTEXT_ADAPTATION_PILOT.md`). Real-context primary AUC **−755** versus fine-tune **−454**, versus zero context **−652**, versus wrong-task context **−725**. Confirmation physics hash `87b83c41be34aa1a` was not evaluated in that pilot.

## Why earlier runs stayed off confirmation

The (48, 48) context trunk (4332 parameters) was already far behind the (64, 64) MLP (4868 parameters) at budget zero. Real and wrong-task encoder vectors were close (`‖z_real − z_wrong‖` about 0.10–0.72). Using the prefix made control worse than a constant zero context. Those encoder runs did not earn a confirmation. The direct-latent source screen is a different result and is what the next experiment tests.

## Diagnosis that replaced the trunk-widening plan

The development diagnosis (`docs/NEXUS_CONTEXT_ADAPTATION_DIAGNOSIS.md`) kept the (48, 48) trunk. Fixed-length real context did not beat zero context on held-out source MAE (0.0703 vs 0.0700 at budget 128) and raised development MAE from 0.0774 to about 0.084, mostly in angular velocity. Open-loop horizon-16 error moved the same way. Variable-length training had a positive short-budget point estimate and a seed-level AUC interval that includes 0. Zero-context control stayed about 146 points below the frozen MLP. The final-epoch MLP matched the selected checkpoint, so that asymmetry is not the gap.

## Optimization diagnostic

More updates improved the shared dynamics and did not make real context useful (`docs/NEXUS_CONTEXT_OPTIMIZATION_DIAGNOSTIC.md`). At 3000 updates the source audit still had real angular-velocity MAE **0.1264** versus zero **0.1256** and wrong **0.1234**. The 5% screen failed. Do not continue to 10,000 updates.

## Frozen-dynamics diagnostic

Freezing that 3000-update trunk and training the encoder and FiLM did not make real context useful (`docs/NEXUS_FROZEN_DYNAMICS_CONTEXT.md`). On a fresh source audit, selected real-context angular velocity was **0.1484** versus zero **0.1159**, wrong **0.1207**, and a trained constant vector **0.1127**. The screen failed. The paired constant-minus-MLP difference on that same artifact is **−0.00228 [−0.0137, +0.0092]** and includes 0. Overlap of the two separate intervals is not that test. Do not add more encoder updates.

## Direct latent diagnostic

Optimizing `z` alone, with the history decoder frozen, passed the source screen (`docs/NEXUS_DIRECT_LATENT_CONTEXT.md`). The locked rule is Adam learning rate **0.1** for **256** updates from the global vector. Fresh-audit angular velocity was **0.0628** versus zero **0.1151**, global **0.1109**, and wrong-support **0.1762**. Paired intervals exclude 0. The frozen encoder on the same 128 rows stayed worse than zero context (**0.1256**). Cos and sin paired differences versus the global vector include 0.

## Direct latent confirmation

The locked rule passed on the reserved physics (`docs/NEXUS_DIRECT_LATENT_CONFIRMATION.md`). Confirmation angular velocity was **0.152** versus zero **0.308**, global **0.314**, and wrong-support **0.398**. Paired intervals exclude 0. The frozen encoder on the same support rows stayed at **0.307**, level with zero context. Low-mass task c2 remained the high-error case at **0.335**.

## The one next experiment

The protocol for this question is locked in `docs/NEXUS_AMORTIZED_LATENT_INFERENCE.md`. The development artifact is not in the implementation commit.

**Ask whether a history encoder can be trained to predict the support-optimized latent, and whether that predicted latent keeps the query gain.**

Keep the decoder frozen. On each training task, fit the teacher latent with the locked rule (Adam **0.1**, **256** updates from the global vector, support only). Train a small encoder so its inferred `z` matches that teacher. The success metric is held-out query angular-velocity MAE against zero context, the global vector, and the teacher latent itself. Matching the teacher on support is not success if the query error does not move. Do not retune the teacher rule from the student scores. Do not run control. A student that fails to beat zero leaves the useful step as test-time optimization, not amortized inference.
