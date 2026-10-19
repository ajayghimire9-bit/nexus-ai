# Full-policy source return screen — completed, mixed and exploratory

Implementation/protocol execution commit:
`1d78d2965e04175824f53355ed2253e33bcba260`.
Branch `codex/unified-full-policy-source-screen`.
Base `5221d7f46650f99f453288c7e3482fc5ba21e55a`. Frozen protocol:
`NEXUS_UNIFIED_FULL_POLICY_SOURCE.md`. No outcomes informed its four policies.

## Result and scope

All 32 complete 200-step episodes finished under the registered caps. Neither
generated policy passed the declared cross-family exploratory point screen.
The ranking composition has a useful-looking **Acrobot-only** signal; its
Pendulum result is strongly model-dependent and worse than the successor anchor.
This establishes that repeated policy execution supplies distinctions the
earlier neutral-tail first-action proxy missed. It does not establish a useful
quality predictor, feedback-driven improvement, transfer or general control.

Mean episodic returns, averaging episodes within models and then the two models:

- Pendulum: flat −563.772426; successor −226.029525; switch −225.261266;
  rank blend −429.787525.
- Acrobot: flat −300.806082; successor −302.249176; switch −299.946900;
  rank blend −273.602564.

All registered generated-minus-anchor contrasts follow. Parentheses give the
two model-level paired differences after averaging their two episodes; these
are not independent episode replications or confidence intervals.

- Pendulum switch−flat: +338.511160 (+606.664883, +70.357437), point screen passes.
- Pendulum switch−successor: +0.768259 (+1.910563, −0.374046), fails.
- Pendulum rank−flat: +133.984901 (+609.620864, −341.651062), fails.
- Pendulum rank−successor: −203.758000 (+4.866545, −412.382545), fails.
- Acrobot switch−flat: +0.859182 (−4.696100, +6.414464), fails.
- Acrobot switch−successor: +2.302276 (0.000000, +4.604552), fails.
- Acrobot rank−flat: +27.203518 (+41.637895, +12.769140), passes.
- Acrobot rank−successor: +28.646612 (+46.333996, +10.959228), passes.

These are eight descriptive comparisons on inspected family-default source
physics, n=2 separately fitted models per family and two evaluation episodes per
model. The two families use different rewards and are not pooled into a return
estimate. No statistical-success claim or adjusted/unadjusted significance
claim is made. The rank composition was fixed before this sample; treating its
Acrobot result as a selected winner for deployment would be premature.

## What actually ran and cost

Command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3
scripts/run_unified_full_policy_source.py`. One execution, 39.333486 seconds
wall, 39.308939 CPU; no cap extension or retry. Local CPU, Torch single-thread.
6400 evaluation environment interactions, 0 training/support interactions,
9,617,100 imagined state transitions, 293,900 forward calls. No optimizer or
parameter updates. No confirmation environments or previously closed seeds.

Each controller executed 1600 real steps. Flat used 2,457,600 imagined states /
25,600 calls; successor 2,385,600 /81,600; switch 2,388,300 /79,500; rank blend
2,385,600 /107,200. Same 1536-state decision ceiling does not mean equal calls
or time. These are catalogue controllers, not the historical H16×16 experiment.

Raw trajectories and every reset/planner seed are in
`artifacts/unified_full_policy_source.json`, capture SHA
`f25b55d3f371acf480f0d35e375989234e8ebbef774881e5c05d8a3216de5af4`.
Full per-call journals are compressed in `unified_full_policy_resources.jsonl.gz`
(about40 MiB). Checkpoints are the unchanged local E2.9 files, not added to Git;
the raw result records their paths/hashes and the eight source-array hashes.
Original E2.9 manifest lacks an original execution SHA, so hash-verified local
availability does not repair that historical provenance limitation.

## Independent saved-data verification

`scripts/verify_unified_full_policy_source.py` performed no inference or
environment steps. It verified 6400 decision journals /613400 chained events,
execution-commit source hashes, published reward timing, complete paired grid,
transition continuity, both families' action plans, all four checkpoint byte
hashes, before/after weight-buffer-normalizer fingerprints and all317 previous
JSON byte hashes. Maximum reward reconstruction discrepancy3.89552e−7, within
the declared float32 observation tolerance1e−5. Reserved and completed work
match exactly; unknown cost is zero. Validation is in
`artifacts/unified_full_policy_validation.json`.

The reused E1 Journal's chain preimage retains its inherited
`synthetic_fixture` format tag; it is a serialization convention, not a claim
these actual host-observed steps were authored fixture rewards. This standalone
host does not enable or repair the older blocked scientific dispatcher. The
journal proves internal record consistency, not external authentication of CPU
measurements or execution.

Offline audit took9.206182 seconds and is conservatively charged to the carried
session ledger:383.939872001 used /3216.060127999 remaining. Unit-test and Git
time are reported separately from experiment/audit execution. This allocation
is consumed, not reusable. E2.17 remains consumed/inconclusive and H17 blocked.

## Tests and interpretation limits

Before execution:184 focused/relevant source-only regression tests passed in
2.14 seconds (same selection also passed in2.15 before final preflight edits).
They cover missing/nonfinite grids, seed pairing, synthetic model-call shapes,
checkpoint mismatch, interrupted cost and gzip journals. No simulator smoke
trial was run. Repository-only result tests added after execution do not need
untracked checkpoint binaries; explicit checkpoint audit fails if absent.
Final selected regression:186 passed in2.32 seconds, including the two added
saved-capture and fail-closed offline audit checks. Full repository suite was
not run; the executed selection is reproduced below.

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest
tests/test_unified_full_policy_source.py tests/test_unified_headroom.py
tests/test_unified_e225_e30.py tests/test_evolution2_return_scoring.py
tests/test_evolution2_feedback_integration.py
tests/test_evolution2_feedback_normalization.py tests/test_evolution1_resources.py
tests/test_evolution2_planner_adapter.py -p no:cacheprovider -o addopts='' -q`

This run tests fixed policies, not whether the generator learns better proposals.
It does not compare every grammar member, use unfamiliar physics, independently
confirm an advantage, or measure learning-to-learn. Sources share the established
collection recipe; episodes/models are few. Task-specific sign changes could
reflect planner suitability, model error or reset variability; no causal
attribution is warranted. Frozen checkpoints were neither retrained nor replaced.

## One next experiment

Independently replicate the rank-blend-versus-both-anchors comparison on fresh
paired source episodes in both families, keeping these policies/models fixed.
Four new resets per model would cost9600 real steps (4models×4episodes×3policies
×200), imagined ceiling14,745,600, estimated60–90 seconds local CPU with a
180-second cap. Register new seeds and a separate branch/protocol first; do not
reuse this consumed allocation. This tests whether the family-specific signal
survives episode variability before using it as a learning target. Not executed
in this branch.
