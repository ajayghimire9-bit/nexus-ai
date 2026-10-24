# Wave-5 grammar prior and event-record transfer results

Branch `cursor/seed-wave5-prior-and-transfer` from `f66ae34`.
Protocol `d2c0105`. This results commit is separate.
Artifact hash
`c489a6357e1a1fd2aa0d4d05af24671a45a1fc30bc7991d3e42ecaa44f876866`.
Verifier `valid: true` on 504 cells. Historical grids were not
rescored. Track B coding/LLM closed. 0 model calls. Frozen 1.5B
debit **0**. Wall **1.316 s**, classified as symbolic standing-grant
CPU (not the frozen 1.5B ledger). Pilot, not confirmation. Not
general learning-to-learn. Not AGI.

`up_source` has 0 even labels. A disclosed development curriculum
`w5_source` was used (id 1 / pos 2 / even 3). Relational features are
programmer-supplied. The prior was frozen before assessment.

```
total = env + confirmatory + bank_hyp + policy + distill + retrieval
      + residual_synthesis + prior_score + feature_extract
      + mapping + prior_train
```

## Track A — same integer language, fresh mechanisms

### Related compositions (`even_add3`, `odd_mul2`)

| Method | Useful | Tot |
| --- | ---: | ---: |
| static_fixed_probe_static_synth | 6 | 2718 |
| learned_probe_static_synth | 6 | 2598 |
| frequency_order_fixed_probe | 6 | **2415** |
| heuristic_fixed_probe | 6 | 2490 |
| learned_prior_cleared_fixed_probe | 6 | 2709 |
| full_clauses_learned_prior | 6 | 2649 |
| full_clauses_static_fallback | 6 | **2355** |
| shuffled_prior_fixed_probe | 6 | 2787 |

Learned prior-cleared beat static enumeration (2709 < 2718) but lost
to frequency (2415) and the residual heuristic (2490). Full+prior lost
to full+static-clauses (2649 > 2355). Beating static enumeration only
is not an advantage over strong simple learning baselines.

### Misleading transforms (same-case comparison, not 9975)

| Method | Useful | Lock | Even rejected | Tot |
| --- | ---: | ---: | ---: | ---: |
| static_fixed_probe_static_synth | 6 | 0 | 0 | 4068 |
| learned_probe_static_synth | 6 | 0 | 0 | 3912 |
| frequency_order_fixed_probe | 6 | 0 | 0 | 3966 |
| heuristic_fixed_probe | 6 | 0 | 0 | **2295** |
| learned_prior_cleared_fixed_probe | 6 | 0 | 0 | 3714 |
| full_clauses_learned_prior | 6 | **0** | **6** | 5058 |
| full_clauses_static_fallback | 6 | **0** | **6** | 5316 |
| shuffled_prior_fixed_probe | 6 | 0 | 0 | 3255 |

Clause methods proposed even and confirmatory-rejected it on these
fresh lookalikes, then recovered. Heuristic residual order was cheaper
because it never took the false even lock.

### Unrelated `abs_ge2` / OOG / retain

Unrelated: all eight methods 6/6, 0 locks (static-clauses 2538 cheapest).
OOG `sum`/`plus_prev`: all methods 6/6 abstain, 0 FP.
Retain Wave-1–4: all methods **12/12**.

## Track B — event-record environment

What differs: observations are field bags; actions are `READ_*` /
`ASK_*`; feedback is generic parsed fields; the log grows; the goal
is bind-then-identify. Parsing is shared. No task-specific “result is
y” gift.

### Supplied mapping (not evidence for acquired mapping)

Related: all six methods **6/6**, mapping_correct 6/6. Skills-only 2220
< scratch 2634; full NEXUS 2262 ties ordinary template 2262.

| Method | Related useful | Tot | Map |
| --- | ---: | ---: | ---: |
| target_scratch | 6 | 2634 | 6 |
| ordinary_template | 6 | 2262 | 6 |
| acquired_skills_only | 6 | **2220** | 6 |
| prior_only_cleared | 6 | 2352 | 6 |
| full_nexus | 6 | 2262 | 6 |
| irrelevant_memory | 6 | 2634 | 6 |

Lookalike supplied: 3/6 useful, 0 locks (one of two event lookalikes
stayed unresolved). OOG 6/6 abstain, 0 FP.

### Acquired mapping (separate)

Related: **0/6** useful, **0/6** mapping_correct. Binding search (96
candidates, charged) preferred a `stamp` rotation over `result`.
Acquired-mapping transfer is **not established**. Do not read the
supplied-mapping table as this result.

### Successful supplied trajectory (seed 0, `w5e_rel_even_add3`, full NEXUS)

Reads `READ_ALPHA/BETA/GAMMA/DELTA`. Supplied binding
`{alpha:0, beta:1, gamma:2, delta:-1, output_field: result}` produced
integer transcript `(0,3), (1,1), (2,5), (-1,-1)` and representative
`even|add3|id`. Work 362. Mapping correct.

Failed acquired counterpart on the same task: binding
`{alpha:-1, beta:0, gamma:1, delta:2, output_field: stamp}`, mapping
correct false, representative none, work 1850, mapping_evals 96.

## Gates

| Gate | Result |
| --- | --- |
| Safety (locks / OOG / retain / labels) | **pass** |
| A prior vs static-with-clauses | fail (2649 > 2355) |
| A prior-cleared vs static | pass (2709 < 2718) |
| A prior-cleared vs heuristic / frequency | fail |
| B supplied full vs scratch | pass (useful 6/6) |
| B acquired mapping established | **fail** |

Conclusion: **ordinary-template / heuristic tie** on source-language
ordering; **supplied-mapping reuse** of even structure on this one
event-record interface; **acquired mapping not established**. Not
general learning-to-learn. Abstention is not acquisition of the
unknown. Retention 12/12 is not universally zero forgetting.

## Three next steps

1. Treat acquired mapping as a separate problem: require a predictive
   holdout on the binding itself so stamp-like counters cannot win.
2. Keep the residual-exists heuristic as the strong baseline; a
   learned prior needs source variation beyond pos/even/id or it is
   redundant.
3. Test a constructor family that never appeared in source, and do
   not describe frequency learning as discovering its semantics.
