# Unfamiliar beyond-catalog acquisition results

Branch `cursor/seed-unfamiliar-beyond-catalog` from `6e0df3a`.
Protocol `8554c04`. This results commit is separate.
Artifact hash
`1a4132bb400209ee3877e06739e2436b8a828ccf76dd2755361456c2a5cecc07`.
Verifier `valid: true` on 72 cells. `f2e8942` and `6e0df3a` artifacts
were not edited. Track B not run. 0 model calls. Frozen debit **0**.
Pilot, not confirmation. Not general learning-to-learn. Not AGI.

Holdout mechanisms have **0%** coverage in `supplied_bank`.

```
total_acquisition_work = env + confirmatory + bank_hyp + policy
                       + distill + retrieval + residual_synthesis
```

## Four-way holdout totals (4 mechanisms × 3 seeds)

| Method | Useful | Exhaust | FP | Env | Confirm | Bank hyp | Policy | Retr | Distill | Synth | **Total** | Sub |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| supplied_bank_only | 0 | 12 | **0** | 21 | 0 | 264 | 165 | 0 | 0 | 0 | **450** | 0 |
| untrained_open_grammar | 12 | 12 | 0 | 54 | 12 | 687 | 0 | 0 | 0 | 7353 | **8106** | 0 |
| learned_policy_open_grammar_cleared | 12 | 12 | 0 | 36 | 12 | 264 | 165 | 0 | 0 | 7398 | **7875** | 0 |
| nexus_abductive_beyond_bank | 12 | 12 | 0 | 36 | 12 | 264 | 165 | 24 | 78 | **6297** | **6876** | **18** |

Reserved retest: all four methods **6/6**. Bank-only reserved stays in-bank (0 exhaust).

## Gates

| Gate | Result |
| --- | --- |
| 1 Zero false positives and calibrated unknowns | **pass** — bank-only 12/12 exhaust, 0 claims, 0 FP; others 12/12 + 6/6 |
| 2 Adaptive open grammar beats untrained | **pass** — 2625 < 2702 every seed |
| 3 Abductive beats cleared open grammar | **pass** — 2292 < 2625 every seed after distill 26 + retrieval 8; Type B miss has 0 sub-hits and still solves |

## Per-seed holdout

| Seed | Bank-only | Untrained open | Learned open | Abductive (distill 26) |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 7 / 150 (0/4 useful, 4 exhaust, 0 FP) | 18 / 2702 | 12 / 2625 | **12 / 2292** (6 sub, Type B 0) |
| 1 | 7 / 150 | 18 / 2702 | 12 / 2625 | **12 / 2292** |
| 2 | 7 / 150 | 18 / 2702 | 12 / 2625 | **12 / 2292** |

## Per-task holdout (seeds 0–2 identical)

| Task | Kind | Bank-only | Untrained | Learned open | Abductive |
| --- | --- | ---: | ---: | ---: | ---: |
| oob_hold_pos_plus3 | Type A | 2 / 43 abstain | 5+1 / 709 | 3+1 / 615 | 3+1 / **498** (sub 2, distill 26 on seed-first) |
| oob_hold_pos_mul3 | Type A | 2 / 43 abstain | 5+1 / 725 | 3+1 / 697 | 3+1 / **547** (sub 2) |
| oob_hold_neg_add1 | Type A | 1 / 21 abstain | 5+1 / 660 | 3+1 / 616 | 3+1 / **494** (sub 2) |
| oob_hold_even_add2 | Type B | 2 / 43 abstain | 3+1 / 608 | 3+1 / 697 | 3+1 / 753 (sub **0**, fallback grammar) |

`env+c` written as diagnostic + confirmatory. Type B costs more than cleared open grammar on that one cell; Type A residual savings still win the seed.

## What this does not show

This is not general learning-to-learn, not open-domain coding, and not
Track B. Synthesis stays inside a programmer-supplied primitive
grammar. A later unknown outside that grammar must still abstain.
