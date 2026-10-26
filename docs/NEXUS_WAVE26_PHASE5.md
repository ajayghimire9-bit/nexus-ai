# Wave 26 Phase 5 — long-term memory across a drifting continual stream (locked before streams 5001–5005)

Branch `codex/wave26-phase5-continual-memory` (from Phase 4 `e41c681`). Code: `src/nexus/wave26_phase5.py`,
driver `scripts/phase5_memory.py`, tests `tests/test_wave26_phase5.py`. It reuses the Phase 4 router,
synthesizer and slot-level library, with three changes to `wave26_phase4.py` on this branch:
* optional extra (opaque) tools;
* the ΔC tier recombines base mechanisms only;
* a sound contract index drops projecting library schemas when every public output is a sub-multiset of
  its input.

## Stream

* **Size:** 18 base worlds plus one revisit each, 36 visits. Each base world is scheduled at lag 5, 10 or 20,
  and the actual distance is bucketed. This is a **disclosed deviation** from 50–100 worlds, because
  snapshot counterfactuals make full-size streams exceed the budget.
* **Tasks:** 2 per visit.
* **Drift:**
  * fresh field names per world;
  * the hidden-mechanism subset changes per world;
  * distractor correlations flip sign in some worlds;
  * from mid-stream, some worlds' opaque top-k tool emits items not in its input.
* **Empirical contracts:** every opaque tool carries an EMPIRICAL sub-multiset contract, observed on each
  application. It never prunes, and a counterexample retires it (RETIRED_BY_DRIFT).

## Gates

* Revisit cost ratio Σ visit 2 / Σ visit 1 < 1 for every lag bucket.
* Backward interference (Σ full-library visit-2 cost − Σ snapshot cost) / Σ snapshot ≤ 0.10.
* 100% of drift-broken opaque contracts retired, and 0 false certificates.
* G_tycho.
* Identical per-stream fresh-process replays.

## Dev evidence (dev streams 731–732)

* First version (ΔC over base + library at depth 3), stream 731: lag ratios 3.71 / 6.19 / 0.90,
  interference 32.5%.
* Base-only ΔC, streams 731 + 732: ratios 1.53 / 1.04 / 1.09, interference 12.1%; retirement 5 / 5, 0 false
  certificates, 125 / 128 solved.
* With the contract index, stream 731: ratios 2.41 / 2.16 / 0.99, interference 37.0%. Variance between
  streams is large.

**Expected to fail:** revisit and interference. **Expected to pass:** retirement and soundness.

**Diagnosis.** The sound union-of-repair-tiers certificate runs a synthesis scan and searches every library
instantiation on every hidden-mechanism task. Memory therefore cannot shortcut the work it would save, and
library growth enlarges the certified space. Under exact certification, retention does not pay here.

## Runs

```
python3 scripts/phase5_memory.py --confirm --checkpoint runs/experimental/wave26_phase5_confirm.jsonl --out artifacts/wave26_phase5_confirmation.json   # repeat until COMPLETE
python3 scripts/phase5_memory.py --replay-of artifacts/wave26_phase5_confirmation.json --seeds <subset>             # bounded calls
```
