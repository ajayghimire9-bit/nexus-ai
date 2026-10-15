# NEXUS open questions

This list records what the latent-adaptation sequence has not established. It does not start an experiment. The sequence is not a general control improvement, not learning-to-learn, and not AGI.

## Measured phase split

On newly registered fresh-physics episodes, with the saved student and zero-context controllers held fixed, the paired student-minus-zero return was **−30.671 [−41.540, −19.801]**. Steps 0–15 were **−1.230 [−2.583, 0.123]** and include 0. Steps 16–199 were **−29.441 [−40.706, −18.175]**. The late share was **0.928 [0.836, 1.020]**. The locked label is `primarily_late` (`docs/NEXUS_RETURN_PHASE_DECOMPOSITION.md`). This is a new episode sample, not a remeasurement of the closed **−19.4** gap. `rp2` carries most of the late difference. Observation distance grows from step 16 to step 199, so the late sum is not a same-state effect. No architecture change follows.

## Still unresolved, and not the next run

- Which mechanism produces the fresh-physics return gap. The receding-horizon decision is `inconclusive`. Replay matched **1920 / 1920** stored decisions. Pooled visited-state regret and the matched next-16 continuation both include 0.
- Whether cosine and sine error, rather than angular velocity, can be lowered by the support-fit latent. Those paired intervals included 0 on the direct-latent audits.
- Whether the encoder can reproduce a latent from a second support of the same task. Representability passed on the supports that defined the eight saved codes.
- Why training latent distance stayed near **0.65** on development and **1.56** on confirmation while query angular velocity still fell.
- Whether the fresh return gap versus the frozen encoder is negative. That interval includes 0. The gap versus zero context does not.
- Whether seeds 0–2 would have separated the original three-decoder return interval with more episodes. Those episode seeds are closed, and the ten-decoder replication is the later sample.

No architecture change, planner change, or new training run follows from this list.

## Latest development decision

The completed late-control result leaves both same-state 16-step comparisons unresolved: common-zero **+0.0312 [−0.0827,+0.1452]**, full policy **−0.0234 [−0.2236,+0.1767]**. The next question is whether a disadvantage appears in a longer continuation tail while the frozen policies start from identical late states. `docs/NEXUS_LONG_CONTINUATION_PROTOCOL.md` defines one proposed 64-step study and competing delayed-action versus full-policy descriptions. No new environment data have been collected; approval is required before execution.
