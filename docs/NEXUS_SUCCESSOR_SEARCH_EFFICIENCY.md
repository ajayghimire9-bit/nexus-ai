# Exact successor-search efficiency audit

## Scope and recovered provenance

Engineering audit authorized by the user's migration task. No environment episodes,
neural training, controller-comparison experiment, reserved-outcome access or expired
budget reuse. The earlier replanning-readout proposal is superseded by recovered
research history; it was not implemented or executed in this task.

Both remotes were fetched. `github/cursor/lookahead-generalization-synthesis` is
`f3898f6` and is an ancestor of the chosen starting revision:
**57cbf25b8a1f93210bce383846d05910248a6517**, the completed prefix-max result.
Branch **codex/successor-search-efficiency-audit** uses an isolated worktree.
The original checkout's uncommitted MountainCarContinuous confirmation preparation
is preserved and excluded. `main` is unchanged. No older branch is treated as current.

Read AGENTS/master, latest progress/hypothesis/next-experiment entries, synthesis,
prefix-max report, family lookahead implementations and compute-matched reports.
The successful mechanism is reused planning with family-specific world models,
not shared learned weights or learning-to-learn. Pendulum and MountainCar retain
compute-matched evidence; Acrobot did not meet the practical margin. Nearest reuse
**−14.751 [−37.142,+7.641]** and prefix-max **−9.832 [−31.108,+11.445]** stay closed.

## Implementation review and bottleneck

For each of three first actions the current controller makes one model call,
then sixteen calls with sixteen candidate states each. This is **51 model calls**,
**51 neural forwards** for the current single-network adapters, and **771 imagined
transitions** (3 + 3×16×16). The Python outer action loop serializes independent
successor trees. Each call repeats NumPy/PyTorch conversions, observation
normalization, one-hot creation, `eval`/`no_grad` entry and output conversion.
The FiLM adapter additionally snapshots its fixed context on every call.

The neural architecture itself is unchanged: residual 64×64 MLPs for Acrobot and
MountainCar; the fixed Pendulum FiLM model and eight-dimensional context. No GPU,
ensemble, fitted value function or approximate reuse is introduced. Sequential
dynamics dependencies still require sixteen tail time steps.

Important actual-code distinction: Pendulum `bellman_backup_control` computes
`r + max(tail)` and ignores the **outer** termination probability. Acrobot and
MountainCar compute `r + (1-p) max(tail)`. All retain cumulative survival inside
the tail. The synthesis's generic formula must not replace Pendulum's recorded
behavior. Reward timing is native current-state torque cost for Pendulum and
successor dense height for the other two; these are not the sparse Gym benchmarks.

## Exact optimization, opt-in only

`PreparedSuccessorSearch` predicts all three first-action successors in one batch,
then scores all 3×16 successor candidates in a batch of48 at each of sixteen ticks.
The candidate matrix is copied once, tiled into contiguous time-major action
vectors, and may be shared across context conditions. Two local writable action
copies keep the cached matrix protected and avoid read-only NumPy/PyTorch warnings.
Candidate order, duplicated sequences, smallest-index ties, rewards, clipping and
survival accumulation order **within each trajectory** are preserved.

This is **17 calls/forwards**, a structural66.7% reduction in dispatches; the number
of imagined transitions remains **771**, not259 or256. Forward-call reduction is
not a promised threefold wall-time speedup: batch48 performs more arithmetic than
batch16, and CPU kernels and allocations matter. Memory for simultaneous tail states
triples from16 to48; stored action table is48×16 int64 (6144bytes), plus a writable
working copy. No unbounded cache is retained. The temporary score/alive arrays grow
from16 to48. Model parameters and normalization are unchanged.

Different successor states generally do **not** have interchangeable tails even
though action sequences are shared. Reusing a tail across different roots would be
an approximation. Exact identical-prefix sharing is a possible later engineering
optimization, but is not implemented here: it needs branch-state and floating-point
parity tests. Failed nearest/prefix-max values are not retried. Tensor-native unrolls,
normalization fusion or compilation are also deferred; they change numerical paths
and require separate validation.

The new scorer rejects GRU, unknown stateful models and simulator adapters. Only
known row-independent models (or explicit row-independent toy adapters) are accepted.
Historical runners, checkpoint loaders, rewards and `RandomShootingMPC` are unchanged.
No default controller is switched to the optimized path.

## Declared deterministic audit

Executable configuration: `configs/successor_search_efficiency.yaml`, strictly
checked against runtime settings. CPU, one Torch thread, maximum30seconds.
This is a lightweight implementation audit, not a scientific control budget.

1. Unit tests compare original family functions with the batched scorer on
   elementwise toy dynamics: require bitwise Q equality, identical rankings/actions,
   all tail scores, clipped termination, rewards, duplicate/tie handling, candidate
   pairing and exactly51 versus17 calls at771 states in both paths.
2. Neural-code tests use deterministically initialized **untrained** MLP/FiLM
   models; no optimizer or gradient update. Absolute Q tolerance **2e-4**, relative
   **2e-5**; selected actions must match on tested inputs.
3. Explicit read-only checkpoint audit loads ten original decoders per family,
   each verified from committed source-checkpoint hashes **before** loading and
   again after evaluation. It reads only checkpoint metadata from the replication
   manifest/parent config and the development compute-matched configs, not reserved
   confirmation outcome artifacts. Missing/altered binaries fail; no retraining.
4. Four synthetic observations and candidate matrices per model, two fixed contexts
   (zero and `linspace(-.2,.2,8)`) for Pendulum: **160 planned cells**, not a new
   physics/episode sample. Record raw Q, selected actions, ranking agreement and exact
   weights/normalization/context fingerprints. The nonzero vector is synthetic,
   not a newly inferred or historically confirmed student latent.
5. Warm up each method twice; seven alternating-order timing blocks, three decisions
   each, on seed0 per family. Exclude candidate generation from both timed paths;
   reference planner construction remains in the original family function. Report
   medians and raw timings, not statistical evidence of return improvement. Pendulum
   timing uses the final synthetic nonzero context. Source file hashes/dependencies
   and clean execution revision are saved with the audit.

Float32 matrix kernels can change rounding when batch size changes. Mathematical
equivalence is **not** universal bitwise equivalence. The audit reports full ranking
and action disagreements, even when Q differences satisfy tolerance. A near-tie can
change an argmax. Do not assert universal decision parity from a finite input grid.
Numerical failures, missing cells or changed fingerprints make the audit invalid;
an action mismatch means decision parity was not established. No tolerance tuning
from outcomes and no automatic rollout or scientific retest follows.

## Gate for any later scientific evaluation

Before deployment require a separately authorized, locked **recorded-state** parity
audit covering all saved student contexts and near ties, with explicit numerical
failure handling. If new environment episodes are needed, request separate
authorization with exact episode/interaction/time caps and a decoder-level paired
noninferiority rule. No such run is authorized or launched by this document.
This task establishes engineering properties on tested inputs only; not improved
control, cross-family weight transfer, learning-to-learn or AGI.

## Reproduction

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_successor_search.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/audit_successor_search_efficiency.py \
  --checkpoint-root /absolute/path/to/original/nexus-ai \
  --output artifacts/successor_search_efficiency.json
```

Checkpoint binaries are intentionally outside Git; the explicit audit fails in a
fresh clone until its original binaries are supplied. Toy/neural-code unit tests
require no saved checkpoints. Do not recreate an existing output or rewrite old
artifacts to obtain a different result.
