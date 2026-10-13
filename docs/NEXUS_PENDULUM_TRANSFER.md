# NEXUS Pendulum adaptation and transfer

Branch `cursor/pendulum-adaptation-transfer`. Parent `a63c391`. Artifact `artifacts/pendulum_transfer.json`. Prior `cross_environment.json` (`402ce4151837eb0d`) and `planning_generality.json` (`c32ee7c682467cf9`) were **not overwritten**.

Not AGI. Not learning-to-learn. Independently trained residual (64, 64) world models. Pendulum planner frozen at **H=16 × 16** candidates from the diagnostic; CartPole **H=3** untouched. MAE ratio **0.97** not retuned.

## Pre-registered success (frozen before confirm)

1. **Adaptation:** MAE-gated vs frozen, seed-mean return across the three confirmation physics, Student-t 95% CI lo **> 0**.
2. **Learning-to-learn:** A→B→C then D beats both naive D and matched-volume D, both CIs lo **> 0**.

A system that fits a new model is not a system that has learned how to learn. Those two claims are scored separately.

## Planner and physics

Source: Gymnasium default **g=10, m=1, l=1**. Development detector shift **g=11.5**. Confirmation (unused in the horizon diagnostic): **g=6.5**, **m=1.8**, **l=1.45**. Sequence A/B/C/D: g=9.0 / m=0.55 / l=0.65 / compound (13.5, 1.35, 1.25). Eval seed **175000**. n=10 source-training seeds.

## Confirmation (n=10, mean over three physics)

| Method | Return | Δ vs frozen |
| --- | --- | --- |
| Frozen pretrained | −776 [−869, −684] | 0 |
| Snapshot retrieval | −776 | **0** (memory held source) |
| **MAE-gated (primary)** | −747 [−859, −635] | **+29 [−28, +86] includes 0** |
| Conservative low-LR | −671 [−804, −538] | **+106 [39, 173] excludes 0** |
| Always-adapt fine-tune | −566 [−662, −469] | **+211 [134, 288] excludes 0** |
| Scratch | −1164 [−1219, −1109] | **−388 [−479, −296]** worse |

Primary adaptation **failed**. Offline target fine-tuning (always / low-LR) **did** beat frozen on control. That is ordinary task adaptation with extra target data, not a learned update rule. MAE-gated accepted **1.3 / 1.5** proposals (beneficial 0.7, harmful 0.6). Retrieval matched frozen.

Per-physics always-adapt means: g=6.5 **−329**; m=1.8 **−768**; l=1.45 **−600** (frozen **−547 / −982 / −801**).

## Learning curve (confirm gravity task, budgets include train+val)

Frozen **−547** at every budget. Always-adapt: **−547 → −336** at 1024. Low-LR **−428** at 1024. Scratch stays worse than frozen at every budget. MAE-gated **−513** at 1024. AUC vs frozen: always **+128k [−17k, +273k] includes 0**; MAE **+20k includes 0**; scratch **−772k excludes 0** (worse). Extra target data helps **ungated** fine-tunes more than the gate.

Prediction error on **source** val at max budget (seed 0): frozen MAE **0.043**; always-adapt **0.090**. Lower source error is not the control criterion; adapted models drift on source while improving target return.

## Learning-to-learn (held-out D)

| Controller | D return |
| --- | --- |
| Naive D (stage cap 224) | −1078 [−1168, −988] |
| A→B→C then D | −1057 [−1152, −961] |
| Matched volume (896) | −1051 [−1147, −955] |

ABC vs naive **+22 [−12, +55] includes 0**. ABC vs matched **−6 [−40, +28] includes 0**. Prior-task experience did **not** reduce D’s interaction need. **Learning-to-learn is not demonstrated.**

## Detection

Source false-alarm fraction **0**. Target miss **0.70** (many gravity-11.5 streams never crossed the source residual threshold). Delay, when an alarm fired, is not a reliable statistic (n=3).

## Costs

Pretrain **1328** env steps. Checkpoint **~19.5 KB**. Pool **1024**. Wall **1167 s**. Protocol hash `7fde7c9c01fc8524`. `pytest` **250 passed**.

```bash
PYTHONPATH=src:.deps python3 -m pytest tests -q
PYTHONPATH=src:.deps python3 scripts/run_pendulum_transfer.py
```

## Decision

Do **not** proceed to meta-learning. The frozen MAE gate still fails its paired control test. Ungated / low-LR fine-tuning can use target data on Pendulum; that does not train a meta-learner. Do not retune 0.97 from this confirm. No finance. No architecture search.

Python 3.13.5, PyTorch 2.14.1, NumPy 2.5.4, Gymnasium 1.4.0.
