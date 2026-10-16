# MountainCarContinuous lookahead versus H=16 — confirmation transfer results

## Decision

The complete 60-episode confirmation grid on the new unused holdout
`bc7c74c781c9e24f` passed the predeclared 25-point rule: lookahead minus H=16
**81.518 [55.450, 107.586]** (student-t 95%, df 9, n = 10 training seeds).
Label `mountaincar_continuous_lookahead_transfer_established`. Nine of ten
seeds were positive (per-seed gains from −0.939 to 122.640); H=16 mean return
−70.568 [−83.458, −57.677] versus lookahead mean 10.950 [−13.814, 35.715].

The frozen development lookahead package transferred to new MountainCarContinuous
physics without retuning: dense valley-height reward, discretized force,
H=16 × 16 candidates, frozen residual recipe (1024+256 transitions, 20 epochs),
no goal termination, 200-step TimeLimit. The development split stays closed and
H=16 was not retuned. This confirms the development result (69.758 on the
closed development split) on disjoint confirmation physics.

This is transfer of an established algorithm with separately trained family
models. It is **not** cross-family weight learning, not learning-to-learn,
not AGI.

## Cost

**27.054 s wall** (300 s cap), **24,800 real steps** (12,800 training
collection + 12,000 control), **6,162,000 imagined transitions**, **200
frozen-recipe training epochs** (10 models × 20), local CPU, one execution
after the authorized allocation. Ten new world models were trained on the
source task `mcc_default` with new collect seeds (340000/345000 blocks);
development checkpoints were not reused. Session ledger: 108.341 s consumed
before this run, 27.054 s for this run, 3464.606 s of the standing 3600 s
session allowance remains.

## Integrity

The allocation binds config SHA256 `24ce8c85…` and protocol SHA256
`c5614a61…`; the rule `mcc_lookahead_confirm_v1` reproduced the locked physics
exactly and the holdout is disjoint from the source and the closed development
physics; reset/step seeds (32000000/32100000 blocks) are disjoint from the
closed registries. The independent Git-only results audit passed: saved label,
per-cell reward reconstruction, return-gain identities, 30-cell grid and
controller identity flags all verified.

## Provenance

Branch `cursor/mountaincar-continuous-lookahead-h16-confirm`.

- Lock commit `5a8f9f2` (prepared confirmation protocol + implementation +
  tests; collection unauthorized).
- Authorization commit `00e8d7d` (one-run allocation citing the human standing
  grant of 2026-10-16 and the explicit continue/full-authorization
  instructions; bound hashes; session usage record).
- Executed exactly once after `00e8d7d` with a clean committed tree; no retry.
- Raw `artifacts/mountaincar_continuous_lookahead_confirm.json` SHA256
  `524bcd92ea4e5b10d6a6ec837a10fb2ca9ba639de0902beba8a7fe9d72f2579e`.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_mountaincar_continuous_lookahead_confirm.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_mountaincar_continuous_lookahead_confirm.py --results-audit
```

The exhausted historical scientific ledger was not reset; the standing
2026-10-16 development budget funded this one run. No closed screen, split or
budget was reopened. `main` is unchanged.
