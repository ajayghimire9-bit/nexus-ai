# E3.10 — Frozen-model evidence integration verified

Implementation and protocol were committed before execution:
`dc52c849c7de7f35affcb57d081e3f0d441a407f` on
`codex/e3-10-metered-model-integration`, from
`9c16f7c1be8a27a40af280d3b0aaae0afbb34506`.
Protocol: `NEXUS_E3_10_METERED_MODEL_PROTOCOL.md`. One authorized run;
no retries, environment construction, new episodes or training.

## Finding

**Metered inference equivalence verified.** All eight model×observation cells
completed, each with both16-candidate H16 sets. Maximum evidence-minus-direct
score difference **0.0** (registered absolute tolerance1e-9, relative0).
Full stable rankings, selected candidate indices, state histories and
termination probabilities match exactly. Saved-state reward reconstruction
also passes, including current-state Pendulum reward timing and cumulative
predicted survival. These are predicted planning scores, not measured returns.

The two candidate sets are deterministic IID test inputs named incumbent and
challenger; they are not a test of which generated strategy is best. Both
paths deliberately reuse the existing scorer. Agreement establishes wrapper
and metering equivalence on these inputs, not independent validation of the
planner, learned physics, or all possible model inputs.

Four original E2.9 CPU residual MLP files, their network/RMS/context-buffer
fingerprints, and all eight source train/validation array hashes remain
unchanged. The source MLPs have4,868 parameters (Pendulum) and5,255 (Acrobot).
These are the current Evolution source models, not replacements for historical
latent/student checkpoints. No model weights were retrained or replaced.
No previous confirmation data or the closed E3.4 return bank was scored.

## Metering and costs

Evidence path:4,096 imagined transitions/256 model calls/256 network forwards.
Direct-reference path: another4,096/256/256. **Total8,192 imagined transitions,
512 model calls and512 observed top-level network forwards**; real steps0,
optimizer updates0. Every call has a pre-dispatch ReservationLedger receipt;
all512 operations complete without unknown work or denied forwards. The hook
counts top-level dynamics-net invocations, not individual Linear layers/FLOPs.
Extra calls and omitted calls fail synthetic adversarial tests; those tests
do not execute learned-model inference.

Measured parent wall0.8183019579882966s, including child startup, imports,
checkpoint loading, scoring and capture persistence. Worker process CPU0.6625s;
peak worker RSS235,798,528 bytes. Time cap30s; one local CPU thread. Both
reference work and evidence work are disclosed; no claimed reduction in
imagined transitions or speedup over uninstrumented control. Small-input
engineering timing is not an end-to-end fresh-study runtime estimate.

Saved-data verifier:0.5794402920000721s, **zero additional model inference**.
It checks raw forecasts, complete expected grid, reward/survival arithmetic,
ledger/hook counts and execution source hashes. After execution plus audit,
carried ledger is **787.6449502930179 used /2812.355049706982 remaining**.
All370 pre-existing research JSON files retain their hashes. The previous
HTML replay is unchanged; the new demonstrator has a separate filename.

## Tests and reproducibility

Focused pre-execution source-only suite:56 passed in1.12s. Broader regression
before the final viewer test:520 passed in10.99s. Final28-module relevant
regression suite: **521 passed in10.82s**. Exact modules/command are recorded
in `artifacts/e3_10_test_report.json`. This is not the entire historical suite;
the known legacy learned-inference benchmark is excluded from source-only
tests. Node `--check` also accepts the generated page's JavaScript; no browser
visual inspection is claimed.

Executed once:

```
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_e3_10_metered_model.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_e3_10_metered_model.py --verify
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/build_learning_lab_replay.py --integration
```

Python3.13.5, NumPy2.5.4, Torch2.14.1. Usage file is consumed; no automatic
rerun. Raw capture retains forecasts and per-cell resource journal receipts:

- `artifacts/e3_10_metered_model.json`, SHA256
  `a577c545f50a270ef7cdf94248f0520528871268b56f6f5ffa86a867459539d3`.
- `artifacts/e3_10_metered_model_validation.json`, SHA256
  `2f223a003b6b5edde685e36736059dd4707643d4b56000331602a910f0a0d4a2`.
- `artifacts/nexus_learning_lab_e3_10.html`, SHA256
  `49108786196f0c5aa8318d1ac9c1602eecfc35257713b30cd77813b4ca5bff66`.

The viewer is offline/read-only. It verifies the new capture/validation digest
before showing engineering status separately from historical observed return
replay and synthetic lineage illustrations. It cannot collect feedback or
authorize an experiment. Tests reject an altered capture. No historical binary
checkpoint is added to Git; existing paths/hashes remain in the capture.

## Interpretation and next step

This completes E3.10's **model-evidence path** for the verified source residual
MLP profile. It does not establish useful strategy-quality prediction,
autonomous improvement, continual learning or control transfer. It does not
bind the full StagedStudy real-environment worker, support-state restoration,
or interruption-safe environment collection. Neural call counts remain a
trusted, vetted-model contract rather than a hostile-code security sandbox.

The single next research milestone is **E3.11: lock and implement the fresh
post-probe return comparison**, with fixed evidence extraction, independent
training/evaluation reset blocks, model-mean and fixed-planner baselines,
shared8-step probes and explicit192-step continuation accounting. Include all
proposal/evidence/controller costs, complete expected axes and frozen recipes
before new returns. Decide one-time selection versus per-step switching before
collection; they are different interventions. Do not fit another static feature
variant on the36 inspected pairs. Four models give only two independent
pretrained models/family; do not count episodes as independent model replicas.
No E3.11 seed registration, allocation or collection was performed here.

Keep E3.12 mutation credit, E3.13 A→B→A→C and E3.14 experiment selection as later
separate hypotheses. Existing working APIs are not empirical evidence for
those capabilities. E3.8's negative selection outcome, consumed E2.17,
blocked H17, old checkpoints, closed splits and main remain unchanged.
