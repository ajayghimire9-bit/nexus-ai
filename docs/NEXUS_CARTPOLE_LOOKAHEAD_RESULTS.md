# CartPole lookahead versus frozen H=3 — complete development screen

## Registered decision

The locked 60-episode (10 training seeds × 3 tasks × 2 arms) development grid completed. Label: `cartpole_lookahead_not_established`.

Lookahead minus frozen H=3 episode return: **4.000 [−5.048, 13.048]**. The mean is below 25 and the interval includes 0, so the registered improvement rule does **not** pass.

This is a ceiling result on this physics draw, not a proof that lookahead cannot help CartPole. Frozen H=3 already returned **500** on 9 of 10 training seeds. Lookahead returned **500** on all 10. Seed 3 was the only off-ceiling H=3 mean (**460**), where lookahead reached 500. That single-seed gap cannot pass a 10-seed, 25-point rule.

Pendulum FiLM weights were not used. CartPole kept frozen H=3 × 16, not Pendulum H=16. Successor value remained open-loop H=3 from `s'`. Do not retune H=3, candidate count, or reward from this sample.

## What was tested

Holdout `4bc1f5866ac6c753`: (8.5, 0.39, 0.19), (11.6, 0.9, 0.07), (7.9, 0.88, 0.29). Ten residual 2×64 MLPs trained with the frozen V0.7.2 recipe on `cartpole_default`. Shared 16×3 candidates, objective `both`, time budget off. Replication unit: source-training seed. Student-t 95%, df 9. Margin 25.

## Secondary (cannot upgrade)

Lookahead mean **500.000**. H=3 mean **496.000 [486.952, 505.048]**.

Per-task return_gain:

- task0: **0.000 [0.000, 0.000]**
- task1: **12.000 [−15.144, 39.144]** (includes 0; seed 3 only)
- task2: **0.000 [0.000, 0.000]**

## Integrity

`--results-audit` passed. Reward sums and return_gain identity reconstructed. Pendulum weights flag false. Training epochs 200. 42,680 real steps (under 42,800 cap because some H=3 episodes ended before 500). 2,184,240 imagined (under 2,190,000 cap). Retries: 0.

## Provenance

Branch `cursor/cartpole-lookahead-h3`. Preparation SHA **bf9c148f87c79b9451cac21c72182dd49af80800**. One-run SHA **bf82956af9300cf017d83d56eb38159c170f359a**.

- Config SHA256 `de1113d814ef506eba7e477fc314c48a9d289a497bab018a02cd1acaa6673ece`
- Protocol SHA256 `6bbd5caa29fc4156adfb13f72d00466d0d640812b62b7ca4215ddc8e0335c112`
- Raw artifact SHA256 `62cc377674bf2114027518d586306b25553752cf1986c1bad6279eac08489098`

Execute **12.399 s**, process **13.465 s**. One-run remaining is 0.

## One next experiment

Do not retune H=3 from this ceilinged draw. A later distinct question is whether lookahead beats H=3 on **harder unused CartPole physics** where H=3 is not saturated (V0.7.3 task 2 was such a regime, but that split is historically closed). That proposal is not implemented and is not authorized here.
