# Harder CartPole lookahead versus frozen H=3 — complete development screen

## Registered decision

The locked 60-episode (10 training seeds × 3 tasks × 2 arms) harder-physics grid completed. Label: `cartpole_hard_lookahead_not_established`.

Lookahead minus frozen H=3 episode return: **4.600 [−7.481, 16.681]**. The mean is below 25 and the interval includes 0, so the registered improvement rule does **not** pass.

This is still a near-ceiling result, not a proof that lookahead cannot help CartPole. Frozen H=3 already returned **500** on 8 of 10 training-seed means and on 28 of 30 episodes. Lookahead returned **500** on 9 of 10 seed means and on 29 of 30 episodes. Seed 6 was the only large positive gap (H=3 **343** on task 1, lookahead **500**). Seed 3 was a small negative gap on task 0 (H=3 **397**, lookahead **378**). Those two seeds cannot pass a 10-seed, 25-point rule.

Pendulum FiLM weights were not used. H=3 was not retuned. V0.7.3 confirmation tuples were not reused. Successor value remained open-loop H=3 from `s'`. Do not retune H=3, candidate count, or reward from this sample.

## What was tested

Holdout `9a60e48299b738ef` in the published V0.7.3 off-ceiling region: (14.0, 0.42, 0.22), (13.3, 0.43, 0.25), (12.4, 0.28, 0.22). Ten residual 2×64 MLPs trained with the frozen V0.7.2 recipe on `cartpole_default`. Shared 16×3 candidates, objective `both`, time budget off. Replication unit: source-training seed. Student-t 95%, df 9. Margin 25.

## Secondary (cannot upgrade)

Lookahead mean **495.933 [486.735, 505.132]**. H=3 mean **491.333 [477.916, 504.750]**.

Per-task return_gain:

- task0: **−1.900 [−6.198, 2.398]** (includes 0; seed 3 only)
- task1: **15.700 [−19.813, 51.213]** (includes 0; seed 6 only)
- task2: **0.000 [0.000, 0.000]** (both arms 500 on every seed)

## Integrity

`--results-audit` passed. Reward sums and return_gain identity reconstructed. Pendulum weights flag false. `retuned_h3` false. Training epochs 200. 42,418 real steps (under 42,800 cap because some episodes ended before 500). 2,165,564 imagined (under 2,190,000 cap). Retries: 0.

## Provenance

Branch `cursor/cartpole-lookahead-hard-h3`. Preparation SHA **425fb6bf8cb70ade08c4e17ac3c25cdc651e90cc**. One-run SHA **4a46fbacf89f476987c613beedebbfb525d0b0e2**.

- Config SHA256 `0515452c75a45d94d610a21ddea91727c499b00a4aeae3d72f56f322a65f954c`
- Protocol SHA256 `c2bb743a003544ee1ef6a310ea4c77633fa6f9b42db428a5cfe4a0b40cb26f6e`
- Raw artifact SHA256 `5343590154ab212b6118f4ef291b22e851f57cb1f74e8e99516087720a90f7b7`

Execute **12.275 s**, process **13.344 s**. One-run remaining is 0.

## One next experiment

Do not retune H=3 from this still-ceilinged draw, and do not resample the same published box hoping the hash rule lands off-ceiling. A later distinct question is an **H=3-only saturation diagnostic** on unused stricter-corner CartPole physics (shorter pole / heavier mass, still rejecting closed V0.7.3 tuples), with lookahead withheld until H=3 is actually unsaturated. That proposal is not implemented and is not authorized here.
