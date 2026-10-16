# Same-set suffix replanning — locked protocol v1

Base `16d904cf5cd38df6e4c6a2f4295ee876053f0ffa` (`cursor/receding-policy-consistency`). Branch `cursor/same-set-planning-audit`. Terminal-value and first-action Q score-correction remain **closed**. The source receding-consistency primary label `replan_consistency_not_established` is unchanged. Confirmation physics stay untouched.

Frozen FiLM world models, encoders, saved contexts, H=16, 16 candidates, published pendulum reward, and all 120 checkpoints stay read-only.

## Retrospective audit (no new steps)

The completed 160-cell source capture is reconstructed from saved returns, reset seeds and selected plans. Independent decoder-level Student-t 95% intervals are computed for same-set minus recede-fresh and same-set minus commit-16. Per-task, per-visitor and per-decoder values are reported. Candidate sets are rebuilt with `candidate_sequences(seed)`.

These analyses are **secondary and retrospective**. They cannot pass, fail, or replace the locked source primary. They cannot be treated as a preregistered success.

Known implementation inequality in that source run: same-set receding scores the remaining suffixes of the original 16-step window (horizons 15…1; 1,920 imagined transitions per cell). Fresh receding scores a new 16×16 set at each of 15 later states (horizons always 16; 3,840 imagined transitions per cell) and can optimize imagined reward after the 16-step evaluation ends. Same-set is aligned with the evaluation window; fresh is not. Predicted scores and per-step rewards were not stored, so return gaps cannot be decomposed into score gaps.

## Question for the confirmation (unauthorized)

Does repeatedly selecting among remaining suffixes of previously generated plans provide a reliable 16-step return advantage over **equal remaining-horizon** fresh-candidate replanning on new development states?

**H1:** same-set suffix replanning preserves useful plan information and improves 16-step return.

**H2:** the source appearance is sampling noise, limited search, or unequal candidate coverage / horizon mismatch.

**H3:** neither equal-horizon method reliably outperforms the other.

## Locked collection design (unauthorized)

Development only: three `pendulum_context_development` physics. Not source, not confirmation. One new phase-0 reset per decoder and task (seeds `8000000+`). Two visitors per reset: student `(d+t) mod 5` and zero. Ten independently pretrained decoders are the statistical units. Average three tasks then two visitors inside each decoder. Student seeds are not extra decoder replications.

At each restored `s0`, draw candidate set `C` (16×16) with a visitor-specific seed. Score `C` with the visitor's frozen H=16 planner (`base` scores only; V and Q unused). Select plan `π`. Independently draw `C2` at the same `s0` (search-noise control). Restore `s0` for each executed arm:

1. **A. Same-set suffix replanning:** execute `π[0]`; at remaining horizon `h = 15…1` re-score the remaining suffixes of `C` (shape 16×h); take the new first action.
2. **B. Equal-horizon fresh replanning:** execute `π[0]`; at the same remaining horizons draw a **new** 16×h set and re-score. This is not the source recede-fresh controller. It equalizes candidate count and scored horizon with A.
3. **C. Original H=16 MPC:** from `s0`, the production receding RandomShootingMPC (`H=16`, 16 candidates) chooses every action, including the first. It is **not** yoked to `π[0]` and is **not** remaining-horizon equalized. It is the deployed baseline, not an equal-budget variant of A/B.

Primary return is the **16-step** sum of published environment rewards.

Do not describe A and B as equivalent to C merely because all three begin with 16 candidates. A and B each score 1,920 imagined receding transitions per cell. C scores 4,096 production H=16 transitions per cell. Environment steps are equal (16 per arm per cell).

## Primary estimand and screen

Primary contrast: A minus B (`gain_same_fresh`), decoder n=10, Student-t 95%, df 9. Pass `same_set_replanning_gain` only if the complete 60-cell grid is valid, mean ≥ 1, and lower bound > 0. Entirely negative with mean ≤ −1: `fresh_equal_horizon_gain`. Otherwise `same_set_advantage_not_established`. Incomplete runs are `incomplete`. Do not change this screen after seeing results.

Secondary, cannot upgrade the primary label: A minus C; B minus C; search-noise first-action switch at `s0`; same-set switch at `s1`; equal-horizon fresh switch at `s1`; per-task and per-visitor intervals.

If the primary passes, a later protocol may test fresh physics and full episodes. That test is not this experiment. If it fails, do not retune same-set receding; recommend a distinct hypothesis.

## Budget and authority

Hard cap **60 seconds total process wall** (checkpoint loading, collection, validation, independent audit), **2,880** new real steps, **506,880** imagined transitions. Breakdown: A 960; B 960; C 960. Imagined: s0 `C` 15,360; search-noise `C2` 15,360; A recede 115,200; B recede 115,200; C production 245,760. No new support. No Q/V refit. Local CPU only. Memory: six frozen FiLM models per decoder×task, 120 read-only checkpoints.

The consumed receding one-run and the exhausted 3,600-second standing session are unmodified and are not this budget. Collection is unauthorized until a new explicit human approval binds this configuration hash. The committed allocation has `authorized: false` and `runs: 0`.

## Tests and execution

Tests must lock remaining-horizon identity, equal A/B recede imagined counts, production C as H=16×16, seed disjointness from closed Q and receding blocks, unauthorized collection, preservation of receding parent hashes, and the offline 160-cell reconstruction without environment steps. They must not collect the registered development grid.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_same_set_planning.py tests/test_same_set_planning_feasibility.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_same_set_planning.py --feasibility
PYTHONPATH=src:.deps python3 scripts/run_same_set_planning.py
# Collection is blocked until a fresh approved allocation is committed:
PYTHONPATH=src:.deps python3 scripts/run_same_set_planning.py --execute
```

architecture_change_authorized: false
authorized: false
runs: 0
horizon: 16
n_candidates: 16
time_cap_s: 60
env_cap: 2880
model_cap: 506880
score_correction_closed: true
confirmation_physics_authorized: false
