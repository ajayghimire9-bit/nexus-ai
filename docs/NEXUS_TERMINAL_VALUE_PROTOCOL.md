# Terminal-value pilot — locked design v1

Status: implementation and tests only; **no research collection or fitting has run**. Base `03ae1874339ffa2d7e3cb63daa4d72b0d200f143`, verified against GitHub. Working tree was clean. This protocol is committed before outcomes. A new, materially different experiment requires approval of the exact configuration hash and budget; the underlying execution function enforces this, not only the CLI. Never infer approval from the preceding diagnostic's budget.

## Question

Does a small source-trained terminal-value correction improve same-state first-action choices over the unchanged student-context score? The last source diagnostic found that even exact H=16 reward ranking omitted later value, but committed full 16-action blocks. That does not establish a problem with actual first-action decisions. Competing explanations: useful missing continuation value can be learned; a small readout cannot generalize; model endpoint error makes the readout misleading; or first-action choices hardly change despite block-ranking differences.

## One intervention

Freeze all ten existing decoders, five associated broad students each, normalization, FiLM and heads. H=16, sixteen candidates, torque actions −2/0/+2, existing reward and base scoring remain fixed. Add only an explicit terminal score:

`corrected_score = original_score + predicted_survival_at_16 * V(predicted_obs_at_16, frozen_context)`.

One ridge readout per independent decoder. Inputs: three predicted endpoint observations and eight frozen context coordinates. Features: eleven linear coordinates and all 66 quadratic products with repetition, plus intercept: **78 fitted coefficients**. No physics parameters or task IDs enter features. Standardize the 77 nonconstant features using source-fitting rows only; fixed floor 1e-8 maps constant features to unit scale. Solve mean squared error plus lambda=1 times squared nonintercept coefficients in float64; intercept unpenalized. No hyperparameter selection, clipping, ensembles or new neural architecture. Existing normalization stays unchanged. Endpoint rollout is separate from original scoring and doubles candidate-rollout inference for this comparison; disclose the cost.

Fit `V` to the actual next-48 reward of the unchanged zero-context controller from the actual endpoint, with fixed per-step candidate seeds. Training input is the **predicted** endpoint under each frozen context, so imagined-state input is seen during training. Targets use the actual endpoint. V therefore estimates a specified zero-policy continuation, not optimal or student-policy value.

## Source collection and fitting

Eight existing `pendulum_context_train()` physics, one new reset per task. New 128-row random support per task, shared across decoders. Generate the standard 16×16 candidate set; use only prespecified indices [0,4,8,12] for source targets. This selects training examples, not a change to the deployed 16-candidate budget. Execute the four 16-action prefixes once per task and cache observations/rewards/endpoints across all models.

For every decoder/task/candidate, restore the actual endpoint with original episode clock 16 and execute 48 steps of unchanged zero MPC. Draw identical per-step continuation candidates across candidate indices. For each of the six frozen contexts, pair its predicted endpoint and context with this same source-only tail target. There are 32 unique source endpoint targets per decoder and 192 readout rows (six contexts per target). Repeated labels are **not** independent examples; mean loss weights each endpoint equally. Fit once using all registered source rows, no selection on development.

Save all ten readouts, source metadata, support hashes, feature/scaling/weight hashes and source diagnostics **before collecting any development query outcomes**. No fitting or normalization updates after this boundary. Support hashing uses a full SHA256 including arrays, flags, shapes, dtypes and episode/reset IDs. The existing 16-character legacy hashes are not mislabeled as full hashes.

## Development intervention

Three existing context-development physics, separate from readout source physics. They are previously inspected development material, not untouched confirmation and not necessarily unseen to all historical components. Register two new initial-state seeds each. New 128-row random support per physics, shared across decoders. No reserved confirmation task is collected. No old diagnostic rows are fitted or rescored as independent evidence.

At each same true state, generate a single shared 16×16 candidate set. Score zero and five student contexts with and without the same decoder's readout. Conditions: student+value, unchanged student, zero+value, unchanged zero. No controller sees true state, physical parameters or realized counterfactual rewards as input. Tie-break by first argmax index.

Execute all three possible first actions separately from that exact state. After the first action, follow the **identical unchanged zero-context policy** for 63 steps, using action-independent per-step planner seeds. Cache these three actual returns across every condition and student. Compare returns of the actions selected before outcomes are opened. This is a fixed-policy same-state intervention, **not** evaluation of a corrected full-episode controller. Future-policy/distribution shift remains unresolved.

## Primary estimand and screen

Within each decoder/task/state, average corrected-student minus unchanged-student common64 returns over five student seeds; equally average the two states, then three tasks. Ten decoder means are the independent units; t95% interval with df9, critical value2.262. One primary comparison, no multiplicity adjustment. Meaningful local gain requires mean >=1 and lower95% >0, complete finite grid, unchanged original parameters/context and valid provenance. Otherwise label local result inconclusive, or local harm if the interval is entirely negative. Incomplete/invalid runs are not scientific negatives. Do not reinterpret a positive point estimate as success.

