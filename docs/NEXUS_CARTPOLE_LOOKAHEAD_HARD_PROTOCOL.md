# CartPole lookahead versus frozen H=3 on harder unused physics — locked protocol v1

Base `82d85519f97533e2969834e09dd80c9333a0e3a6`. Branch `cursor/cartpole-lookahead-hard-h3`. The ceilinged development screen stays closed. Do **not** retune H=3, candidates, or reward from that sample. Pendulum H=16 is not copied. V0.7.3 confirmation tuples stay closed.

This is the same frozen lookahead *mechanism* against CartPole H=3 × 16, on a physics region where H=3 was historically off-ceiling.

## 1. Why a harder region

The previous unused-physics draw labeled `cartpole_lookahead_not_established` because H=3 already returned 500 on 9/10 seeds. That cannot measure lookahead. V0.7.3 published that high gravity, short pole, heavier mass was off-ceiling (task 2 mean 459). This protocol samples that published corner and **rejects** the exact V0.7.3 confirmation tuples.

Hard region: gravity ∈ [12.0, 16.0], length ∈ [0.25, 0.45], masspole ∈ [0.15, 0.30].

## 2. Holdout

Rule `cartpole_lookahead_hard_v1`, split hash `9a60e48299b738ef`:

- `cartpole_look_hard0`: (14.0, 0.42, 0.22)
- `cartpole_look_hard1`: (13.3, 0.43, 0.25)
- `cartpole_look_hard2`: (12.4, 0.28, 0.22)

Disjoint from the ceilinged development draw `4bc1f5866ac6c753` and from V0.7.3 confirmation including (13.0, 0.35, 0.18).

## 3. Frozen controllers

Unchanged from the ceilinged screen: V0.7.2 residual 2×64, 1024+256, 20 epochs, H=3 × 16, objective `both`, time budget off, 2 first-action lookahead of frozen open-loop H=3 score with survival weight `(1-p)`.

## 4. Primary

Training-seed mean of (lookahead return − H=3 return), three tasks inside the seed. Student-t 95%, df 9. Margin **25**.

- `cartpole_hard_lookahead_established`
- `cartpole_hard_lookahead_harm_established`
- `cartpole_hard_lookahead_not_established`
- `incomplete`

## 5. Budget

**300 s**, **42,800** real steps max, **2,190,000** imagined max, **200** frozen-recipe epochs. Resets `19000000+`. Local CPU.

**Collection is unauthorized.** `authorized: false`, `runs: 0`.

Not a result, not learning-to-learn, not AGI.
