# NEXUS V0.8.2 — Belief states and gated adaptation

Status: **measured**. Not AGI. V0.8.1 remains the finding that residual fine-tuning can cut MAE without helping noisy-observation control. This increment tests filters, a small GRU estimator, and commit/rollback.

Branch: `cursor/v082-belief-adaptation`. Parent: `21c2925`. Artifact: `artifacts/v082_belief.json` (n=**10**, wall **323 s**). Prior JSON preserved.

## Accounting (Phase 1)

`InteractionLedger` splits **pretrain**, **target_used** (detect+adapt collect, cap-enforced), and **eval_only**. Exceeding the target cap raises `BudgetExceededError`. All confirmation rows in this run have `within_cap=true`. Mean pretrain **1280**/seed. Eval episodes are not charged to the target budget.

## Belief estimators (Phases 2–3)

No estimator reads simulator latent state. Kalman is **independent scalar A=I, H=I, Q=1e-4, R=0.01** (random-walk; not CartPole linearization). EMA α=0.6. Stack k=3. GRU hidden 16 trained to predict next obs; planning uses a residual MLP on the 4-D GRU output (GRU is not unrolled in imagination).

Development returns (H=3, noise 0.10, unused physics, n=10):

| Belief | Return [t 95%] |
| --- | --- |
| Kalman | **243 [189, 297]** |
| Identity | **224 [192, 256]** |
| EMA | 186 [160, 211] |
| Stack | 55 [36, 73] |
| GRU | 20 [11, 28] |

Kalman vs identity CIs overlap. Stack and GRU **fail as controllers**. Selection (dev return, not confirm): identity 4 seeds, Kalman 5, EMA 1.

## Gated loop (Phases 4–5)

Loop: plan on belief → collect under the target cap → window detector → optional fine-tune on episode-disjoint train → commit if val MAE drops ≥3%, else rollback. Compared with always and never fine-tune.

Noisy confirmation (new physics + **obs_noise=0.10**, eval seed **106000**), identity (n=10):

| Budget | never | gated | always |
| --- | --- | --- | --- |
| 0 / 64 | **284 [257, 311]** | 276 [251, 301] | 262 [235, 289] |
| 128 | **284 [257, 311]** | 270 [238, 302] | 282 [253, 311] |
| 256 | 284 | 271 | 290 [242, 338] |

Paired 128 vs identity|never: always **−1.9 [−33, +29]**; gated **−13.8 [−46, +18]** (both include 0). Detector fired on **all** noisy collect streams. Gated still **committed 85%** of identity@128 cases (MAE improved) without raising return — the gate is prediction-based and **does not protect control**.

Kalman (n=5 selected seeds) never **263 [183, 343]** vs always@128 **285 [135, 435]**; paired vs identity never includes 0.

## Clean confirmation (transfer vs estimation)

Identity on clean unused physics is **500** at every policy (ceiling again). Kalman on the same clean task **281 [213, 348]** — filtering **hurts** when observations are already clean. Belief is not a free lunch.

## Memory A→B→C→A (Phase 6)

Gated shared **236 [175, 297]** vs snapshot **284 [221, 347]** vs retrieve **268 [206, 329]**. Snapshot remains the better A controller. Memory **≈104 kB**/seed.

## Criteria

1. **More useful internal state:** not established. Kalman is statistically tied with raw obs on noisy dev; GRU/stack are worse.
2. **Better decisions, not just MAE:** **no**. Gated MAE commits do not beat never-adapt returns.
3. **Detect and adapt:** window detector fires on noisy targets; adaptation is automatic under the cap.
4. **Reject harmful updates:** **partial/failed**. Rollback exists, but a 3% val-MAE rule still commits updates that do not help (and can hurt) return.
5. **Retrieve prior knowledge:** snapshot ≥ retrieved ≥ gated shared; not in-network retention.

Not AGI. Next: a **return-based** (or on-policy failure) commit rule, or a filter whose imagination is consistent with the estimator.
