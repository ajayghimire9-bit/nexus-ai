# Continual Wave-3 assimilation protocol

Isolated branch `cursor/seed-continual-wave3-assimilation` from
`0d4596e`. Protocol committed before scoring. Do not edit `0d4596e`,
`6e0df3a`, or `f2e8942`. Opened prior grids stay closed. Track B stays
closed. Not confirmation. Not AGI. Do not merge `main`.

Wave 2 `even_add2` was a Type B fallback. This study asks whether
assimilating that invention (sub-clause + parity probe priority) makes
the next unfamiliar parity family cheaper, while true out-of-grammar
unknowns stay abstentions and Wave-1/Wave-2 reserved items are retained.

## Stream

- Wave 1: `up_source` trains the frozen adaptive policy and pos/neg
  library.
- Wave 2: new IDs of the out-of-bank suite, including `even_add2`.
- Wave 3 expressible: `even_mul3`, `even_sub1`, `odd_plus2`.
- Wave 3 out-of-grammar: `count`, `delay` (stateful / history; not in
  the primitive grammar).
- Retention after Wave 3: Wave-1 `add1`/`if_pos` and Wave-2
  `even_add2`/`pos_plus3`.

## Methods (seeds 0, 1, 2)

1. `untrained_open_grammar`
2. `learned_policy_open_grammar_cleared`
3. `wave1_frozen_abductive` — library and probes frozen after Wave 1
4. `continual_assimilating_nexus` — assimilates verified Wave-2
   inventions, including the even guard and ACT_0/ACT_1 parity priority

```
total_acquisition_work = env + confirmatory + bank_hyp + policy
                       + distill + retrieval + residual_synthesis
```

Wave-3 continual totals include Wave-1 distill plus Wave-2 even
assimilation.

## Gates

1. All methods abstain on both out-of-grammar tasks (`0` false
   positives) every seed.
2. On Wave-3 expressible tasks, continual has strictly lower total work
   and strictly lower `env + residual_synthesis` than the other three
   methods every seed.
3. After Wave 3, every method is `4/4` on reserved Wave-1 and Wave-2
   retests (`100%`).

## Resources

Standing local-CPU grant. Symbolic only. 0 model calls. Frozen debit
**0**. Cap 120 s. Do not edit `local_model_runtime.py`.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_continual_wave3_assimilation.py -q
PYTHONPATH=src:.deps python3 scripts/run_continual_wave3_assimilation.py artifacts/seed_continual_wave3_assimilation
PYTHONPATH=src:.deps python3 scripts/verify_continual_wave3_assimilation.py artifacts/seed_continual_wave3_assimilation/seed_continual_wave3_assimilation.json
```
