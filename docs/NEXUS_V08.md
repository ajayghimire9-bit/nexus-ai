# NEXUS V0.8 — Adaptive world models and predictive memory

Status: **measured** on CartPole physics variants. Not AGI. V0.6 and V0.7 remain closed. This track does **not** claim a general continual learner.

Branch: `cursor/v08-adaptive-world-model`. Parent: `25f4bf9` (`cursor/v073-planning-final`). Artifact: `artifacts/v08_adaptation.json` (wall **172 s**, n=5 model seeds). Prior V0.6/V0.7 JSON files were not overwritten.

## Question

Can NEXUS reuse a frozen V0.7 residual world model, detect a physics shift from prediction residuals, update from a matched target budget, and retrieve stored snapshots when a task returns — without privileged gravity/length/mass at inference?

## Frozen V0.7 baseline (Phase 1)

Unchanged: residual 2×64 MLP, 1024+256 transitions, 20 epochs, H=3 random-shooting MPC (16 candidates, objective `both`, persistent episode RNG). Regression tests cover the recipe, confirmation physics disjointness, and reproducible H=3 actions.

Source (default CartPole) one-step MAE on val is small (four of five seeds ≈ **0.0065–0.0073**; seed 3 **0.0188**). Source H=3 return is **500** on all five seeds.

## Protocol

- **Source train:** default CartPole `(g,L,m)=(9.8, 0.5, 0.1)`, collect seeds 90k-band.
- **Development (selection only):** sequence B `(8.05, 0.54, 0.21)`, C `(12.15, 0.66, 0.04)`, and held-out dev `(6.15, 0.36, 0.17)`. Method/budget choice used **dev val MAE**, never confirmation.
- **Confirmation (unused for selection):** eval seed **94000**; physics `(8.65, 0.26, 0.20)`, `(11.75, 0.69, 0.055)`, `(5.45, 0.47, 0.26)`.
- **Budgets:** 0, 64, 128, 256, 512 matched target transitions.
- **Methods:** frozen source, fine-tune, scratch, replay mix, frozen trunk + additive adapter.
- Model inference and Page–Hinkley detection consume residuals only. Imagined MPC does not call the simulator.

Replication unit = source-model seed (Student-t 95%, df=4).

## Detection (Phase 2)

Mean one-step MAE of the **frozen source** model:

| Stream | typical MAE (per seed) |
| --- | --- |
| Source holdout | 0.0045–0.0074 (seed 3: 0.0059) |
| Sequence B | 0.011–0.014 |
| Sequence C | 0.019–0.022 |
| Dev | 0.031–0.037 |

Page–Hinkley alarm fraction: source **0.145 [−0.007, 0.298]** vs B **0.694 [0.207, 1.18]**. Residual **magnitude** rises on unused physics. The binary detector is **not reliable**: seed 3 never alarmed on B or C (`first_alarm=None`). Do not treat CUSUM as a calibrated change-point detector.

## Adaptation of predictions (Phase 3, confirmation MAE)

Mean one-step MAE across the three confirmation tasks:

| Budget | Frozen | Fine-tune | Scratch | Replay | Adapter |
| --- | --- | --- | --- | --- | --- |
| 0 | **0.0348 [0.0332, 0.0364]** | same (no data) | same | same | same |
| 64 | 0.0348 | 0.0230 [0.0214, 0.0246] | 0.0961 [0.0819, 0.110] | **0.0207 [0.0197, 0.0217]** | 0.0328 [0.0309, 0.0347] |
| 128 | 0.0348 | **0.0166 [0.0144, 0.0188]** | 0.0946 [0.0818, 0.107] | 0.0192 [0.0178, 0.0206] | 0.0303 [0.0291, 0.0316] |
| 256 | 0.0348 | **0.0112 [0.0091, 0.0133]** | 0.0470 [0.0346, 0.0594] | 0.0187 [0.0180, 0.0193] | 0.0271 [0.0261, 0.0282] |
| 512 | 0.0348 | **0.00897 [0.00868, 0.00926]** | 0.0224 [0.0138, 0.0310] | 0.0174 [0.0161, 0.0188] | 0.0203 [0.0188, 0.0218] |

