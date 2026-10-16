# Action-conditioned first-action Q — fail-closed resume protocol v1

Base `36a9753ba1afcf49b50802bfe0fd7d85625629c0` (`cursor/action-conditioned-first-action-q`). Branch `cursor/action-conditioned-q-resume`. This protocol does **not** replace or edit `docs/NEXUS_ACTION_CONDITIONED_Q_PROTOCOL.md`, `configs/action_conditioned_q.yaml`, `artifacts/action_conditioned_q.json`, or `artifacts/action_conditioned_q_fit.json`. The incomplete capture remains the scientific record until a complete 60-cell artifact independently validates.

World models, encoders, the frozen 78-coefficient sequence-value readout, H=16, 16 candidates, family `action_obs`, ridge λ=0.1, source labels, and both frozen Q fits stay unchanged. The 59 saved evaluation cells are not used to retune features, ridge, seeds or the screen.

## Question

The authorized 240 s run saved 59/60 evaluation cells. Completing that locked grid by generating only the missing cell, if and only if that cell is independently determined by the original seeds and frozen fits, yields the same scientific object as a successful original run.

**H-resume-valid:** decoder 9, development task 2, zero visitor can be collected from the locked reset/collection/candidate/future seeds and frozen models/fits, the 59 saved cells reconstruct from raw traces, and the assembled 60-cell artifact is identical in identity to the original grid except for that one added cell.

**H-resume-invalid:** any fingerprint, replay, seed, Q-fit, or metric reconstruction failure. Then this resume is rejected and a **fresh full run** is required. Do not patch, interpolate or retune.

## Locked missing cell

Exactly one cell is admissible:

- decoder **9**
- development task **2** (`pendulum_context_development()[2]`)
- visitor index **1** = **zero**
- reset seed `reset_seed(cfg, 9, 2)` (shared with the saved student visitor; collection seeds are visitor-independent by the original protocol)
- candidate seed `candidate_seed(cfg, 9, 2, 1)`
- future seeds `future_seeds(cfg, 9, 2, 1)`
- models: frozen decoder 9, student contexts for scoring, zero visitor for live collection and common-zero continuation
- Q: frozen `artifacts/action_conditioned_q_fit.json` decoder 9, not refit

The original runner counted 50 collection steps for this cell before the timeout, but did not save traces. Those unsaved buffers are discarded. Resume recollects them from the locked seeds. That is recapture of a defined cell, not reuse of a partial trajectory.

## Fail-closed assembly

1. Parent SHA256 of `artifacts/action_conditioned_q.json` must remain `6f80696ca7cb94d0789ef950c90cf34aa425aab20b4fc9d776c4397201322680`.
2. Parent SHA256 of `artifacts/action_conditioned_q_fit.json` must remain `2da13f24f102f84474c466d6b214a4be51672e609881e69cf3054144e35771ae`.
3. Ten Q readouts must rebuild from the 160 source cells with family `action_obs` and λ=0.1; additive rebuilds must match as well.
4. All 59 saved cells must have complete live actions/rewards/seeds, three 64-step first-action traces, fingerprints, and metrics that rebuild from those traces. Frozen 59-cell digest: `6e8bff7dd117ab396811165d690d6c9f7a45d5959b4b1dd3db8aedaaca423e5a`.
5. Resume writes **new** paths only: `artifacts/action_conditioned_q_resume_cell.json` and `artifacts/action_conditioned_q_completed.json`. It refuses to exist if those files already exist. It never writes the original OUTPUT/FIT.
6. Assembly copies the 59 frozen cells and appends exactly the missing cell. Replacement, deletion, reordering-as-identity-change, or extra cells is a failure.
7. Original `validate()` is not applied to the incomplete parent (it correctly requires 60 cells and matching 240 s counts). Completed-artifact validation is a full 60-cell reconstruction plus resume accounting. The original 240 s wall and incomplete counts stay on the parent file.
8. No scientific label is assigned until the assembled file passes full-grid validation **and** an independent raw-trace arithmetic audit. Incomplete resume remains `incomplete`.
9. Development outcomes from the 59 cells are not inspected for hyperparameter choice. The original screen is unchanged: complete grid, mean gain_vs_h16 ≥ 1 and lower bound > 0 for `action_conditioned_gain`.

If Gym/CPU replay of the missing cell fails fingerprint, live replay, seed or metric reconstruction, abort. Recommend a fresh full 240 s / 45,240 / 11,612,160 run. Do not splice.

## Budget and authority

Hard cap **60 seconds**, **242** new real steps (50 collection + 192 first-action), **64,512** imagined transitions for that one evaluation cell. Estimate 15–25 CPU seconds including frozen-model load. Local CPU only. No new support. No source labels. No Q refit.

The original one-run remaining is 0. The exhausted 3,600-second standing session file is unmodified (SHA `c14f16e667d1e52d3ebddff1412498f5db75832c25a74b0579bc8bcf98750462`) and is not this budget. Collection is unauthorized until a new explicit human approval binds this resume configuration hash with remaining ≥ 60 s. The committed allocation has `authorized: false` and `runs: 0`.

## Tests and execution

Tests must lock parent hashes, missing-cell identity, visitor-independent collection seeds, visitor-dependent candidate/future seeds, Q-fit rebuild, 59-cell raw reconstruction, refuse-wrong-cell assembly, refuse-mutated-59-cell assembly, unauthorized collection, and preservation of the original protocol hashes. They must not collect the missing cell.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_action_conditioned_q_resume.py tests/test_action_conditioned_q_resume_feasibility.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_action_conditioned_q_resume.py --feasibility
PYTHONPATH=src:.deps python3 scripts/run_action_conditioned_q_resume.py
# Collection is blocked until a fresh approved allocation is committed:
PYTHONPATH=src:.deps python3 scripts/run_action_conditioned_q_resume.py --execute
PYTHONPATH=src:.deps python3 scripts/run_action_conditioned_q_resume.py --audit
```

architecture_change_authorized: false
authorized: false
runs: 0
n_weights: 16
family: action_obs
ridge: 0.1
missing: decoder 9 / task 2 / state 1 / visitor zero
time_cap_s: 60
env_cap: 242
model_cap: 64512
