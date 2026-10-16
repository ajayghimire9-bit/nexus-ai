# CartPole lookahead versus frozen H=3 on the unsaturated holdout — complete development screen

## Registered decision

The locked 120-episode (10 training seeds × 6 tasks × 2 arms) grid completed. Label: `cartpole_sat_lookahead_not_established`.

Lookahead minus frozen H=3 episode return: **14.000 [−4.621, 32.621]**. The mean is below 25 and the interval includes 0, so the registered improvement rule does **not** pass.

The point estimate is positive (lookahead **494.433**, H=3 **480.433**). That cannot upgrade the primary. Six of ten seed means for H=3 were already 500. Lookahead reached 500 on seven of ten seed means. 54 of 60 H=3 episodes and 57 of 60 lookahead episodes hit the TimeLimit.

H=3 was not retuned. Ceilinged tasks were not dropped. Pendulum FiLM weights were unused. V0.7.3 confirmation tuples were unused. Successor value remained open-loop H=3 from `s'`. Models were trained with new collect seeds, so this H=3 return is not a paired re-use of the diagnostic checkpoints.

## What was tested

Holdout `a69833ab38a34ab4`: (13.2, 0.27, 0.23), (15.6, 0.25, 0.28), (15.4, 0.27, 0.20), (15.5, 0.30, 0.28), (16.0, 0.34, 0.20), (13.8, 0.31, 0.27). Ten residual 2×64 MLPs, frozen V0.7.2 recipe, shared 16×3 candidates, objective `both`, time budget off. Replication unit: source-training seed. Student-t 95%, df 9. Margin 25.

## Secondary (cannot upgrade)

Per-task return_gain:

- task0: **6.100 [−7.698, 19.898]**
- task1: **0.000 [0.000, 0.000]** (both arms 500 on every seed)
- task2: **0.000 [0.000, 0.000]** (both arms 500 on every seed)
- task3: **26.600 [−33.569, 86.769]** (includes 0; seed 7 H=3 **234**)
- task4: **23.800 [−40.138, 87.738]** (includes 0)
- task5: **27.500 [−41.563, 96.563]** (includes 0)

## Integrity

`--results-audit` passed. Reward sums and return_gain identity reconstructed. `drop_ceilinged_tasks` false. `retuned_h3` false. Pendulum weights flag false. Training epochs 200. 71,292 real steps (under 72,800 cap). 4,290,916 imagined (under 4,380,000 cap). Retries: 0.

## Provenance

Branch `cursor/cartpole-lookahead-sat-h3`. Preparation SHA **b8c94161c1adb539c5d6290adc422d0024cd9ee0**. One-run SHA **a7b1b019662e7920db03012d11e1262a5f198148**.

- Config SHA256 `7fe2a70eaf88953f2203f9f70de586d69991e16741864075fcdfbe7148547dbe`
- Protocol SHA256 `3c82cdd477082ea3898ac346e4d193eda5506e6aab947f259d76fe954d75dac8`
- Raw artifact SHA256 `76fef73eb814607a4567ff6d655f4a2ea8f5134cf6b938a2f93d3bc690de7826`

Execute **23.088 s**, process **24.176 s**. One-run remaining is 0.

## One next experiment

Do not retune H=3 from this sample, and do not drop tasks after seeing task 1 and task 2 ceiling. CartPole lookahead versus frozen H=3 is now not established on three development draws. A later distinct question is whether the same frozen lookahead *mechanism* beats the frozen planner on a **family without a 500-step survival ceiling**. That proposal is not implemented and is not authorized here.
