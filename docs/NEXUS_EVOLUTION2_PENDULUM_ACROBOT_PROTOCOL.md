# Evolution-2 Pendulum→Acrobot catalogue-proposer protocol

Status: **DESIGN LOCKED — COLLECTION UNAUTHORIZED**.
Branch: `cursor/evolution2-pendulum-acrobot-protocol`.
Parent: `d36b49f519496f29282d1321d5314a623c2ee280`.

This lock freezes the question, methods, metrics, budget comparison,
and occupied-physics exclusion for a later Pendulum→Acrobot
catalogue-proposer screen. It does not collect data, name an unused
Acrobot holdout, unlock H17, or promote the synthetic Evolution-2
contract to LEVEL 2 evidence.

Ledger unchanged: **305.842 s used / 3294.158 s remaining**.

## 1. Question

After AdaptiveProposer training on default Pendulum physics
`(g, m, l) = (10, 1, 1)`, does **persisting proposer state** improve
Acrobot discovery relative to resetting that state, drawing at
random, running equal-budget evolution, retrieving guarded memory,
or using one frozen catalogue index?

This is a LEVEL 2 proposal-policy transfer screen on real families.
It is not LEVEL 3/4, not learning-to-learn, not H17, and not AGI.
Pendulum network weights must not be copied onto Acrobot. The
families are observation-incompatible (3 vs 6).

## 2. Methods (locked)

| ID | Name | Role |
|---|---|---|
| A | fixed | One frozen catalogue index. No proposer update. |
| B | random | Independent uniform catalogue draws on Acrobot. |
| C | reset | Train on Pendulum; discard proposer state; same budget on Acrobot. |
| D | persist | Train on Pendulum; retain proposer state; same budget on Acrobot. |
| E | evolution | Equal-budget catalogue mutation/crossover started fresh on Acrobot. |
| F | retrieval | Guarded Pendulum memory. Incompatible weight transfer fails closed. |

Primary estimand: persist minus reset (`D − C`) on mean Acrobot
return. Secondary: persist minus random, evolution, retrieval, and
fixed.

## 3. Replication and intervals

- `n = 10` independent source-training seeds.
- 95% Student-t interval, `df = 9`.
- Replication unit is the source-training seed. Episodes, catalogue
  draws, and student seeds are not extra replications.
- Established only if the primary interval lies entirely above 0.
- Labels: `persist_beats_reset_established`,
  `persist_beats_reset_not_established`, or
  `persist_beats_reset_blocked` while collection is unauthorized.

## 4. Families and occupied physics

Train family: Pendulum. Train instance: default source `(10, 1, 1)`.
That tuple is historically occupied and is reused only as the
training source, never as a new holdout.

Eval family: Acrobot. Development instance: **unnamed**.

Occupied Pendulum `(g, m, l)` and Acrobot
`(LINK_MASS_1, LINK_MASS_2, LINK_LENGTH_1)` keys are frozen from
`pendulum_family.py` and `acrobot_family.py` as source literals.
Every occupied key is rejected. MountainCar, MountainCarContinuous,
CartPole, and all H12–H17 / MCC holdouts are forbidden.

A deterministic unused-instance rule `e2_pendulum_acrobot_dev_v1`
exists so a later independent review can name a key without
shopping. This lock does not execute that rule against the live
occupied set to persist a chosen unused tuple.

## 5. Budget versus standing limits

| Cap | Standing | Proposed if later authorized | Authorized now |
|---|---|---|---|
| Wall time | 900 s | 300 s | **0 s** |
| Real interactions | 100,000 | 40,000 | **0** |
| Imagined transitions | disclose separately | 0 in this lock | **0** |

Local CPU only. The proposed caps are below the standing grant.
They do not authorize collection. `authorized: false`, `runs: 0`.

## 6. What this lock does not do

- No Gymnasium construction, no training, no env steps.
- No import of untracked `nexus.evolution1.adapters`.
- No H17 unlock and no MCC physics.
- No new holdout shopping and no named unused Acrobot instance.
- No claim that the synthetic Evolution-2 persist-versus-reset
  contract answers this question.

Scientific dispatch remains `require_scientific()`-blocked until a
later authorization cites this protocol hash, names a holdout by
the frozen rule, and supplies trusted family adapters.
