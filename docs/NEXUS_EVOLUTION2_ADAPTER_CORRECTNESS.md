# Evolution-2.2 adapter correctness and real-model feasibility

Status: **engineering audit**. Not a scientific result.
Branch: `cursor/evolution2.2-adapter-correctness`
Parent: `9b6c6d0f435ba0d6d78aa4957e342a919c72fb95`.

No collection. No holdout named. No H17 change. No new scientific
ledger debit. Untracked Evolution-1 adapters preserved.

## Verdicts

| Gate | Result |
|---|---|
| Adapter correctness | **PASS** |
| Twelve-variant dispatch readiness | **BLOCKED** |
| Evolutionary-baseline fairness | **PASS** |
| Real-model timing evidence | **MEASURED** (existing probe; not re-run) |
| Full v2 feasibility | **NO-GO** |
| v2-pilot feasibility | **UNKNOWN** |
| Scientific-execution readiness | **BLOCKED** |

## 1. Adapter

`historical_parity` now uses the **actual** catalogue candidate count.
At cap 1,536, H=16 IID is 96 flat / 31 successor candidates, so every
worksheet row is `historical_parity: false`. Historical 16×16 remains
a separate predicate (`n_candidates == 16`).

Scoring reuses `planning.InferenceCounter` and
`RandomShootingMPC._score_batch`. Local copies of the counter and
the open-loop loop were removed. `mpc_for_model` is still unused.
Historical planner modules were not edited.

## 2. Twelve-arm dispatch

Six balanced-generator variants remain
`IMPLEMENTED_adapter_DISPATCH_BLOCKED`. Host
`operator_fingerprint` / `bind_evaluation` /
`validate_public_payload` still raise
`unsupported_balanced_generator`. That is a reviewed source-only
contract: the 12-arm scientific protocol **cannot proceed**. Dispatch
was not enabled.

## 3. Evolution

After a parent exists, `choose` may return only a one-coordinate
legal mutant. If none exist in `available`, it raises
`no_legal_mutant_in_available`. It no longer falls back to an
unrelated `available[0]`. Cold start without feedback still returns
`available[0]`. Crossover stays illegal.

## 4. v2-pilot reveal/cache

Methods share one `RevealCache`. Cache hits are still charged.
Unused catalogue variants cannot be revealed. Imagined charge is
`decisions × 1536`. Locked v2/v2-pilot hashes are unchanged.

## 5. Timing (existing, not re-run)

From `artifacts/evolution2_residual_timing_probe.json` (0 env steps):

| Model | µs/state | v2 | pilot |
|---|---|---|---|
| Pendulum residual | 2.95 | 326 s | 145 s |
| Acrobot residual | 5.24 | 580 s | 258 s |
| Historical live | 5.53 | 612 s | 272 s |

Conservative planning = `1.25 × max(measured, historical)`:
v2 **765 s**, pilot **340 s**. Source fitting of 20 models is
unmeasured. Fake-model speed was not used.

## 6. Next action that would produce real evidence

Do **not** collect and do **not** name a holdout. Time residual-MLP
**source fitting** on already-stored transitions from the same frozen
files (0 new env steps). Until that cost is measured, v2-pilot stays
UNKNOWN and scientific execution stays BLOCKED.
