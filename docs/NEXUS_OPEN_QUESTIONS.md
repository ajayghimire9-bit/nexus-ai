# NEXUS open questions

This list records what the latent-adaptation sequence has not established. It does not start an experiment. The sequence is not a general control improvement, not learning-to-learn, and not AGI.

## Recommended next measurement

On newly registered fresh-physics episodes, with the saved student and zero-context controllers held fixed, what fraction of the paired student-minus-zero return difference accumulates during steps 0-15, and what fraction accumulates during steps 16-199?

That is the one recommended question. The saved weights stay fixed. The closed episode seeds stay closed. The receding-horizon next-16 continuation is a different measurement: it follows one committed action with a shared zero-context replanner, and its fresh interval includes 0. A split of the live return would say whether the closed **−19.4 [−35.4, −3.3]** gap is already present inside one planning horizon of the executed policy. This document does not collect those episodes.

## Still unresolved, and not the next run

- Which mechanism produces the fresh-physics return gap. The receding-horizon decision is `inconclusive`. Replay matched **1920 / 1920** stored decisions. Pooled visited-state regret and the matched next-16 continuation both include 0.
- Whether cosine and sine error, rather than angular velocity, can be lowered by the support-fit latent. Those paired intervals included 0 on the direct-latent audits.
- Whether the encoder can reproduce a latent from a second support of the same task. Representability passed on the supports that defined the eight saved codes.
- Why training latent distance stayed near **0.65** on development and **1.56** on confirmation while query angular velocity still fell.
- Whether the fresh return gap versus the frozen encoder is negative. That interval includes 0. The gap versus zero context does not.
- Whether seeds 0–2 would have separated the original three-decoder return interval with more episodes. Those episode seeds are closed, and the ten-decoder replication is the later sample.

No architecture change, planner change, or new training run follows from this list.
