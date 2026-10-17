# H17 protocol-readiness review — source only, NOT LOCKED

## Outcome

The five-source/t12 proposal now has executable draft validation, a
collision-checkable symbolic RNG schema, a native-state replay-record
contract and a strict checkpoint-file manifest audit. **98 source-only
tests passed.** These are engineering checks, not scientific findings.

The review returns **`not_lock_ready`**, with `locked=false` and
`authorized=false`. No unused physics or numerical experimental seeds
were selected. No allocation, training, simulator, inference, imagined
transition or scientific execution occurred. The experiment ledger stays
**305.842 seconds used / 3294.158 remaining**.

Branch: `codex/h17-protocol-readiness`. Clean starting SHA and verified
GitHub feasibility reference:
`5436893dc8a361f0894e848cd68fac23a921e98c`. Origin was fetched. The prior
H16/H17 reports, raw results, allocations, checkpoints, AGENTS, master
context and main are unchanged. No previous holdout was reopened.

## Scientific scope retained

One prospective factorial contrast remains proposed:

`I_s = mean_nested[(D_multitask_fixed + D_scratch_fixed +
                   D_multitask_redraw + D_scratch_redraw)/4 − D_reference]`

where `D_p = (S_mt,L0 − S_sc,L0) − (S_mt,redraw − S_sc,redraw)` at the
same state from source p. Average inside ten independent training pairs
before the df9 Student-t interval. No alternative favorable source may
replace the mixture primary. Within-library oracle opportunity cancels.

The draft uses directional dependence, zero practical margin and critical
value2.262. That can establish a direction if subsequently locked and
tested; it cannot establish a practically useful controller benefit. A
zero-crossing interval is inconclusive, not invalid. Missing/failed cells
are a separate integrity failure and must not receive a scientific label.

Trajectory L0 remains attached to all five source policies, including the
reference. Generator redraw and diagnostic redraw are independent streams.
Since the learned state depends on L0, this remains a **joint state/library
distribution** diagnostic. It would not causally explain H14/H15, and the
zero-margin decision is not a control-success rule.

## Implemented contracts

### Configuration is connected to the arithmetic

`configs/h17_occupancy_draft.json` is validated by
`src/nexus/h17_protocol_readiness.py`. The check enforces the declared
ten pairs, five sources, one reset, t12, H16,16 candidates, equal-source
estimand, interval, coupling and resource counts. Nested numeric types are
checked: `[12.0]` cannot silently substitute for integer `[12]`; a boolean
cannot replace a count. Missing, unknown or altered fields fail closed.

The draft's target physics, exclusion manifest, numerical seed map and
checkpoint manifest are intentionally null. The readiness tool refuses to
convert the draft into a lock by filling them in. A later registration must
be a separately reviewed protocol/configuration, not a silent edit to this
record. This draft and its300-second proposal are not an allocation.

### RNG schema — 480 symbolic keys, no numerical allocation

Per independent pair:

- Six keys: model initialization, continued-training minibatches, reset,
  reference actions, L0, diagnostic redraw.
- Eleven generation-redraw keys, for decisions1–11.
- Eighteen source-reset keys and three source-behavior keys, for the three
  source physics with six reset seeds each.
- Six target-training reset keys, one target-training behavior key, two
  target-validation reset keys and one validation-behavior key.

Thus48 keys/pair ×10 =480. One model-initialization key is deliberately
shared between model arms as paired initialization; it is not an extra
independent replication. Reset/L0 keys omit the source label; generation
redraw keys omit the model arm. Both redraw generators therefore receive
the same proposals. Diagnostic redraw is a distinct namespace. Replay uses
stored actions and creates no additional policy-RNG draws.

`validate_seed_mapping` checks a supplied future mapping against this exact
key set, duplicate keys, duplicate numerical seeds, uint32 range, strict
integer types, extra/missing entries and overlaps with supplied closed IDs.
It does **not** generate numerical seeds or certify that a caller supplied
the complete closed registry. Completeness and provenance of that registry
remain a pre-lock requirement. Test mappings are synthetic only and are
not saved as scientific seed registrations.

