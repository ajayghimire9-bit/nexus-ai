# NEXUS V0.6.5 — Causal transfer (encoder vs normalization)

Branch `cursor/v065-causal-transfer`. Not merged. Measured 2026-10-11, CPU.

`pytest` **105 passed**. `artifacts/v064_adaptation.json` and earlier V0.6 JSON files were not overwritten. Artifacts use **strict JSON** (`allow_nan=False`; empty CIs are `null`).

Reproduce: `PYTHONPATH=src:.deps python3 scripts/run_v065_benchmarks.py`

Not AGI. Corrected CartPole physics (`cartpole_derived_v1`). Replication unit = **source-training seed** (n=10, Student-t df=9).

## Reliability

- Empty statistical groups serialize as `null`, not NaN.
- Adaptation halt restores a **saved checkpoint** (weights, optimizer, RMS, PPO cursor) and **stops**. It does not claim bitwise-exact env rollback. A missing checkpoint **raises** rather than continuing.

## Causal ablations (2 048 matched target steps, confirm seed 75000)

New frozen confirmation tasks `cartpole_v065_{0,1,2}`. V0.6.4 confirmations are development only.

| Ablation | encoder | obs RMS | mean [t 95%] |
| --- | --- | --- | --- |
| A scratch | random | fresh | 99.1 [63.8, 134.4] |
| **B random + source RMS** | random | **source** | **227.5 [168.8, 286.3]** |
| C pretrained encoder | copied | fresh | 80.0 [44.0, 116.0] |
| D pretrained encoder + source RMS (V0.6.4 recipe) | copied | source | 117.8 [84.3, 151.3] |
| E full policy + source RMS | full copy | source | 188.0 [109.2, 266.8] |
| F frozen encoder + source RMS | copied, frozen | source | 67.7 [52.8, 82.6] |

Paired seed-level:

- **B − A (normalization only):** **+128.4 [73.3, 183.6]** — CI excludes 0.
- **D − B (encoder weights given source RMS):** **−109.7 [−180.6, −38.8]** — pretrained encoder **hurts**.
- **C − A (encoder without source RMS):** **−19.1 [−66.3, +28.1]** — includes 0.

**Do not call the V0.6.4 +300 result representation transfer.** On these confirmation tasks, copying **observation normalization** accounts for the gain; copying encoder weights does not independently help and is worse than a random encoder with the same RMS.

Val-best source vs 8 192-step source for recipe D: **+74.4 [40.7, 108.1]**. Later checkpoints help D, but D still loses to B.

## Source competence

Same 10-seed, 32 768-step, 10-epoch recipe as V0.6.4. Independent **154.7 [75.0, 234.3]**. **0/10** val-solved. Total pretrain **327 680** steps. Failed seeds kept.

## Selectors (val only; never seed 75000)

LinUCB fit on V0.6.4 confirmation tasks using **val** returns (3 source seeds × 5 arms). Confirmation freeze.

| Method | mean [t 95%] | notes |
| --- | --- | --- |
| heuristic (V0.6.4 risk-aware) | 231.8 [148.8, 314.7] | 27× conservative, 3× reuse |
| learned LinUCB | 209.1 [147.2, 271.0] | **30× conservative** |
| val probe (256+256, rest on winner) | 171.8 [126.5, 217.0] | 30× conservative; probe steps counted |

Learned − heuristic: **−22.7 [−74.0, +28.6]** (includes 0). Learned − B: **−18.4 [−120, +83]** (includes 0). The selector never chose the winning ablation B (that arm was not in `{reuse, conservative, encoder-FT, frozen, scratch}`).

## Continual sequence

Naive sequential fine-tune on v065_0 then v065_1: first-task return **163** after its phase, **106** after the second phase (mean over 10 seeds). Immutable source snapshot on the first target **145**. Keeping a **separate copy** is not in-network retention.

## Success criteria

1. **Failed.** Encoder weights do not improve target learning beyond normalization-only (B) and random-init (A) controls. They are credibly worse than B.
2. **Failed.** LinUCB copies conservative LR and does not beat B or the heuristic with a CI excluding 0.
3. **Failed.** Sequential adaptation degrades the first task; snapshot copies are extra memory, not a retained policy head.
4. **Partial / weak.** Heuristic and LinUCB avoided encoder-FT (which is harmful vs B) but never selected source-RMS + random encoder, and probe paid extra steps for a worse final return than B.

Likely cause of the V0.6.4 encoder win: **shared RMS + longer 8 192 budget**, not a transferable latent. Next test: freeze RMS as an explicit adaptation action, or disable `normalize_obs` so weight transfer cannot smuggle statistics.

Wall clock **151 s**.
