# NEXUS meta-learning and architecture pilot

Branch `cursor/meta-learning-pilot`. Parent `eb7a083`. Artifact `artifacts/meta_learning_pilot.json`. Prior `cross_environment.json`, `planning_generality.json`, and `pendulum_transfer.json` hashes were **not overwritten**.

Not AGI. Not learning-to-learn. First-order **Reptile** vs an equally resourced **multitask** initialization, same residual-family planner (**H=16 × 16**), same ordinary fine-tune inner loop (lr **5e-4**, the method that beat frozen in the transfer confirm). MAE 0.97 was **not** the inner learner.

## Distinctions this run is allowed to make

| Effect | What would show it |
| --- | --- |
| Better final weights | Higher return at budget 0 |
| Better fine-tuning | Higher return after the same target prefix |
| More / more diverse pretraining data | Multitask vs single-source with **matched env steps** |
| Learning-to-learn | Reptile AUC **>** multitask AUC, seed CI lo > 0, same data and inner loop |

## Protocol

Meta-train physics (4): g=7.2; m=0.7; l=0.8; mild compound (10.8, 1.2, 1.1). Meta-val (arch only): g=14.0; (m=1.5, l=0.9). Confirm (untouched): g=5.5; m=2.2; l=1.7; compound (12.8, 0.4, 1.35). Disjoint from all earlier Pendulum suites. Eval seed **187000**. n=10.

Prior env per seed: **1280** for source and **1280** for meta (4×(256+64)). Target pool **1024** shared across inits (same transitions). Budgets **0, 32, 64, 128, 256, 512, 1024** (train+val inside the prefix).

Reptile: 24 outer steps, 5 inner epochs, ε=0.1. Multitask: same collections, 48 pooled epochs (~matched SGD). Film context is a mean embedding of **(obs, action)** from the target prefix — not g, m, or l.

## Architecture (development only)

| Arch | Params | Meta-val AUC (n=2) |
| --- | --- | --- |
| **film (selected)** | 5828 | −355k |
| mlp 64×64 | 4868 | −390k |
| gru-36 | 4900 | −520k |

Selection froze **film**. Confirmation did not retune architecture.

## Confirmation (n=10, mean over four physics)

Learning-curve AUC (higher / less negative is better):

| Init | AUC | Final return @1024 |
| --- | --- | --- |
| Scratch | −1.34M | −1144 [−1225, −1063] |
| Source pretest | −689k | −597 [−680, −514] |
| **Multitask** | **−525k** | **−491 [−576, −406]** |
| Reptile | −1.29M | −1120 [−1219, −1021] |

Mean return by budget (average across confirm tasks):

| Budget | Scratch | Source | Multitask | Reptile |
| --- | --- | --- | --- | --- |
| 0 | −1354 | −756 | **−551** | −1313 |
| 128 | −1336 | −691 | **−545** | −1353 |
| 512 | −1382 | −673 | **−498** | −1275 |
| 1024 | −1144 | −597 | **−491** | −1120 |

Paired:

- Reptile − multitask AUC **−765k [−857k, −672k] excludes 0** (Reptile **worse**)
- Reptile − multitask final **−629 [−766, −492]**
- Multitask − source AUC **+163k [70k, 257k] excludes 0** (diverse pooled pretraining helps)
- Scratch stays near random-quality control

MAE-gated extra (first confirm task only): mean **1.3** accepts; not the primary comparison.

## Decision

**Meta-learning success: no.** Reptile did not adapt faster than the strongest fair pretrained baseline (multitask on the same 1280 steps). It behaved like a weak/scratch init. Multitask beating source is **more diverse pretraining**, not learning-to-learn.

Do not scale Reptile, NAS, or a meta-controller from this confirm. Wall **2300 s**. Protocol hash `c6e921b0564a5315`. `pytest` **255 passed**.

```bash
PYTHONPATH=src:.deps python3 -m pytest tests -q
PYTHONPATH=src:.deps python3 scripts/run_meta_learning_pilot.py
```

Python 3.13.5, PyTorch 2.14.1, NumPy 2.5.4, Gymnasium 1.4.0.