### Native-state identity closes a precision gap

The historical H16 runner casts raw state to float32 before equality.
Two distinct float64 states can therefore pass that representation-level
comparison. Historical H16 results are not rewritten or invalidated here.

The proposed H17 contract retains observation comparison at float32 but
compares **native raw states at float64**, including the reset state.
Prefix rewards remain float64, and actions, source/reset identifiers,
elapsed count and termination flags must match. Comparison is bitwise at
the declared representation, including signed zero. A one-ULP state drift
that disappears under float32 conversion is rejected in a deterministic
test. Wrong reset/source, early termination, reward/action drift, dtype
change and elapsed-step mismatch also fail.

This consumes supplied mock records only; it does not reset or construct
an environment. A future runner must capture native state before any
float32 conversion, check the actual wrapper stack and reward timing,
and enforce this gate during counted reset-plus-prefix replay. Empirical
restoration success for fresh physics remains unknown.

### Checkpoints — strict byte audit, no neural deserialization

`validate_checkpoint_manifest` requires exactly20 distinct files and the
complete ten-pair × multitask/scratch grid. It checks file existence,
SHA256, unique paths, no path escape, exact residual MLP(64,64) metadata,
two observations/three actions, and finite normalization metadata.
Any explicit audit fails on missing or corrupted files; it never skips.

Tests use small synthetic byte files, not trained checkpoints. The tool
does not call Torch or load any historical network. A byte audit alone
does not prove that metadata describes tensors inside a file. A future
runner must verify reconstructed architecture, normalization and live
parameter fingerprints and preserve them before/after all inference. No
actual H17 checkpoint manifest exists; no real checkpoint-integrity pass
is claimed.

## Remaining blockers

1. A complete, versioned closed/active MCC physics exclusion inventory and
   subsequent prospective target registration, without outcome-based choice.
2. A numerical seed mapping checked against the full frozen closed-seed
   registry, including training initialization and behavior streams.
3. A future guarded runner that saves model/data manifests and checks live
   parameter/normalization fingerprints. Fresh future model pairs must not
   replace historical binaries or rerun consumed H14/H15/H16 entry points.
4. Native-state restoration, reward, wrapper, complete-grid, timeout and
   interaction gates integrated into that runner. Any empirical preflight
   must be budgeted, not an uncounted preliminary experiment.
5. Independent review and commitment of the final protocol before any
   separate authorization or collection.

These blockers are explicit in the readiness output. Passing synthetic
tests does not remove them. No original experiment permission is revived.

## Resources and commands actually run

The connected draft still computes **62,360 planned real steps** and
**174,080 planned imagined transitions**. The suggested total runtime cap
is300 seconds, with the inherited5–30s estimate on the same local CPU;
none is allocated. Source-only engineering does not debit or reset the
scientific execution ledger. Actual new scientific interactions and
training updates in this task are all zero.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_h17_protocol_readiness.py tests/test_h17_occupancy_feasibility.py tests/test_h16_selection_mechanism_diagnosis.py -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 scripts/review_h17_protocol_readiness.py
```

Result: **98 passed in0.88s** (32 new readiness checks,36 H17 feasibility,
30 H16 diagnosis). The read-only review completed and reported
`not_lock_ready`. Isolated subprocess tests reject NumPy, Torch, Gym and
world/task/RL imports while reviewing the real draft. Historical input
hashes and the session ledger remain verified. No full simulator/training
suite was run or claimed. Draft configuration SHA256:
`4eb9401465744e2f29d026b9a42f6480015c1774cf66f676018eeaf256b45f0f`.

## One next recommendation

Complete a separately scoped H17 registration and independent lock review,
using the existing five-source/t12 estimand and these fail-closed contracts,
before implementing or authorizing scientific execution.
