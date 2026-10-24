# Wave-4 diagnostic and ablation protocol

Isolated branch `cursor/seed-wave4-diagnostic-ablations` from
`c8bc5ad`. Protocol committed before scoring. Do not edit `c8bc5ad`,
`0d4596e`, `6e0df3a`, or `f2e8942`. Opened prior grids stay closed.
Track B stays closed. Not confirmation. Not AGI. Do not merge `main`.

Wave 2 discovered `even_add2` by Type B fallback. Wave 3 showed that
assimilating that clause plus parity probes cheapens related parity
compositions. This study asks four audit questions in one suite, and
separates the acquired clause from the acquired probe strategy.

## Stream

- Wave 1: `up_source` trains the frozen adaptive policy and pos/neg
  library.
- Wave 2: out-of-bank suite, including `even_add2`.
- Wave 3 prefix: parity compositions (not rescored).
- Wave 4 Group A `related_parity`: `even_add4`, `even_mul2`, `odd_add3`.
- Wave 4 Group B `unrelated_guard`: `abs_ge2` magnitude mechanisms.
- Wave 4 Group C `misleading_lookalike`: `mod4_eq0|add2` and
  `is_zero|add2` mechanisms that match `even` on `{0, 1}` and diverge
  on `x = 2`.
- Wave 4 Group D: true out-of-grammar `count`/`delay` plus reserved
  Wave-1/2/3 retests.

## Methods (seeds 0, 1, 2)

1. `untrained_open_grammar`
2. `learned_policy_open_grammar_cleared`
3. `wave1_frozen_neither` — Wave-1 library and Wave-1 probes
4. `ablation_wave2_probe_only` — ACT_0/ACT_1 parity priority, no even clause
5. `ablation_wave2_clause_only` — even clause, Wave-1 probe policy
6. `continual_full_both` — even clause and parity probes, plus leaf index

```
total_acquisition_work = env + confirmatory + bank_hyp + policy
                       + distill + retrieval + residual_synthesis
```

## Gates

1. Groups B and C: both/clause/probe solve every cell with `0`
   false-positive parity locks. Continual must reject the even
   lookalike on Group C via confirmatory ACT_2. Group D: all methods
   abstain with `0` false positives.
2. Report probe-only and clause-only marginals versus `neither` on
   Group A, and lookup/rejection overhead on B and C.
3. On A+B+C combined, `continual_full_both` has strictly lower total
   work than `neither`, learned-open, and untrained every seed, and
   every method is `6/6` on Wave-1/2/3 retention (`18/18` across seeds).

## Resources

Standing local-CPU grant. Symbolic only. 0 model calls. Frozen debit
**0**. Cap 120 s. Do not edit `local_model_runtime.py`.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_wave4_diagnostic_ablations.py -q
PYTHONPATH=src:.deps python3 scripts/run_wave4_diagnostic_ablations.py artifacts/seed_wave4_diagnostic_ablations
PYTHONPATH=src:.deps python3 scripts/verify_wave4_diagnostic_ablations.py artifacts/seed_wave4_diagnostic_ablations/seed_wave4_diagnostic_ablations.json
```
