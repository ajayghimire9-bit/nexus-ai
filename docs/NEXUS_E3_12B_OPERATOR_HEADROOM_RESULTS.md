# E3.12B — Real operator headroom exists; selection evidence is mixed

Branch `codex/e3-12b-paired-operator-headroom`, starting at GitHub-verified
`ed89b49547f39f787387192036268fef60eca0ef`. Tested protocol/config/allocation
committed before outcomes at **570d10184354901291f2903eb4e8de20203e9839**.
One run, no tuning or retry. E3.12's previous zero sampled-choice result stays
closed and unchanged.

## Registered decision

**headroom_visible_selection_not_established.** Both source families exceed
the prespecified finite-suite5-point hindsight headroom threshold. The primary
training-mean selection screen passes Pendulum and fails Acrobot because its
interval includes zero. The BOTH-family overall selection screen therefore
fails. This complete valid execution is distinct from an incomplete run.

The important new finding is that the two existing operators can differ greatly
in actual return, and their model-specific mean ordering persisted in all four
models. It does not establish a superior learning rule or control generalization.

## What executed and what learned

Four existing frozen source MLP models, two per family; eight training resets
and four fresh query resets per model. At every reset, parent successor H16,
switch(parent,flat H16,.25) and rank_blend(parent,flat H16) each execute a full
paired200-step episode. Exact simulator/RNG/time-limit restoration and the same
per-tick planning seeds apply to all three. No new physics, neural fitting,
teacher fitting, latent fitting or reserved confirmation access.

Same StrategyGenerator mean structural credit, measured_mutation bridge,
Host/Dispatch/ForwardCheckedStep, ReservationLedger and planner implementations.
Sixty-four legitimate paired training-credit updates, sixteen per model. A
parent receipt is reused logically for both updates, with distinct operator
pair IDs, but its physical episode is counted once. Query feedback is sealed
from all updates. Both selectors are recorded before query paths:

- Simple baseline: argmax of eight observed training episode returns/operator.
- Existing credit rule: argmax of final mutation probabilities after cost-
  normalized, tanh-transformed paired gains. No temperature or rule changes.

Both selectors choose the **same** operator for all four models: Pendulum0
rank_blend, Pendulum1 switch, Acrobot0 switch, Acrobot1 rank_blend. Thus their
identical query gains are mathematically dependent, not corroborating studies.
The more elaborate credit rule does not outperform observed-return means.

This panel gives full feedback for both operators at every training reset.
It is not a demonstration of feedback-efficient bandit discovery. It also
changes feedback coverage and selection from E3.12; cross-study differences
cannot be attributed causally to only one of those changes.

## Primary paired returns and uncertainty

Average query episodes within each independently pretrained model, then use
two models per family, exploratory unadjusted95% t intervals with df1. Do not
pool families or count episodes/strategies as additional model replications.

**Pendulum:** training-mean/credit return **−219.189**, uniform-expected
**−338.916**. Primary gain **+119.727 [3.139,236.315]**, model gains+128.903
and+110.552. The1-point screen passes this family. Training-selected operator
wins8/8 query contexts, matching the retrospective upper reference here.

**Acrobot:** training-mean/credit **−288.846**, uniform-expected **−296.144**.
Primary gain **+7.298 [−34.703,49.298]**, model gains+10.603 and+3.992. Positive
point estimates do not resolve uncertainty. Selected operator wins6/8 query
contexts. This family fails the registered interval criterion.

Uniform-expected is the arithmetic expected return of choosing either operator
once at episode start with probability.5, computed from the two actually
executed paired paths. It is **not another executed policy**, and does not
mean randomly switching operators at each action. Retrospective best chooses
using query returns and is unavailable to the learner/controller.

Hindsight-best minus uniform-expected: Pendulum **+119.727 [3.139,236.315]**,
Acrobot **+8.169 [−36.188,52.526]**. Both exceed the finite-suite5-point screen
in mean, but Acrobot's uncertainty remains large. Best-minus-uniform equals
half the absolute paired operator gap; hindsight regret and related winner
metrics are dependent descriptions of these same outcomes.

## Strong fixed baselines and individual-model failures

Pendulum mean returns: parent **−252.450**, fixed switch **−348.092**, fixed
blend **−329.741**. Selected-minus-parent **+33.262 [−419.346,485.869]**;
minus-fixed-switch **+128.903 [−1508.966,1766.772]**; minus-fixed-blend
**+110.552 [−1294.141,1515.245]**. These broad intervals do not establish
superiority over the strong fixed parent or either fixed operator.

Acrobot: parent **−292.653**, fixed switch **−292.838**, fixed blend **−299.449**.
Selected-minus-parent **+3.807 [−103.507,111.122]**; minus-switch
**+3.992 [−46.732,54.717]**; minus-blend **+10.603 [−124.122,145.329]**.
No reliable superiority over these fixed policies is established.

Pendulum0: selected−308.638 versus parent−377.520 (gain+68.883).
Pendulum1: selected−129.740 versus parent−127.380 (**loss−2.359**).
Acrobot0: selected−280.769 versus parent−293.022 (gain+12.253).
Acrobot1: selected−296.923 versus parent−292.285 (**loss−4.639**).
Choosing the better mutation does not guarantee improvement over its parent.

