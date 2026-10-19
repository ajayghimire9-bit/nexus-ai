# Crossed-reset Pendulum diagnostic — preference split persists descriptively

Branch `codex/unified-crossed-reset-diagnostic`; base
`b68ecb4ff4c1cee0dcf6759afff4e5d8d78fd4b6`. Tested implementation, protocol and
exact allocation were committed before outcomes at
`9e88043832812431104db4ca68c43eb3116e7784`. Frozen protocol:
`NEXUS_UNIFIED_CROSSED_RESET_PROTOCOL.md`.

## Registered result

All16 complete200-step episodes finished. The registered label is
**`model_preference_split_descriptive`**. Rank blend minus successor averages
**+392.653559** for model0 and **−130.777553** for model1. Model0 is positive on
3/4 shared resets; model1 is negative on4/4. The corresponding matched-reset
interaction averages **+523.431111 points**. Both model means and the per-reset
sign criteria pass the prespecified descriptive split screen.

This removes the different-reset/search-block explanation as a sufficient
explanation of the preference split **on these four tested initial conditions**.
It identifies an interaction between the fixed model bundle and planner rule,
conditional on the tested resets. It does not isolate neural weights from
normalization/source-training data or establish the generality of that interaction.
There are only two pre-existing models, no newly trained model replications,
and no statistical-success or general-control claim. No learning method changed.
These are the two plain residual E2.9 models, not the historical ten-decoder
FiLM/student control study. This result does not explain that study's closed
fresh-physics negative transfer.

## Every matched reset

Rank blend minus successor, reset indices0..3:

- Model0: +525.598827, +645.824911, +523.188229, −123.997733.
- Model1: −133.563900, −3.764084, −126.516375, −259.265852.
- Model0-minus-model1 interaction: +659.162727, +649.588995, +649.704604,
  +135.268120.

Mean raw returns:

- Model0 successor−557.438060; rank blend−164.784502.
- Model1 successor−66.575270; rank blend−197.352822.

The overall equal-model rank advantage is+130.938003, but it does **not** pass
the two-model improvement screen and cannot upgrade the primary split label.
No inferential intervals are supplied for n=2 model bundles. Four matched resets
are not four newly trained models. Old and new samples are not pooled or used
to pick/tune a winning policy. Model0's successor sometimes performs extremely
well too (reset3 return−7.484256), so a blanket claim that it is unusable is false.

## Pairing, frozen state and limits

Both models and both policies used exactly reset2107000000+e and planner
2108000000+200e+t. Initial-observation hashes matched across all four cells at
each reset. All per-step seeds, complete-grid identities and transition chains
passed. Later trajectories diverge as controllers choose different actions;
this is not a same-state intervention at every future decision.

No fitting, new support, new physics, confirmation access or online updates.
Both Pendulum E2.9 checkpoint byte hashes and weight/buffer/RMS fingerprints
match their parents exactly. Source NPZ hashes and parent capture/audit/journal
hashes verify. All323 historical JSON files are unchanged. Historical binaries
remain local and outside Git; missing files fail explicit `--audit`. The old
E2.9 manifest still lacks an original fit execution SHA. H17 and the older
scientific dispatcher remain blocked; E2.17 stays consumed and main unchanged.

## Work actually executed

One registered run,26.554137 seconds wall /26.377644 CPU, local Torch1 thread,
inside the90-second cap.3200 real evaluation steps,4,771,200 imagined states,
188800 model/forward calls. No training/support interactions or optimization.
Reserved/completed work agree exactly and unknown work is0.

Each policy executes1600 real steps and2,385,600 imagined states. Successor
uses81600 model calls; rank blend107200. Same1536-state ceiling and actual1491
states/decision do not imply equal inference calls or speed. These are catalogue
H16 controllers, not historical H16×16. Measured mean planning latency includes
host metering: model0 successor5.247ms/blend6.820ms; model1 successor5.602ms/
blend7.024ms. Fixed order/warmup and local system load limit timing conclusions.

Independent saved-data audit:5.424127 seconds, zero simulation or inference.
It reconstructed3200 decision journals/390400 chained events, published rewards,
all model/source/code hashes, exact resources and pairing. Maximum observed
reward reconstruction difference4.16352e−7 is within the1e−5 precision tolerance.
The inherited E1 synthetic_fixture journal tag remains a serialization convention;
trusted host logs are not external proof of execution or an OS sandbox.

Carried session ledger455.414043459 +26.554137375 +5.424126834 =
**487.392307668 used /3112.607692332 remaining**. Unit-test/Git time is separate.
This allocation is consumed. There was no retry, dropped cell or cap extension.

## Reproduction artifacts and tests

Config SHA `f30b8e56179d079c6ac6a5d26c7d8f0ea3231ecdb4079b4fb85234da7507029b`;
protocol SHA `b9988d9d7d1210ca3e83a17d9563eb968405b45c5e889973f46e276f8b95b237`.
Capture `artifacts/unified_crossed_reset.json`, SHA
`90861b2205bdfcd4b48907e054ca3f3e7a24af09aa245201cd5861de30bab260`.
Raw observations/actions/rewards and checkpoint lineage are retained. Full
compressed per-call journal is `unified_crossed_reset_resources.jsonl.gz`
(about25MiB), with digest anchored in the capture. Saved-data audit artifact:
`artifacts/unified_crossed_reset_validation.json`.

Execution command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3
scripts/run_unified_full_policy_replication.py --crossed-reset`; add `--audit`
for explicit local integrity verification. Source-only checks run before data:
**216 selected regression tests passed in2.75 seconds**. They include cross-model
state pairing, shared RNG schedules, absent/nonfinite/mispaired cells, exact
allocation hashes, interaction/sign arithmetic and all earlier selected planner,
feedback and resource tests. No simulator smoke trial was performed. Two extra
repository-only capture/lineage checks were added afterward; they require no
local model binaries. The full repository suite was not run.
Final selected regression: **218 passed in2.76 seconds**, using:

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest
tests/test_unified_crossed_reset.py tests/test_unified_full_policy_replication.py
tests/test_unified_full_policy_source.py tests/test_unified_headroom.py
tests/test_unified_e225_e30.py tests/test_evolution2_return_scoring.py
tests/test_evolution2_feedback_integration.py
tests/test_evolution2_feedback_normalization.py tests/test_evolution1_resources.py
tests/test_evolution2_planner_adapter.py -p no:cacheprovider -o addopts='' -q`

## One next scientific question

Do the two frozen model bundles differ in state-prediction and termination
calibration on **identical recorded transitions**? Design a source-only cross-model
audit of all3200 saved transitions, with both frozen models evaluated on the same
observations/actions/targets. No new environment interactions, no fitting, at
most6400 one-step model rows and a proposed30-second cap. Group errors by the
recorded model/policy visitor, report each bundle separately, and retain duplicate
state provenance rather than calling rows independent model replications.

This would check an available model-quality signal before building another
planner-quality predictor. Correlation with the present return split would not
prove that prediction error causes it. The follow-up is proposed only, not run or
allocated here; no architecture or controller change follows from this result.
