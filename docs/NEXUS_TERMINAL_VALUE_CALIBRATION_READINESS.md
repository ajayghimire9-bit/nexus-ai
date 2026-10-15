# Frozen terminal-value calibration — readiness, not results

Prepared on `codex/terminal-value-calibration` from GitHub-matched clean base `d3c3fa8156e8b3ded896385fcf6085b6081a372c`. Implementation and protocol commit: **24db6c469a94d75810fba809582428b9f8964704**. The preparation JSON was generated from that clean revision before this reporting commit. The exact config hash and parent hashes are in `artifacts/terminal_value_calibration_preparation.json` and the locked protocol. No calibration output, approval record, research fitting or new research experience exists.

The single next test compares the already-fitted terminal-value readouts on fresh states, using imagined versus actual16-step endpoints with fixed saved contexts. Frozen-source-mean RMSE is the primary comparator, and actual-endpoint calibration is secondary. This can identify useful differences in value calibration; it cannot establish a causal explanation of full-control failure. The preceding inconclusive correction result remains unchanged.

## Checks actually completed

- Focused synthetic/recorded-evidence suite: **34 passed**,11.41 seconds. An initial test fixture supplied NumPy scalar objects to the strict JSON-number validator; the fixture was corrected to builtin numbers. No scientific method or earlier artifact changed.
- Full regression suite after the final source edits: **550 passed,1 deselected**,123.39 seconds. The deselected test is marked for explicit local-checkpoint verification.
- Explicit `--verify-inputs`: **120 checkpoint files verified**, zero missing/mismatched; all **110 decoder/task groups** (six model/context fingerprints each) reproduced the previous network, normalization and context hashes; ten fixed readouts validated. This is file/model reconstruction, not a new prediction/control evaluation.
- Read-only default preparation: validates all parent artifacts, source fits, seed closures, task tuples and budget arithmetic without creating an environment or fitting a readout.
- Synthetic full-capture tests reconstruct labels, predictions, fixed-source baselines, task/context means and decoder intervals; reject missing whole seeds/tasks, conditions, incorrect endpoints, altered contexts/readouts, stale candidate RNG, raw/summary disagreement, invalid numeric types and resource-count drift. An explicit missing-checkpoint test verifies failure propagation rather than silent skipping.
- Existing terminal-value result JSON, source-fit JSON, checkpoint manifest, original executable config and frozen protocol remain byte-for-byte unchanged from the starting revision. No main merge.

These checks establish implementation readiness, not that the readout generalizes. The new primary screen remains untested.

## Approval boundary and exact proposed cost

One local run, estimated **2–3 minutes**, hard cap **600 seconds**. **21,824 real interactions** (704 cached prefix steps plus21,120 decoder-specific continuation steps); **5,448,960 imagined transitions**; no new support collection, encoder training or readout fitting. Existing context and readout hashes are reused exactly. No paid services. The new run has its own fresh seeds; closed evaluation samples are preserved.

The previous run's approval authorized one consumed experiment and explicitly did not authorize further experiments. `AGENTS.md` requires a new exact-budget approval before a materially different simulation. The underlying entry point rejects missing/stale approval before any environment call; it also requires committed clean code and refuses an existing result. After approval, record and commit the human authorization for this exact configuration before invoking execution. Do not self-supply it.

Configuration SHA256: `0fea17504d5a5baea32d857947cd516ab14cef84df524d7f835594d71d7d6184`.

The one scientific recommendation is to execute this frozen calibration test before changing the value readout, controller or architecture. The experiment has not been run.
