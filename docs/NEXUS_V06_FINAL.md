# NEXUS V0.6 — Final report (continual learning and knowledge transfer)

Status: **V0.6 research track complete.** Branch `cursor/v066-transfer-finalization`. Not merged. Not AGI. V0.7 world models are **not** implemented here.

This document answers the transfer, retention, and adaptation hypotheses with the evidence that was actually trained and measured. A statistically positive result was not required for completion.

Primary artifacts: `artifacts/v06_continual.json` … `artifacts/v066_transfer.json`. Physics: V0.6–V0.6.3 used `cartpole_setattr_only` (invalid for gravity/length/mass edits under Gymnasium 1.4). V0.6.4+ uses `cartpole_derived_v1`. Do not pool those eras.

Replication unit (V0.6.4+): **source-training seed**, Student-t intervals. Confirmation eval seeds are reserved (`74000` / `75000` / `76000`). Selectors never see those returns.

---

## 1. Demonstrated capabilities

- A working PPO actor–critic, network factory, checkpoints (weights, optimizer, observation RMS), and a bounded research loop on CartPole-family tasks.
- **Observation-normalization transfer:** copying source running mean/variance into a **randomly initialized** policy, then training on the target, reliably raises 1 024–2 048-step target return versus a fresh RMS (V0.6.5 B−A **+128 [73, 184]**; V0.6.6 B−A **+222 [173, 272]** on a new confirmation suite).
- Frozen vs updating copied RMS is interchangeable on V0.6.6 (Δ **+2.1 [−3.8, +7.9]**).
- Probe-and-continue can **resume the winner’s checkpoint** instead of restarting (V0.6.6).
- A LinUCB strategy selector can be fit on **development VAL** with a real RMS-shift feature and an explicit **rms_only** arm. On held-out source seeds it selected `rms_only` in **18/18** confirmation cells. That is arm preference after batched fit, not a proof that LinUCB beats the fixed RMS-only policy.
- Independent evaluation seeds, frozen confirmation generators, and strict JSON artifacts (`allow_nan=False`).

## 2. Failed hypotheses

- **Learned encoder transfer.** Copying pretrained encoder weights does not help, and given the same RMS it **hurts** (V0.6.5 D−B **−110 [−181, −39]**; V0.6.6 D−B **−223 [−294, −152]**). Frozen-encoder transfer is worse still.
- **Full-policy transfer as the default reuse mechanism.** Full copy + source RMS (E) loses to random net + source RMS (B) on V0.6.5 and V0.6.6.
- **V0.6.4 “encoder +300 vs scratch” as representation transfer.** Causal ablations attribute that gain to **shared RMS** (and a longer target budget), not to encoder features.
- **Learned selector beats a frozen RMS-only rule.** V0.6.6 learned − B **−57 [−138, +23]** (includes 0) on held-out seeds. V0.6.4/5 selectors tied or copied conservative LR when `rms_only` was absent.
- **In-network continual retention.** Naive, replay, EWC, and multi-head sequential training at these budgets do not produce forgetting CIs that exclude 0, nor ACC above a weak CartPole regime. Corrected EWC and task-aware replay did not rescue the sequence.
- **Solved, stable CartPole sources at the V0.6 pretrain cap.** 32 768 steps, 10 epochs, n=10: **0/10** val-solved, independent **154.7 [75, 234]**. Lower LR 1e-4 at 16 384 steps: **0/3** solved, failure rate **1.0**. Failures were kept; the cap was not lifted.

## 3. Inconclusive results

- Heuristic vs learned vs probe rankings: wide intervals on n=6 held-out seeds; several paired CIs include 0.
- Disabling observation normalization (H) vs fresh RMS (A): **−14 [−32, +3]** includes 0 at 1 024 steps.
- Forward transfer in sequential CL vs untrained: point estimates positive for RMS-aware sequences, but forgetting variance is huge.
- Whether a **solved** source policy would yield encoder transfer. That experiment was not run; unlimited CPU search for a solved source was forbidden.

## 4. Improvements caused by normalization rather than learned representations

Copying **source `obs_rms`** into a random network (B) is the only consistently positive transfer treatment.

Target-calibrated RMS from 128 unlabeled target observations (F) gives a **small** gain vs A (**+17 [3, 32]**), much smaller than B. Pooled RMS from other source-family envs (G) **fails** relative to B. Therefore the benefit is not “any scaling” and not “any CartPole-like distribution.” It is specifically the **source policy’s running statistics**, which also stabilize optimization of a randomly initialized actor–critic on a shifted physics variant.

Encoder weights independently add nothing once RMS is controlled.

## 5. Evidence of genuine neural weight transfer

**None that survives the RMS control.**

Positive V0.6.2/V0.6.4 encoder-vs-scratch deltas were **confounded** (legacy physics and/or copied RMS). V0.6.5–V0.6.6 2×2 ablations are the relevant evidence: pretrained encoder ≤ random encoder when RMS is matched, and often strictly worse.

## 6. Evidence of retention beyond saving independent models

**None demonstrated.**

Keeping the source checkpoint and evaluating it (snapshot retrieval) preserves source-task return by **not modifying those weights**. Sequential adapters share one network and forget or wander within noise. Replay’s extra **122 880** bytes and EWC Fisher snapshots are additional memory; they did not produce a CI-backed retention win. Multi-head is a form of **task-indexed parameters**, i.e. partitioned weights, not a single shared skill store.

Treat “memory” in V0.6 as **RECALL of stored checkpoints and RMS stats**, not as a proven continual representation.

## 7. Remaining limitations (relevant to V0.7)

- Domain is a 4-D CartPole physics family. No image, POMDP, or long-horizon prediction task.
- Sources are **unsolved and unstable**. Planning on top of a value function trained this way is not justified.
- Transfer that works is **input whitening**, not a world model or a skill embedding.
- Selector “learning” is batched LinUCB on a handful of development cells, not a validated online meta-controller.
- Continual sequences are short (three tasks, 1 024 steps). Compute was deliberately bounded.
- No predictive model of next observation or reward exists in this branch. **PREDICT / PLAN are V0.7**, only after this report.

## Completion recommendation

**Close V0.6.** Do not add V0.6.7 because encoder transfer and in-network retention failed. The hypotheses have defensible answers.

V0.6 supplies **RECALL** (checkpoints, RMS, snapshots), **LEARN** (PPO on-task), and **VERIFY** (held-out seeds, reserved eval, causal ablations).

Next, if pursued: **V0.7 world models** for PREDICT and PLAN, on tasks where a learned dynamics model can be scored against independent rollouts — not by resurrecting encoder-transfer claims from V0.6.4.

Long-term loop: OBSERVE → RECALL → PREDICT → PLAN → ACT → LEARN → VERIFY → STORE.
