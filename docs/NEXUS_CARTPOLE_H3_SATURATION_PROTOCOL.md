# CartPole frozen H=3 saturation diagnostic — locked protocol v1

Base `894f5ca3ab0ec7b084d7c0e4f041b6c58de1f5b0`. Branch `cursor/cartpole-h3-saturation-diagnostic`. Both CartPole lookahead screens stay closed. Do **not** retune H=3, candidates, or reward. Do **not** run lookahead. V0.7.3 confirmation tuples stay closed.

## 1. Why a diagnostic, not another lookahead screen

The unused draw and the published-hard draw both labeled lookahead not established because frozen H=3 was already at the 500-step TimeLimit on most seeds. Resampling the same box cannot measure lookahead. This protocol asks whether H=3 is unsaturated on a **stricter unused corner**. Lookahead is withheld until that question is answered.

## 2. Stricter region

gravity ∈ [13.0, 16.0], length ∈ [0.25, 0.34], masspole ∈ [0.20, 0.30].

Shorter poles and higher gravity than the ceilinged hard draw. The closed V0.7.3 cell (13.0, 0.35, 0.18) is outside this length/mass box and is rejected anyway.

## 3. Holdout

Rule `cartpole_h3_saturation_v1`, split hash `a69833ab38a34ab4`:

- `cartpole_h3_sat0`: (13.2, 0.27, 0.23)
- `cartpole_h3_sat1`: (15.6, 0.25, 0.28)
- `cartpole_h3_sat2`: (15.4, 0.27, 0.20)
- `cartpole_h3_sat3`: (15.5, 0.30, 0.28)
- `cartpole_h3_sat4`: (16.0, 0.34, 0.20)
- `cartpole_h3_sat5`: (13.8, 0.31, 0.27)

Disjoint from `4bc1f5866ac6c753`, `9a60e48299b738ef`, and V0.7.3 confirmation.

## 4. Frozen controller

V0.7.2 residual 2×64, 1024+256, 20 epochs, H=3 × 16, objective `both`, time budget off. One arm only: frozen H=3 receding. Lookahead is not executed.

## 5. Primary

Training-seed mean of (500 − H=3 return) across six tasks. Student-t 95%, df 9. Margin **25**.

- `cartpole_h3_unsaturated` if mean ≥ 25 and lower bound > 0
- `cartpole_h3_still_ceilinged` otherwise
- `incomplete`

If unsaturated, a later distinct question may run lookahead on unsaturated cells. If still ceilinged, CartPole lookahead versus H=3 is unmeasurable with this planner and TimeLimit; the next family should not have a 500-step survival ceiling. That later work is not authorized here.

## 6. Budget

**300 s**, **42,800** real steps max, **1,440,000** imagined max, **200** frozen-recipe epochs. Resets `20000000+`. Local CPU.

**Collection is unauthorized.** `authorized: false`, `runs: 0`.

Not a result, not learning-to-learn, not AGI.
