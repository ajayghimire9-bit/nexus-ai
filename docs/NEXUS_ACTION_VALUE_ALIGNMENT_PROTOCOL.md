# Sequence-value versus first-action value — exploratory protocol v1

Base `1f73c39f0ca608c0498dd62742814ed3e50221c6` verified against GitHub before branch `codex/action-value-alignment-audit`. This protocol precedes calculation of the new action-alignment metrics. Source results are already inspected development evidence; this is a registered exploratory reanalysis, not independent confirmation.

## Question and fixed data

H-objective: the first action of the actually best64-return full sequence can be inferior when followed by immediate zero-context replanning instead of that sequence's remaining15 actions. H-alignment: full-sequence choice remains aligned with the first-action/common-zero intervention on the sampled states. H-coverage: a gap is explained by the best first action not appearing in the16 sampled sequences. Do not assume a particular explanation.

Use exactly the saved60 decoder/task/visitor cells from the fresh source-scalar evaluation. Each contains16 measured full-sequence64 outcomes and three measured forced-first-action64 outcomes from the same restored phase50 state. The full sequence executes16 actions then48 zero-policy steps; the first-action branch executes one action then63 zero-policy steps. Both measure64 real rewards, but their futures differ. Never describe the sequence research reference as an oracle for the first-action policy. All ten decoders, existing student contexts and fixed beta/readout remain unchanged. No new data, model inference, fitting or MPC. True outcomes are research labels only and never feed a deployed agent.

## Exact contrasts, ties and coverage

Let q_i be recorded16-prefix+48-tail return for candidate i, A_i its first action, and Q_a the recorded forced-action+63zero return for action a∈{0,1,2}. Choose i*=argmax(q), breaking exact ties toward the lowest candidate index. Choose the research best action argmax(Q) with the lowest action index for ties. No favorable tie selection or tolerance-based reselection.

Primary **total alignment regret** is max_a Q_a−Q_(A_i*). Let S be the first actions represented by the16 candidates. **Coverage gap** is max_all Q−max_S Q; **represented-action alignment regret** is max_S Q−Q_(A_i*). Verify total=coverage+represented within1e−8 and nonnegativity. This prevents attributing absent-action coverage to sequence ranking. Report the fraction of states representing all three actions. The optimal-action indicator uses regret≤1e−8 only as a numerical reporting tolerance; it never changes selection.

The exploratory screen requires total regret mean≥1 with paired95% lower>0 **and** represented regret mean≥1 with paired95% lower>0. Label `sequence_first_action_misalignment_detected` only if both pass. If only the total screen passes, label `first_action_gap_with_coverage_or_uncertainty`; otherwise `alignment_gap_not_established`. An interval including zero is not equivalence. A complete valid failure of this screen differs from an incomplete execution.

Store primary state metrics once per decoder/task/visitor, not five copies: total/represented/coverage gaps, selected first-action value, best three-action value, best represented value, optimal-action indicator and full first-action coverage. Additional first-action references use original, uncalibrated-correction and fixed calibrated scores for each saved context. Report their first-action values/regrets, selected-action agreements with the sequence reference and sequence-reference-minus-reference first-action return. Their differences and regrets are dependent diagnostics, not independent evidence. No secondary reference upgrades the primary screen.

## Aggregation and scientific limits

Average both visitor groups equally, then three tasks equally inside each independently pretrained decoder. Compute paired two-sided t95 intervals across ten decoder values,critical2.262,df9. For context-based references, average five scoring students inside each decoder/task/visitor before the same aggregation; report zero scoring context separately. Candidate sequences, states, visitors and students are not extra training replications. Report every task and visitor subset as unadjusted exploratory sensitivity. Primary metrics depend on actual simulator outcomes/zero continuations, not the pooled fitted scalar; reference comparisons remain conditional on the locked shared scalar.

Even a positive screen only demonstrates an objective/future-policy alignment gap for the specified common-zero intervention. It does not establish student-policy action values, full-episode failure causality, a better controller or general transfer. No controller is built from the research outcomes. If the screen fails, retain uncertainty and investigate prediction rather than asserting alignment universally. Do not increase model size, retune beta, change horizon/candidate count or reuse these states for confirmation.

## Budget and provenance

Local CPU cap60seconds, estimated<30. Standing session ledger leaves177.5045seconds before allocation. Zero new environment steps, imagined transitions, neural inference or fitting. Existing scalar sourcefit and75,960-step evaluation costs are inherited. Validate source capture, fit/config/protocol hashes, complete60-cell grid, clocks/rewards/contexts and saved summaries without loading binaries. Frozen scalar readout formulas may be recomputed arithmetically during validation; no world model is executed.

Commit protocol, executable config, tests and exact allocation before analysis. Require a clean implementation revision, immutable parents and no existing output. Save complete finite metrics and state/reference rows, dependencies, runtime and hashes. Save partial output on errors/timeouts, never shrink or quietly retry. Do not alter historical files, main or checkpoints. Explicit binary auditing is separate; repository-only analysis must not require .pt files.

## Meaningful tests

Construct a known synthetic case where the best committed sequence begins with a bad replanning action; a fully aligned case; missing-action coverage; duplicate/tied candidates; and all-flat values. Test exact decomposition, lowest-index tie selection, no repeated student counting for state metrics, equal visitor weights/ten-unit intervals, strict missing-seed/task/visitor/context/metric/type rejection, raw reward reconstruction and no environment/model execution. Independently recompute the primary gaps from integer selected indices and plain reward sums after execution.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_action_value_alignment.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_action_value_alignment.py
# Once, from clean protocol commit:
PYTHONPATH=src:.deps python3 scripts/run_action_value_alignment.py --execute
PYTHONPATH=src:.deps python3 scripts/run_action_value_alignment.py --audit
PYTHONPATH=src:.deps python3 -m pytest -p no:cacheprovider
```

Conclude only what the recorded interventions distinguish, then recommend one later experiment. No further experiment is included in this allocation.
