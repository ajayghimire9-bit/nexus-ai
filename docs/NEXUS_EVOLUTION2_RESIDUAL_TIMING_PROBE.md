# Evolution-2 residual-MLP timing probe

Status: **BOUNDED INFERENCE PROBE — NO ENV COLLECTION**.
Parent: `1898d0c16349dd2a9aef9a01559a01926a67aab8`.
Does **not** rewrite v2 or v2-pilot, name a holdout, train, or unlock H17.

This probe times existing frozen residual MLPs on random observation
batches. It is not a transfer result and not a v2 pass.

## 1. Question

At residual-MLP inference cost on the listed frozen files, do the
locked v2 (110,592,000 imagined) and v2-pilot (49,152,000 imagined)
worksheets fit inside 900 s of planning, or does the historical
5.529 µs/state extrapolation still apply?

## 2. Allowed work

- Read and hash-verify the three listed checkpoints.
- Load them for CPU inference only.
- Score catalogue-faithful successor H=16 decisions through
  `evolution2.planner_adapter.decide` on **random** observations.
- Cap: **60 s**, **0** real env steps, **200,000** imagined states.
- Debit wall time from the standing session ledger after the run.

## 3. Forbidden work

- No Gymnasium construction, no `make_task_env`, no new dataset.
- No checkpoint write, retrain, or hash rewrite.
- No named unused instance.
- No v2/v2-pilot collection and no H17 unlock.

## 4. Checkpoints

| ID | Family | Path | Role |
|---|---|---|---|
| pendulum_frozen_decoder | Pendulum | `artifacts/frozen_dynamics_checkpoints/seed0_history_u1000.pt` | Frozen history decoder in the 120-file audit |
| pendulum_residual_mlp | Pendulum | `artifacts/context_optimization_checkpoints/seed0_mlp_u1000.pt` | Residual 64×64 MLP in the 120-file audit |
| acrobot_lookahead_seed0 | Acrobot | `checkpoints/acrobot_lookahead_h16/seed0.pt` | Existing Acrobot H=16 residual |

Missing or mismatched files fail closed. Random observations are not
environment resets. A measured rate here is **not** interchangeable
with the 68.146 s / 12,324,000 live Pendulum lookahead, but it is
the residual-MLP number we can obtain without new env steps.

## 5. Outcomes

`probe_complete`, `incomplete_budget`, `invalid_integrity`,
`checkpoints_missing`. A complete measurement does not authorize
v2 collection.

## 6. One next scientific action

After this probe, say honestly whether v2-pilot planning still looks
like `incomplete_budget` under 900 s. Do not collect on unnamed
physics either way.
