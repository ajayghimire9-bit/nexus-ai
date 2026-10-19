# E3.1 — Learned-world-model discovery headroom audit

Branch `codex/e3-1-learned-model-headroom-audit`, base
`59c7718cca2ce5c2b23eaa79ba64077ae74d229d`. Protocol and tested code were
committed before new inference at `7e417307f6d4693971af521719ceff713aaa9762`.
Protocol: `NEXUS_E3_1_CALIBRATION_PROTOCOL.md`. All prior outcomes are preserved.

## Answer to the research question

The **old first-action/neutral-continuation evaluator is saturated**, while the
**recorded full-policy evaluations can distinguish useful and harmful strategy
choices on the tested source models**. This is not an either/or proof that the
learning mechanism is adequate or inadequate. Its useful discovery capability
has not been demonstrated using the discriminative return labels.

The requested learned-model headroom experiment already ran on the ancestral
branch. E3.1 verifies and reanalyzes that capture rather than silently repeating
its closed16-state342-strategy run. It also verifies three subsequent controller
captures and executes the next registered recorded-transition calibration audit.
No new environment collection, planner run, generated-strategy search or training.

## What the source evidence establishes

1. **Frozen learned-model proxy:** all16 source cells have zero grammar-best
   minus best-anchor headroom; the predeclared practical screen failed. The342
   strategy names collapse to just1–3 selected first-action labels per state,
   and all strategies selecting the same first action receive the same raw
   neutral-tail reward. Anchors already achieve the maximum on this finite
   suite. This evaluator cannot reward a beyond-anchor discovery there, even
   for a perfectly effective search mechanism. This is a verified statement
   about that proxy and those inputs, not every possible source state.
2. **Full repeated control:** the fixed rank blend, chosen from the existing
   executable grammar, beats both Acrobot anchors in the first source sample
   (+27.203518/+28.646612 versus flat/successor) and the fresh-episode replication
   (+15.317174/+19.298325). Each replication used the same two frozen models,
   so these are not extra independently pretrained model replications.
   These passed the local descriptive1-point rule, not the historical
   25-point/ten-decoder general-control rule.
3. **Conditional planner quality:** Pendulum rank-minus-successor varied greatly
   across episode samples. With reset/search schedules crossed across models,
   it is+392.653559 on model0 and−130.777553 on model1. The registered descriptive
   preference split passed on four shared resets. A global ranking of strategies
   is insufficient on these tested model bundles; source physics alone does not
   identify the preferred planner. This does not isolate weights from RMS/data.
4. **Learning remains unestablished:** these fixed generated policies were
   explicitly evaluated, not autonomously discovered/promoted by a successful
   feedback learner. Earlier E2.25/unified quality-prediction and useful-feedback
   failures remain negative results for their protocols. Outcome variation does
   not turn those failures into learning-to-learn success.

The full342-policy grammar was not evaluated in full environment episodes.
Thus there is no complete full-policy discovery frontier or evidence that an
autonomous generator can find it. The fixed rank-blend examples establish
discriminative labels locally, not an optimal planner or general transfer.

## New identical-transition calibration result

Both frozen Pendulum models received all3200 identical recorded observation,
action, next-observation and termination targets in canonical visitor order.
The query hash is shared and unchanged across models. Each of32 metric cells
contains one complete200-row episode; episodes and visitor strata are equally
weighted. Duplicate trajectory rows are retained with provenance, not counted
as independent training replications. No fitted parameter changed.

Model0 versus model1, lower error is better:

- Overall raw-state MAE: **0.050533 vs0.034716**; difference+0.015817.
- Episode-averaged one-step RMSE:0.057894 vs0.054362; difference+0.003532.
- Cosine MAE:0.037161 vs0.022137; difference+0.015024.
- Sine MAE:0.067121 vs0.011666; difference+0.055455.
- Angular-velocity MAE: **0.047316 vs0.070345**; difference−0.023029.

H-state's predicted direction (model0 worse in angular velocity) does not hold
as a point estimate. Model0 has lower angular-velocity error in all four visitor
strata, while its overall MAE and sine/cosine errors are higher in all four.
Overall MAE mixes differently scaled physical coordinates; it is not a proven
decision-quality metric. These component disagreements caution against using
one scalar dynamics error as a guaranteed planner selector. No causal link to
the return interaction has been established.

Recorded-state mean termination probability:0.005333112 vs0.005244714, difference
0.0000883984. Brier error:0.0000323781 vs0.0000283572, difference0.00000402084.
Mean Brier differences are positive in two visitor strata and negative in two.
Neither model exceeds the fixed0.5 termination threshold on any row. Actual
termination count is0;16 TimeLimit truncations are not termination labels.
H-stop has a small positive aggregate directional difference, but this does
not establish a termination mechanism. No positive-class calibration, imagined
trajectory calibration or compounding-risk conclusion is supported.

