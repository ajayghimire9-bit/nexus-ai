# MountainCar lookahead versus compute-matched H=16 — locked protocol v1

Base `41fb0c5c84023f6ab53acd3991ce5fe345e34a03`. Branch `cursor/mountaincar-compute-matched-h16`. MountainCar development and confirmation stay closed. Do **not** retune H=16, the 16-candidate lookahead successor, or the dense height from those samples. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused.

This is a **compute-matched mechanism** test of the frozen MountainCar lookahead package. It is not a new transfer test and does not reopen confirmation physics `bf4b4412f4f683dd`.

## 1. Why this experiment

Lookahead still uses **771** imagined model states per step versus **256** for 16-candidate H=16. The established development (+44.092) and confirmation (+50.366) wins therefore test the complete controller package, not computation-matched isolation.

This protocol gives H=16 **48** candidates (48 × 16 = **768** imagined states per step) while the lookahead successor stays frozen at 16 candidates (3 + 3 × 16 × 16 = **771**). The extra 32 H=16 sequences are the prefix-stable continuation of the same RNG draw, so lookahead's 16 candidates are exactly the first 16 of the matched planner.

Acrobot compute-matched failed this isolation (**12.834**). Pendulum compute-matched passed (**60.182**). MountainCar is a third family with the same unmatched package.

## 2. Physics and checkpoints

Development split `2a5cc4979642cc2a` with **fresh** resets `27000000+` / step seeds `27100000+`. Confirmation physics are not rolled out. Ten frozen residual checkpoints from `checkpoints/mountaincar_lookahead_h16` are loaded read-only. **0** optimizer updates. Development episode seeds `25000000+` and confirmation seeds `26000000+` are not reused.

## 3. Frozen controllers

- Arm A `matched_h16`: receding H=16 over 48 shared candidates from `s`.
- Arm B `lookahead`: unchanged three-action backup of frozen open-loop 16-candidate H=16 height from `s'`, survival-weighted `(1-p)`.

Unchanged: residual 2×64, dense valley height, 200-step TimeLimit, no goal termination, H=16, 3 actions, argmax tie-break, time budget off. Successor value remains frozen open-loop H=16 height, not receding-policy Q.

## 4. Primary

Training-seed mean of (lookahead return − matched-H=16 return), three development tasks inside the seed. Student-t 95%, df 9. Margin **25**.

- Complete, mean ≥ 25, lo > 0: `mountaincar_compute_matched_lookahead_established`
- Complete, mean ≤ −25, hi < 0: `mountaincar_compute_matched_lookahead_harm_established`
- Else complete: `mountaincar_compute_matched_lookahead_not_established`
- Incomplete grid: `incomplete`

The original 16-candidate H=16 comparison stays closed and cannot upgrade this label.

## 5. Budget and authorization

**180 s** total process wall, **12,000** new real steps, **9,234,000** imagined transitions, **0** optimizer updates. Local CPU. Ten seeds × three tasks × two arms × 200 steps.

**Collection is unauthorized.** `authorized: false`, `runs: 0`. Do not execute until a new explicit human approval binds this configuration hash, protocol hash, and these caps.

Not a result, not learning-to-learn, not AGI.
