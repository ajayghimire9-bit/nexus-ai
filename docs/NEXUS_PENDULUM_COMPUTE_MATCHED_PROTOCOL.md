# Pendulum lookahead versus compute-matched H=16 — locked protocol v1

Base `cceb4b126c3d04ca0ca477a6294035ddca5b5aac`. Branch `cursor/pendulum-compute-matched-h16`. Acrobot compute-matched stays closed. Pendulum unmatched development **155.647** and transfer **98.608** stay closed. Do **not** retune the 16-candidate lookahead successor, H=16, or the published reward. Confirmation holdout `73844661addfa11b` is not reused.

This is a **compute-matched mechanism** test of the frozen Pendulum lookahead package. Successor value remains frozen **open-loop** H=16 score from `s'`. Do not call it Bellman-consistent receding-policy value.

## 1. Why this experiment

Acrobot lookahead versus 48-candidate H=16 did not pass the 25-point rule: **12.834 [3.815, 21.853]**. Extra search closed most of that family's unmatched gap. Pendulum's unmatched development gap was larger (**155.647**), so the same contrast has more room to detect a compute-free remainder.

Lookahead stays at **771** imagined states per step. Matched H=16 scores **48** prefix-stable candidates (**768**/step) instead of 16 (**256**). Lookahead's 16 candidates are exactly the first 16 of the matched planner.

## 2. Physics and checkpoints

`pendulum_context_development` with **fresh** resets `15000000+` / step seeds `15100000+`. Confirmation physics unused. 120 frozen FiLM checkpoints, stored development codes via `load_models(d, t+8, ...)`. **0** optimizer updates. Development episode seeds `13000000+` and transfer seeds `14000000+` are not reused.

## 3. Frozen controllers

- Arm A `matched_h16`: receding H=16 over 48 shared candidates from `s`. Scoring is local to this protocol because the frozen `_score_open_loop` rejects any shape other than `(16, 16)`.
- Arm B `lookahead`: unchanged `lookahead_first_action` over 16 candidates from `s'`.

Unchanged: 10 decoders, 5 student encoders, normalization, 3 torques, published Pendulum reward, H=16, argmax tie-break, student visitor `(d+t) mod 5`, zero-context visitor.

## 4. Primary

Decoder mean of (lookahead 200-step return − matched-H=16 200-step return), averaging three development tasks and both visitors. Student-t 95%, df 9. Margin **25**.

- Complete, mean ≥ 25, lo > 0: `pendulum_compute_matched_lookahead_established`
- Complete, mean ≤ −25, hi < 0: `pendulum_compute_matched_lookahead_harm_established`
- Else complete: `pendulum_compute_matched_lookahead_not_established`
- Incomplete grid: `incomplete`

Student-minus-zero is secondary and cannot upgrade. The unmatched 16-candidate comparison stays closed.

## 5. Budget and authorization

**180 s** total process wall, **24,000** new real steps, **18,468,000** imagined transitions, **0** optimizer updates. Local CPU. Ten decoders × three tasks × two visitors × two arms × 200 steps.

**Collection is unauthorized.** `authorized: false`, `runs: 0`.

Not a result, not learning-to-learn, not AGI.
