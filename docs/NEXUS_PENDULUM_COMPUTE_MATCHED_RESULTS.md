# Pendulum lookahead versus compute-matched H=16 — complete development screen

## Registered decision

The locked 120-episode (30 decoder×task × 2 arms × 2 visitors) compute-matched grid completed. Label: `pendulum_compute_matched_lookahead_established`.

Lookahead minus 48-candidate H=16 200-step return: **60.182 [11.439, 108.924]**. The mean is at least 25 and the paired 95% lower bound is above 0, so the registered improvement rule **passes**.

Successor value remained the frozen **open-loop** H=16 score from `s'`. Extra H=16 search (768 imagined states per step versus the original 256) did not remove the 25-point remainder on these development physics. The unmatched development gap was **155.647**; this matched remainder is smaller, so extra candidates still explain part of the original package win.

This does not reverse the closed Acrobot compute-matched miss (**12.834 [3.815, 21.853]**). Do not retune H=16, the 16-candidate lookahead successor, or the published reward from this sample. Confirmation physics unused.

## What was tested

Three `pendulum_context_development` physics, ten independently pretrained FiLM decoders, student visitor `(d+t) mod 5` and zero. Fresh resets `15000000+` and shared step seeds `15100000+`. Arm A scored 48 prefix-stable H=16 candidates from `s`. Arm B kept frozen `lookahead_first_action` over the first 16 of those candidates from `s'`. Student-t 95%, df 9. Margin 25.

## Secondary (cannot upgrade)

Student-only: **57.902 [4.384, 111.419]**. Zero-only: **62.461 [7.183, 117.739]**. Both favor lookahead; neither can change the pooled label.

Student-minus-zero inside matched H=16: **23.366 [−37.376, 84.107]**. Inside lookahead: **18.806 [−30.006, 67.619]**. Both include 0. Do not infer adaptation from this compute-matched contrast.

Lookahead means: student **−420.745**; zero **−439.552**. Matched H=16: student **−478.647**; zero **−502.013**.

Per-task return_gain (exploratory):

- task0: **55.208 [2.609, 107.806]**
- task1: **135.530 [28.645, 242.416]**
- task2: **−10.194 [−105.102, 84.714]**

Decoder pooled means: 41.9, 126.3, −36.7, 136.7, 102.7, −25.4, −19.3, 134.3, 52.1, 89.1. Three decoder means are negative; the pooled rule still passes.

## Integrity

`--results-audit` passed. Reward sums, 48-wide matched argmax, 3-wide lookahead Q argmax, shared seeds, return_gain identity, and the primary interval reconstructed. Frozen checkpoints before and after: 120 verified, 0 missing, 0 mismatched. Confirmation unused. Training updates: 0. 24,000 real steps (exact cap). 18,468,000 imagined (exact cap). Retries: 0.

## Provenance

Branch `cursor/pendulum-compute-matched-h16`. Preparation SHA **1887442fbda3d3bed65877f65727be0c98c52ba5**. One-run SHA **8c274b9f80ada7f909525082922984c0f0af7729**.

- Config SHA256 `5a553ab3a3718c0ef4e3404a44e284f20bc0aebc09e15884e197d405ebf36673`
- Protocol SHA256 `bcc77ee3c6e3fdd886d66840f07100dd7b9da1a61407e77be83fb31b569e3f24`
- Raw artifact SHA256 `02ae07e32c5554f2464eb1e7202854d37003aa43b78fe991326a5547fe1853e6`

Execute **68.154 s**, process **69.590 s**. One-run remaining is 0.

## One next experiment

Do not retune H=16, candidates, or reward from this sample. Compute-matched remainder is established on Pendulum development and was not established on Acrobot. A later distinct question is the unmatched frozen lookahead package on a **new environment family**, not another Pendulum confirmation split. That proposal is not implemented and is not authorized here. This is not learning-to-learn or AGI.
