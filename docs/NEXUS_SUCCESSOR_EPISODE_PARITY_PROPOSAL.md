# Full-episode successor batching parity — proposal only

**Not executed. No default controller integration.** This is the one next
validation question after the synthetic and archived engineering audits passed.
It does not reopen the failed tree-reuse screens or compare a new planning rule
with H=16. A separate research branch, tested implementation and committed exact
configuration/allocation must precede any environment execution. Do not reuse an
expired scientific budget or treat this proposal as a one-run allocation.

## Falsifiable question

Do the original serial successor scorer and the mathematically equivalent batched
scorer produce identical closed-loop actions and rewards throughout paired200-step
Pendulum episodes with actual saved student contexts? A single action mismatch
rejects the strict episode-parity screen, even if the resulting return is higher.
No new precision/fallback/tolerance may be selected using these outcomes.

## Fixed design to implement before execution

- Ten existing decoders, three known `pendulum_context_development` tasks.
- Two frozen contexts per decoder/task: archived student `(decoder+task) mod5`
  and zero; exact original checkpoint/z hashes, no new encoder inference/support.
- Two implementations per context: recorded serial successor and opt-in batched.
- One paired fresh episode per decoder/task/context,200 steps. Total120 episodes.
- Existing native reward and physics, H16,16 candidate sequences,three torque
  actions and Pendulum's original termination semantics. No time-budget pruning.
- Proposed reset seed `61_000_000+100*d+t`; candidate seed
  `61_100_000+10_000*d+1_000*t+k` for local step k. Couple identical seeds across
  implementations and context groups. Verify exact disjointness against **all**
  closed registries when implementing, and fail before collection on any collision.
- Serialize per-step observation, action, reward, Q, candidate seed and context hash.
  Keep independent environments/RNG for each implementation. No simulator truth
  enters the world model or its candidate scores.

## Decision, integrity and interpretation

Require the complete locked120-episode grid, unchanged checkpoints/normalization,
all200 steps, identical action sequences in all60 episode pairs, and equal rewards/
returns within1e-8 absolute tolerance. Report all action/Q/observation mismatches,
the first divergence and per-decoder/task/context breakdown. Q tolerance remains
2e-4 absolute/2e-5 relative; it cannot excuse a changed selected action.

If a complete valid grid meets all requirements, conclude tested full-episode
implementation parity. If any action differs, conclude parity was not established;
inspect its original Q margin without tuning and rerunning. Missing/capped/corrupt
execution is incomplete, not evidence for or against parity. No improvement
claim or return-significance selection is allowed. Ten decoder units remain
distinct; student/context/episode counts are not extra independent training seeds.

## Proposed cost and authorization boundary

**24,000 fresh real environment steps**, **18,504,000 imagined transitions**
(each implementation uses771/step), **816,000 model calls** (12,000×51 plus
12,000×17), zero fitting/support collection. Reused original support is historical
cost, not counted again. Estimate60–120 CPU seconds based on measured scorer
microtimings plus environment/logging overhead; proposed hard cap **180seconds**.
This is a proposal estimate, not measured episode runtime. Stop/save incomplete
results at either time or interaction cap; no silent grid reduction or retry.

The standing scientific session ledger remains exhausted in the recovered research
history. A new explicit bounded allocation must bind the final implementation,
configuration and protocol hashes before this simulation. No such allocation,
runner or environment data is created by this proposal. It does not start an
autonomous loop or authorize larger follow-up runs.
