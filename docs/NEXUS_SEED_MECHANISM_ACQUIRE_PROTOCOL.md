# Mechanism acquisition — protocol

Isolated branch `cursor/seed-mechanism-acquire` from
`cursor/seed-mechanism-varied-probes` `7ae2432`. Protocol committed
before scoring. Opened C/D/E, mismatch and varied-probe cells stay
closed. Not confirmation. Not AGI. Do not merge `main`.

## Three claims

The evaluator scores these separately:

1. **Catalogue identification** — one candidate remains in the supplied
   language.
2. **Predictive competence** — the hypothesis predicts observations on
   a fresh instance.
3. **Exact mechanism identification** — evidence distinguishes the
   hidden generator from relevant alternatives.

A finite set of agreeing probes does not establish (3) in an
unrestricted environment. That column stays false. Observational twins
are an equivalence class: “consistent with add1; exact identity
unresolved.” Guessing the hidden generator’s name is not success.

## Synthesis first

Primitives (shared, programmer-supplied): `add1`, `add2`, `mul2`, `neg`.
Length at most 2. The stored language is not expanded.

| Role | IDs | Mechanisms |
| --- | --- | --- |
| Gate (unstored) | `acq_gate_mul_add`, `acq_gate_add_neg`, `acq_gate_neg_add` | `mul2_then_add1`, `add1_then_neg`, `neg_then_add1` |
| Source | `acq_src_*` | the four primitives |
| Holdout | `acq_hold_add2_mul`, `acq_hold_neg_add2`, `acq_hold_mul_neg` | `add2_then_mul2`, `neg_then_add2`, `mul2_then_neg` |

Stage 1: `fixed_synthesis` and `catalogue_only` get the same primitives.
The gate passes only if the synthesizer predicts every gate task, never
guesses the generator, never claims exact identity, and the catalogue
alone cannot predict the same set.

Stage 2 opens only after Stage 1. Task solutions reset. Trained search
(source composition-IG + DAgger) is compared to `fixed_synthesis` and
`composition_ig` on holdout accuracy, interactions and total work.

## Resources

Standing local-CPU grant. No model calls. Frozen debit **0**. Cap 120 s.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_mechanism_acquire.py tests/test_seed_mechanism_varied.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_mechanism_acquire.py artifacts/seed_mechanism_acquire
PYTHONPATH=src:.deps python3 scripts/verify_seed_mechanism_acquire.py artifacts/seed_mechanism_acquire/seed_mechanism_acquire.json
```