**These query-trajectory error metrics are retrospective diagnostics. They are
not available before episode decisions and must not become pre-decision
features in a future quality predictor.** Any residual features need separately
permitted support available at decision time. No query label was used to fit
a model, student, latent, proposer or predictor in E3.1.

## Provenance, resources and validation

All four existing Pendulum/Acrobot E2.9 bundle0/1 checkpoints and eight original
source-array hashes were verified before loading either Pendulum model. Existing
headroom provenance agrees with the fit manifest and array inventory. Prior
controller checkpoint hashes, compressed journals, complete reward grids,
historical code snapshots and registered arithmetic also match. Original fit
execution SHA is still absent: present-file consistency is not independent
attestation of the original training. Local model binaries are not in GitHub;
explicit verification fails if they are missing or wrong.

New source-only audit: **0.669058 seconds wall /0.458246 CPU**,26 frozen neural
forward calls,6400 one-step diagnostic model rows,0 new real steps,0 fitting,
0 MPC rollout. Reused historical control cost19200 real steps is **not newly
executed**. There were no new teacher targets, physics, seed registration or
confirmation outcomes. Four checkpoint files were verified; only two ran.

The existing ReservationLedger records complete6400-row work, no unknown cost;
its journal is retained. It remains a trusted-host contract, not an OS sandbox.
Both inferred model/normalizer fingerprints and all326 previous JSON files are
unchanged. Separate no-inference saved-data verification took0.567836 seconds,
reproducing all32 metric cells, query identity, evidence arithmetic, source-code
hashes, checkpoint hashes and the resource journal. No retry or cap extension.

Carried ledger487.392307668 +0.669057750 +0.567835833 =
**488.629201251 used /3111.370798749 remaining**. Unit-test/Git time is separate.
H17 and the old scientific dispatcher remain blocked; E2.17 is not reused.
Main and all historical results remain unchanged.

Capture `artifacts/e3_1_learned_model_audit.json`, SHA
`79282831995a5ea7ec681f382b0dba6ad227ed9395704c8de5ec816e2cfc5418`.
Config SHA `2b57039cd2e2df0267bf7ee00c267aa69ac30de0e06d9241ec597603c0d2e12d`;
protocol SHA `cb34aecf7ecdb92c958b5c69e0518933d3228a3277b39ff242686785e1a956b6`.
Raw next-state predictions/probabilities,32 per-visitor episode metrics, all
source/checkpoint/evidence hashes, dependency versions and resource traces are
saved. Validation: `artifacts/e3_1_learned_model_validation.json`.

Commands: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3
scripts/audit_e3_1_learned_model.py`, then the same with `--verify`.
Before execution239 selected source-only tests passed in2.97s; no simulator or
model-loading test fixture. Added repository-only saved-result checks afterward
do not require local .pt files. Full repository suite was not run.
Final selected regression: **241 passed in3.22 seconds** using:

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest
tests/test_e3_1_learned_model_audit.py tests/test_unified_crossed_reset.py
tests/test_unified_full_policy_replication.py tests/test_unified_full_policy_source.py
tests/test_unified_headroom.py tests/test_unified_e225_e30.py
tests/test_evolution2_return_scoring.py tests/test_evolution2_feedback_integration.py
tests/test_evolution2_feedback_normalization.py tests/test_evolution1_resources.py
tests/test_evolution2_planner_adapter.py -p no:cacheprovider -o addopts='' -q`

## One next scientific experiment

Test the **existing planner-advantage predictor on fresh paired full-policy
source-return feedback**, against per-model training means and simple family
priors fit only from that new permitted training feedback. Register new training
and held-out evaluation reset blocks before collection. Never fit on any of
the closed control captures audited here or use their rewards for tuning.
Only genuinely pre-decision inputs and training-revealed feedback are allowed;
the above future-trajectory error metrics cannot be inputs. Keep all world
models frozen. One small proposal: four existing source models×(three training
plus four evaluation resets)×two fixed controllers×200 steps=11200 new real
interactions, imagined ceiling17,203,200, estimated90–120s/proposed180s CPU cap.
This is a separate prospective development experiment, not new physics/model
confirmation. No allocation or collection is executed in E3.1.

That directly tests learning on an evaluator known to distinguish full-policy
outcomes before scaling datasets/architecture or attributing failure to the
learner. It cannot by itself establish continual learning, L2L or AGI.
