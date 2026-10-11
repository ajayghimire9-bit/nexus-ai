# NEXUS V0.6.1 — Reliable continual learning and positive transfer

Status: corrected protocol plus a larger matched-compute CartPole-family study. **Not AGI.** V0.6 artifacts in `artifacts/v06_continual.json` are unchanged.

Branch: `cursor/v06-continual-transfer`. Reproduce: `PYTHONPATH=src:.deps python3 scripts/run_v061_benchmarks.py`.

`pytest` **74 passed**. Training / validation / independent seeds: **n/a (controller seed)** / **71000** / **72000**. Held-out transfer eval: **73000**. The adaptive curriculum observes **validation only**.

## Audit of V0.6 (fixes)

| Issue | V0.6 | V0.6.1 |
| --- | --- | --- |
| Curriculum leakage | Observed independent eval seed 70000 | Observes val 71000; reports independent 72000 |
| Replay | Single FIFO, no task ids | Per-task buckets, balanced BC sampling |
| EWC Fisher | One snapshot of 2 current obs; overwrite | Last PPO rollout batch; **accumulated** across tasks |
| Metrics | Peak vs last ad hoc | Lopez-Paz ACC / FWT / BWT from the full independent matrix after every phase |
| Encoder copy | Frozen transfer only, no zero-shot curve | Zero-shot, frozen, finetune, scratch vs target-task steps |
| Budget | 2048 steps (specialists ~80–140, unsolved) | Specialist curves at 2048 / 8192 / **16384**; CL at **8192**/task (24576 matched) |

Sequential PPO still continues the optimizer cursor (`_timesteps_done + extra`). Checkpoints: `checkpoints/v061/` (gitignored).

## Specialist learning curves (independent seed 72000)

Mean return, 3 seeds, 95% CI. CartPole solve threshold is 475; **not reached**.

| Task | 2048 | 8192 | 16384 |
| --- | --- | --- | --- |
| cartpole_default | 98.1 [96.8, 99.4] | 87.0 [72.5, 101.5] | 131.5 [18.9, 244.1] |
| cartpole_long | 106.6 [90.1, 123.2] | 128.2 [86.1, 170.3] | 217.5 [59.6, 375.4] |
| cartpole_heavy | 81.8 [72.3, 91.4] | 105.8 [98.8, 112.7] | 122.2 [63.2, 181.2] |

Returns rise with compute on long/heavy, with large seed variance. Independent specialists **do not reliably learn** these variants at 16k steps. CL comparisons at 8k/task remain underpowered relative to a solved policy. That is a measured limit, not a reason to invent gains.

## Sequential CL at 8192 steps/task (matched 24576 env steps, 1315 params; multi-head 1513)

Independent-eval ACC (mean last-row return), FWT, BWT; 3 seeds:

| Method | ACC | mean FWT | mean BWT / forgetting |
| --- | --- | --- | --- |
| independent specialists | 138.0 [97.6, 178.3] | n/a | n/a |
| naive fine-tune | 177.6 [76.8, 278.4] | **−44.8 [−84.9, −4.8]** | +65.2 [−5.9, +136.3] |
| replay (task-balanced) | 96.4 [66.6, 126.2] | −39.1 [−90.7, +12.6] | −8.5 [−43.1, +26.0] |
| EWC (accumulated Fisher) | 108.8 [40.2, 177.4] | **−45.4 [−85.5, −5.3]** | −4.8 [−49.0, +39.4] |
| multi-head | 57.2 [31.5, 82.9] | **−140.1 [−183.1, −97.2]** | **−77.1 [−141.6, −12.5]** |

Naive ACC point estimate exceeds specialists, but CIs overlap. **FWT CIs for naive, EWC, and multi-head exclude 0 and are negative**: after training task \(i-1\), task \(i\) is worse than a matched-step specialist. Multi-head is strictly worse than specialists on ACC and BWT.

Replay did not beat naive. EWC did not beat naive.

## Held-out `cartpole_lowg` (eval seed 73000)

Source encoder from naive sequential. Mean independent return (3 seeds):

| Mode | at 0 steps | after 8192 target-task steps |
| --- | --- | --- |
| zero-shot (copied encoder, new heads) | 9.3 [8.9, 9.7] | — |
| frozen encoder | 9.3 [8.9, 9.7] | 21.7 [0.2, 43.2] |
| finetune encoder | 9.3 [8.9, 9.7] | 83.5 [0.4, 166.6] |
| scratch (same MLP, matched steps) | 121.9 [11.4, 232.3] | **164.2 [104.1, 224.3]** |

Copied-encoder zero-shot is **far below** an untrained scratch net on this variant (negative transfer of the source encoder + new heads). Scratch remains best after 8192 target steps. Positive transfer is **not** supported.

## Curriculum (val 71000 for selection; independent 72000 for reporting)

Mean independent return across source tasks: fixed **179.8** [97.5, 262.0]; random **77.8** [11.0, 144.5]; adaptive **145.6** [41.7, 249.5]. Adaptive does not beat fixed. CIs overlap. Not tuned on the test seed.

## Verdict vs success criterion

**Not met.** There is no statistically credible retention or positive knowledge transfer over matched specialists and naive fine-tuning.

Credible **negative** findings (CIs exclude 0):

1. Forward transfer is negative for naive, EWC, and multi-head at 8192 steps/task.
2. Multi-head backward transfer is negative.
3. Source-encoder zero-shot on held-out low gravity is worse than scratch initialization.

**Next testable explanation:** 16k PPO steps still do not produce a stable, shareable CartPole representation (specialists unsolved, high variance). Transfer may start working only after source policies actually solve default/long/heavy, or with a different encoder (e.g. larger net, more envs, no observation-normalizer leak across tasks). Do not raise inner steps to 250k on all methods until a single specialist solve is cheap enough to reuse.

Not AGI. Not meta-RL. Not a trading system. Not a claim of autonomous self-improvement.
