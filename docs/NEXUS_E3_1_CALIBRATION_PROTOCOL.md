# E3.1 learned-model evidence and recorded-transition audit — protocol v1

Base `59c7718cca2ce5c2b23eaa79ba64077ae74d229d`, verified local/GitHub. Branch
`codex/e3-1-learned-model-headroom-audit`. Requested E3.1 overlaps completed
headroom work; do not repeat closed studies or call them new discoveries.
This task verifies their evidence and executes the already proposed cross-model
calibration diagnostic on recorded source transitions. Commit before inference.

## Evidence questions, not retrospective success redefinition

E3.1 asks whether existing generated strategies have meaningful outcome variation
beyond fixed anchors under frozen learned-model control. Reverify the16-cell,
342-strategy learned-model headroom capture, its source/checkpoint provenance,
and the three completed full-policy captures. Recompute their registered metrics
without model/controller reruns. Distinguish the saturated first-action/neutral
continuation proxy from full-policy actual returns. Saturation of that proxy is
not proof the learner is incapable; observed policy variation is not proof the
learner discovered it or can predict it. No new grammar, search, feature sweep,
confirmation access, H17/H12–H16 rerun, E2.17 grant reuse or collection.

## New source-only diagnostic

H-state: model0 has greater held-record angular-velocity error than model1 on
identical recorded transitions. H-stop: model0 has greater false-termination
Brier error on those same transitions. These are competing/descriptive model
quality signals, not causal explanations of return or selection success.
The two model bundles include different source data and normalization. Report
directions and magnitudes without a statistical/generalization pass claim.

Use every3200 transition in the locked crossed-reset capture, no filtering by
return or error. Ordering is visitor model0/1 ×policy(successor,rank blend)
×episode0..3 ×tick0..199. Both frozen Pendulum E2.9 models receive exactly those
same observation/action/next-observation/terminated arrays. TimeLimit truncation
is not a positive termination target. Preserve duplicate rows and their visitor
provenance; they are not independent model replications. No new support/labels.

Verify all four Pendulum/Acrobot bundle0/1 E2.9 checkpoint files and eight original
source NPZ hashes before loading any model. Only the two Pendulum models run.
Compare weights/buffers/RMS hashes with parent captures and before/after
inference. CPU residual64×64, original WorldModel.step and original normalization,
no optimizer, fitting, context change, simulator or environment construction.
The original fit manifest lacks an execution SHA: do not overclaim provenance.

Reuse `full_policy_source` validation/hash helpers, `disposable_model`,
`fit_clock.LOCKED_ARRAYS`, `WorldModel.step`, existing ReservationLedger and
headroom summarizer. No new proposer, memory, planner, metering or RL framework.

## Metrics and aggregation

32 raw metric cells:2candidate models×2visitor models×2visitor policies×4episodes.
Each contains all200 rows. Save raw predicted next states and termination
probabilities in the common canonical row order so errors can be independently
recomputed. Required fields: overall MAE/RMSE; cosine, sine and angular-velocity
MAE; mean predicted termination, maximum probability, Brier error and false
positive fraction at fixed threshold0.5; actual positive termination count.
Only negative termination labels exist on this suite: this cannot estimate
recall, positive-class calibration or calibration on imagined trajectories.

Average episodes equally inside visitor model/policy, then give the four
visitor strata equal weight. Report model0-minus-model1 differences in every
metric and visitor stratum. No pooling rows as independent trained models, no
confidence/significance claim with two selected frozen models. No dynamics
rollouts/MPC or reward outcomes fed into a proposer/predictor. Correlation of
errors with observed returns is not causal evidence. Do not tune any threshold.

## Bound, failure and provenance

Standing grant2026-10-16 plus current instruction authorize source-only work.
Session starts487.3923076680088 seconds used,3112.607692331991 remaining.
One run,30-second wall/CPU cap,0 real steps,0 fits,6400 one-step inference rows.
Batch256 gives13 calls/model,26 total; reserve each call through existing ledger
before execution. Count these as diagnostic neural transitions, not new real
experience or executed MPC trajectories. Unknown/interrupted work stays charged.
No automatic retry, episode reduction or substitution of weights. Deadline,
missing/nonfinite cells, invalid probabilities, wrong hashes or changed model
state => incomplete/invalid capture, never a favorable scientific conclusion.

Preserve all historical JSON and prior resource journals. Freeze exact config,
protocol and allocation hashes before inference. Record execution SHA, source/
checkpoint/evidence/config hashes, dependencies, complete/unknown resource work,
raw predictions and all32 cells. A separate no-inference validation recomputes
metrics and evidence arithmetic and conservatively debits its wall time too.
Old collected steps are cited as historical costs, not charged as new steps.
Commit results separately and push without merging.

Source-only tests before execution cover canonical identical queries, termination
versus truncation, known-error arithmetic, exact cell grid/omission/nonfinite
rejection, evidence/hash validation, actual probability constraints, resource
plan caps and old profile regressions. They instantiate no models or worlds.

Execute `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3
scripts/audit_e3_1_learned_model.py`; then append `--verify` for saved-data checks.
The E3.1 conclusion must say precisely which evaluator distinguishes outcomes,
which does not, and that useful feedback-driven discovery remains unestablished.
