# Wave-5 grammar prior and event-record transfer protocol

Isolated branch `cursor/seed-wave5-prior-and-transfer` from reviewed
`f66ae34`. Protocol committed before scoring. Do not edit `f66ae34`,
`c8bc5ad`, `0d4596e`, `6e0df3a`, or `f2e8942`. Track B coding/LLM work
stays closed. This cross-environment track is a separate symbolic
event-record pilot. Do not merge `main`.

## Part 1 — locked Wave-4 record

Full-system combined A+B+C work was **20,586**. Related-parity savings
came mainly from the acquired even clause. Probe-only did not reduce
related-parity work. Misleading clauses were rejected. Tested OOG
tasks were declined. Reserved retests passed. Transfer remains bounded
to that language. A claim that static synthesis order caused the
probe-only gap is a **hypothesis**, not a verified cause.

## Track A — experience-learned grammar prior

Reuse `filter_specs`, `SubMechanismLibrary`, `BeyondMeter`, and the
Wave-4 residual helpers. One `GrammarOperatorPrior` orders existing
guards. Features are programmer-supplied residuals and public I/O
fractions. No target names or hidden labels.

`up_source` lacks even. A disclosed development curriculum `w5_source`
(pos/even/id compositions of already-available mechanisms) is used
and charged. The prior is frozen before assessment.

Methods, matched **fixed** probes except method 2:

1. `static_fixed_probe_static_synth`
2. `learned_probe_static_synth`
3. `frequency_order_fixed_probe`
4. `heuristic_fixed_probe`
5. `learned_prior_cleared_fixed_probe`
6. `full_clauses_learned_prior`
7. `full_clauses_static_fallback`
8. `shuffled_prior_fixed_probe`

Fresh assessment (new IDs): related compositions, misleading
transforms, unrelated `abs_ge2` guards, true OOG `sum`/`plus_prev`,
Wave-1–4 retention. Compare lookalikes to method 7 on **these**
cases, not the historical 9975.

```
total = env + confirmatory + bank_hyp + policy + distill + retrieval
      + residual_synthesis + prior_score + feature_extract
      + mapping + prior_train
```

Wall time is recorded separately.

## Track B — event-record transfer

Target is a bounded event-record environment (`event_record_env.py`).
It differs from the integer world:

| Axis | Source | Target |
| --- | --- | --- |
| Observation | integer `y` | field bag `{payload, result, echo, stamp}` |
| Actions | `ACT_0/1/2/NEG` | `READ_*` slot / `ASK_*` field |
| Feedback | one number | generic parsed fields |
| Time | stateless probe | growing event log |
| Goal | identify `guard\|then\|else` | bind slot/field, then identify |

Generic parsing is shared. No task-specific “result is y” gift.

- **Supplied mapping:** documented slot→x and `result` output.
- **Acquired mapping:** search 96 bindings from observations; charge
  `mapping_evals`. Do not report supplied as acquired.

Methods: scratch, ordinary template (same binding+abstraction),
skills only, prior only (memory cleared), full NEXUS, irrelevant
(neg) memory.

## Gates (predeclared)

Safety (suite `passed` requires these):

- Track A lookalikes: methods 5–7 have 0 false-positive parity locks
  versus method 7 on the same cases.
- Track A OOG: all methods 6/6 abstain, 0 FP.
- Track A retain: all methods 12/12.
- Track B OOG: 0 FP. Mapping conditions labeled separately.

Advantage labels (may fail; reported anyway):

- A: prior vs static-with-clauses; prior-cleared vs static /
  heuristic / frequency on related.
- B supplied: full useful on related ≥ scratch and ≥ 3/6.
- B acquired mapping established: full `mapping_correct` ≥ 3/6.

Possible conclusions: learned ordering helps; supplied-mapping
transfer; acquired-mapping transfer; policy-only transfer; heuristic
tie; negative or inconclusive. Not general learning-to-learn.

## Resources

Standing local-CPU grant. Symbolic only. 0 model calls. Frozen 1.5B
ledger debit expected **0** after classification check. Cap 120 s.
Record wall time. Do not edit `local_model_runtime.py`.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_wave5_prior_transfer.py -q
PYTHONPATH=src:.deps python3 scripts/run_wave5_prior_transfer.py artifacts/seed_wave5_prior_and_transfer
PYTHONPATH=src:.deps python3 scripts/verify_wave5_prior_transfer.py artifacts/seed_wave5_prior_and_transfer/seed_wave5_prior_and_transfer.json
```
