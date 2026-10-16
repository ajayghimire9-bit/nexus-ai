# CartPole lookahead versus frozen H=3 — locked protocol v1

Base `98001817019102aadf20d5c0e60a23eeb341402b`. Branch `cursor/cartpole-lookahead-h3`. Pendulum lookahead transfer stays closed and is **not** used to retune horizon, candidates, or reward. Historically inspected CartPole confirmation physics stay closed.

This is a **different-family** test of the lookahead *mechanism*: one-step backup of the family’s frozen open-loop planner value versus executing the first action of that planner. CartPole’s frozen planner is **H=3 × 16**, not Pendulum H=16. Pendulum FiLM weights are not loaded (`obs_dim` 4 vs 3, `n_actions` 2 vs 3).

Successor value is frozen **open-loop H=3** score from `s'`, survival-weighted by predicted termination. Do not call it Bellman-consistent receding-policy value.

## 1. Why H=3, not H=16

V0.7.3 froze CartPole shooting at H=3 × 16 (budget 48). H=10–20 at that budget failed from candidate starvation. Copying Pendulum H=16 onto CartPole would ignore that evidence and would be a hyperparameter transfer from another family. This protocol keeps the CartPole frozen recipe.

## 2. Development physics

New holdout from rule `cartpole_lookahead_dev_v1`, split hash `4bc1f5866ac6c753`, disjoint from 81 registered CartPole keys including V0.7.3 confirmation:

- `cartpole_look_dev0`: (8.5, 0.39, 0.19)
- `cartpole_look_dev1`: (11.6, 0.9, 0.07)
- `cartpole_look_dev2`: (7.9, 0.88, 0.29)

This is a **development** screen. It is not CartPole confirmation of a selected method, and it is not Pendulum confirmation reuse.

## 3. Frozen controllers

Ten residual 2×64 MLPs trained with the frozen V0.7.2 recipe on `cartpole_default` only (1024 train + 256 val, 20 epochs). No FiLM, no Pendulum checkpoint.

- Arm A: score shared 16×3 candidates from `s`, execute `seq[argmax, 0]`.
- Arm B: for each of 2 first actions, one model step to `s'`, score the **same** 16×3 array from `s'`, execute `argmax_a [r + (1-p) max_k score_H3]`.

`r` uses frozen objective `both`: predicted +1 plus `-(|θ|+0.25|ω|)`. Time budget off. Shared `candidate_sequences(seed, 16, 3, n_actions=2)`.

Lookahead uses **98** imagined states per step versus **48** for H=3. This tests the complete package, not a compute-matched isolation.

## 4. Primary

Estimand: training-seed mean of (lookahead episode return − H=3 episode return), averaging three development tasks. Student-t 95%, df 9. Practical margin **25** (CartPole return is 0–500). Replication unit = source-training seed, not episode.

- Complete, mean ≥ 25, lo > 0: `cartpole_lookahead_established`
- Complete, mean ≤ −25, hi < 0: `cartpole_lookahead_harm_established`
- Else: `cartpole_lookahead_not_established`
- Incomplete grid: `incomplete`

There is no student-versus-zero estimand. Do not infer Pendulum student adaptation from this screen.

If this development screen later establishes the mechanism, the next recommendation is a **new** CartPole confirmation holdout, not Pendulum retuning. If it fails, do not retune H=3 from this sample.

## 5. Budget and authorization

Hard cap **300 seconds total process wall**, **42,800** new real steps (12,800 train/val + 30,000 control max), **2,190,000** imagined transitions max, **200** frozen-recipe epochs (10 × 20). Episodes may end before 500; the env cap is an upper bound.

Fresh eval resets `18000000+`, step seeds `18100000+`. Local CPU.

**Collection is unauthorized.** `authorized: false`, `runs: 0`. Do not execute until a new explicit human approval binds this configuration hash, protocol hash, and these caps.

## Tests

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_cartpole_lookahead.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_cartpole_lookahead.py
# Collection blocked:
PYTHONPATH=src:.deps python3 scripts/run_cartpole_lookahead.py --execute
```

Not a result, not learning-to-learn, not AGI.
