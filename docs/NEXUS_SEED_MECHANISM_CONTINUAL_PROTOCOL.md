# Continual mechanism experience — Track A protocol

Isolated branch `cursor/seed-mechanism-continual` from
`cursor/seed-mechanism-acquire` `a37503d` (protocol `11a08f6`).
Protocol committed before scoring. Opened acquire, varied, mismatch and
C/D/E cells stay closed. Not confirmation. Not AGI. Do not merge `main`.

Audit: acquire synthesis works then policy ties (`a37503d`). The length-2
affine enumerator was already complete, so experience could not help.
Investigation-policy L2L (`11b934d`) never identified. Acquired-experience
coding (`aab3477`) was a tool-tie. Metal Best-of-4 (`592aa81`) ran on M4
not M5 and did not show useful diversity. Skill memory reuses the
RepairSchemaStore field pattern and OrdinaryExactCache. Policy weights
stay in `mechanism_policy`. No second capsule store or investigation
engine. Probe operators and types are programmer-supplied.

## Inner and outer loops

Inner: probe → outcome → typed/affine hypothesis update → scoped model →
fresh-instance validation.

Outer: source-only DAgger on the **full probe sequence** (not last-probe
credit) updates linear investigation weights. Memory and policy reset
independently.

## Structural language

Primitives: `add1`, `add2`, `mul2`, `neg` (transform), `if_pos`,
`if_neg` (gate), `sat_inc`, `sat_dec` (bounded state). Type-directed
pairs only. Affine least-squares is a simple model-fitting baseline.
Observational equivalence collapses remaining pipelines. Every arm gets
the same primitives, actions, observations and budget.

| Wave | IDs | Mechanisms | Role |
| --- | --- | --- | --- |
| 1 source | `w1_add1`, `w1_mul2`, `w1_if_pos`, `w1_sat_inc` | primitives | acquire + save skills |
| 1 dev | `w1d_add2`, `w1d_neg`, `w1d_if_neg`, `w1d_sat_dec` | held-out primitives | competence |
| 2 target | `w2_if_pos_add1`, `w2_sat_inc_mul2`, `w2_if_neg_neg` | unseen compositions | transfer |
| 2 reject | `w2_sign_pos` | `sign_pos` (not synthesizable) | correct reject, not acquisition |
| 3 compose | `w3_add1_if_pos` | new combo of acquired concepts | composition |
| 3 retain | `w3r_add1`, `w3r_if_pos`, `w3r_sat_inc` | reserved source seeds | retention |

`sign_pos` adapter: programmer-supplied hidden executor only. No
representation mapper.

## Arms (frozen after Wave 1)

1. `fixed_learner` — typed synth + affine fit, no memory
2. `fixed_exact` — same + exact evidence cache
3. `fixed_template` — same + type-tag template memory
4. `policy_only` — source-trained policy, solution memory reset
5. `memory_only` — fixed investigation + NEXUS skills
6. `full_nexus` — learned policy + NEXUS skills
7. `irrelevant_memory` — fixed investigation + mismatched skills

Assessments do not write policy or source memory.

## Gates and thresholds

Inner learner must usefully acquire all four development tasks before
Waves 2–3 open. Trained policy must do the same on own-development
episodes.

Predeclared (development-scale, not 2×):

- Transfer: memory_only ≥ fixed_learner + 1 useful, or same useful at
  ≤ 80% interactions, else no advantage over template
- Learning-to-learn: policy_only more useful or cheaper than
  `fixed_learner` at matched useful
- Retention: report reserved useful/n; not “zero forgetting”
- Rejected `sign_pos` is never useful_acquisition

Track B and an online continual stream are registered **not run**.
Track B is not a substitute for the policy-only assessment.

## Resources

Standing local-CPU grant. Symbolic Track A. Estimated < 5 s, 0 model
calls, frozen debit **0**. Cap 120 s.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_mechanism_continual.py tests/test_seed_mechanism_acquire.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_mechanism_continual.py artifacts/seed_mechanism_continual
PYTHONPATH=src:.deps python3 scripts/verify_seed_mechanism_continual.py artifacts/seed_mechanism_continual/seed_mechanism_continual.json
```
