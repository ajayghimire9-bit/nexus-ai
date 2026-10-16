# Tree-reuse lookahead versus frozen H=16 — locked protocol v1

Base `57cff66fd5f8f0451fc45bcf9771a9d0bcdcf3d2`. Branch `cursor/lookahead-generalization-synthesis`. MountainCar unmatched development, unmatched confirmation, and compute-matched screens stay closed. Do **not** retune H=16, the 16-candidate successor, dense valley height, or confirmation physics `bf4b4412f4f683dd`. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused. MountainCarContinuous unused.

This is a **compute-efficiency** test of the frozen MountainCar lookahead package. It is not a new transfer test, not a Q/V refit, and not a cross-family learning claim.

## 1. Why this experiment

Successful lookahead spends **771** imagined model states per real step, of which **768** are a fresh open-loop H=16 search from each successor `s'`. Sixteen-candidate H=16 from `s` already spends **256**. Closed Q and terminal-value readouts did not replace that search. Tree-reuse asks whether the tree grown from `s` is already a usable long-horizon value at `s'`.

## 2. Physics and checkpoints

Development split `2a5cc4979642cc2a` with **fresh** resets `29000000+` / step seeds `29100000+`. Confirmation physics are not rolled out. Ten frozen residual checkpoints from `checkpoints/mountaincar_lookahead_h16` are loaded read-only. **0** optimizer updates. Development episode seeds `25000000+`, confirmation seeds `26000000+`, and compute-matched seeds `27000000+` are not reused.

## 3. Frozen controllers

- Arm A `h16`: receding H=16 over 16 shared candidates from `s` (256 imagined/step).
- Arm B `tree_reuse`: one H=16 tree from `s` (256), cache `(state, remaining open-loop value)` at every imagined state including the 16 terminals with remaining 0; for each of three first actions, one `model.step` to `s'`; `V(s')` is the remaining value of the nearest cached state in Euclidean observation distance; `Q(a) = r + (1 − p) V(s')`. Distance threshold `tau = inf` (always nearest). **259** imagined/step. No `_score_batch` from `s'`. No fitted critic.
- Arm C `lookahead`: unchanged three-action backup of frozen open-loop 16-candidate H=16 height from `s'` (**771**). Diagnostic only.

Unchanged: residual 2×64, dense valley height, 200-step TimeLimit, no goal termination, H=16, 3 actions, argmax tie-break, time budget off. Successor value for arm C remains frozen open-loop H=16 height, not receding-policy Q.

## 4. Primary

Training-seed mean of (tree-reuse return − H=16 return), three development tasks inside the seed. Student-t 95%, df 9. Margin **25**.

- Complete, mean ≥ 25, lo > 0: `tree_reuse_lookahead_established`
- Complete, mean ≤ −25, hi < 0: `tree_reuse_lookahead_harm_established`
- Else complete: `tree_reuse_lookahead_not_established`
- Incomplete grid: `incomplete`

Arm C cannot upgrade or replace this label. Closed 16-candidate and compute-matched MountainCar labels stay closed.

Secondary (cannot pass the screen): lookahead minus tree-reuse; lookahead minus H=16 on this fresh-seed draw; mean nearest-neighbor distance.

## 5. Budget and authorization

**180 s** total process wall, **18,000** new real steps, **7,716,000** imagined transitions, **0** optimizer updates. Local CPU. Ten seeds × three tasks × three arms × 200 steps. Imagined identity: `10 × 3 × 200 × (256 + 259 + 771) = 7,716,000`.

**Collection is unauthorized.** `authorized: false`, `runs: 0`. Do not execute until a new explicit human approval binds this configuration hash, protocol hash, and these caps. The 2026-10-16 standing grant does not authorize this experiment.

Not a result, not learning-to-learn, not AGI.