Secondary unadjusted comparisons: corrected student versus unchanged zero; corrected zero versus unchanged zero; corrected student versus corrected zero; action disagreement; source-fit prediction error; first-action regret among three available actions; exact frozen-model hashes, cost and per-task/per-decoder failures. No full-control or learning-to-learn claim is permitted. A local gain cannot establish new-physics control transfer.

## Exact budget and seeds

Executable source of truth: `configs/terminal_value.yaml`. Source support1,024 + cached prefixes512 + source tails15,360 + development support384 + common interventions11,520 = **28,800 real steps**. Source model states: endpoint30,720 + continuation3,932,160. Development: paired base/endpoint scoring184,320 + continuation2,903,040 = **7,050,240 imagined transitions**. Extra encoder work70,400 history rows, separately recorded. Ten fits, 780 total fitted coefficients, with source-only scaling metadata; source neural-optimizer steps0.

Estimate **2–4 minutes** simulation from the previous238-second/15.85M-state run, plus fitting, loading and serialization; hard cap **600 seconds** including integrity checks and final validation. Tests are separate. Cap counters inside environment and model calls; save incomplete capture on failure. No automatic retry or larger budget. No paid services. Preserve all old artifacts/binaries. Check all120 existing files before/after; exact network, original normalization and context equality throughout.

All seeds are listed through base/formula rules in executable helpers. Train support reset `2000000+10*t`, action RNG `2001000+t`; train reset `2010000+t`, candidate RNG `2020000+t`, tail seeds `2030000+64*t+k`, k0..47. Eval support reset `2040000+10*t`, action RNG `2041000+t`; eval reset `2050000+10*t+j`, candidate RNG `2060000+10*t+j`, common continuation `2070000+256*t+128*j+k`, k0..63. The first action is forced and does not draw candidate randomness; subsequent k values remain shared across forced actions. No seed depends on action or fitted outcome. Validate disjointness against prior closed control registries and the previous planning-value set.

## Tests and execution gates

Tests must show exact endpoint replay and reward timing; score addition with survival; constant-value invariance when survival is one; informative toy value fitting and independent prediction; source-only normalization; no fitting from development; exact same candidate sets and action-independent continuation randomness; frozen context/network hashes; full expected decoder/task/state/condition grids; NaN/inf/bool/numeric-string rejection; deterministic fit/save/load; missing approval rejected before any environment call. Test success is implementation evidence only.

Preparation and tests are approved development work. Commit protocol/implementation before collecting any training or evaluation outcomes. Runner requires explicit `--approved-config-sha256 HASH` matching the committed configuration, clean source state and intact parent/manifest/checkpoints. Without approval it prints a preparation estimate and does not collect or train. The approval hash is a scope check, not a replacement for human authorization. Do not supply it autonomously.

Save a source-fitting stage before development, raw per-state scores, candidates, observations, actual action traces, common returns, statistics and readouts. Refuse overwrite of results. Finish with independent raw-to-decoder arithmetic audit. Update research status honestly even if no simulation is authorized. Current status is **prepared, not tested scientifically**.


## Pre-execution readiness record

Focused tests: **35 passed** in **9.36 seconds**. Full repository regression: **515 passed**, one explicitly local checkpoint test deselected, in **110.93 seconds**. Explicit checkpoint test: **1 passed**, three unrelated tests deselected, in **0.62 seconds**; all120 required binaries verified. No registered research episode or source readout fitting has run. Unit tests use toy labels and unregistered fixture states; these are not scientific evidence of a controller gain.

Tests cover the real frozen neural model and normalization during endpoint scoring; synthetic objective recovery and checkpoint round trips; source-only fitting and normal-equation verification; rejection of missing seeds/tasks/conditions, corrupt scores, RNG, frozen records and counters; full synthetic capture reconstruction; and approval rejection before any collector call. This resolves the helper-contract testing weakness encountered in the prior diagnostic. The full real-checkpoint experimental path remains to be evaluated only after budget approval.

Commands actually executed:

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_terminal_value.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 -m pytest -p no:cacheprovider
PYTHONPATH=src:.deps python3 -m pytest tests/test_checkpoint_integrity.py -m checkpoint_integrity -p no:cacheprovider
git diff --check
```

After the implementation commit, run the default command to inspect the no-data proposal:

```sh
PYTHONPATH=src:.deps python3 scripts/run_terminal_value.py
```

Only after human approval of its exact hash/budget, execute once with `--approved-config-sha256` and that hash. After a complete run, `PYTHONPATH=src:.deps python3 scripts/audit_terminal_value.py` is a read-only audit, including on a fresh clone with JSON files but no `.pt` binaries; add `--write` once to save the audit. The explicit checkpoint audit always requires actual binaries and fails if any are absent. Experimental return and generalization results remain unknown.
