# E2.25 planner advantage — optional extension

The original E2.25 is complete and negative, not a missing deliverable:
`NEXUS_E2_25_PLANNER_QUALITY.md`. Candidate/context ridge MAE0.0814084
lost to paired mean0.0109969 and observation kernel0.0122852. Its query
normalization was transductive; later E2.26–E2.29 repairs do not retroactively
make that evidence independent. Preserve its artifact and result unchanged.

This user-authorized source-development extension reuses `fit_ridge` and
`predict_ridge` through `generated_strategies.AdvantagePredictor`. It is an
optional candidate-versus-anchor ranker, not a replacement memory/proposer.
Only actually revealed source receipts enter fitting and incremental updates.
Fixed sum-squared loss +1×coefficient penalty; antisymmetric pair augmentation
and RMS scaling are fitted only to source training rows. No neural network.

Features: source-normalized observation (tanh, padded to6), three existing
support statistics, two charged anchor receipts, family/schema through the
existing contextual operator features, active/inactive operator descriptors,
composition/gate indicators and analytic compute bound. Outer-product task
and strategy features give192 coefficients. No fingerprint, hidden physics,
bundle ID, task ID, or outcome table is a predictor input. Support helpers
retain their documented synthetic reward proxy; it is not observed reward.

For each held source bundle, fit on six common revealed catalogue receipts
from each of four contexts in the other bundle. Target is observed advantage
over anchor0. Predictions over all342 descriptors are frozen before reading
their query labels. Report all-arm MAE, sign/abstention/calibration bias,
fixed-catalogue ranking accuracy and common-support paired mean/observation
kernel comparisons. Missing paired-baseline coverage is explicit, not imputed
as successful prediction. Query local learning uses only the two anchors and
four selected feedback values and is reported separately from frozen prediction.

This new benchmark changes the label to a common sixteen-step FakeStepModel
first-action probe and uses a fixed analytic feedback transform. It is not
a rerun, replication or repair of the closed original E2.25 metric. Complete
protocol and results are in `NEXUS_UNIFIED_AUTONOMOUS_LEARNING.md`. A failed
predictor will be retained but not called useful or promoted.

Completed: fixed-domain MAE0.000685291 versus zero0.000314323; common-support
ridge0.000702215 versus paired mean0.000382788/kernel0.000506623. Novel
descriptor MAE0.000687918 versus zero0.000303970. The new predictor also fails
its source screen. The optional ranker works mechanically; useful quality
generalization is not established. No original E2.25 result was changed.
