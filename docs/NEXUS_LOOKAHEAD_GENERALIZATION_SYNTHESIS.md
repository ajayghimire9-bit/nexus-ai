# Lookahead generalization synthesis — source-only audit

Base `57cff66fd5f8f0451fc45bcf9771a9d0bcdcf3d2`. Branch `cursor/lookahead-generalization-synthesis`. Offline. No new models, no simulations, no confirmation-physics access, no retune of closed screens, no merge to `main`.

Cited intervals are Student-t 95% with df 9. Practical full-episode margin is **25** return points unless a closed Q/V protocol registered a different threshold. Numbers are copied from saved artifacts, then rounded to three decimals as in the published reports.

This is not a result, not learning-to-learn, and not AGI.

## Locked cited evidence

| Screen | Label | Primary (lookahead − comparator) | Artifact SHA256 |
|---|---|---|---|
| Pendulum unmatched development | `bellman_backup_improves_episode_return` | **155.647 [109.825, 201.469]** | `d9bc3a0d…b86b0f6` |
| Pendulum unmatched transfer | `lookahead_transfer_established` | **98.608 [43.258, 153.957]** | `226e649e…75298019` |
| Pendulum compute-matched | `pendulum_compute_matched_lookahead_established` | **60.182 [11.439, 108.924]** | `02ae07e3…fe1853e6` |
| CartPole H=3 development | `cartpole_lookahead_not_established` | **4.000 [−5.048, 13.048]** | `62cc3776…8489098` |
| CartPole H=3 hard | `cartpole_hard_lookahead_not_established` | **4.600 [−7.481, 16.681]** | `53435901…0a90f7b7` |
| CartPole H=3 unsaturated | `cartpole_sat_lookahead_not_established` | **14.000 [−4.621, 32.621]** | `76fef73e…90de7826` |
| Acrobot unmatched development | `acrobot_lookahead_established` | **27.914 [13.962, 41.867]** | `83b9fbee…1a04e87` |
| Acrobot unmatched transfer | `acrobot_lookahead_transfer_established` | **37.961 [21.106, 54.816]** | `435fdcf7…ebcde5b` |
| Acrobot compute-matched | `acrobot_compute_matched_lookahead_not_established` | **12.834 [3.815, 21.853]** | `ed99327d…e256bcc2` |
| MountainCar unmatched development | `mountaincar_lookahead_established` | **44.092 [13.945, 74.239]** | `28e19af3…5fa78eb` |
| MountainCar unmatched transfer | `mountaincar_lookahead_transfer_established` | **50.366 [36.493, 64.239]** | `bbf22c17…80b81678` |
| MountainCar compute-matched | `mountaincar_compute_matched_lookahead_established` | **54.649 [26.611, 82.686]** | `8a829874…3ca6c8f` |
| MountainCarContinuous unmatched development | `mountaincar_continuous_lookahead_established` | **69.758 [29.321, 110.196]** | `668a9a85…1b49a15` |
| 15-coeff first-action Q | `aligned_first_action_gain_not_established` | **−3.535 [−9.840, +2.769]** | `1ea6c5e2…43e3828a` |
| Terminal-value correction | `local_first_action_inconclusive` | **−0.221 [−5.881, +5.438]** | `74dcff9c…a86f9a420` |
| Action-conditioned Q resume | `action_conditioned_gain_not_established` | **−4.293 [−15.751, +7.165]** | `aa78514a…c01a3793` |

MountainCarContinuous confirmation was not collected. Capacity-matched 81-coefficient Q was never collected. Those closed splits stay unused.

## 1. What is common across the successful controllers

The controllers that cleared the 25-point full-episode rule share a **planning rule**, not a world-model weight vector.

Shared algorithm:

1. Family-specific world model, frozen at evaluation.
2. `RandomShootingMPC` open-loop H=16 over 16 random action sequences.
3. One-step lookahead: for each of three discrete first actions, take one imagined step to `s'`, score the **same** 16 sequences from `s'`, and backup `Q(a) = r + (1 − p) max_k V̂_H16(s', seq_k)`.
4. Receding execution: replan at every real step.
5. Dense, non-ceiling 200-step rewards (Pendulum native torque cost; Acrobot upright height; MountainCar / MountainCarContinuous valley height). Episodes are `TimeLimit=200` with goal termination off, so return is not truncated by a sparse success flag.
6. Ten independent training units, Student-t 95% df 9, registered margin 25.

Shared **non**-ingredients:

- No shared network weights across families. Pendulum uses frozen FiLM `ContextWorldModel`. CartPole, Acrobot, MountainCar, and MountainCarContinuous each train a residual 2×64 MLP on that family's transitions.
- No fitted critic, Q, or terminal-value readout in the successful package.
- No cross-family replay, Reptile, or context encoder at control time for the residual families.

CartPole is the informative failure of the same algorithm under a survival ceiling: three development draws (4.000, 4.600, 14.000) never cleared 25. That is a measurement-and-horizon mismatch, not a disproof of backup on dense-height families.

