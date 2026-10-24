# Unfamiliar sub-clause skill work-reduction protocol

Isolated branch `cursor/seed-unfamiliar-skill-work-reduction` from
`f2e8942` on `cursor/seed-unfamiliar-policy-replication`. Protocol
committed before scoring. Do not edit `f2e8942` or artifact
`6f7437ede1a0b5f582a0b1e71bdf83881fa2067011b0ee902740c20512f532ff`.
Opened prior grids stay closed. Track B stays closed. Not confirmation.
Not AGI. Do not merge `main`.

Auditor revision #1: memory does not need the fixed synthesizer to
fail. Matching accuracy while reducing total acquisition cost is
useful transfer. Continual Wave-2 whole-mechanism hits were 0 because
retrieval stored identical mechanisms, not reusable verified
guard/transform sub-clauses.

## Frozen policy

`source_learned_adaptive_policy` from `f2e8942` stays the probe
chooser. `env_interactions` must remain 21 and `policy_evals` 246 on
the 12 holdout cells. Skill memory may change only hypothesis
evaluation after the first observation.

## SubMechanismLibrary

Populated only from verified Wave-1 / source acquisitions. Each
verified episode indexes:

- an exact whole-mechanism cache key (OrdinaryExactCache)
- a sub-clause keyed by the first-probe exclusive-or signature
  `(informative_ACT_2, informative_ACT_NEG)` → pos or neg
  guard/leaf

Wave-2 holdout mechanisms are new pairings of those sub-clauses, so
whole-mechanism hits must be 0. After the frozen policy’s first
probe, lookup the sub-clause and restrict later `hyp_evals` to
signature-compatible candidates.

`total_acquisition_work = env_interactions + hyp_evals + policy_evals
+ retrieval_evals`. Every library lookup and structural match is a
`retrieval_eval`.

## Four equalized rows (seeds 0, 1, 2)

1. `untrained_policy_no_memory` — f2e8942 untrained checklist
2. `source_distilled_fixed_no_memory` — f2e8942 static source order
3. `learned_adaptive_policy_memory_cleared` — f2e8942 policy-only
   (21 env, 432 hyp, 246 policy = 699)
4. `learned_adaptive_policy_plus_subskill_memory` — same policy plus
   Wave-1 sub-clause retrieval

## Gates

1. All four methods 12/12 holdout and 6/6 reserved retest.
2. Wave-2 whole-mechanism hits = 0 and sub-clause hits > 0 on every
   seed.
3. Memory `total_acquisition_work` < cleared policy-only on every
   seed, after charging `retrieval_evals`.

## Resources

Standing local-CPU grant. Symbolic only. 0 model calls. Frozen
research-CPU ledger debit **0**. Cap 120 s. Do not edit
`local_model_runtime.py`.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_unfamiliar_skill_work.py -q
PYTHONPATH=src:.deps python3 scripts/run_unfamiliar_skill_work_reduction.py artifacts/seed_unfamiliar_skill_work_reduction
PYTHONPATH=src:.deps python3 scripts/verify_unfamiliar_skill_work_reduction.py artifacts/seed_unfamiliar_skill_work_reduction/seed_unfamiliar_skill_work_reduction.json
```
