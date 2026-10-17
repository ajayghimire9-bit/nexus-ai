# Cross-environment CartPole-target transfer — results (rung 7)

## Decision

**`xenv_cartpole_target_not_established`.** The predeclared primary —
per-seed mean control return over {128, 1024}, paired `xenv − scratch` —
was **−2.500 [−10.359, +5.359]** (student-t 95%, df 9, n = 10); the
interval includes 0, one of ten seeds positive on the averaged primary.

Switching the target family off MountainCarContinuous did **not**
establish shared-trunk transfer. Per budget: @128
**−0.500 [−7.110, +6.110]** and @1024 **−4.500 [−14.679, +5.679]** —
both include 0. Mean returns @128: xenv 12.200 versus scratch 12.700 and
reference 26.400. @1024: xenv 188.200 versus scratch 192.700 and
reference 174.400. At the large budget both shared-trunk arms often hit
the 200-step cap; that ceiling is not a transfer gain. Held-out MAE gain
@1024 was +3.41e-04 [+4.89e-05, +6.33e-04] (xenv worse; lower bound
above 0).

Seven matched xenv rungs are now closed `not_established` (six MCC
targets plus this CartPole target). The established adaptation lever
remains multitask pretraining across physics variants **within** a
family.

This is a valid negative result for this configuration only — not
learning-to-learn, not AGI. Target physics (6.5, 0.57, 0.28) and this
recipe are closed.

## Cost

**10.233 s wall** (600 s cap), **38,066 fresh real steps** of 44,000
maximum (19,200 prior + 12,800 target + 6,066 evaluation; CartPole
episodes may terminate before 200), **1,552,896 imagined transitions**
of 3,072,000 maximum, local CPU, one valid execution after authorization
commit `e91de72` (no invalid attempts). Session ledger: 258.118 + 10.233
= 268.351 s of 3600 s consumed; 3331.649 s remain.

## Integrity

The independent Git-only results audit passed: saved label, 60-trace
grid, reward reconstruction, action range, execution totals under the
locked caps and forbidden-claim flags. Rule `cartpole_xenv_v1`
reproduced **(6.5, 0.57, 0.28)** against 89 occupied CartPole keys;
seeds `69,000,000+` are disjoint from closed blocks. MCC holdouts were
not reused.

## Provenance

Branch `cursor/xenv-cartpole-target`: lock `c3e9393`, authorization
`e91de72`, executed once with a clean tree. Raw artifact
`artifacts/xenv_cartpole_target.json` SHA256
`e04448c55be316ef4b6f55ef6ec05487ef0e1cc9d1739a67b8d556fa7834e498`.

## One next recommendation

Leave the cross-family shared-trunk line closed at this scale. Do not
add an Acrobot-target copy, another FiLM variant, or a retune of any
closed MCC or CartPole holdout. A 5× prior scale still exceeds the
100,000 standing cap. Nothing here pre-authorizes a further xenv rung.
