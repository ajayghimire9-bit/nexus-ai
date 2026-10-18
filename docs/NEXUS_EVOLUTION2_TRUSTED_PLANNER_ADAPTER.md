# Evolution-2.1 trusted planner adapter and CPU feasibility

Status: **engineering milestone**. Not a scientific result.
Branch: `cursor/evolution2-trusted-planner-adapter`
Parent: `1ccaec76afc508571a261200b56c3121dcd39323`

No collection. No named holdout. H17 blocked. Ledger
**305.842 / 3294.158**. v2 hashes are unchanged.

Reused, not replaced: Evolution-1 catalogue/`plan_bound`,
`RandomShootingMPC._score_batch`, family rewards, `reviewed_binding`,
`ReservationLedger`, `EvolutionarySearch`.

Did **not** use `planning.mpc_for_model`. Did not change historical
lookahead modules.

## 1. Compatibility matrix

Source: `nexus.evolution2.planner_adapter.compatibility_matrix()`.

| Family | Rule | Generator | H | Candidates @1536 | Status |
|---|---|---|---|---|---|
| Pendulum / Acrobot | flat | iid | 4/8/16 | 384 / 192 / 96 | IMPLEMENTED catalogue-faithful |
| Pendulum / Acrobot | successor | iid | 4/8/16 | 127 / 63 / 31 | IMPLEMENTED catalogue-faithful |
| Pendulum / Acrobot | either | balanced_first_action | 4/8/16 | same counts | IMPLEMENTED in adapter; **DISPATCH_BLOCKED** by existing host validator |
| Other families | — | — | — | — | out of v2 scope |

Historical H=16 × 16 IID scoring rules match:

- Pendulum successor: `Q = r + max V_H(s')` (`ignore_root_probability`)
- Acrobot successor: `Q = r + (1-p) max V_H(s')` (`multiply_root_survival`)
- Tie-break: first NumPy `argmax`
- IID draw: `numpy.default_rng(seed).integers`

Those historical functions still require a 16×16 array. Catalogue
successor H=16 at cap 1,536 uses **31** tails, not 16. That is
catalogue-faithful, not a silent relabel of the historical 16×16
controllers.

No variant was substituted. Balanced remains dispatch-blocked.

## 2. Evolutionary baseline

`EvolutionarySearch` now keeps a population of 4 scored variants and
selects a parent by tournament 2. Mutation still flips one catalogue
coordinate. Crossover raises. Cold start with no feedback still
returns `available[0]`, which preserves the previous synthetic
contract test. Fitness does not persist across `reset_task`.

## 3. CPU feasibility

Locked v2 worksheet remains 97,600 real steps and 110,592,000
imagined transitions. Authorized caps stay 0.

**Measured historical evidence** (`NEXUS_BELLMAN_BACKUP_CONTROL_RESULTS.md`):
68.146 s wall for 12,324,000 imagined states
→ 5.529 µs / imagined state
→ **611.6 s** extrapolated to 110,592,000 imagined states.

That historical rate already consumes most of the 900 s standing
grant **before** source fitting of 20 family models, development
episodes, and method overhead.

**Non-scientific fake-model microbenchmark** (this branch, 8
successor decisions, 11,928 imagined states, 0.00612 s wall):
0.513 µs / imagined state, **56.7 s** if naively scaled to
110,592,000. That is adapter-plus-linear-fake-model overhead
only. It is **not** interchangeable with historical residual-MLP
planning (5.53 µs / state, 611.5 s). No Gymnasium, checkpoint, or
ledger debit.

**Verdict:** the full v2 screen is **likely `incomplete_budget`**
under 900 s on local CPU if historical residual-MLP cost applies.
v2 is not rewritten. A later prospective **v2-pilot** could keep
n=10, Bonferroni, and all five controls while evaluating only the
six revealed rows per family (no unused-variant matrix) and two
development conditions. That is a new versioned design, not a
silent v2 change.

## 4. Scientific execution boundary

| Gate | Status |
|---|---|
| Catalogue-to-planner scoring adapter | **PASS** (fake models) |
| Request-to-reservation digest bind | **PASS** (existing host) |
| Pre-call imagined `plan_bound` | **PASS** |
| Measured CPU / wall | **PASS** (measurement) |
| Worker CPU enforcement | **BLOCKED** |
| OS / filesystem sandbox | **BLOCKED** (process ≠ sandbox) |
| Balanced dispatch | **BLOCKED** |
| Frozen real checkpoint identity | **BLOCKED** (fixtures only) |
| Real planner / env / training | **BLOCKED** |
| Scientific authorization | **BLOCKED** |

`authorized=false`. Subprocess isolation is not a security sandbox.

## 5. Remaining blockers

1. Trusted real checkpoints and family adapters that construct envs
   only after authorization.
2. CPU enforcement, or an explicit `incomplete_budget` policy.
3. Independent unused-instance naming.
4. Host dispatch of balanced generators, if those variants stay in
   the catalogue.
5. Separate authorization citing v2 hashes.

## 6. One next scientific action

Do **not** collect. Lock a prospective **v2-pilot** worksheet that
keeps n=10 and the Bonferroni five-control rule while reducing
imagined work to the six revealed rows, and say honestly that full
v2 likely censors at 900 s. Holdout stays unnamed.
