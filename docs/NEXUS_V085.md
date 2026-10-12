# NEXUS V0.8.5 — Candidate Quality and Verification

Branch `cursor/v085-candidate-quality-verification`. Parent `4158b4f` (V0.8.4). Artifact `artifacts/v085_verification.json`. Prior artifacts were not overwritten.

This is **not** AGI, not a trading system, and not a claim of general intelligence.

Two questions, answered separately:

- **H1** — Does the current adaptation recipe produce candidates that improve control?
- **H2** — Can a limited-budget verifier tell beneficial candidates from harmful or ineffective ones?

V0.8.4 could not separate these: H=32 MPC scores were 32 vs 32, so “no accepts” was uninformative.

## Frozen protocol

- Same residual (64, 64) + H=3 MPC as V0.7. Identity belief. No new architecture, no new env family.
- Candidate bank: two predetermined recipes (`c128` / `c256` collect + 64 independent val episodes, 8-epoch finetune). Every generated pair is kept. Every verifier sees the **same** pairs. Generation cost is shared, not a verifier difference.
- Independent val uses disjoint reset seeds. If val is missing, checkpoint is **last epoch**; train loss is not labeled as val.
- Reference eval: 2 matched full episodes, horizon **500**, margin **10**, `eval_only`. Never passed into `GateInput`.
- Verifiers: never, always, MAE (32 charged steps), `control_h32` (V0.8.4), `control_h128`.
- Development (`dev_v085`) selects the verifier by `accepted_benefit − accepted_harm`, then cheaper. Confirmation physics and `V085_CONFIRM_REF_SEED=123000` unused until after freeze.
- n=10 source-training seeds. Planned runtime 10–25 min CPU; actual **89.5 s**.

V0.8.4 runners keep `adapt_method(..., allow_overlap_val=True)` (default). The silent train-as-val path remains for historical code; V0.8.5 sets `allow_overlap_val=False` and passes `independent_val`.

## Commands and provenance

```bash
PYTHONPATH=src:.deps python3 -m pytest tests -q
PYTHONPATH=src:.deps python3 scripts/run_v085_benchmarks.py
```

- Python 3.13.5, PyTorch 2.14.1, NumPy 2.5.4, Gymnasium 1.4.0
- Artifact git field: parent `4158b4f`, dirty working tree at run time (this V0.8.5 source), protocol_hash `86e0c72679ecc71a`
- Replication unit: source-training seed (Student-t 95%). Pairs within a seed are clustered.

## H1 — candidate quality (confirmation, n=10)

60 pairs (2 recipes × 3 tasks × 10 seeds), including clean ceiling controls.

| Split | n | Benefit | Harm | Inconclusive | Ref ceiling both | Per-seed mean Δ return |
| --- | --- | --- | --- | --- | --- | --- |
| All confirm | 60 | 23 | 16 | 21 | 0.32 | +41.9 [−7.3, +91.1] |
| Noisy only | 40 | 23 | 15 | 2 | **0.00** | +41.9 [−7.3, +91.1] |

Clean pairs sit at the 500 ceiling and account for the inconclusive/ceiling mass. On **noisy** tasks, long-horizon reference is not saturated.

**Measured:** adaptation produces both better and worse controllers. 23/40 noisy pairs meet the pre-registered benefit margin; 15/40 meet harm. The seed-level mean difference **includes 0**, so we do **not** claim a systematic average gain.

`control_h32` on the same noisy pairs: **40/40** scores `(32, 32)` / `tie_or_small_diff`. That reproduces V0.8.4 and is a verifier limitation, not evidence of no candidate effect.

## H2 — verifier quality (confirmation)

Development selected **MAE** (`max_tp_minus_fp_then_cheaper`). Dev H=32 and H=128 were 100% ceiling, so they could not win.

| Verifier | Accept | Inconcl. | Ceiling both | Acc. benefit | Acc. harm | Rej. benefit | Choice vs never (per-seed) | Harm status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| never | 0/60 | 0 | 0 | 0 | 0 | 23 | 0 | no_acceptance (N/A) |
| always | 60/60 | 0 | 0 | 23 | 16 | 0 | +41.9 [−7.3, +91.1] | inconclusive_audits (21 unresolved) |
| **mae (selected)** | 48/60 | 0 | 0 | 22 | 6 | 1 | **+50.5 [8.7, 92.2]** | inconclusive_audits (20 unresolved); 6/48 harmful |
| control_h32 | 0/60 | 1.00 | 1.00 | 0 | 0 | 23 | 0 | no_acceptance |
| control_h128 | 3/60 | 0.92 | 0.92 | 2 | 0 | 21 | +3.0 [−1.7, +7.7] | 3 accepts, 1 unresolved |

MAE val cost: 64 env steps/pair (32 charged transitions used for both models’ MAE). H=32: 64 steps. H=128: ~255 steps. Always/never: 0. Shared generation: mean **256** collect steps/pair + pretrain **1280**.

**Measured:** H=32 cannot observe differences (ceiling). H=128 still saturates on most pairs (35/40 noisy ties; 3 accepts, 2 of them reference-benefit, 2 `control_worse`). MAE rejects 10 of 16 harmful all-confirm (6 remain) and misses 1 of 23 benefits. Its **decision value vs never** on confirmation has a 95% interval that **excludes 0**. Always-accept does not (same mean as raw H1, interval through 0).

Rejection-only (`never`, `control_h32`) is not counted as verifier success.

## Costs and limits

- Wall **89.5 s** local CPU (under the planned cap).
- Reference eval is expensive in env steps (H=500 × 2 × 2 models) but `eval_only`.
- H=128 still mostly ceiling; do not assume a modest horizon bump fixes control gates.
- MAE harm is not zero. 20 accepted pairs have inconclusive long-horizon labels (mostly clean 500 vs 500).
- This is one CartPole family, frozen small MLP, n=10 seeds.

## Does V0.8.5 support useful adaptation / verification?

- **H1 mixed, not a mean gain claim.** Candidates can help and can hurt. Long-horizon reference can see that; H=32 cannot.
- **H2: selected MAE has confirmatory decision value vs never** on this bank (CI excludes 0). Control-return gates at 32 and 128 do not. MAE is not a harm-free filter.

Not AGI. Not V0.9. Not a new environment family.

## Next step

Keep CartPole. **Reduce the harmful-candidate rate** of the same finetune recipe (more independent val, replay, or fewer aggressive updates) while freezing the MAE gate that already has decision value. Do not jump to a second family until the seed-level mean candidate delta is credibly positive **or** conditional harm is low enough to report without 6/48 harmful accepts. Do not lengthen control-H as the main bet: H=128 still tied 35/40 noisy pairs.
