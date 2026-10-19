# Fixed-policy source replication — completed exploratory result

Branch `codex/unified-full-policy-replication`; base
`eff0100690fd82aa22b157a28fc58bbc38a51dc3`. Protocol and tested implementation
were committed before outcomes at `0179cb7073cca09e4f263414e97502543766465c`.
Locked protocol: `NEXUS_UNIFIED_FULL_POLICY_REPLICATION_PROTOCOL.md`.

## Decision

Acrobot's rank-blend advantage passes the registered **descriptive episode
replication** screen against both anchors on these same frozen source models.
The earlier Pendulum loss versus successor does not pass the harm-replication
screen: its aggregate sign reverses, while its model-block signs remain mixed.
The cross-family advantage screen still fails. This is neither a new independent
model replication nor evidence of useful autonomous strategy learning.

All48 registered complete200-step episodes finished. There was one run and no
retuning, fitting, early stopping, dropped episode, retry or confirmation access.
Four model files, all parameter/buffer/RMS fingerprints and320 prior JSON files
are unchanged. E2.17's grant remains consumed and H17 remains blocked.

## Returns and every primary contrast

Mean return averages four episodes within each model, then two models equally.
Families have different reward units and are never pooled.

- Pendulum: flat −392.178200; successor −334.254576; rank blend −246.492644.
- Acrobot: flat −294.260826; successor −298.241977; rank blend −278.943652.

Rank blend minus flat:

- Pendulum: **+145.685556**; model0 +329.500487, model1 −38.129374. Fails
  two-model sign-consistency screen.
- Acrobot: **+15.317174**; model0 +9.477217, model1 +21.157131. Passes the
  >=1-point, both-model-positive screen.

Rank blend minus successor:

- Pendulum: **+87.761932**; model0 +245.452127, model1 −69.928263. Neither
  consistent improvement nor registered consistent harm is demonstrated.
- Acrobot: **+19.298325**; model0 +28.094689, model1 +10.501961. Passes the
  >=1-point, both-model-positive screen.

Old versus new means are descriptive comparisons of different closed episode
samples, not extra confirmation replications. Acrobot's old +27.203518/+28.646612
against flat/successor becomes +15.317174/+19.298325, retaining direction but
shrinking. Pendulum rank-minus-successor changes from −203.758000 to +87.761932.
Its model-block directions were positive/negative in both samples; the magnitude
and aggregate mean are sensitive to episodes. Do not average old and new scores
to redefine the registered result.

Eight new paired episodes per family do not all favor rank blend: Acrobot has
6/8 positive differences against each anchor; Pendulum has4/8 against successor
and5/8 against flat. The full per-episode returns, actions and seeds are saved
in the raw capture. No episode is counted as an independently trained model.

## Important unresolved confounding

There are still only **two independently initialized source models per family**.
These are the same models as the initial screen, not four new model replicates.
No inferential CI or statistical-control-success claim is made. These familiar
physics provide no fresh-physics generalization evidence.

Crucially, reset and planner seed blocks include the model index. Controller
comparisons within a model are paired, but the two models do not encounter the
same reset/candidate schedules. Their different contrasts therefore cannot
causally distinguish a model-quality effect from an initial-state/search-sample
effect. The repeated block sign pattern is diagnostic evidence, not a causal
attribution to model weights. Episode distributions also diverge across policies.
No changes to model architecture, candidate count or conditioning follow.

## Costs and latency

Execution:58.675150 seconds wall /58.133530 CPU. New real interactions9600,
all control evaluation; training/support collection0, fitting0. Imagined
transitions14,457,600 and neural forwards428800; unknown work0. Registered caps
were180 seconds,9600 real and14,745,600 imagined; no extension was needed.

Each policy executes3200 real steps. Flat:4,915,200 imagined/51200 calls;
successor:4,771,200/163200; rank blend:4,771,200/214400. The equal1536-state
ceiling does not make inference calls or wall time equal. Historical H16×16
controllers are not being compared here.

Measured mean planning latency (milliseconds, includes host metering):

- Pendulum: flat2.532, successor5.578, rank blend7.191.
- Acrobot: flat2.115, successor5.007, rank blend6.427.

These local timings include journal/resource-contract overhead and are not a
hardware-independent planner speed benchmark. No model or proposer training
compute was consumed.

## Provenance and independent saved-data audit

Config SHA `3c9445e3533d517edd9385f6e3af3c9ffff3af87b030a58039adee1c75745775`;
protocol SHA `de51600d4329808ade18292f9dfb2183e601820ef4d6316b88c0af7a9b345e23`.
Raw artifact `artifacts/unified_full_policy_replication.json`, SHA
`9853661fc4aa623ebff346f0db2c77a241d8c8b6b5039d302ffd75452dc22e63`.
Its manifests contain all checkpoint/source/parent hashes, dependencies and
code hashes. Checkpoint binaries remain outside Git at their unchanged E2.9
paths. Original E2.9 fit manifest lacks an original execution SHA; this inherited
limitation is not repaired by hashing present files.

The separate `--audit` consumed12.799022 seconds and zero new environment steps,
neural calls or fitting. It reconstructed all9600 decision journals and896000
chained events, source-code hashes at execution commit, published rewards,
resource plans/settlements, paired full grid, continuity, checkpoint bytes,
frozen fingerprints and320 historical JSON hashes. Maximum reward mismatch
3.95413e−7 is below the1e−5 observation-precision tolerance. Resource journals
are gzip-compressed (about57 MiB) and hash-anchored by the raw capture. E1's
inherited synthetic_fixture chain tag is serialization metadata, not a synthetic
reward claim or proof of OS isolation. This is a trusted single-process host,
not activation of the older blocked scientific dispatcher.

Validation artifact `artifacts/unified_full_policy_replication_validation.json`.
Session carried383.939872001 seconds; experiment plus offline audit brings it
to455.414043459 used /3144.585956541 remaining. Unit-test and Git time are
separate. Allocation is consumed, with no automatic retry.

Commands:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_unified_full_policy_replication.py`
- Same command with `--audit` for explicit local binary/journal verification.

## Tests actually run

Before execution200 selected regression tests passed in2.84 seconds. They include
four-episode aggregation, model-level consistency, exact new allocation and
parent hashes, seed freshness/pairing, missing-grid/nonfinite rejection, fixed
operation budgets, original-source-profile regression and existing catalogue,
feedback, resource and planner-adapter checks. No simulator smoke trial ran.
After execution two repository-only capture/fingerprint checks were added; they
do not require untracked checkpoint binaries. Full repository suite not run.
Final selected regression: **202 passed in2.52 seconds** using:

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest
tests/test_unified_full_policy_replication.py
tests/test_unified_full_policy_source.py tests/test_unified_headroom.py
tests/test_unified_e225_e30.py tests/test_evolution2_return_scoring.py
tests/test_evolution2_feedback_integration.py
tests/test_evolution2_feedback_normalization.py tests/test_evolution1_resources.py
tests/test_evolution2_planner_adapter.py -p no:cacheprovider -o addopts='' -q`

## One next scientific experiment

Run a **crossed same-reset Pendulum comparison**: both unchanged models each
control the same four newly registered resets and planner seed streams, comparing
rank blend versus successor only. This would isolate the model factor from the
reset/search block in the present paired design. Eight paired model/episode
comparisons require3200 real steps and imagined ceiling4,915,200, estimated20–30
seconds local CPU, proposed90-second cap. Register rules and new seeds on a
separate branch before collecting; this is a proposal, not an executed or
allocated follow-up. It tests a concrete confound before training another quality
selector or making a model-quality explanation.
