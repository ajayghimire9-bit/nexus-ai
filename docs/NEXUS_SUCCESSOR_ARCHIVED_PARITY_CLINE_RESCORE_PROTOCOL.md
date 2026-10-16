# Cline independent re-scoring of archived successor parity — protocol

## Locked scope

Branch `cline/successor-search-archived-parity`, from
`9c6ed4aa75b3fe430514ea77bf44064faaf34011` (tip of the completed Codex
archived-parity audit chain `f6230c5` → `1ebb782` → `9c6ed4a`). The user's
2026-10-16 task authorizes read-only code inspection, archived observations,
frozen-model inference and lightweight tests. This is an **independent
verification of a recorded engineering result**, not a new scientific
experiment: no environment episode, physics change, model training, candidate
change, tolerance retuning, closed-split evaluation, budget reset, confirmation
scoring or controller/runner integration.

The original checkout's uncommitted MountainCarContinuous confirmation
preparation stays in place, untouched; this isolated worktree holds this branch
only. `main` is unchanged. The Codex worktree and its branch are untouched.

## Question

Does fresh frozen-model re-scoring of the locked archived 2160-cell grid,
using hash-verified checkpoints and the genuine archived student context
vectors, reproduce the recorded reference and batched Q values, actions,
rankings and parity metrics? Prior review already verified the recorded
arithmetic, provenance and checkpoint hashes; only fresh neural inference
remained unverified. No rule is selected after seeing the outcomes.

## Existing inputs only

The identical locked grid and parents of `configs/successor_archived_parity.yaml`
(10 decoders × 3 tasks × 2 visitors × 6 phases × 6 contexts = 2160 cells),
observations and candidate seeds from `artifacts/late_episode_decision_trajectory.json`,
genuine saved student contexts from `artifacts/source_scalar_calibration.json`,
60 hash-verified frozen checkpoint binaries, and the recorded result
`artifacts/successor_archived_parity.json`, read only as the cross-check
reference. The recorded artifact's own code hashes must match the current
files before any scoring, pinning the reused audited implementation to the
code that produced the recorded result. No reward, return or query-outcome
field selects any input, context or threshold.

## Mechanics

Score every cell with both the historical serial Pendulum successor scorer and
the opt-in `PreparedSuccessorSearch`, exactly as recorded: 51 versus 17 model
calls at 771 imagined transitions each. Re-verify all 60 checkpoint hashes
before and after scoring; verify frozen model/normalizer/context fingerprints
per cell. Cross-check every fresh Q vector against the recorded one and
recompute the recorded parity metrics from fresh values.

## Predeclared numerical and decision rules

- Fresh parity gate (unchanged from the recorded audit): every cell's fresh
  actions and rankings identical and Q within 2e-4 absolute / 2e-5 relative.
- Cross tolerance: fresh-versus-recorded maximum deviation ≤ **1e-9** for both
  scorers in a cell.
- `independent_rescore_reproduced`: complete grid, fresh parity 2160/2160,
  all fresh actions equal the recorded actions, all cross deviations ≤ 1e-9
  and all fresh parity metrics identical to the recorded metrics.
- `independent_rescore_confirmed_within_tolerance_not_bitwise`: complete grid
  and fresh parity with agreeing actions, where cross deviations exceed 1e-9
  but stay within the 2e-4/2e-5 audit tolerance.
- `independent_rescore_disagrees`: any action mismatch, fresh parity failure or
  cross deviation beyond tolerance. This is a valid negative verification
  finding; it never silently becomes incomplete.
- Missing cells, cap failures, corrupt checkpoints or changed fingerprints
  make the run `invalid_or_incomplete_execution`, never evidence for or
  against parity. No automatic rerun on the same sample.

## Bounds

CPU only, one Torch thread, **120-second hard cap**, **3,330,720 fresh imagined
transitions** (2160 × 1542), **146,880 fresh model calls**, **0 real environment
interactions**, **0 optimizer updates**. All checkpoint files are read-only.
The output `artifacts/cline_archived_rescore.json` is a new file; no historical
artifact is overwritten and the repeated-run/clean-tree guards apply.

## Tests and boundaries after the audit

Lightweight guards cover the locked configuration, recorded-grid identity,
cross-check classification, label rules, per-call caps and the repeated-run
refusal. A Git-only recorded test recomputes the committed artifact arithmetic
without binaries. A passing verification narrows engineering risk before any
later integration; it does not cover unseen states, other families' missing
observation streams or a changed default runner. The next proposed validation
remains the bounded full-episode parity proposal; nothing here authorizes
episodes, and no control-improvement, learning-to-learn or AGI claim follows.

```sh
PYTHONPATH=src:/absolute/path/to/original/nexus-ai/.deps python3 -m pytest \
  tests/test_cline_archived_rescore.py -p no:cacheprovider
PYTHONPATH=src:/absolute/path/to/original/nexus-ai/.deps python3 \
  scripts/cline_verify_successor_archived_rescore.py \
  --checkpoint-root /absolute/path/to/original/nexus-ai
```
