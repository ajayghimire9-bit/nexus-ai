# Horizon-alignment diagnostic — locked protocol v1

Base `aa3a5fb5af0f0145ee5d63aa471813499bdb8eb1` (`cursor/same-set-planning-audit`). Branch `cursor/horizon-alignment-diagnostic`. Score-correction stays **closed**. Same-set versus equal-horizon fresh stays closed. Confirmation physics stay untouched.

Frozen FiLM world models, encoders, saved contexts, discrete torque set, 16 candidates, published pendulum reward, and all 120 checkpoints stay read-only.

## Source-code audit (no collection)

Gymnasium `Pendulum-v1` is time-limited to **200** steps (`PENDULUM_MAX_STEPS`, `env.spec.max_episode_steps`). A diagnostic rollout terminates with `terminated=False` and `truncated=True` at step 200. That is a wrapper cutoff, not a physical absorbing state.

`RandomShootingMPC._score_batch` sums imagined step rewards over the candidate length. Survival weights use the **world-model termination logit** `p`, not elapsed episode time and not `TimeLimit`. The model input has no clock. Therefore production H=16 continues to score 16 imagined rewards at episode step 199, including 15 post-cutoff steps that the environment will never return.

The previous development secondary (equal-horizon fresh minus production H=16 **+3.646 [+0.280, +7.011]**; same-set minus H=16 **+4.479 [+1.046, +7.913]**) was a **16-step artificial evaluation window**, not episode termination. It cannot be read as general control improvement.

## Question

Does setting the scored planning horizon to `H = min(16, remaining environment steps)` improve **complete-episode** return versus always scoring H=16?

**H1:** alignment avoids optimizing past the real cutoff and improves episode return.

**H2:** the 16-step appearance disappears over a real 200-step episode.

**H3:** fixed H=16 is as good as or better than remaining-horizon planning.

Do not assume H1.

## Locked collection design (unauthorized)

Development only: three `pendulum_context_development` physics. Not source, not confirmation. One new phase-0 reset per decoder and task (seeds `9000000+`). Two visitors: student `(d+t) mod 5` and zero. Ten independently pretrained decoders are the statistical units. Average three tasks then two visitors inside each decoder.

From each restored `s0`, run four paired rollouts. Candidate sets are `candidate_sequences(step_seed, 16, h)`. The two controllers in a window share the **same per-step seed**, so they draw identical 16×16 sets whenever both use `h=16`.

1. **Short diagnostic (artificial 16-step cutoff, not episode end):**
   - **A-short:** fixed `h=16` every step, 16 environment steps, then stop.
   - **B-short:** `h = min(16, 16-t)`. Step 0 must match A-short. Later steps may differ.
2. **Full episode (real TimeLimit, primary):**
   - **A-full:** fixed `h=16` for 200 steps until truncation.
   - **B-full:** `h = min(16, 200-t)`. For steps `0…184`, `h=16`, so A-full and B-full must take identical actions from the shared seeds and shared state. They may first differ at step 185 (`remaining=15`).

Primary return is the **200-step** sum of published environment rewards. The 16-step sums are a diagnostic cutoff, not episode return.

No third arm. Same-set candidate reuse is closed.

## Primary estimand and labels

Primary: B-full minus A-full, decoder n=10, Student-t 95%, df 9. Practical margin **25** (the established full-episode control screen, not the 16-step margin of 1).

- Complete grid, mean ≥ 25, lower bound > 0: `horizon_alignment_gain`
- Complete grid, mean ≤ −25, upper bound < 0: `fixed_horizon_retained`
- Otherwise, if the 16-step diagnostic B-short minus A-short has mean ≥ 1 and lower bound > 0: `boundary_specific_alignment`
- Else: `horizon_alignment_not_established`
- Incomplete, identity failure on steps 0–184, or non-200 truncation: `incomplete`

Do not promote the short window or last-15-step tail into the primary pass. If identity on steps 0–184 fails, reject the grid.

Secondary, cannot upgrade the primary: short-window contrast; prefix-185 return difference (must be 0 if identity holds); tail-15 return difference; per-task and per-visitor intervals; action-mismatch rate on steps 185–199.

If `horizon_alignment_gain`, a later protocol may use confirmation physics. If `boundary_specific_alignment` or `horizon_alignment_not_established`, close this horizon-alignment claim; do not retune the same episodes.

## Budget and authority

Hard cap **180 seconds total process wall** (checkpoint loading, collection, validation, independent audit), **25,920** new real steps, **6,405,120** imagined transitions.

Breakdown, 60 cells: short A 960; short B 960; full A 12,000; full B 12,000. Imagined: short A 245,760; short B 130,560; full A 3,072,000; full B 2,956,800.

Local CPU. Six frozen FiLM models per decoder×task. 120 read-only checkpoints. No training. No Q/V. No confirmation physics.

The consumed same-set one-run, receding one-run, and exhausted 3,600-second standing session are unmodified. Collection is unauthorized until a new explicit human approval binds this configuration hash. The committed allocation has `authorized: false` and `runs: 0`.

## Tests and execution

Tests must lock TimeLimit=200 with `terminated=False`, planner scoring independent of elapsed time, identical 16×16 draws from a shared step seed, remaining-horizon identity on steps 0–184, seed disjointness from closed same-set/Q/receding blocks, unauthorized collection, and offline reconstruction of the previous 16-step H=16 secondary without new registered-grid steps.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_horizon_alignment.py tests/test_horizon_alignment_feasibility.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_horizon_alignment.py --feasibility
PYTHONPATH=src:.deps python3 scripts/run_horizon_alignment.py
# Collection is blocked until a fresh approved allocation is committed:
PYTHONPATH=src:.deps python3 scripts/run_horizon_alignment.py --execute
```

architecture_change_authorized: false
authorized: false
runs: 0
horizon: 16
n_candidates: 16
short_window: 16
episode_steps: 200
time_cap_s: 180
env_cap: 25920
model_cap: 6405120
score_correction_closed: true
confirmation_physics_authorized: false
primary: gain_full
practical_margin_full: 25.0
