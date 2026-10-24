# Unfamiliar sub-clause skill work-reduction protocol

Isolated branch `cursor/seed-unfamiliar-skill-work-reduction` from
`f2e8942`. Protocol committed before scoring. Do not edit `f2e8942` or
artifact
`6f7437ede1a0b5f582a0b1e71bdf83881fa2067011b0ee902740c20512f532ff`.
Opened prior grids stay closed. Track B stays closed. Not confirmation.
Not AGI. Do not merge `main`.

Whole-mechanism caching scores 0 hits on genuinely unfamiliar Wave-2
compositions. This study extracts verified branch guards and leaf
transforms from Wave-1 discoveries and uses them to prune `hyp_evals`.

## Frozen policy

`source_learned_adaptive_policy` from `f2e8942` stays the probe
chooser. Holdout `env_interactions` must remain 21 and `policy_evals`
246. Memory may change only hypothesis evaluation after the first
observation.

## SubMechanismLibrary and costs

Wave-1 distillation (`distill_cost`): each verified source acquisition
is decomposed into a `(branch_condition_signature, sub_transform)`
clause. Structure walk, guard extract, leaf extract and store are
metered.

Wave-2 retrieval (`retrieval_evals`): after the frozen policy’s
diagnostic probes, match the observed remaining family against the
library. Exact whole-mechanism hits must be 0. Restrict later
`hyp_evals` to the residual unknown component.

```
total_acquisition_work = env_interactions + hyp_evals + policy_evals
                       + distill_cost + retrieval_evals
```

## Four equalized rows (seeds 0, 1, 2)

1. `untrained_default_policy` — no memory
2. `source_distilled_fixed_order` — no memory
3. `source_learned_adaptive_policy` — memory cleared (`f2e8942`: 699
   total work, 0 retrieval hits)
4. `adaptive_policy_plus_compositional_subskills` — frozen policy plus
   Wave-1 sub-mechanism library

## Gates

1. All four methods 12/12 holdout and 6/6 reserved retest.
2. Wave-2 whole-mechanism hits = 0 and sub-skill hits > 0 on every
   seed.
3. Condition 4 `total_acquisition_work` (including `distill_cost` and
   `retrieval_evals`) is strictly below condition 3 (`< 699` overall
   and below that seed’s 233), condition 2, and condition 1 on every
   seed.

## Resources

Standing local-CPU grant. Symbolic only. 0 model calls. Frozen
research-CPU ledger debit **0**. Cap 120 s. Do not edit
`local_model_runtime.py`.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_unfamiliar_skill_work.py -q
PYTHONPATH=src:.deps python3 scripts/run_unfamiliar_skill_work_reduction.py artifacts/seed_unfamiliar_skill_work_reduction
PYTHONPATH=src:.deps python3 scripts/verify_unfamiliar_skill_work_reduction.py artifacts/seed_unfamiliar_skill_work_reduction/seed_unfamiliar_skill_work_reduction.json
```
