# Evolution-2 Pendulum↔Acrobot catalogue-proposer protocol v2

Status: **DESIGN ONLY — COLLECTION UNAUTHORIZED**.
Supersedes v1 for any future executable lock.
Preserves v1 as historical evidence:
`docs/NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL.md`.

Parent of this review: `f9154f08e480db631d20f5594f51dcf8cac379cc`.
Requirement source: `docs/NEXUS_EVOLUTION1_FEASIBILITY.md` §§5–8.

This document does not collect data, name unused physics, unlock H17,
or authorize an allocation. Ledger **305.842 / 3294.158**.

## 1. Question

On independently initialized Pendulum and Acrobot world-model bundles,
does a memory-conditioned catalogue proposer that **retains proposer
state across the first training family** improve discovery on the
second family, judged on held-out development tasks of both families,
versus random, evolution, reset, fixed H=16 flat, and fixed H=16
successor?

This is a LEVEL 2 proposal-policy screen. It is not LEVEL 3/4, not
learning-to-learn, and not AGI. Network weights are never copied
across families.

## 2. Methods

Shared objects: the 12-variant Evolution-1 catalogue, six proposal
slots per training family, two fixed anchors consuming the first two
slots, no duplicate evaluation of a variant on the same task, identical
source datasets and models inside a bundle.

| ID | Name | Rule |
|---|---|---|
| A1 | fixed_flat | Frozen H=16 flat. No proposer update. |
| A2 | fixed_successor | Frozen H=16 successor. No proposer update. |
| B | random | Uniform remaining-catalogue sample. No learned weights. |
| C | reset | Adaptive proposer; discard weights at the family boundary. |
| D | persist | Same proposer; retain weights across the family boundary. |
| E | evolution | Population ≤4, tournament 2, one legal operator-coordinate mutation. No crossover. |

Retrieval of incompatible network weights is **not** a method. It
must fail closed. Guarded memory of proposer statistics is method D,
not a sixth competitive arm.

Training-family order is counterbalanced across bundles
(Pendulum→Acrobot and Acrobot→Pendulum).

## 3. Replication and statistics

- n = 10 independent search/model-bundles.
- Each bundle has independently initialized family models and one
  proposal trajectory. Methods are paired inside the bundle.
- Episodes, catalogue draws, and student seeds are not replications.
- Normalize return differences by the trusted analytic reward range
  declared before data. Reject undefined or zero ranges.
- Primary: persist minus each of B, C, E, A1, A2.
- Established only if the persist-minus-control mean is at least 0.05
  of the analytic range **and** all five Bonferroni 99% paired
  Student-t intervals (df 9) lie above 0.
- Ordinary 95% intervals are exploratory.
- Failure to beat reset forbids a claim that learned proposal
  statistics caused the gain.

## 4. Outcomes

`transfer_screen_passed`, `development_screen_failed`,
`inconclusive`, `negative_transfer`, `incomplete_budget`,
`invalid_integrity`, `invalid_leakage`.

A complete nonsignificant run is `inconclusive`, not incomplete.
Missing cells, nonfinite values, or hash mismatch are
`invalid_integrity`. Do not drop cells or pick a winner from the
final family.

## 5. Families and physics

New Pendulum and Acrobot source and development instances, disjoint
from every occupied key listed in
`src/nexus/evolution2/pendulum_acrobot_protocol.py`. Default
`(10, 1, 1)` is occupied and is not a new source. Default Acrobot
`(1, 1, 1)` is occupied. MCC, CartPole, and H12–H17 remain
forbidden. Family C (navigation) is out of scope.

The unused-instance rule `e2_pendulum_acrobot_dev_v1` may be used
later by an independent review. **This v2 lock does not name a
tuple.**

## 6. Operators and cost

Legal mutation flips exactly one of `{rule, generator, horizon}`.
Crossover is illegal. Imagined-transition cap is owned by the
broker: 1,536 per decision unless a later authorized worksheet
lowers it uniformly. Report actual used imagined transitions, not
padded work. A five-action formula must not be used.

## 7. Resource worksheet versus standing limits

Feasibility first-screen arithmetic remains the scientific target:
10 bundles × 2 families × (1,024+256) source/validation +
10 × 12 × 2 × 200 training-matrix + 10 × 6 × 2 × 200 development
= **97,600 real steps**, plus charged imagined transitions.

Standing grant: 900 s / 100,000 real / local CPU. The full
feasibility screen is inside the interaction cap and likely outside
the 900 s wall if planning is charged at historical Pendulum rates.
A future authorization must either accept `incomplete_budget` or
obtain a separate wall-clock grant. **This document authorizes 0 s
and 0 steps.**

Account wall time, process CPU, real steps, imagined transitions,
failed attempts, and memory bytes. Cached revealed rows are still
charged. CPU enforcement on the stub host remains BLOCKED; that
alone keeps collection unauthorized.

## 8. What this lock does not do

- No Gymnasium construction, training, or env steps.
- No import of untracked `nexus.evolution1.adapters`.
- No H17 unlock.
- No named unused instance.
- No claim that v1 or the synthetic E2 screen answers this question.
