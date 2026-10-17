# H10/H11 prediction-versus-control disagreement — source audit

Analysis of committed artifacts only. No new environment steps,
no training, no reserved-holdout scoring, no fitted Q-functions,
and no H10/H11 rerun. Not learning-to-learn, not AGI.

## Recomputed primaries

H10 `multitask − scratch` **+145.785 [+106.617, +184.953]**
(10/10 positive). Saved label `mcc_multitask_128_beats_scratch`.
H11 `multitask − scratch` **+18.879 [-65.988, +103.747]**
(8/10 positive). Saved label `mcc_multitask_128_confirm_not_established`.
Both intervals match the closed artifacts to 1e-12.

## What the traces actually contain

Each of the 20 H10 and 20 H11 eval traces stores `actions`,
`rewards`, `seeds`, `n_steps`, `terminated`, `truncated`, and
`episode_return`. None stores observations, predicted next
states, candidate sequences, planner scores, residuals, or
checkpoints. Reward reconstruction matches every saved return.
All 40 episodes ran 200 steps and truncated; none terminated.

## Seed-level control patterns that the artifacts support

H10 early (steps 0–15) **+0.131 [-0.484, +0.747]**
includes 0. Late (16–199)
**+145.653 [+106.634, +184.673]** matches the primary.
H11 early **-0.222 [-0.657, +0.213]**
includes 0. Late
**+19.101 [-65.975, +104.177]** again matches the primary.
Correlation of paired return with the late split is 0.9999 on both
studies. The first planning horizon is not where the return gap sits.

H11 negative seeds are **4 and 5**. Scratch returns +70.109 and
+68.712; multitask −129.556 and −127.944. Those two scratch
episodes have late sums +85.5 and +84.2 (hill climb on the dense
height reward). The matching multitask late sums are −114.8 and
−112.6 (stay near the valley). This is not a general pretraining
harm: the H11 mean remains positive, and eight seeds still favor
multitask.

## MAE does not explain the control label

H10 MAE delta **-0.000901 [-0.001301, -0.000501]**.
H11 MAE delta **-0.000563 [-0.000825, -0.000300]**.
Correlation with paired return is 0.313 (H10)
and 0.230 (H11). Both H11 disaster seeds still
have lower val MAE than scratch (−6.31e-4 and −1.02e-3). H11 seed 8
is the only seed with worse MAE, and it still wins on return.
MAE is a scalar on the 32-row random/exploratory val prefix. It
cannot localize error on planner states. Residuals were not saved,
so a region-wise error map cannot be built.

## Physics versus randomness

H10 target (0.0032, 0.0022, 0.06); H11 (0.0022, 0.0016, 0.07);
sources (0.0025, 0.0015, 0.07), (0.0038, 0.0019, 0.085),
(0.0024, 0.0019, 0.09). Those are documented parameter differences.
Collect and eval seeds also differ (72M vs 73M). Two holdouts
cannot separate physics from training/controller randomness.
H11 scratch mean −83.9 is in the same weak-128 band as H10 scratch
−112.7. The confirmation failure is high variance plus two
scratch-climb seeds, not a mean sign flip.

## Mechanisms that cannot be tested from saved artifacts

- Action ranking: no candidate sequences or planner scores.
- Multi-step prediction bias: no predicted or true next observations.
- Model uncertainty: no ensembles, variances, or checkpoints.
- Reward-model mismatch: planner uses the published height reward;
  env rewards were recorded, but imagined scores were not.
- Same-state occupancy: no observations, so later-step comparison
  is not a matched-state contrast.

Historical Pendulum work already separated “better one-step
prediction” from episode return (`NEXUS_PREDICTION_CONTROL_GAP.md`).
H11 is another instance of that disagreement, now on MCC H=16,
without the ranking measurements that diagnostic had.

## Strongest supported explanation

One-step held-out MAE is not a sufficient statistic for H=16 control on these two holdouts. The registered return gap lives in steps 16-199. H11 seeds 4 and 5 lose control while still showing lower val MAE.
This does **not** establish that pretraining is harmful.

## Remaining gaps and one next diagnostic

The missing objects are planner-state observations and H=16
candidate scores. The smallest falsifiable follow-up is a
same-state ranking audit of the frozen H10 recipe on one new
unused MCC physics: matched resets, shared 16×16 candidates,
record realized 16-step height versus the selected score for
both arms. Primary: paired selected-minus-best regret. That
tests whether lower val MAE co-occurs with better first-horizon
ranking. It is not a source-count, epoch, or budget sweep.
Nothing here authorizes that run.

Closed H10 raw `caca746457eb72e89c95b6f8b9cd82c7cf06cff68713ff1d9ad8a98519e4d274`.
Closed H11 raw `e8045423ff257e2f55acbead5a3f2eafc54f5ed5f88dab99933cca5eea286950`.

