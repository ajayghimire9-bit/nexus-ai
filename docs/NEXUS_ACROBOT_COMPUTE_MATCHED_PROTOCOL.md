# Acrobot lookahead versus compute-matched H=16 — locked protocol v1

Base `84c35883486b6b280e8930c02b20bd237e352a6d`. Branch `cursor/acrobot-compute-matched-h16`. Acrobot development and confirmation stay closed. Do **not** retune H=16, the 16-candidate lookahead successor, or the dense height from those samples. CartPole H=3 unused. Pendulum FiLM unused.

This is a **compute-matched mechanism** test of the frozen Acrobot lookahead package. It is not a new transfer test and does not reopen confirmation physics `b309bd481fd8abcb`.

## 1. Why this experiment

Lookahead still uses **771** imagined model states per step versus **256** for 16-candidate H=16. The established development (+27.914) and confirmation (+37.961) wins therefore test the complete controller package, not computation-matched isolation.

This protocol gives H=16 **48** candidates (48 × 16 = **768** imagined states per step) while the lookahead successor stays frozen at 16 candidates (3 + 3 × 16 × 16 = **771**). The extra 32 H=16 sequences are the prefix-stable continuation of the same RNG draw, so lookahead's 16 candidates are exactly the first 16 of the matched planner.

## 2. Physics and checkpoints

Development split `911ea726b6ed2111` with **fresh** resets `24000000+` / step seeds `24100000+`. Confirmation physics are not rolled out. Ten frozen residual checkpoints from `checkpoints/acrobot_lookahead_h16` are loaded read-only. **0** optimizer updates. Development episode seeds `22000000+` are not reused.

## 3. Frozen controllers

- Arm A `matched_h16`: receding H=16 over 48 shared candidates from `s`.
- Arm B `lookahead`: unchanged three-action backup of frozen open-loop 16-candidate H=16 height from `s'`, survival-weighted `(1-p)`.

Unchanged: residual 2×64, dense upright height, 200-step TimeLimit, no goal termination, H=16, 3 actions, argmax tie-break, time budget off. Successor value remains frozen open-loop H=16 height, not receding-policy Q.

## 4. Primary

Training-seed mean of (lookahead return − matched-H=16 return), three development tasks inside the seed. Student-t 95%, df 9. Margin **25**.

- Complete, mean ≥ 25, lo > 0: `acrobot_compute_matched_lookahead_established`
- Complete, mean ≤ −25, hi < 0: `acrobot_compute_matched_lookahead_harm_established`
- Else complete: `acrobot_compute_matched_lookahead_not_established`
- Incomplete grid: `incomplete`

The original 16-candidate H=16 comparison stays closed and cannot upgrade this label.

## 5. Budget and authorization

**180 s** total process wall, **12,000** new real steps, **9,234,000** imagined transitions, **0** optimizer updates. Local CPU. Ten seeds × three tasks × two arms × 200 steps.

**Collection is unauthorized.** `authorized: false`, `runs: 0`. Do not execute until a new explicit human approval binds this configuration hash, protocol hash, and these caps.

Not a result, not learning-to-learn, not AGI.