## 2. Why extra candidate search explains more of the Acrobot improvement

Lookahead uses **771** imagined transitions per real step (`3 + 3 × 16 × 16`). Sixteen-candidate H=16 uses **256**. Compute-matched H=16 uses **48** candidates (**768** imagined/step) against a frozen 16-candidate lookahead successor (**771**). The extra 32 sequences are a prefix-stable continuation of the same RNG draw.

Unpaired remainder after giving H=16 that extra search (development physics, different episode seeds from the unmatched screens):

| Family | Unmatched lookahead − 16-cand H=16 | Compute-matched lookahead − 48-cand H=16 | Unpaired points closed by extra H=16 search | Registered 25-point remainder |
|---|---|---|---|---|
| Acrobot | 27.914 | **12.834** | 15.080 (~54% of the unmatched gap) | Fail (mean < 25; lo > 0) |
| Pendulum | 155.647 | **60.182** | 95.465 (~61% of the unmatched gap) | Pass |
| MountainCar | 44.092 | **54.649** | none on this unpaired sample | Pass |

Extra search does **not** close a uniquely large *fraction* on Acrobot (Pendulum's unpaired fraction is similar). It explains more of Acrobot **relative to the registered decision rule** because the unmatched Acrobot gap was only 2.914 points above 25. Closing ~15 points dropped the remainder below the margin while leaving a strictly positive interval. Pendulum started 130 points above the margin, so even a larger absolute extra-search share left a 60-point remainder. MountainCar's unmatched remainder was already well above 25, and the compute-matched draw did not shrink it.

Scientific reading: on Acrobot, a large share of the 16-candidate win is **more H=16 shooting**, not one-step backup of successor height. On Pendulum and MountainCar, backup still clears 25 after that extra shooting. These are unpaired, family-specific, and not a license to retune any closed screen.

## 3. Shared planning algorithms versus separately trained world models

| Layer | Shared? | Evidence |
|---|---|---|
| `RandomShootingMPC` + receding H=16 | Algorithm copy | Same class, same 16×16 recipe, family `step_reward` injected |
| One-step backup of open-loop successor height | Algorithm copy | Same `lookahead_first_action` pattern; 771 imagined/step |
| Residual 2×64 world model | Recipe copy, **weights not shared** | Fresh training per family, frozen V0.7.2 sizes |
| Pendulum FiLM context model | Family-specific | Not loaded into CartPole/Acrobot/MountainCar screens (`pendulum_weights: false`) |
| Checkpoints | Never copied across families | Locked `checkpoint_sha256` lists are disjoint |
| Reward | Analogous dense height/cost, **not a shared head** | CartPole kept sparse survival and failed the ceiling |

A copied planner with a new world model is **algorithm transfer**, not weight transfer and not meta-learning. Each successful family retrained dynamics from that family's transitions. The synthesis does not treat a YAML clone of H=16 as a learned cross-family skill.

## 4. Audit: do existing results support cross-family learning or meta-learning?

**No.**

Required for a genuine cross-family learning claim, none of which exist here:

1. One model, memory, or encoder trained on more than one environment family and then evaluated on a held-out family.
2. A meta-learner whose update rule, not just its hyperparameters, is itself trained and compared to a matched non-meta baseline (the Reptile vs multitask pilot already lost in its Pendulum configuration; it is not L2L).
3. Weight or latent transfer that beats a family-specific from-scratch controller on full-episode return.

What the lookahead series actually shows:

- The **same planning algorithm** improves dense-height control on Pendulum, Acrobot, MountainCar, and MountainCarContinuous **when each family has its own trained world model**.
- CartPole's three H=3 draws failed.
- Acrobot compute-matched failed the 25-point isolation of backup from extra search.
- Historical Pendulum student-minus-zero control on disjoint physics was negative transfer (fresh-episode difference **−30.7**, concentrated in steps 16–199). That is the opposite of cross-family or even cross-physics learning-to-learn.

Copying a planner is an engineering reuse of a tested decision rule. It is not evidence that NEXUS learned a domain-general world model, a domain-general value function, or a learning rule that improves with the number of families. Do not upgrade `mountaincar_lookahead_transfer_established` or any sibling label into a meta-learning claim.

## 5. Computational bottlenecks in the 771-transition lookahead

From `lookahead_first_action` plus `RandomShootingMPC._score_batch` (`src/nexus/world/planning.py`):

1. **Three independent successor trees.** For each discrete action the planner calls `model.step` once, then `_score_batch(s', sequences)` which loops `horizon=16` and, at each t, batches `n_candidates=16` `model.step` calls. Cost: `3 + 3×16×16 = 771`. The 16-candidate H=16 arm from `s` already spent 256 of those inferences on a tree that lookahead then throws away.
2. **Python horizon loop, not a fused unroll.** `_score_batch` steps sequentially in Python. Each tick is a residual-MLP (or FiLM) forward plus survival multiply. There is no JAX/scan, no cached KV, and no prefix reuse across the three `s'` trees.
3. **No prefix sharing across first actions.** Sequences are identical for all three backups, but because they are scored from different `s'`, the implementation re-simulates the entire 16-step tail three times.
4. **Receding every real step.** A 200-step episode imagines `200×771 = 154,200` transitions per lookahead arm. Ten seeds × three tasks × two arms already reach millions of imagined states before any extra family is added.
5. **Dominant term is successor search, not the one-step backup.** The scientifically useful part of lookahead is the three first-action queries. 768 of 771 imagined states are open-loop H=16 from `s'`. That is why compute-matched 48-candidate H=16 (768 from `s`) was the right isolation, and why a cheaper successor value is the right efficiency question.

Not a bottleneck in the current residual models: GPU dispatch, ensemble disagreement, or time-budget pruning (`enforce_time_budget: false` on these screens).

## 6. One mechanism: tree-reuse lookahead

**Proposal (one mechanism, not a menu):** grow the usual 16-candidate H=16 tree **once from the current state `s`**, cache every imagined `(state, remaining open-loop value)` along those 256 transitions, then for each first action `a` take **one** imagined step to `s'` and set

`V_tree(s') = remaining value of the nearest cached imagined state` (Euclidean, `tau = inf` locked),

`Q(a) = r + (1 − p) V_tree(s')`.

Imagined cost: **256 + 3 = 259** per real step. No second H=16 search from `s'`. No fitted critic. Nearest-neighbor lookup is not a model step and is not counted as an imagined transition.

Falsifiable content: the current-step open-loop tree already contains local long-horizon height that is a good enough interpolator of successor value to keep the registered 25-point full-episode gain versus 16-candidate H=16 on MountainCar development physics.

MountainCar is the testbed because compute-matched backup already survived extra search there (`54.649`), so a cheap backup that fails cannot be excused as “it was only extra shooting.” Frozen development checkpoints are reused read-only. Confirmation physics `bf4b4412f4f683dd` stay unused. MountainCarContinuous confirmation is not this experiment.

## 7. Distinction from closed Q/V and terminal-value failures

| Closed attempt | What it learned | Primary | Why tree-reuse is a different hypothesis |
|---|---|---|---|
| 15-coeff linear first-action Q | Ridge Q(s,z,a) on source 64-step returns | **−3.535 [−9.840, +2.769]** | Tree-reuse fits **zero** readout weights |
| 78-coeff terminal-value correction | Ridge V of imagined H=16 endpoints | **−0.221 [−5.881, +5.438]** | Tree-reuse does not score a terminal latent; it reuses remaining open-loop height already computed for H=16 |
| Action-conditioned 16-coeff Q | Action×observation Q, same 64-step labels | **−4.293 [−15.751, +7.165]** | Tree-reuse does not change action ranking through a global linear map |
| Capacity-matched 81-coeff Q | Never collected | — | Not reopened |

Failure modes those screens actually hit: source RMSE ~70, development RMSE 107.5, additive Q's state-independent argmax, and a value readout that changed decisions without improving 64-step or 48-step return. None of those diagnose “the H=16 tree from `s` is a bad interpolator of successor height.” Tree-reuse can fail for a new reason (nearest cached state is off-manifold, remaining value is prefix-conditioned on the cached sequence, Euclidean distance is a bad metric). If it fails, the 771 controller stays the known MountainCar package; this protocol does not authorize another ridge Q.

## 8. Next major research milestone

Toward an adaptive agent that operates across environment families, the evidence now separates three claims:

1. **Algorithm-level planning generalization (supported, bounded):** one-step backup of frozen H=16 height improves dense-height full-episode return on four families with separately trained world models. Isolation from extra search holds on Pendulum and MountainCar, not Acrobot.
2. **Compute-efficient long-horizon first-action planning (untested):** can that backup keep the 25-point MountainCar remainder at ~259 imagined states instead of 771?
3. **Cross-family learning (unsupported):** no shared weights, no meta-update, historical negative transfer on disjoint Pendulum physics.

The next **major** milestone is therefore:

**A compute-efficient receding planner whose first-action long-horizon backup does not spawn a fresh H=16 tree per candidate, transferred as an algorithm across families that keep their own world models, measured by full-episode control return against H=16, with compute-matched isolation where the unmatched package wins.**

That is still not weight transfer, not learning-to-learn, and not AGI. It is the smallest path from “we can copy a 771-step planner” to “an adaptive agent can afford long-horizon first-action planning in more than one family.”

The one falsifiable experiment that starts that milestone is locked in `docs/NEXUS_TREE_REUSE_LOOKAHEAD_PROTOCOL.md`. Collection is unauthorized until a new explicit approval binds that configuration hash, protocol hash, and the caps below.

MountainCarContinuous confirmation remains a smaller later within-family transfer question. It does not advance cross-family efficiency.