No seed showed fine-tune MAE worse than frozen at budget 128 (no negative transfer on this metric). Scratch is **failed adaptation** at every budget tested: higher MAE than frozen through 256, and still worse than fine-tune at 512.

Dev selection (val MAE): budget 0 → frozen; 64/256/512 → fine-tune on all five seeds; 128 → fine-tune on four seeds, replay on one.

Open-loop 3-step MAE on confirmation (mean over tasks×seeds): frozen **0.0317** vs fine-tune@128 **0.0213**. Horizon-8 is almost unchanged (**0.0398** vs **0.0385**). Short-horizon prediction improves more than long-horizon.

## Planning / control (Phase 3 continued)

Frozen H=3 already returns **500** on all confirmation tasks at every seed. Fine-tune, replay (except budget 64), and adapter stay at **500**. That is a **ceiling**: improved MAE did **not** convert into higher return.

Scratch **hurts** control. Budget 128: scratch **171 [18, 324]** vs frozen **500**; paired scratch−frozen **−329 [−482, −176]**. Replay at 64: **484 [440, 528]** (one seed dropped below 500).

Per confirmation task at budget 128, frozen/fine-tune/replay/adapter remain 500. Hardest prediction is confirm_0 (short heavy pole): frozen MAE **0.072** vs fine-tune **0.032**, still 500 return.

## Predictive memory and continual sequence (Phases 4–5)

Sequence A→B→C→return to A, 128 target steps per stage.

After C, the **shared** fine-tuned model’s MAE on A is higher than the frozen A snapshot (e.g. seed 0: 0.023 vs 0.007). After the return-to-A update: naive shared MAE on A **0.0108 [0.0078, 0.0138]** vs snapshot **0.0093 [0.0026, 0.0159]** (CI overlap). Retrieval uses probe MAE, not task IDs; retrieval cost **192** model inferences/seed; memory **≈105 kB**/seed; source checkpoint **19.8 kB**.

This is **snapshot retrieval plus a small replay buffer**, not demonstrated retention inside one shared net. Planning on A remains 500 throughout, so forgetting is visible in MAE only.

## Exploration (Phase 6)

Matched **128** target interactions on B. Fine-tune after **random** collection MAE **0.0109 [0.0073, 0.0144]** vs **uncertainty** (source-ensemble disagreement) **0.0157 [0.0108, 0.0207]**. Both H=3 returns **500**. Extra disagreement-seeking did **not** improve subsequent prediction in this setup.

## Costs

Mean source learning steps **1280**/seed (1024 train + 256 val). Every target method at budget *N* used *N* target env steps (0 if frozen-only). Eval episodes are counted separately in the artifact. Wall **172 s** on CPU.

## Scientific close-out (success criteria)

1. **Recognize unfamiliar dynamics:** residual MAE rises on unused physics. Binary Page–Hinkley is noisy (missed seed 3). Partial.
2. **Improve predictions from limited new data:** **yes** for fine-tune and replay vs frozen; **no** for scratch at these budgets.
3. **Convert that into better control:** **not demonstrated** (frozen H=3 already at CartPole ceiling on these confirmation tasks). Scratch **worsens** control.
4. **Reuse prior knowledge on a revisited task:** replay beats scratch; frozen snapshot remains a strong A predictor. Not a clear win of shared-model continual learning over the snapshot.
5. **Retain vs retrieve:** forgetting of A is visible in the shared net after B/C; the stored snapshot preserves A. Memory bytes and retrieval inferences are accounted.

CartPole with the V0.7 planner is too easy for control transfer. Prediction transfer is the positive, bounded result.

Not AGI. Not a new physics family. Not V0.9.
