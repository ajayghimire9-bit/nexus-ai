# Evolution-2 Pendulum/Acrobot four-role instance rules

Status: **FOUR_ROLE_RULES_LOCKED_UNNAMED**.
Parent: `80d93e60f5fd132b51d324ccadb3b1acceebf8d0`.
Does **not** name a holdout, persist a physics tuple, rewrite
v1/v2/v2-pilot hashes, collect data, or unlock H17.
Ledger **305.842 / 3294.158**.

## 1. Why this lock exists

The unused-instance review was **NAMING_BLOCKED** because
`e2_pendulum_acrobot_dev_v1` is Acrobot-only and v2 needs four
disjoint roles. This lock adds a regular Pendulum grid and a
predeclared assignment order. It still does not persist tuples.

## 2. Pendulum unused-instance grid

Regular lattice around Gymnasium defaults. Not a shopped list of
convenient leftover keys.

| Axis | Values |
|---|---|
| `g` | 5.0, 5.5, …, 15.0 (step 0.5; 21 values) |
| `m` | 0.60, 0.65, …, 1.40 (step 0.05; 17 values) |
| `l` | 0.60, 0.65, …, 1.40 (step 0.05; 17 values) |

Grid size: **6,069**. Occupied keys off the lattice remain occupied
and cannot become new sources. Default `(10, 1, 1)` is on the
lattice and is occupied.

Rule name: `e2_pendulum_acrobot_pendulum_v1`.
Walker: the existing `unused_instance_from_rule`.

## 3. Four-role assignment

Order is locked before any draw. Later roles exclude earlier draws
from the same family.

| Order | Role | Rule | Counter |
|---|---|---|---|
| 1 | acrobot_development | `e2_pendulum_acrobot_dev_v1` | 0 |
| 2 | acrobot_source | `e2_pendulum_acrobot_dev_v1` | 1 |
| 3 | pendulum_source | `e2_pendulum_acrobot_pendulum_v1` | 0 |
| 4 | pendulum_development | `e2_pendulum_acrobot_pendulum_v1` | 1 |

Acrobot development keeps the already-published digest
`f63b54f2ed140915b4ac8b3fd924bc7ae0c5c754496e417784603a206ea72f19`.
The other three roles are recorded as digests only.

`hold_named` stays **false**. `LOCKED_TARGET` stays **null**.

## 4. What this lock does not do

- No Gymnasium construction, training, or env steps.
- No plaintext physics tuple in this document or the artifact.
- No rewrite of v1, v2, or v2-pilot hashes.
- No H17 unlock and no MCC physics.
- No claim that locked rules authorize collection.

CPU enforcement, trusted checkpoints, balanced dispatch, and
`authorized: false` remain independent blockers.

## 5. One next scientific action

Do **not** collect and do **not** persist the four tuples. Next:
a residual-MLP timing probe on existing checkpoints, or a later
independent naming authorization that must match these four
digests exactly.
