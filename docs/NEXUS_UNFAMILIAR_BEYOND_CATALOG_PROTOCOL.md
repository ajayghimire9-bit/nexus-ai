# Unfamiliar beyond-catalog acquisition protocol

Isolated branch `cursor/seed-unfamiliar-beyond-catalog` from `6e0df3a`.
Protocol committed before scoring. Do not edit `f2e8942`, `6e0df3a`, or
their artifacts. Opened prior grids stay closed. Track B stays closed.
Not confirmation. Not AGI. Do not merge `main`.

In `f2e8942` and `6e0df3a` the target was always inside `supplied_bank`.
This study holds out mechanisms with **0%** bank coverage.

## Suite

Source training reuses `up_source` and the frozen adaptive policy recipe.
Holdout (per seed): 3 Type A partial-structure unknowns + 1 Type B
novel-structure unknown. Reserved: 2 in-bank retention checks.

- Type A: known Wave-1 guard (pos or neg) plus a novel leaf absent from
  the bank (`oob_pos_plus3`, `oob_pos_mul3`, `oob_neg_add1`).
- Type B: guard/leaf pair absent from `SubMechanismLibrary`
  (`oob_even_add2`).

## Mechanisms

1. `detect_catalog_exhaustion` — after diagnostic probes, if
   `surviving_bank_candidates == 0`, set `catalog_exhausted`. Never
   return an eliminated bank candidate.
2. `synthesize_beyond_bank` — on exhaustion, query stored guards
   (`retrieval_evals`). If a guard has a residual that fits the trace,
   freeze it and enumerate only that residual (`residual_synthesis_evals`).
   Type B misses and falls back to the open primitive grammar.
3. `verify_synthesized_unknown` — any out-of-bank synthesis must pass at
   least one confirmatory probe on a fresh unused input. If no survivor
   or more than one observational class remains, `abstained_unknown`
   (`0` false positives).

```
total_acquisition_work = env_interactions + confirmatory_env_probes
                       + bank_hyp_evals + policy_evals + distill_cost
                       + retrieval_evals + residual_synthesis_evals
```

## Four equalized rows (seeds 0, 1, 2)

1. `supplied_bank_only` — frozen adaptive policy, bank only; abstain on
   exhaustion (`0/12` holdout claims, `0` false positives).
2. `untrained_open_grammar` — checklist probes + open grammar; no
   library.
3. `learned_policy_open_grammar_cleared` — frozen adaptive probes + open
   grammar; library cleared (`0` sub-skill hits).
4. `nexus_abductive_beyond_bank` — frozen adaptive probes + Wave-1
   library + residual grammar + stream registration of new sub-skills.

## Gates

1. Bank-only detects `12/12` out-of-bank unknowns with `0` false
   positives. Conditions 2–4 solve `12/12` holdout (confirmatory +
   held-out inputs) and `6/6` reserved.
2. Condition 3 total work `<` condition 2 on every seed.
3. Condition 4 total work `<` condition 3 on every seed after charging
   distill, retrieval, confirmatory, and residual synthesis. Type B
   misses the library without a false hit or crash.

## Resources

Standing local-CPU grant. Symbolic only. 0 model calls. Frozen
research-CPU ledger debit **0**. Cap 120 s. Do not edit
`local_model_runtime.py`.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_unfamiliar_beyond_catalog.py -q
PYTHONPATH=src:.deps python3 scripts/run_unfamiliar_beyond_catalog.py artifacts/seed_unfamiliar_beyond_catalog
PYTHONPATH=src:.deps python3 scripts/verify_unfamiliar_beyond_catalog.py artifacts/seed_unfamiliar_beyond_catalog/seed_unfamiliar_beyond_catalog.json
```
