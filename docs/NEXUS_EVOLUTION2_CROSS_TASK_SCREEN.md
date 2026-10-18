# Evolution-2 cross-task algorithm-discovery screen

Status: **SYNTHETIC_CONTRACT_AND_DESIGN — NOT A SCIENTIFIC RESULT**.
Branch: `cursor/evolution2-cross-task-screen`.
Parent: Evolution-1 results `96c71ae297e6329517d4afb4d3bad50162832c21`
(implementation `f4de1e135dd88ee18ef7a6b05a42c70df917d00e`).

This milestone tests **LEVEL 2** only: whether retaining permitted
proposal-policy state across synthetic algorithm-improvement tasks
changes discovery on later tasks. It does not claim LEVEL 3 (new
operators) or LEVEL 4 (improving the update rule). It is not
self-evolution, learning-to-learn, or AGI.

No scientific environment rollout, model training, H17 work, or
ledger consumption occurred. Session ledger remains
**305.842 s used / 3294.158 s remaining**.

## 1. Architecture and update rules

Evolution-2 reuses the Evolution-1 catalogue, public context,
`TrainingFeedback` type, and linear adaptive proposer. It does not
reimplement those components.

For successor indicator S, balanced-generation indicator B, H/16=h,
public observation dimension O and action count A:

`x = (1, S, B, h, S*O/16, h*A/16)`

Prediction is `w·x`. The Evolution-1 update is unchanged:

`w ← w + 0.5*(y − w·x)*x/(x·x)`

with y=0 on an explicit failure. Weights start at zero.

Methods:

- **Random:** uniform remaining-catalogue sample. No learned weights.
- **Fixed:** highest horizon, then flat, then IID. Feedback ignored.
- **Reset adaptive:** Evolution-1 SGD within a task; weights discarded
  before the next task. Tie order is preserved for determinism.
- **Persistent adaptive:** the same SGD object across training tasks.
  After training, weights are frozen. Development and shifted feedback
  cannot write the global vector.
- **Evolutionary:** equal-budget within-task mutation of rule,
  generator, or horizon. Fitness does not persist across tasks.

Every method receives the same two Evolution-1 anchors
(IID flat H16, IID successor H16), then two free proposals, the same
public context, and the same four scalar receipts. Persistent memory
is the only extra information.

## 2. Task generation

Scores are authored linear functions of (S, B, h) plus a small
instance offset. They are **not** H12–H16 returns and not copied
H16 advantages. The same variant always receives the same score on
a task, regardless of proposal order.

| Family | Role | Public (O, A) | Hidden (bias, S, B, h) |
|---|---|---|---|
| `successor_scale` | train | 16, 2 | (0.20, 0.36, 0.06, 0.10) |
| `horizon_scale` | train | 4, 8 | (0.18, 0.06, 0.05, 0.38) |
| `balanced_scale` | train | 8, 4 | (0.22, −0.06, 0.34, 0.08) |
| `successor_dev` | development | 12, 3 | (0.21, 0.33, 0.07, 0.11) |
| `inverted_successor` | shifted | 16, 2 | (0.40, 0.05, −0.40, −0.35) |
| `holdout_horizon` | untouched | 4, 8 | (0.17, 0.04, 0.06, 0.40) |

`hidden_score` lives on the evaluator side. Proposer APIs accept only
`TrainingFeedback`. The holdout family is generated and then excluded
from the default train/dev/shifted split.

## 3. What each method sees

Public: task id, role label, context `(n_actions, obs_dim,
episode_steps, imagined_cap)`, remaining catalogue variants, and
permitted receipts for **proposed** variants only.

Hidden from every proposer: family hidden weights, the full oracle
table, unchosen scores, holdout tasks, and development/shifted
updates to the persistent global vector.

Within-task adaptation is a separate flag. When it is off, eval
clones choose from frozen or zero weights and do not learn. When it
is on, local clones may update, but the stored global weights stay
fixed.

## 4. Baseline fairness

All five methods: 4 proposals/task, 2 shared anchors, identical task
instances, identical catalogue, identical public contexts. Reset and
evolution discard cross-task memory. Persistent is not given extra
lookups. Evolutionary search is implemented and charged the same
four receipts.

## 5. Deterministic synthetic demonstrations

Seed 7. Labeled `synthetic_illustration_not_a_result`.

- After one `successor_scale` task, persistent weights are nonzero
  and `choose()` on a `horizon_scale` context differs from a reset
  policy. Withholding all training feedback leaves both at zero
  weights and identical later choices.
- Aligned successor-only training, frozen eval: persistent mean
  discovered score exceeds reset on `successor_dev` (related family).
- The same frozen policy has a **lower** mean than reset on
  `inverted_successor`, where high-horizon balanced successors are
  punished. Persistence can hurt.
- Mixed three-family training is the default screen. It is a
  contract check, not a scientific ranking.
- Evaluation with local updates does not change frozen global
  weights. Lookup counts match (40 per method on the default split).

## 6. When persistence hurts

`inverted_successor` rewards mid-horizon IID variants and punishes
balanced high-horizon successors. The successor-trained persistent
policy still proposes those punished arms. Reset, starting from zero
weights, follows its tie order and can propose a less-punished arm.
This is an authored counterexample, not a real-environment finding.

## 7. CPU and memory cost

Synthetic only: 6-vector weights, 12 catalogue arms, 4 proposals per
task, 6 training + 2 development + 2 shifted tasks in the default
split (40 lookups/method). No scientific ledger debit. No measured
wall-clock claim beyond unit tests.

## 8. Scientific limitations

Evolution-1 proved feedback can change later toy choices. It did not
prove better real planning, transfer, dominance over evolution, a new
optimizer, or recursive self-improvement. Evolution-2 adds a
cross-task **contract** and a future protocol. Toy means are not
LEVEL 2 evidence. A better weight vector is still LEVEL 1 adaptation
unless a predeclared held-out comparison is independently authorized
and run.

H17 remains blocked. Closed H12–H16 artifacts are untouched.

## 9. Required independent review before a real experiment

Proposed, **not locked or authorized**:

- Train on new, disjoint source instances (not these synthetic
  tables and not closed holdouts).
- Development: physics-disjoint tasks in the same families; no
  development outcome updates the global proposer.
- Untouched holdout families, separately reviewed.
- Independence unit: model/search bundle, n=10, Student-t 95%, df=9.
- Primary: mean development `(best_persistent − best_reset)`.
- Labels: `e2_persistence_helps_transfer`,
  `e2_persistence_hurts_transfer`, `e2_transfer_not_established`,
  `incomplete`.
- Caps must be reviewed; a real screen is expected to exceed the
  standing 100,000-step / 900 s experiment limits if it includes
  model training. No allocation is created here.

Do not tune on a future holdout. Do not select favorable seeds.

## 10. Next research milestone

Prepare an independent readiness review of a **bounded real
cross-task proposal-policy screen** against memory-reset and
equal-budget evolution, with family adapters, actual meters, and
exclusion/provenance gates resolved first. Do not execute that
screen from this branch.

## Reproduction

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_evolution2_cross_task_screen.py -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_evolution2_cross_task_screen.py --demo
```
