# Frozen terminal-value calibration — protocol v1

Status: implemented proposal awaiting separate budget approval. No research collection has occurred. Starting SHA: d3c3fa8156e8b3ded896385fcf6085b6081a372c, matching GitHub before branching. Branch: codex/terminal-value-calibration. The preceding terminal-value result remains closed and inconclusive (−0.221 [−5.881,+5.438]).

Executable configuration: configs/terminal_value_calibration.yaml. Locked SHA256: `0fea17504d5a5baea32d857947cd516ab14cef84df524d7f835594d71d7d6184`. The runner validates exact task tuples, all parent hashes and protocol lock before preparation or execution. This is a new-state development calibration test on known physics, not untouched-physics confirmation or a new control-success trial.

## Competing hypotheses and intervention

H-readout: the frozen source-fitted value readout does not generalize sufficiently to held-out state/candidate endpoints. H-endpoint: model endpoint error changes value estimates enough to degrade calibration. These can coexist; the test cannot causally explain the earlier full-episode loss.

Freeze all ten 78-coefficient readouts and their source-fitted feature scaling; all decoders, heads, FiLM, original/student encoders, observation normalization and context vectors stay fixed. Reuse exact recorded contexts from the preceding source/evaluation input rows and verify their network/normalizer/context fingerprints after loading and after evaluation. No inference from new support, no fitting, no new optimizer updates. Previously collected support costs remain historical costs, not new interactions.

Use the eight source and three development physics in the executable config. Do not access reserved confirmation physics. Collect one new reset per physics with seed 2200000+t, t=0..10; draw a shared16×16 candidate array using2210000+t. Preselect indices0,4,8,12 before any outcomes. Execute each complete16-action prefix from identical restored simulator state once, caching its actual endpoint across all decoders and contexts. Prefix rewards are recorded for accounting but are not terminal-value labels.

From each actual endpoint, execute48 steps of that decoder's unchanged zero-context H16 MPC,16 candidates, unchanged torque actions/reward. Set the original episode clock to16. At tail step k, use seed2220000+64*t+k, k=0..47, shared across candidates and decoders; randomness cannot depend on outcomes. Tail labels differ across decoders because their zero-policy planning models differ. All candidate prefixes and contexts for a decoder share those exact target labels. Every restoration, action, seed, reward and termination flag is retained. Reject unexpected termination/truncation or incomplete trajectories.

## Predictions and primary estimand

For each decoder/task/context, compare three fixed estimates of that48-step tail return:

- V(imagined16-step endpoint observation,z).
- V(actual16-step endpoint observation,z), research only.
- The fixed mean of the32 distinct source tail labels used to fit that decoder's readout. Do not fit a new constant from query returns or count the six repeated context labels as new targets.

Actual endpoints may be outside the fitted feature distribution. They are not oracle value estimates and must never be supplied to a deployed controller. No action is selected using these estimates during this diagnostic.

Compute RMSE over the four candidate targets **within each task and context first**. Then average the five student RMSEs with equal weight, and average the three development tasks equally, obtaining one value per decoder per prediction condition. Do not pool squared errors across tasks before taking the square root. For the baseline the five equal copies reduce to one task-level RMSE. Zero-context results remain separate descriptive diagnostics.

Primary paired benefit: fixed-source-mean RMSE minus student imagined-endpoint RMSE, positive means the readout predicts held-out tails better. Use ten independently pretrained decoders as the statistical units. Report mean benefit and paired two-sided t95% interval (df9, critical2.262). Practical screen: at least10% reduction, defined as mean decoder-level benefit divided by mean decoder-level baseline RMSE, **and** interval lower bound>0. If the denominator is zero the screen fails and fraction is null. One primary test; source and endpoint comparisons are secondary unadjusted exploratory intervals. No posthoc threshold/metric selection.

Report raw four-candidate targets/predictions; per-context/task/decoder RMSE; paired imagined-minus-actual RMSE; per-task sensitivity; zero-context results. A passing calibration screen would not establish better MPC control or learning-to-learn. A failed screen would not prove all possible value functions fail. Better actual-input calibration motivates endpoint investigation; poor results for both motivate readout/coverage investigation, without causal attribution. Candidate errors and endpoint differences are dependent measurements on the same labels, not independent replications.

## Resources, integrity, and stopping

Proposed one-run cap:600 seconds,21,824 real steps and5,448,960 imagined model transitions. Cached prefixes11×4×16=704; decoder tails10×11×4×48=21,120. Tail planning5,406,720 imagined states plus42,240 endpoint transitions. Zero new support steps, zero encoder-history processing, zero model/readout training. Expected local CPU time2–3 minutes based on the preceding109.68-second pilot; this is an estimate, not a measured result. No paid compute.

Require a newly committed human approval record for this exact config and budget, plus a clean execution revision descended from the starting SHA. The consumed previous approval is invalid. Refuse overwrites/repeated execution. Save partial results on exception or cap exhaustion; complete=true requires all110 decoder/task cells,11 cached prefix groups, all six contexts, three prediction conditions, finite raw values, reproducible arithmetic, exact budgets and120 checkpoint files verified before/after. Missing axes, duplicate cells, booleans/numeric strings/nonfinite values are invalid, not an inconclusive scientific outcome.

Repository JSON/config provenance checks are independent of local binary availability. Explicit --verify-inputs checks all120 checkpoints and all110 saved context/network groups; missing binaries cause failure. Models/checkpoints remain outside Git. Parent JSON files and historical reports are never modified. The default command prepares/validates existing inputs only; it cannot create an environment.

## Commands and planned tests

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_terminal_value_calibration.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_terminal_value_calibration.py
PYTHONPATH=src:.deps python3 scripts/run_terminal_value_calibration.py --verify-inputs
PYTHONPATH=src:.deps python3 -m pytest -p no:cacheprovider
# Only after separate exact-budget approval and committed approval record:
PYTHONPATH=src:.deps python3 scripts/run_terminal_value_calibration.py --approved-config-sha256 0fea17504d5a5baea32d857947cd516ab14cef84df524d7f835594d71d7d6184
PYTHONPATH=src:.deps python3 scripts/run_terminal_value_calibration.py --audit
```

Tests cover context reuse/fingerprints, no refitting/query leakage, fixed baseline from source labels, exact aggregation and decoder CI, full-grid/type rejection, locked budgets, closed-seed refusal, missing approval before any environment and checkpoint loader failure propagation. Synthetic tests do not establish research success. Results will be committed separately if approved and executed. No additional experiment is authorized by this protocol.
