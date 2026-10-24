# Wave-8 hierarchical gated evolution protocol

Isolated branch `cursor/seed-wave8-hierarchical-gated-evolution` from
`907db66`. Protocol committed before scoring. Do not rescore `907db66`
or earlier grids. Track B coding/LLM stays closed. Do not merge
`main`. Do not edit `local_model_runtime.py`.

Wave 7 compiled one flat palindrome (`L0→L1`), paid eager role-probes
on easy G1 (`534` vs `198`), and expanded the bank on OOG Caesar
(`2,217` vs `1,710`). This study stacks `L0→L1→L2`, gates compiled
operators by a 1-step I/O invariant, and defers analogy until the
depth-1 fast path fails or a lookalike confirm conflict appears.

## Methods (seeds 0, 1, 2)

1. `factored_interface_scratch`
2. `factored_relational_analogy_static_bank`
3. `wave7_ungated_flat_evolving` (eager role-probe, flat L1, ungated)
4. `ablation_hierarchical_ungated` (L1+L2, no gate, no lazy)
5. `ablation_gated_flat_L1_only` (lazy + gate, no L2 compose)
6. `nexus_hierarchical_gated_evolving` (lazy + L0→L1→L2 + gate + MDL)

## Groups

12 fresh task IDs × 6 methods × 3 seeds = **216 cells**. Do not
reuse Wave-7 IDs.

1. Analogous first-fit (`even_append`, `odd_dup`)
2. Misleading lookalikes
3. L1 palindrome invent/reuse + one-off `first==last` distractor
4. L2 palindrome-rotate invent/reuse (`L1` inside `L2`)
5. Alias ambiguity, OOG Caesar, Domain A `even_add2` retain

```
total = public_env + public_validation + channel_invariance
      + binding + role_probe + schema_distill + gate_evals
      + retrieval + synthesis + micro_codegen + operator_compile
```

## Gates

1. Private isolation; 0 false analogy locks; 100% ambiguous / OOG /
   Domain A retention.
2. On G1, nexus strictly below wave7-ungated and at or below
   factored scratch; G1+G2 still beats scratch.
3. On OOG Caesar, nexus strictly below wave7-ungated and
   hierarchical-ungated, within a small gate-check margin of scratch.
4. On G3 L1+L2 and the suite, nexus strictly lower total work and
   `micro_codegen+synthesis` than flat-gated L1, wave7-ungated, static
   analogy, and factored scratch on every seed.

## Resources

Symbolic standing-grant CPU. 0 model calls. Frozen debit **0**. Cap
120 s.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_wave8_hierarchical.py -q
PYTHONPATH=src:.deps python3 scripts/run_wave8_hierarchical.py artifacts/seed_wave8_hierarchical_gated_evolution
PYTHONPATH=src:.deps python3 scripts/verify_wave8_hierarchical_gated_evolution.py artifacts/seed_wave8_hierarchical_gated_evolution/seed_wave8_hierarchical_gated_evolution.json
```
