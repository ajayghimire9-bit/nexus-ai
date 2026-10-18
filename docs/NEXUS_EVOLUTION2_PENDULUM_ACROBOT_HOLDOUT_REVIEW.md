# Evolution-2 Pendulum/Acrobot unused-instance naming review

Status: **NAMING_BLOCKED**.
Parent: `2b52894214eb4efe83a943a610428ce91d9d3e5a`.
Rule reviewed: `e2_pendulum_acrobot_dev_v1`.

This review does **not** name a holdout, persist a physics tuple,
rewrite v1/v2/v2-pilot hashes, collect data, or unlock H17.
Ledger **305.842 / 3294.158**.

## 1. Question

Can the unused-instance rule now be executed against the live
occupied sets to lock named Pendulum and Acrobot source and
development physics for v2 or v2-pilot?

## 2. Verdict

**No.** Occupancy bookkeeping is complete enough to reject closed
keys. An unused Acrobot cell exists on the locked grid. Naming is
still blocked because the live rule can produce only one Acrobot
key, v2 needs unused physics on **both** families, and there is no
Pendulum unused-instance grid.

| Check | Result |
|---|---|
| Occupied lists cover family-file literals | PASS |
| Default `(10,1,1)` / `(1,1,1)` rejected as new sources | PASS |
| Acrobot unused cell exists on the 4,913-cell grid | PASS (digest only) |
| Pendulum unused-instance rule / grid | **FAIL — missing** |
| Four roles filled (Pendulum/Acrobot × source/development) | **FAIL** |
| `LOCKED_TARGET` / `hold_named` | still `null` / `false` |
| Collection authorized by naming | **No** |

## 3. Why one Acrobot key is not enough

v2 and v2-pilot ask a counterbalanced two-family question on
**new** source and development instances. Bundles may share physics
and differ by model seed, but they still need four disjoint roles:

1. unused Pendulum source
2. unused Pendulum development
3. unused Acrobot source
4. unused Acrobot development

`e2_pendulum_acrobot_dev_v1` walks only the Acrobot mass/length
grid. It cannot name a Pendulum key. Using its one Acrobot draw as
both source and development would collapse those roles.

The live Acrobot draw is recorded only as SHA256
`f63b54f2ed140915b4ac8b3fd924bc7ae0c5c754496e417784603a206ea72f19`.
A later authorization that names an Acrobot key from this rule
must match that digest. This review does not write the tuple.

## 4. Occupancy

Pendulum `(g, m, l)` and Acrobot
`(LINK_MASS_1, LINK_MASS_2, LINK_LENGTH_1)` literals in the family
modules are covered by the v1 occupied sets, including implied
defaults `g∈{8.3,11.5,12.1}` at `(m,l)=(1,1)` and the twelve-point
latent grid. MCC, CartPole, and H12–H17 remain forbidden.

Family modules were read as text. They were not imported.

## 5. What this review does not do

- No Gymnasium construction, training, or env steps.
- No rewrite of v1, v2, or v2-pilot hashes.
- No Pendulum grid invented here (that would be a later design lock).
- No H17 unlock.
- No claim that existence of an unused cell authorizes collection.

CPU enforcement, trusted checkpoints, balanced dispatch, and
`authorized: false` remain independent blockers.

## 6. One next scientific action

Do **not** name a holdout. Either lock a Pendulum unused-instance
rule and four-role assignment **without persisting tuples**, or run
a residual-MLP timing probe on existing checkpoints without new
env collection.
