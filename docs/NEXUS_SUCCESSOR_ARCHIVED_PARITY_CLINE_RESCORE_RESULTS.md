# Cline independent re-scoring — archived successor parity results

## Decision

The recorded 2160-cell archived-parity result is now independently verified
end-to-end, including fresh frozen-model inference. An independent Cline
re-scoring of the identical locked grid reproduced the recorded Codex artifact
**bitwise in all 2160 cells**: maximum fresh-versus-recorded Q deviation
**0.0** for both the serial reference and the batched scorer, all 2160 fresh
actions, full rankings and parity metrics identical to the recorded ones, all
**8 near ties** reproduced, and the fresh maximum absolute Q difference
**0.0000810850** identical to the recorded value. Label:
`independent_rescore_reproduced`.

This is verification of a recorded engineering result on tested archived
inputs, **not** universal bitwise parity on unseen inputs, a new control
result, cross-family weight transfer, learning-to-learn or AGI. The optimized
scorer remains opt-in; no default runner, historical controller, closed split
or closed screen was touched.

## What Codex had already completed (verified before re-scoring)

- `codex/successor-search-efficiency-audit` (`506ffc7`, results `f6230c5`):
  opt-in `PreparedSuccessorSearch` batching 51→17 model calls/forwards at
  unchanged 771 imagined transitions, 160/160 synthetic actions/rankings on 30
  frozen decoders, CPU microtimings 2.53–2.61×.
- `codex/successor-search-archived-parity` (`1ebb782` lock, `9c6ed4a`
  results): the archived-state parity audit — 2160/2160 actions, rankings and
  numerical comparisons on genuine archived observations with all five saved
  epoch-200 student context vectors plus zero, raw artifact
  `artifacts/successor_archived_parity.json`.

Independent review performed before any re-scoring: the offline arithmetic
verifier and the 93-test relevant offline suite were re-run and passed; fresh
arithmetic with independently written code reproduced every pooled number
(2160/2160, 8 near ties, max |ΔQ| 8.108498756342897e-05, minimum top gap
4.8908556716242835e-05, 322 distinct decoder/task/observation triples); all 60
checkpoint binaries matched their recorded hashes; observations and candidate
seeds map one-to-one into `artifacts/late_episode_decision_trajectory.json`;
the contexts are the genuine archived student vectors from
`artifacts/source_scalar_calibration.json` with fingerprint agreement across
both visitor archives; the reference scorer is the historical
`bellman_backup_control.lookahead_first_action`, and Pendulum's ignored outer
termination probability is preserved in both paths. Review alone could not
verify that the recorded Q values actually come from those checkpoints; only
fresh neural inference could close that gap.

## Fresh re-scoring mechanics

Branch `cline/successor-search-archived-parity`, implementation/protocol
commit `617c2265a4acb133e79059174a9dfd1c92b37792`, committed and tested clean
before the single execution. The run re-validated the locked configuration,
all six parent artifact hashes and the recorded artifact's own code hashes,
then re-scored all 2160 cells from the archives with hash-verified frozen
decoders, loaded student encoders and installed archived context vectors:
51/17 model calls per cell at 771 imagined transitions each, exactly as
recorded. Every per-cell frozen fingerprint was checked before and after; all
60 checkpoints were re-verified after scoring. Predeclared rules: fresh parity
gate 2e-4/2e-5, cross tolerance 1e-9; outcomes were not used to select any
rule.

## Cost

**12.669 s wall** (cap 120 s), **146,880 fresh model calls**, **3,330,720
fresh imagined transitions** (2160 × 1542), **0 real environment
interactions**, **0 optimizer updates**, CPU only, one Torch thread. This
verification does not spend or renew any expired scientific experiment
allocation.

## Tests

- Pre-execution guards: 10 passed (locked configuration, tamper rejection,
  recorded-grid identity, cross-check classification, label rules, per-call
  caps, repeated-run refusal, clean-tree requirement).
- Post-execution Git-only recorded tests recompute the committed artifact:
  full grid, per-cell action/argmax consistency, fingerprints, counters,
  cross-check recomputation against the recorded artifact, pooled summary and
  corruption rejection.
- The relevant offline repository suite was re-run after execution:
  **111 passed, 4 deselected in 4.73 s** (93 prior relevant tests plus the 18 new
  guard/recorded tests; the two deselections each are the same environment-
  stepping and local-binary exclusions as before). The full repository suite
  was not run; it contains training and environment collection outside this
  task.

## Provenance

Branch **cline/successor-search-archived-parity** from `9c6ed4a`.
Implementation/protocol and clean execution revision
`617c2265a4acb133e79059174a9dfd1c92b37792`; results committed separately.

- Raw `artifacts/cline_archived_rescore.json` SHA256
  `50f0551a8f149586df1b468b255194623b0c35bc037226d9784dd64b50ffd273`.
- Config `configs/cline_archived_rescore.yaml` SHA256
  `a9b65e1eafc5aaed11647072ddc0f3dd037eed5f33842f547e4a9d6598b24d95`.
- Protocol `docs/NEXUS_SUCCESSOR_ARCHIVED_PARITY_CLINE_RESCORE_PROTOCOL.md`
  SHA256 `9683094ad874a231dea364f0adc7b6dc54cff4e056bd69b77035aeed66543735`.

```sh
PYTHONPATH=src:/absolute/path/to/original/nexus-ai/.deps python3 -m pytest \
  tests/test_cline_archived_rescore.py tests/test_cline_archived_rescore_recorded.py \
  -p no:cacheprovider
# Executed once after the clean protocol commit; refuses a repeated run:
PYTHONPATH=src:/absolute/path/to/original/nexus-ai/.deps python3 \
  scripts/cline_verify_successor_archived_rescore.py \
  --checkpoint-root /absolute/path/to/original/nexus-ai
```

The original checkout's uncommitted MountainCarContinuous confirmation
preparation is untouched. `main` is unchanged. The Codex worktree, its branch
and all historical artifacts are unchanged.

## One next recommendation

The remaining gap before any controlled runner integration is strict
**full-episode serial-versus-batched parity** on paired fresh episodes, already
proposed in `NEXUS_SUCCESSOR_EPISODE_PARITY_PROPOSAL.md` (120 episodes,
24,000 new real steps, proposed 180-second cap). Archived parity plus bitwise
independent reproduction does not cover closed-loop divergence after an
unseen near tie. That proposal still requires a separate explicit bounded
authorization before implementation or execution; nothing here starts it.

