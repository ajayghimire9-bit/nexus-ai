# Continual mechanism experience — Track A results

Branch `cursor/seed-mechanism-continual`.
Protocol `7d71e24`. This results commit is separate.
Base `a37503d`. Artifact hash
`fff9fde77348c340acd2697a112c9d8c9524a625140a80a6ee5b7a93d6928d30`.
Verifier `valid: true` on 184 cells; opened prior IDs rejected.
Track B not run. Online stream not run. Pilot, not confirmation.
Not learning-to-learn as a general claim. Not AGI.

## Programmer-supplied vs acquired

Supplied: probe operators, typed primitive set, legal pair rules, affine
fitter, hidden `sign_pos` executor, and the linear feature template.
Acquired: four Wave-1 scoped skills (`add1`, `mul2`, `if_pos`, `sat_inc`)
and source-only linear probe weights from full-sequence DAgger. Policy
and skill memory reset independently. Wave 2–3 did not write either.

## Inner learning (Wave 1)

Fixed learner 4/4 development. Trained policy 4/4 on three seeds.
Assessment opened. Exact identity never awarded.

## Wave 2 — unseen compositions and one reject

3 compositions × 3 seeds + `sign_pos` × 3. All arms: 9 useful
acquisitions, 3 correct rejects, 0 guessed generators. `sign_pos` is
not counted as acquired.

| Arm | Useful | Reject | Interactions | Oracle |
| --- | ---: | ---: | ---: | ---: |
| fixed_learner | 9 | 3 | 105 | 129 |
| fixed_exact | 9 | 3 | 105 | 129 |
| fixed_template | 9 | 3 | 105 | 129 |
| memory_only | 9 | 3 | 105 | 129 |
| irrelevant_memory | 9 | 3 | 105 | 129 |
| policy_only | 9 | 3 | **84** | **108** |
| full_nexus | 9 | 3 | **84** | **108** |

Skill memory retrieval hits on Wave 2: 0. Memory does not beat the
typed+affine learner or the template arm.

Example: `w2_if_pos_add1` → `consistent with if_pos|add1; exact identity
unresolved`, then correct predictions on a fresh instance.

## Wave 3 — composition and reserved source

All arms 12/12 useful, including 9/9 reserved source retests. That is
re-acquisition as well as memory: `fixed_learner` also 9/9 without
skills. Memory arms record 12 retrieval hits. Policy-only again uses
84 vs 111 interactions.

## Verdicts

- Inner learning: **works**
- Skill transfer: **no advantage over template**
- Policy learning: **cheaper at matched accuracy** (84 vs 105 Wave-2
  interactions). Predeclared cost rule, not a new learning procedure.
- Retention: 9/9 reserved; not a “zero forgetting” claim
- Overall: policy cost saving; skill reuse did not improve unfamiliar
  acquisition

## Costs and limits

0.670 s wall, 0 model calls, frozen debit **0**. Product chat unused.
Metal unused. Host remains the CPU symbolic path. The 1.5B Metal
Best-of-4 smoke previously failed to show useful diversity on M4.

## Track B

Prepared as **not run**. Same local runtime, vault and repair store
would be required, with acquired / ordinary / no-memory arms and
identical budgets. It is not a substitute for the policy-only result
above.

## Next (three)

1. Do not rescore this grid or `a37503d`. A later family must make
   typed synthesis plus affine fitting miss before memory can show
   transfer.
2. Keep Track B closed until a stronger local coder and a demonstrated
   diverse sampler exist.
3. Register any online stream separately, with paired task orders.
