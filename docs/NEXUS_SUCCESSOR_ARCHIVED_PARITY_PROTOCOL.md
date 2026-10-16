# Successor search — archived-state/context parity protocol

## Locked scope

Branch `codex/successor-search-archived-parity`, from GitHub-matched
`f6230c5f87148986a42f612ff905353d1aa244f6`. User authorized continuation of the
previous audit. This is read-only engineering validation, not a new scientific
environment/controller comparison. No training, physics change, new environment
episode, return analysis, readout, reserved-split evaluation or runner integration.
The exhausted historical scientific session ledger is not reset or reused.

Configuration SHA256:
`47803e17bd4bc15cdff3a37da121a134d225924f3f9f7f2dff3c861eb0380897`.
The runner validates this hash and executable settings, refuses overwrite, requires
a clean committed implementation/protocol and checks base ancestry in its underlying
execution entry point. Commit implementation and protocol before checkpoint scoring.

## Question and competing failure modes

Does the opt-in batched successor scorer preserve the reference Q/action decision
on recorded controller observations with actual installed student context vectors?
Potential failures include batch-size numerical differences near action ties,
candidate-layout mistakes, incompatible frozen context installation, altered
normalization or loss of parity at late visited states. No architecture or
tolerance changes will be selected after seeing the parity outcomes.

The previous synthetic audit matched160/160 actions/rankings, but used synthetic
contexts. This audit fills part of that coverage gap. It cannot prove universal
bitwise parity or identical full-episode return.

## Existing inputs only

- `artifacts/late_episode_decision_trajectory.json`: complete thirty-decoder/task
  logs, observations and candidate seeds for both student and zero visitors,200
  steps each, on the three known Pendulum development physics. These are **older
  H=16-controller visited states**, not saved successful-lookahead trajectories.
- `artifacts/source_scalar_calibration.json`: exact six installed task context
  vectors and associated frozen model/normalization/context hashes. Require all
  sixteen rows of each context to agree and both visitor records to match.
- Ten original history-decoder checkpoint records, the fifty broad epoch200
  student encoder records, and committed checkpoint metadata. The already completed
  `latent_generalization_confirmation.json` is read **only for its published
  checkpoint metadata**, not query/prediction outcomes. It is not an unused reserved
  confirmation split. All checkpoints are hash-verified before loading and after
  the audit. No checkpoint is recreated or overwritten.

All input artifact hashes are locked in the configuration. Only observation,
candidate-seed, context and fingerprint fields are used; no return, reward,
prediction-success or query-error field selects inputs, contexts or thresholds.

Acrobot and MountainCar lookahead traces do not save the matching observation
streams needed for the same archived-state check. Their earlier synthetic-model
parity results stay unchanged. Do not reconstruct their states through a simulator
under this protocol, infer observations from rewards, or pretend this audit covers
archived states from those families.

## Exact grid and mechanics

Ten decoders × three tasks × two visitor groups × six phases × six contexts =
**2160 planned comparisons**. Phases are fixed **0,16,50,100,150,199**. Contexts:
zero and all five saved student seeds. No states are chosen by Q margin or return.
Each planned cell remains present even when two visitor observations coincide.
Report the unique decoder/task/observation count separately; cases, students,
phases and tasks are not independent model-training replications.

For each decoder/context install the exact saved student encoder (zero context
keeps the unchanged starting encoder). Install the archived z for the task. Check
the full historical frozen network/normalizer fingerprint and context hash against
the archive **before** scoring. Encoder inference is not rerun; no new support is
collected. Reference and batched paths use the very same model instance and
candidate matrix reconstructed from the archived phase-specific seed.

Both paths keep H16,16 sequences,three actions and native Pendulum reward. Preserve
the recorded Pendulum outer backup that ignores termination probability; keep
cumulative survival inside the tail. Score original first, then batched. Compare
and save Q values, selected actions, full stable rankings, exact frozen fingerprints
and actual per-path call/state counters. This audit does not retime the controller;
the prior CPU microtimings are not new evidence here.

## Numerical rule and decision

Retain **absolute Q tolerance2e-4 and relative tolerance2e-5**, as preregistered in
the first engineering audit. A near tie is a reference top-two gap no greater than
`2 × (atol + rtol × max(abs(reference_Q)))`. Save every gap and threshold and report
all near-tie cases, including any mismatches. This is a descriptive sensitivity
flag, not a mathematical worst-case floating-point bound.

Success on this grid requires **all2160 selected first actions identical** and all
Q vectors inside tolerance, with full grid/checkpoint/context integrity. Full
ranking agreement is reported separately; a change between losing actions cannot
be concealed but does not change the primary top-action rule. Every mismatch is
retained; no near-tie exclusion or new tolerance is allowed. No control-success
label, statistical return interval, meta-learning or AGI claim follows.

A complete finite run failing numerical/action parity is a valid negative
engineering finding (`archived_decision_parity_not_established`). Missing cells,
nonfinite numbers, cap failures or checkpoint/context changes are incomplete/invalid
executions, never scientific null evidence. Save partial rows and costs; no
automatic rerun. Tests must enforce the grid from configuration rather than from
produced seed/task/condition lists.

## Bounds and tests

CPU only, one Torch thread, **60-second** hard audit cap. Each pair uses1542
imagined transitions (771+771), for exactly **3,330,720** and **146,880 model calls**
on a complete run; no warmup/timing inference. Per-prediction time/state guards
stop before the next call exceeds its budget. Checkpoint loading, input validation,
scoring and final validation are inside the measured audit clock. Disk serialization
at the end may add process overhead; record incomplete results honestly if capped.
No real interactions or optimizer updates. This engineering allocation does not
spend or renew an expired scientific experiment allocation.

Tests cover config/hash locks, whole-seed/task/visitor/phase/context removal,
duplicates, malformed/nonfinite Q, action/argmax consistency, counter/fingerprint
changes, saved-context identity across archives, outcome-field independence,
near-tie classification, numerical versus incomplete execution distinctions,
and per-call time/transition caps. Reuse the original deterministic scorer tests.
An explicit local checkpoint request must fail if any requested binary is absent
or has a wrong hash. Git-only result arithmetic tests must not need binaries.

## Boundaries after the audit

No production/default controller switch in this branch. A passing finite archived
grid narrows engineering risk; it does not cover unseen inputs, actual lookahead
visited-state shift, other families' missing observations, or float kernels on
different hardware. A failure should identify the exact cells and numerical gaps
before any later mitigation is designed. Do not silently add fallback, precision,
kernel or action-rule changes and rerun on the same sample.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_successor_archived_parity.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/audit_successor_archived_parity.py \
  --checkpoint-root /absolute/path/to/original/nexus-ai
```
