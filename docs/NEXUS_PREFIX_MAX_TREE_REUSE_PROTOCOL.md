# Prefix-max tree reuse versus frozen H=16 — locked protocol v1

Base `f3898f6c95e37ea3f91101e288b71056edae4603`. Branch `cursor/prefix-max-tree-reuse-h16`. Nearest-neighbor tree-reuse **−14.751** stays closed. Do **not** retune H=16, the 16-candidate successor, dense valley height, or confirmation physics `bf4b4412f4f683dd`. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused. MountainCarContinuous unused. No fitted critic.

This is a **compute-efficiency** test of a different reuse rule on the frozen MountainCar lookahead package. It is not a Q/V refit and not a cross-family learning claim.

## 1. Why this experiment

Nearest remaining open-loop height failed the 25-point rule even though successor distance was ~0: argmin over the whole tree is not max successor H=16 height. Prefix-max asks whether the **best cached continuation that already started with action `a`** is a usable cheap backup.

For sequences whose first action is `a`, remaining value at t=1 is the open-loop tail after `(s, a)` and does not require a second H=16 search from `s'`.

## 2. Physics and checkpoints

Development split `2a5cc4979642cc2a` with **fresh** resets `30000000+` / step seeds `30100000+`. Confirmation physics are not rolled out. Ten frozen residual checkpoints from `checkpoints/mountaincar_lookahead_h16` are loaded read-only. **0** optimizer updates. Seeds `25000000+`, `26000000+`, `27000000+`, and tree-reuse `29000000+` are not reused.

## 3. Frozen controllers

- Arm A `h16`: receding H=16 over 16 shared candidates from `s` (256 imagined/step).
- Arm B `prefix_max`: one H=16 tree from `s` (256). For each first action `a`, one `model.step` to `s'`. If any cached sequence has first action `a`, `V(s'|a)` is the **max** remaining open-loop value at those t=1 nodes. If none match, `V` is remaining at the nearest t=1 node (not the whole tree). `Q(a) = r + (1 − p) V(s'|a)`. **259** imagined/step. No `_score_batch` from `s'`. No fitted critic. No 771 lookahead arm.

Unchanged: residual 2×64, dense valley height, 200-step TimeLimit, no goal termination, H=16, 3 actions, argmax tie-break, time budget off.

## 4. Primary

Training-seed mean of (prefix-max return − H=16 return), three development tasks inside the seed. Student-t 95%, df 9. Margin **25**.

- Complete, mean ≥ 25, lo > 0: `prefix_max_tree_reuse_established`
- Complete, mean ≤ −25, hi < 0: `prefix_max_tree_reuse_harm_established`
- Else complete: `prefix_max_tree_reuse_not_established`
- Incomplete grid: `incomplete`

Closed nearest-neighbor tree-reuse and 16-candidate MountainCar labels stay closed. Secondary (cannot pass): prefix hit-rate; fallback rate.

## 5. Budget and authorization

**180 s** total process wall, **12,000** new real steps, **3,090,000** imagined transitions, **0** optimizer updates. Local CPU. Ten seeds × three tasks × two arms × 200 steps. Imagined identity: `10 × 3 × 200 × (256 + 259) = 3,090,000`.

**Collection is unauthorized** until a bound one-run allocation sets `authorized: true` and `runs: 1` for this configuration hash, protocol hash, and these caps. The consumed tree-reuse allocation does not authorize this screen.

Not a result, not learning-to-learn, not AGI.
