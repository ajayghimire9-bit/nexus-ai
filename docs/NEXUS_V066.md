# NEXUS V0.6.6 — Transfer finalization

Branch `cursor/v066-transfer-finalization`. Not merged. Measured 2026-10-11, CPU.

Parent commit `e73e071`. `pytest` **110 passed**. Prior artifacts `v06`–`v065` were not overwritten.

Reproduce: `PYTHONPATH=src:.deps python3 scripts/run_v066_benchmarks.py`

Not AGI. Not V0.7. Corrected CartPole physics (`cartpole_derived_v1`). Replication unit = **source-training seed**. Confirmation eval seed **76000**. Selector fit uses VAL **71000** only.

LinUCB fitting is **batched development outcomes**, not online bandit feedback on confirmation.

## Probe-and-continue (V0.6.5 fix)

Competing candidates train for the same probe budget. Weights, optimizer, and observation RMS are checkpointed. The winner is chosen on VAL and **resumed from that checkpoint**. Confirmation returns are not used for selection. Accounted steps = all candidate probes + remaining winner steps.

Artifact field `restarted_from_scratch_after_probe` is **false** on every confirmation cell.

## Normalization as a transfer mechanism (1 024 matched target steps)

Frozen confirmation tasks `cartpole_v066_{0,1,2}`. V0.6.5 confirmations are development only. n=10 source seeds. Student-t 95%.

| Method | network | obs RMS | extra obs | mean [t 95%] |
| --- | --- | --- | --- | --- |
| A | random | fresh, updating | 0 | 89.8 [79.9, 99.7] |
| **B** | random | **source, updating** | 0 | **312.2 [262.8, 361.6]** |
| C | pretrained encoder | fresh, updating | 0 | 112.6 [61.9, 163.3] |
| D | pretrained encoder | source, updating | 0 | 89.0 [45.3, 132.8] |
| E | full policy | source, updating | 0 | 151.5 [123.9, 179.0] |
| F | random | target-calibrated 128 steps, then updating | 128 | 107.2 [84.5, 129.9] |
| G | random | pooled source-family RMS | 126 | 82.5 [71.9, 93.0] |
| H | random | **disabled** | 0 | 75.4 [63.2, 87.6] |
| B frozen | random | source, **frozen** | 0 | 314.2 [262.9, 365.6] |

Paired seed-level:

- **B − A (source RMS, random net):** **+222.4 [173.0, 271.7]** — CI excludes 0.
- **D − B (encoder given source RMS):** **−223.1 [−294.0, −152.3]** — pretrained encoder hurts.
- **F − A (target-calibrated RMS):** **+17.4 [2.8, 32.0]** — small, CI excludes 0.
- **G − B (pooled family RMS vs source RMS):** **−229.7 [−279.7, −179.8]**.
- **B frozen − B:** **+2.1 [−3.8, +7.9]** — freeze vs update is inconclusive.
- **H − A (no normalization):** **−14.4 [−31.8, +2.9]** — includes 0 at this budget.

**Interpretation:** the transferable object is **source observation scaling**, not a learned encoder. Target-only calibration (F) helps a little, far less than copying the source running statistics. Shared family RMS (G) does not substitute for the actual source policy’s RMS. Freezing vs updating source RMS is interchangeable here. Disabling normalization is not a large additional penalty relative to a fresh running RMS at 1 024 steps.

Measured RMS mean-shift on confirmation (64 target observations) is **nonzero** (mean 0.13, range 0.03–0.28). The V0.6.5 zero placeholder is gone.

## Selectors (held-out source seeds 4–9 only)

Fit seeds `{0,1,2,3}`: every LinUCB arm is trained on development VAL. Test seeds never enter `bandit.update`.

| Method | n seeds | mean [t 95%] | notes |
| --- | --- | --- | --- |
| fixed RMS-only (B, same test seeds) | 6 | 319.3 [245.3, 393.2] | random net + source RMS |
| learned LinUCB | 6 | 261.9 [235.3, 288.5] | **18/18 rms_only** |
| probe-and-continue | 6 | 243.0 [208.1, 278.0] | 17× rms_only, 1× conservative; resumed |
| heuristic (risk-aware; encoder remapped to rms_only) | 6 | 217.6 [66.4, 368.8] | 15× conservative, 3× reuse |
| random arm | 6 | 184.5 [92.9, 276.1] | |
| full-policy (E, test seeds) | 6 | 157.6 [112.2, 203.0] | |

Paired on held-out seeds:

- learned − B: **−57.3 [−137.9, +23.2]** (includes 0). Learned always selected RMS-only but used a **different random initialization** (`seed+43` vs `seed+41`) than the B table, so it is not the same run.
- probe − B: **−76.2 [−157.3, +4.8]** (includes 0).
- learned − heuristic: **+44.3 [−122.5, +211.1]** (includes 0).

The selector **did** add the RMS-only arm and, after batched VAL fit, always chose it on confirmation. That is not evidence that LinUCB beats a fixed RMS-only policy. Fixed B remains the strongest point estimate.

## Continual sequence (development tasks A→B→C, 1 024 steps/task, test seeds n=6)

| Method | ACC [t 95%] | mean forgetting | BWT |
| --- | --- | --- | --- |
| naive | 80.0 [57.9, 102.0] | 12.7 [−42.4, 67.8] | −12.7 |
| task-aware replay | 76.4 [55.4, 97.5] | −5.7 [−14.0, 2.6] | +5.7 |
| EWC | 80.6 [57.0, 104.2] | 11.7 [−41.6, 64.9] | −11.7 |
| multi-head | 78.8 [65.2, 92.4] | −7.7 [−31.6, 16.3] | +7.7 |
| RMS-aware naive | 274.9 [122.1, 427.7] | 67.8 [−149, 285] | −67.8 |
| snapshot retrieval | 173.6 [39.3, 307.9] | n/a | n/a |

Replay buffer bytes recorded: **122 880**. Continual trainer parameter count **1 315** (the lighter V0.6 `make_trainer` factory, not the 4 675-parameter source PPO). Optimizer state is one Adam copy per live trainer; snapshot retrieval stores **additional independent checkpoints**.

Replay / EWC / multi-head forgetting CIs **include 0**. They do not demonstrate in-network retention beyond noise at this budget. RMS-aware sequential fine-tune has high ACC because source RMS is copied before the sequence (same mechanism as B), not because weights remember prior tasks. Snapshot retrieval is a **separate model**, not internal memory.

## Source-policy reliability

Same 32 768-step, 10-epoch recipe: independent **154.7 [75.0, 234.3]**. **0/10** val-solved. Total pretrain **327 680** steps. Failures kept.

Stabilization probe: lr **1e-4**, cap **16 384**, seeds `{0,1,2}`. Independent mean **92.0 [−33.1, 217.1]**. **0/3** val-solved. **Failure rate 1.0**. The cap was not extended.

## Success criteria

1. **Demonstrated.** Source observation RMS is a causal, repeatable transfer mechanism on this CartPole family (B vs A; freeze vs update interchangeable).
2. **Failed.** Encoder / full-policy weight copy does not add target return given RMS (D and E lose to B).
3. **Failed / weak.** Learned LinUCB and probe-and-continue do not beat fixed RMS-only with a CI excluding 0. They do prefer the RMS-only arm after batched VAL fit.
4. **Failed.** Continual methods do not show reliable in-network retention. Snapshots are extra memory.
5. **Failed.** Lower LR at a 16k cap does not produce a solved source policy.

Wall clock **117 s**.
