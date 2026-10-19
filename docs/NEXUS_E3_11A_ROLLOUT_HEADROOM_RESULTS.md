# E3.11A — Controller-specific forecasts have distinguishability headroom

Branch `codex/e3-11a-controller-rollout-headroom`, from
f7c698a91bb56f8cb21fb90b8f9eaab83142218f. Protocol/config/tested implementation
committed before execution: **caeae5f7875459e60690bf74e2270bab526885bd**.
One bounded source-only inference run, no retry or real environment construction.
Protocol: NEXUS_E3_11A_ROLLOUT_HEADROOM_PROTOCOL.md.

## Registered result

Label: **controller_specific_forecast_headroom_visible**. All16 registered
source contexts completed. Twelve had identical proposed first actions. Among
those, controller-specific16-decision model rollouts produced different later
actions AND a forecast-score gap above1e-6 in **11/12 contexts**:

- Pendulum:6/7; bundle0 four/four, bundle1 two/three.
- Acrobot:5/5; bundle0 three/three, bundle1 two/two.

Both families meet the predeclared representational screen. Shared-tail
forecasts stayed exactly equal in all12 equal-first-action contexts. One
negative case is retained: Pendulum bundle1/source row0 had identical action
paths, endpoints and scores. Four unequal-first-action contexts are outside
the registered primary cohort, with their complete raw paths still retained.

This establishes **forecast distinguishability**, not forecasting accuracy,
useful planner selection, control improvement or self-improvement. No actual
outcomes were measured. The numerical1e-6 screen is not a practical-return
threshold. E3.11's zero selection improvement remains unchanged and closed.

## Per-model raw score differences in the equal-first-action cohort

Score difference means rank-blend minus successor predicted cumulative reward
inside its own frozen learned model, with cumulative predicted survival.

- Pendulum0, source offsets0/32/64/96:−0.683490,+1.517707,+0.247303,+3.231494;
  later action disagreement counts5/6/2/2 of15 possible decisions.
- Pendulum1, offsets0/64/96:0,−0.563690,+0.107043; counts0/3/6.
- Acrobot0, offsets0/32/64:+0.004531,−0.122108,+0.030531; counts2/1/5.
- Acrobot1, offsets0/64:−0.539517,−0.283725; counts5/6.

Signs differ and some magnitudes are tiny. Neither controller is established
as better. These are model-self-evaluations; differing imagined trajectories
can compound model errors. One paired candidate stream/context does not
establish robustness to search randomness. Two frozen models/family and four
source observations/model are descriptive diagnostic assets, not16 independent
pretrained replications. No confidence interval or generalization inference
is attached to this numerical headroom screen.

## Cost and practical limitation

**0 real interactions,0 fits/updates.** Policy forecasts cost763904 imagined
rows/30720 top-level network forwards. The common-tail reference adds8192
rows/512 forwards. Total **772096 imagined transitions,31232 model calls and
31232 observed network forwards**, with no unknown work. All calls reserved
through existing ReservationLedger/Host and observed through ForwardCheckedStep.
Cached first-action reuse performs no additional neural work.

Per context the two policy forecasts cost47744 imagined rows versus512 for
common-tail scoring: **93.25×**. Their network-call ratio is60×. This extra
compute must be disclosed and budgeted in any later utility test; this result
does not demonstrate efficiency or justify deployment.

Parent wall4.818614082993008s under30s cap; worker process CPU4.558917s,
local single-thread CPU. Saved-data arithmetic/resource audit0.42341774998931214s,
no new model inference. Recorded ledger after run and verification:
**889.765542043008 used /2710.2344579569917 remaining**. Verification timing
is its measured function interval; engineering process startup is not a model
work count. No further experiment executed in this branch.

Four checkpoint bytes, source arrays, network buffers/context and normalization
fingerprints remain unchanged. **381 pre-existing research JSON files** retain
their hashes. No E3.11 evaluation outcomes were read as labels or features;
that experiment's validation record supplies only the carried ledger. No new
physics/seed holdout registration, environment data or H17 allocation.

## Tests, execution and artifacts

Focused pre-run75 passed in1.83s. Pre-run30-module relevant regressions554
passed in11.76s. Final555 passed in11.50s, including saved-capture replay
without checkpoint access. Not the entire historical suite: the known legacy
learned-inference benchmark remains excluded from source-only tests.
Tests cover same-first/later-divergence, survival/reward timing, independent
state copies, fixed grid, missing models/contexts/conditions/steps, nonfinite
forecasts, counts, immutable fingerprints, screen boundaries and profile paths.

Executed once (thread variables fixed to1, PYTHONDONTWRITEBYTECODE=1,
PYTHONPATH=src:.deps):

```
python3 scripts/run_e3_11_post_probe.py --rollout-audit
python3 scripts/run_e3_11_post_probe.py --rollout-audit --verify
```

The explicit profile reuses the original host, planners, metering and consumed
marker mechanism. No second learner or planning stack was introduced.
Audit replays every predicted transition/reward/survival sum, the common-tail
scores, full expected grid,528 journal receipts and original execution hashes.
It cannot validate model accuracy without independently observed outcomes.

- `artifacts/e3_11a_rollout_headroom.json`, SHA256
  1db2ff1b9b3950b982ce44e11363452a6bf70a66bf40fb3c8580a23cf4428c73.
- `artifacts/e3_11a_rollout_headroom_validation.json`, SHA256
  6faf36bc700d5fddef043c06c79284b4590e5d8d26d3f9587f3f81593f823cf6.
- `artifacts/e3_11a_rollout_resources.jsonl.gz`: full lossless per-call receipts,
  4510360 bytes; checksum in raw capture. Historical logs unchanged.

## One next scientific experiment

**Fresh paired-return calibration of these fixed controller-specific forecasts**
against common-tail and legitimate training-model-mean baselines. Lock predictions
before collecting each pair of actual192-step continuations after a common8-step
probe; use fresh registered reset/planner streams, no feature learning or model
updates, and report first16-step accuracy separately from the192-step target.
This tests whether newly distinguishable forecasts carry accurate information
about later planner quality rather than merely different model hallucinations.
Do not tune using the closed E3.11 outcomes.

A proposed16-context grid on the same four source models would cost6272 real
steps and about9.93 million imagined rows, estimated1–2 minutes with a proposed
180s cap. This is an estimate/proposal, not a registration, allocation or new
execution. No architecture expansion, mutation-credit study or control-success
claim is warranted before that calibration.
