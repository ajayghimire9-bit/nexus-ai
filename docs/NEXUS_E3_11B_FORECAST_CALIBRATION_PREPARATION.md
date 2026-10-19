# E3.11B — Preparation verification

Implementation/proposed protocol committed as
**02909732859265b0e83340105fd32e12975f806d**, based on GitHub-verified
4b8c305562e9c9b30e074d3bff2ecd5ec6cf18ea. Branch:
codex/e3-11b-forecast-calibration-preparation.

**No scientific result or execution authorization.** Proposed protocol is
NEXUS_E3_11B_FORECAST_CALIBRATION_PROTOCOL.md. The new code is a pure capture/
analysis contract plus metadata checker, not a bound environment worker.
The --execute flag intentionally fails before any runtime/model import.
All examples in tests are authored callbacks and scalar reward sequences.

The initial focused check passed79 tests across calibration/headroom/post-probe/
metered-model modules. Three additional strict identifier/overflow tests were
then added; the subsequent relevant regression command passed **585 tests**
across31 modules, including30 new tests. This is not the entire historical
suite. The legacy residual benchmark that executes learned inference is excluded.
No test duration or peak memory measurement was captured for this preparation.

Executed regression command (variables set to1 for OPENBLAS_NUM_THREADS,
OMP_NUM_THREADS, VECLIB_MAXIMUM_THREADS; PYTHONDONTWRITEBYTECODE=1):

```
PYTHONPATH=src:.deps python3 -m pytest -q \
 tests/test_e3_11b_forecast_calibration.py \
 tests/test_e3_11a_rollout_headroom.py \
 tests/test_e3_11_post_probe.py \
 tests/test_e3_10_metered_model.py \
 tests/test_e3_9_evidence_readiness.py \
 tests/test_e3_8_learning_interfaces.py \
 tests/test_e3_7_transition_evidence.py \
 tests/test_e3_6_feature_informativeness.py \
 tests/test_e3_5_residual_advantage.py \
 tests/test_e3_4_feedback_coverage.py \
 tests/test_e3_3_training_feedback_audit.py \
 tests/test_e3_2_return_feedback.py \
 tests/test_unified_e225_e30.py \
 tests/test_unified_headroom.py \
 tests/test_unified_full_policy_source.py \
 tests/test_unified_full_policy_replication.py \
 tests/test_unified_crossed_reset.py \
 tests/test_e3_1_learned_model_audit.py \
 tests/test_evolution2_planner_quality.py \
 tests/test_evolution1_resources.py \
 tests/test_evolution1_source_contracts.py \
 tests/test_evolution1_toy_loop.py \
 tests/test_evolution2_observation_memory.py \
 tests/test_evolution2_observation_memory_cross.py \
 tests/test_strategy_memory.py \
 tests/test_strategy_memory_obs.py \
 tests/test_strategy_memory_selector.py \
 tests/test_strategy_memory_decide.py \
 tests/test_strategy_memory_persist_obs.py \
 tests/test_evolution2_fit_clock.py \
 tests/test_evolution2_fit_clock_run.py -rA
```

Also executed the preparation checker without --execute; it verified the pinned
inventory/TRAIN-prior metadata. Independently byte-hashed all four local frozen
checkpoint files and eight original source arrays against that inventory;
all12 match. No checkpoint deserialization or neural forward was performed.
git diff --check passed; previous tracked artifact paths remain unchanged.
Two pre-existing untracked adapter files were excluded from commits and preserved.

New tests check durable forecast-before-outcome ordering, isolation from caller
mutation, receipt tampering, missing model/family/episode/condition/reward cells,
nonfinite/non-numeric/boolean values and overflow; correct192-step primary
versus16-step secondary arithmetic; tie handling; a baseline beating a wrong
forecast; two-model rather than episode-level intervals; TRAIN-only pinned
prior; exact budget settings; and fail-closed execution. Hashes and resource
verification are in artifacts/e3_11b_calibration_preparation.json.

Scientific consumption **0 real steps,0 imagined transitions,0 model inference,
0 training,0 execution seconds**. Carry ledger unchanged:
889.765542043008 used /2710.2344579569917 remaining.

One next step: finish and review the existing metered-host binding and register
fresh seeds/allocation after explicit approval of E3.11B's proposed6272 real
steps/9932800 imagined transitions/393728 forwards and180-second cap. Only then
commit the final lock and collect outcomes once. The user's roadmap explicitly
withheld execution authorization; test success is not permission or scientific
evidence. E3.11C–E4.0 stay conditional proposals.
