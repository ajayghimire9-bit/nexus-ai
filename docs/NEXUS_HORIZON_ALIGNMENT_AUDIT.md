# Horizon-alignment diagnostic — source audit and offline diagnosis

Base `aa3a5fb5af0f0145ee5d63aa471813499bdb8eb1`. Branch `cursor/horizon-alignment-diagnostic`. **Registered collection has not started.** Score-correction closed. Confirmation unused.

## Environment termination

`PENDULUM_MAX_STEPS = 200`. Gymnasium `Pendulum-v1` / `make_task_env` exposes `spec.max_episode_steps == 200`. A unit-test rollout of development physics with action 0 ran **200** steps and ended `terminated=False`, `truncated=True`. That is `TimeLimit`, not an absorbing physical state. The pendulum can be stepped further only after a new `reset`.

## Planner horizon handling

`RandomShootingMPC.act` always draws `n_candidates × self.horizon` sequences (`16 × 16` for Pendulum). `_score_batch` adds imagined `pendulum_step_reward` for each of those `h` steps. The only early-stop weight is the world-model sigmoid termination logit `p`. The model does **not** receive elapsed time. It does **not** implement `TimeLimit`.

Therefore production H=16, at episode step 199, still scores 16 imagined rewards, 15 of which lie after the environment will truncate. The proposed mechanism (planning past a cutoff) **exists** for TimeLimit. It is not already clipped.

A 16-step diagnostic cutoff is a different, artificial boundary. Remaining-horizon there shortens from the first step after `t=0`. On a 200-step episode it shortens only on steps 185–199.

## Previous result, reread

Locked same-set development confirmation (`same_set_advantage_not_established`):

- Same-set minus equal-horizon fresh: **+0.834 [−0.955, +2.623]** (primary, inconclusive)
- Same-set minus production H=16: **+4.479 [+1.046, +7.913]** (secondary)
- Equal-horizon fresh minus production H=16: **+3.646 [+0.280, +7.011]** (secondary)

Those secondaries used a **16-step artificial window**. Production H=16 planned past that window. They do not measure complete-episode control. They cannot pass H1.

## Identity prediction

If both controllers share the per-step candidate seed and the same restored state, they must choose the same action on full-episode steps **0–184** (`h=16` for both). The first legal disagreement is step **185**. If that identity fails, the registered grid is `incomplete`.

## Recommendation

Run the locked development comparison of remaining-horizon MPC versus fixed H=16, with the **200-step episode as primary** (margin 25) and the 16-step window as a non-promotable diagnostic (margin 1). Do not assume remaining-horizon is better. Collection is unauthorized until a new one-run budget is approved.

Requested budget: **180 s total process**, **25,920** real steps, **6,405,120** imagined transitions, 10 decoders × 3 development tasks × 2 visitors × one paired short window and one paired full episode. Local CPU. No training. No confirmation physics.
