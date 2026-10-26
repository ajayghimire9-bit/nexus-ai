# Wave 29 — Occam-margin certification and mandatory out-of-sample verification (locked before 4021–4025, 5021–5025, 6021–6025)

Branch `codex/wave29-occam-margin` (from Wave 28 `d06f2a2`). Owner design, 2026-10-26.

Code:
* `src/nexus/wave29_core.py`: the Wave 28 engine text, with the changes below.
* `src/nexus/wave29_eval.py` and `scripts/wave29_confirm.py`: unchanged loops and driver.
* `tests/test_wave29_core.py`: 2 tests.

## Changes

1. **k_min + 1 shell.**
   * In the core tier and every repair tier (library, ΔB, ΔC, ΔM), a certificate is no longer issued from the
     minimal size alone. The next size shell, within the tier depth, is enumerated too (Searcher `level()` plus
     macro completions).
   * UNIQUE requires every fitting program in both shells to agree on the query. If the shell can't be finished
     within budget, the tier is not UNIQUE.
   * Only the base tier keeps the plain minimal-size certificate (Occam convention).
   * A test reproduces the Wave 28 ΔB false certificate and shows that the shell makes it AMBIGUOUS, with the
     teacher's answer present in the shell.
2. **x_verify.**
   * No non-core route may certify from passive public examples alone.
   * One verification input is synthesised from observed items only (domain-free; also valid on sealed lists):
     reorderings, a duplicated item, a dropped item, or concatenations of two inputs.
   * It is chosen to maximise distinct predictions among the certified programs (all tiers), the identity,
     every proper sub-program ablation and the shell alternatives. Ties go to inputs the certified program
     changes.
   * One charged oracle call. If no certified program predicts the answer, the pair is appended and the tiers
     are re-certified, with the remaining S3 probe budget. Only an answer that stays UNIQUE is issued.
3. **Core audit.** It uses the same rich x_verify input instead of a reordered query (demotion semantics
   unchanged).

## Pre-lock verification on the Wave 28 false-certificate units

These Wave 28 confirmation seeds are now **Wave 29 development data**: 4019, 4020, 5019, 6016, 6017.

**All 8 recorded false certificates → 0.**
* Phase 4: 2 → 0.
* Phase 5: 5019:11:2 is now AMBIGUOUS.
* Phase 6: Fresh 2 → 0, Placebo 2 → 0, Experienced 1 → 0 (the last one needed the shell in the core tier too).

**Residual: one new false certificate** appeared in the same stream, at 5019:5:1.
* It is a core-tier answer in a no-hidden-mechanism world; the teacher is a ΔB rebinding outside the core tier's
  space, and the single audit input passed.
* Finite probing cannot exclude every coincidence. This is declared, not fixed.

**Coverage cost.**
* Phase 4: 32/42 and 33/42 solved per seed (Wave 28 on the same seeds: about 40/42).
* Phase 6: Fresh and Placebo solve 9 per stream (Wave 28: 10–13).
* Phase 5 stream 5019: 48/64 solved.
* Work rose: Phase 4 about 2.1M per seed.

## Confirmation protocol (unchanged gates; fresh one-use ranges; checkpointed; sequential replays per artifact)

* **Phase 4 (4021–4025):** the Wave 26 gate.
* **Phase 5 (5021–5025):** the Wave 26 gate.
* **Phase 6 (6021–6025):** compositional targets. The Wave 28 primary gate: cost, AUC and coverage in 5/5, plus 0
  false certificates. Raw slope is secondary.
* **Standing gates:** G_soundness, G_replay, G_tycho.
* **No sealed pass in this wave.** The owner did not request one.

**Expected outcomes (declared).**
* False certificates far below Wave 28's 8, but possibly not 0 (see the residual).
* Coverage is lower, so the Phase 4 solved ≥ 80% condition and the Phase 6 coverage condition are at risk.
* The Phase 5 revisit gate is at risk from the higher per-task cost.

**Budget at lock:** 11162 s remaining (≤ 900 s per call).

**Locked code sha256 (first 16 hex digits):** `wave29_core.py`, `wave29_eval.py`, `wave29_confirm.py` = 487aba7b41597c42 5dc701a67a92707d 74fb9a921c6cedd0 

## Confirmation results (locked `4cda0cf`; fresh seeds; replays 15/15 identical; G_tycho pass)

**Runs.** Phase 4: 226 s. Phase 5: 871 s. Phase 6: 704 s.

**Artifacts (sha256, first 16 hex digits).**
* Phase 4: `706d3df76d452c49`.
* Phase 5: `7129ad4dd7bfdbec`.
* Phase 6: `638c885fefe7b614`.

| Phase | Gate | Result |
| --- | --- | --- |
| all | **G_soundness** | **PASS: 0 false certificates in all three phases** (Wave 28 on its seeds: 8) |
| 4 (4021–4025) | router | PASS: 90/90 routed (ΔB 25, ΔC 28, ΔM 26 solved) |
| | primitives | **FAIL**. F 6/10 streams, 37/40 solved (31k → 90k). S 1/10, **31/40 solved** (16k → 64k). Sort 8/10, 36/40 (3.9k → 3.0k) |
| 5 (5021–5025) | revisit | **FAIL**: 0.711 / 1.509 / 1.835 |
| | interference | PASS: 5.1% |
| | retirement | **PASS**: 15/15 retired, 0 false certificates |
| | solved | 273/328 (83%) |
| 6 (6021–6025, compositional) | cost | 3/5 |
| | AUC | 3/5 |
| | coverage | 5/5 |
| | joint | **3/5: FAIL** |
| | raw slope | 3/5 |
| | false certificates | 0 |

**Reading.**
* The Occam-margin shell plus x_verify removed every false certificate on fresh seeds.
* The price is coverage and cost.
  * Disagreement and verify probes withdraw certificates (Phase 4 S 31/40; Phase 5 83% solved).
  * Probationary and library reuse now pays for the shell search and verification, so reuse is dearer than
    invention (F, S) and revisits are dearer at lags 10 and 20.
* No phase passes all its gates.