Training/query mean switch-minus-blend gaps: Pendulum0 **−336.495/−257.806**,
Pendulum1 **+255.481/+221.103**; Acrobot0 **+3.024/+21.206**, Acrobot1
**−22.063/−7.984**. The winner differs between models in each family but its
mean direction is stable across the registered training/query blocks. This
supports investigating model-specific preferences; it does not show that an
observation-only representation identifies the best operator in every state.

## Integrity, costs and reproducibility

All48 contexts,144 physical paths and28,800 actual transitions complete and
finite. Training96 paths/19,200 real steps; query48/9,600. No support, validation,
probe or additional diagnostic interactions. Choices and credit updates replay
from training data only. Every saved transition's action, seed, continuity,
termination and published reward validate; independent math.fsum differs from
recorded sums by0.0. No missing-result filtering or post-hoc grid reduction.

All four network/normalizer fingerprints match exactly before/after. Parameters
4868 per Pendulum model and5255 per Acrobot model remain frozen; four checkpoint
and eight source-array hashes match the pinned inventory. These binaries are
already Git-tracked; no new checkpoint is created. All407 previous JSON files
are byte-identical. The two unrelated untracked adapter files are excluded.

Independent saved-data verification sums28,800 complete per-decision receipts:
**43,340,130 imagined transitions**, **1,311,810 model calls and observed neural
forwards**, zero unknown work. They remain below44,236,800/1,440,000 caps.
Derived selector/uniform/hindsight metrics do not add physical interactions.
Actual operator compute differs despite equal1536-row upper budgets. These
catalogue-budget policies are not historical16-candidate controller parity.

Wall **204.640469s**, worker CPU **203.608166s**, peak RSS **808,386,560B**,
under450s cap. Training path CPU131.743690s, query69.085987s; receipt/capture
work is included, so these are not pure neural latencies. CPU-normalized credit
depends on measured timing; replay uses saved CPU costs, not freshly invented
ones. Mean-return selection is not timing-normalized. The inherited immutable
Journal retains its old synthetic_fixture hashing namespace; actual credit
domain is explicitly real_environment and receipt-backed. This same-process
trusted host is not hostile-process authentication.

Saved-data verification4.425602458s, independent stdlib export0.042848708s.
Carried session ledger: **1485.650493707012s used /2114.349506292988s remaining**.
No additional scientific experiment begins here. Python3.13.5, NumPy2.5.4,
Torch2.14.1, Gymnasium1.4.0, local CPU with library threads fixed to1.

Raw SHA256 **a9b7b80811e8413bb8b541e1e21a8552555986ede0f9359d5f995833fc451d78**.
Config/protocol/allocation hashes, exact execution revision, fresh seed audit,
all actual trajectories,64 credit events, model fingerprints and resource
usage are saved in e3_12b_operator* artifacts. Twenty-nine lossless gzip
receipt parts total190,756,704 bytes. Separate CSV includes all144 executed
episode returns; JSON summary contains derived metrics and independent checks.

Source-only preflight examined9648 identifiers and found no collision against
available historical metadata, source-array seeds and conservative reservations;
unavailable external seed history is not claimed covered. No E2.17/H17 grant
reuse or hidden confirmation access.

## Commands and tests

Use PYTHONPATH=src:.deps, PYTHONDONTWRITEBYTECODE=1 and all three CPU-library
thread variables set to1:

```
python3 scripts/run_e3_12_mutation_control.py --operator-headroom --preflight
python3 scripts/run_e3_12_mutation_control.py --operator-headroom
python3 scripts/run_e3_12_mutation_control.py --operator-headroom --verify
python3 scripts/summarize_e3_12_mutation_control.py --operator-headroom
```

One-run markers reject execution retries on consumed seeds. Explicit verification
fails on missing/hash-mismatched checkpoints, data or journals. Tests cover
complete locked grids, paired episode seeds/restoration metadata, query-data
inaccessibility, sealed choices, two-model statistics, numeric failures,
same-parent/two-kind feedback IDs, original profile isolation and artifact pins.
Initial relevant suite732 passed in23.02s; focused54 passed in7.50s after
additional interval/pin tests. Final regression **737 passed in23.71s**, including
the independent exporter; exact command is in e3_12b_operator_test_report.json. Tests use
synthetic transitions/pure callbacks and do not collect scientific data.

## One next experiment

**Budget-matched explore-then-commit mutation selection:** does a deterministic
exploitation rule preserve the observed gains when each training reset reveals
only one child rather than both? Compare existing credit argmax, observed-return
mean selection and uninformed uniform generation with matched feedback and
compute; retain fixed parent/operator controls. Use fresh source episodes,
unchanged models and a separate protocol. A small design with eight training
parent/child pairs and four query panels/model would use22,400 real steps,
roughly120–180s estimated, proposed300s cap. No allocation, numerical seed
registration or execution for that proposal occurs in this branch. No larger
encoder, architecture search or new neural training is justified here.
