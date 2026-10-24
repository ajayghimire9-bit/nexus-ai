# Wave-4 diagnostic ablation results

Branch `cursor/seed-wave4-diagnostic-ablations` from `c8bc5ad`.
Protocol `25cd50e`. This results commit is separate.
Artifact hash
`486a0ae02bbfa6ebe30e9f1f1eba24494f8bb8da4bbc74029baa200ac67555e9`.
Verifier `valid: true` on 270 cells. `c8bc5ad`, `0d4596e`, `6e0df3a`,
and `f2e8942` artifacts were not edited. Track B not run. 0 model
calls. Frozen debit **0**. Pilot, not confirmation. Not general
learning-to-learn. Not AGI.

```
total_acquisition_work = env + confirmatory + bank_hyp + policy
                       + distill + retrieval + residual_synthesis
```

## Group A — related parity (3 × 3 seeds)

| Method | Useful | Tot | Sub | Even proposed / rejected |
| --- | ---: | ---: | ---: | ---: |
| untrained_open_grammar | 9 | 12549 | 0 | 0 / 0 |
| learned_policy_open_grammar_cleared | 9 | 13263 | 0 | 0 / 0 |
| wave1_frozen_neither | 9 | 13995 | 0 | 0 / 0 |
| ablation_wave2_probe_only | 9 | 14610 | 0 | 0 / 0 |
| ablation_wave2_clause_only | 9 | **3321** | 9 | 9 / 0 |
| continual_full_both | 9 | **3297** | 9 | 9 / 0 |

Per seed: neither 4665, probe 4870 (**−205** vs neither), clause **1107** (**+3558** vs neither), both **1099**.

The acquired even clause is what cheapens related parity. The acquired
parity probe strategy alone costs more than the Wave-1 freeze.

## Group B — unrelated guards (2 × 3 seeds)

| Method | Useful | Lock | Proposed / rejected | Retr | Tot |
| --- | ---: | ---: | ---: | ---: | ---: |
| untrained_open_grammar | 6 | 0 | 0 / 0 | 0 | 8190 |
| learned_policy_open_grammar_cleared | 6 | 0 | 0 / 0 | 0 | 8016 |
| wave1_frozen_neither | 6 | 0 | 0 / 0 | 12 | 8490 |
| ablation_wave2_probe_only | 6 | 0 | 0 / 0 | 12 | 10356 |
| ablation_wave2_clause_only | 6 | **0** | 6 / 6 | 6 | 9996 |
| continual_full_both | 6 | **0** | 6 / 6 | 6 | **7314** |

Lookup overhead is bounded. Clause methods propose even on `{0, 1}`
and confirmatory `ACT_2` rejects it. Continual then reuses stored
leaves. No false-positive parity locks.

## Group C — misleading lookalikes (2 × 3 seeds)

| Method | Useful | Lock | Proposed / rejected | Tot |
| --- | ---: | ---: | ---: | ---: |
| untrained_open_grammar | 6 | 0 | 0 / 0 | 7944 |
| learned_policy_open_grammar_cleared | 6 | 0 | 0 / 0 | 7944 |
| wave1_frozen_neither | 6 | 0 | 0 / 0 | 8370 |
| ablation_wave2_probe_only | 6 | 0 | 0 / 0 | 8292 |
| ablation_wave2_clause_only | 6 | **0** | **6 / 6** | 9624 |
| continual_full_both | 6 | **0** | **6 / 6** | 9975 |

`mod4_eq0|add2` and `is_zero|add2` match `even` on `{0, 1}` and
diverge on `x = 2`. Clause methods propose even; confirmatory `ACT_2`
rejects every lock; residual synthesis recovers the true guard. This
group is the overhead of carrying the even clause.

## Group D — true OOG + retention

OOG `count`/`delay`: all six methods **6/6** abstain, **0** false
positives.

Retention Wave-1 + Wave-2 + Wave-3: all six methods **18/18**.

## Combined A+B+C portfolio

| Method | Useful | Tot | Per seed |
| --- | ---: | ---: | ---: |
| untrained_open_grammar | 21 | 28683 | 9561 |
| learned_policy_open_grammar_cleared | 21 | 29223 | 9741 |
| wave1_frozen_neither | 21 | 30855 | 10285 |
| ablation_wave2_probe_only | 21 | 33258 | 11086 |
| ablation_wave2_clause_only | 21 | 22941 | 7647 |
| continual_full_both | 21 | **20586** | **6862** |

## Gates

| Gate | Result |
| --- | --- |
| 1 Zero wrong assumptions | **pass** — B/C solved 6/6 with 0 parity locks; C even rejected 6/6 for clause and both; OOG 6/6 abstain, 0 FP |
| 2 Clause vs probe attribution | **pass** — Group A clause vs neither **+3558**/seed; probe vs neither **−205**/seed; B retrieval 2/seed; C even rejected 2/seed |
| 3 Net portfolio and retention | **pass** — both 6862 < 9561 / 9741 / 10285 every seed; retain 18/18 |

## What this does not show

This is not general learning-to-learn, not open-domain coding, and not
Track B. The even clause transfers only to families that reuse that
partition. Unrelated and lookalike tasks pay lookup and rejection
overhead. Probe-only parity priority without the clause did not reduce
total work.
