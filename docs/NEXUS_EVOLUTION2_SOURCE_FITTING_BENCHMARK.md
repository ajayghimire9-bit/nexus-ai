# Evolution-2.3 — source-fitting feasibility and trusted cache

Branch `cursor/evolution2.3-source-fitting` from `869a9e56be8405aa62aa3b5f04c66dc4879da1e9`.
Not a scientific result. Zero new environment steps. Ledger not debited.
The frozen H16 scientific ledger remains **305.842 / 3294.158**.

## 1. Source-data and checkpoint provenance

Lookahead recipes (`configs/acrobot_lookahead.yaml`,
`nexus.world.train.train_world_model`) fit residual 64×64 MLPs for 20
epochs on 1024/256 in-memory transitions, then write only `.pt` weights.

Searched permitted stored arrays (`*.npz` / `*.npy` under artifacts,
data, datasets, runs, checkpoints). Closed confirmation / H14–H17 /
holdout names are excluded. **Found: none.**

Verified read-only checkpoints (hashes from the residual timing probe;
files are not rewritten):

| id | family | path | identity |
|---|---|---|---|
| pendulum_frozen_decoder | pendulum | `artifacts/frozen_dynamics_checkpoints/seed0_history_u1000.pt` | hash-locked |
| pendulum_residual_mlp | pendulum | `artifacts/context_optimization_checkpoints/seed0_mlp_u1000.pt` | hash-locked |
| acrobot_lookahead_seed0 | acrobot | `checkpoints/acrobot_lookahead_h16/seed0.pt` | hash-locked |

Those files are weights, not training transitions.

## 2. Fitting cost

**`SOURCE_FITTING_UNAVAILABLE`.** No disposable residual-MLP fit was
run. Replacement collection is forbidden. Ten-bundle × two-family
expected fitting time is therefore `None`, not an invented number.

## 3. Trusted cache integrity

`RevealCache.reveal(method, variant, score)` let callers supply scores.
It is replaced by `TrustedEvaluator`: the evaluator owns
`produce_score`, cache identity, physical vs cached counts, logical
charges, per-method training feedback, and a separate hidden
development store. Adversarial source-only tests cover score
substitution, duplicate charging, unused-variant revelation, hidden
development leakage, and cross-family / cross-bundle contamination.

**Verdict: PASS.**

## 4. Feasibility

Conservative planning (measured residual-MLP inference, 1.25 × max of
measured and historical rates):

| screen | real steps | imagined upper bound | planning | fitting | verdict |
|---|---|---|---|---|---|
| full v2 | 97,600 | 110,592,000 | ~764 s | unavailable | **NO-GO** |
| v2-pilot | 57,600 | 49,152,000 | ~340 s | unavailable | **UNKNOWN** |

Neither estimate is scientific evidence. Session remainder is unused
by this audit.

## 5. Remaining blockers

`SOURCE_FITTING_UNAVAILABLE`, unnamed holdout, twelve-arm dispatch
blocked, full v2 NO-GO, v2-pilot UNKNOWN, scientific dispatch
unauthorized, H17 blocked.

## 6. Next action

Do not collect replacements and do not enable dispatch. The next
allowed step is a separately authorized persist of source-only
train/val arrays for a disposable residual-MLP fit clock, or a smaller
worksheet that does not require twenty unmeasured fits.
