# Visited-state value discrimination — locked exploratory protocol v1

Base `e606212f4015a743a6cca194eb95a671fa29af3a`, verified against GitHub before branching to `codex/visited-value-ranking-audit`. No outcomes for the new metrics have been calculated. The previous phase50 commitment interaction is already known and inconclusive. This is explicitly exploratory reanalysis, not independent confirmation.

## Question and alternatives

Does the frozen terminal readout distinguish better versus worse candidate tails at visited states? H-information: useful candidate-relative information survives, even if selected return is uncertain. H-calibration-only: absolute prediction accuracy does not translate to within-state discrimination. H-prefix: prefix forecast errors and their combination with tail values degrade choices. These alternatives may coexist. Descriptive alignment does not establish causality or explain the closed full-episode loss.

## Fixed data and baselines

Use only the saved60 decoder/task/visitor cells, all16 recorded prefix outcomes and48-step common-zero tails, five saved student scoring contexts and zero context. No MPC call, neural inference, context fitting, environment construction or new data. Preserve every model/readout and all parent hashes. Source labels used for the fixed constant come only from the original source-fit artifact, not these visited query outcomes.

For decoder d, the source constant is the mean of all original source48-step trace returns for d, matching the earlier calibration baseline. For each state and context define tail target y_i=recorded48-step return, prefix r_i=recorded16-step return, and total q_i=r_i+y_i. Prediction p_i is the saved unweighted terminal readout; a_i is saved survival, b_i is original H16 score. Corrected score is b_i+a_i*p_i; constant score is b_i+a_i*c_d. Never assume survival weighting leaves constant selection unchanged.

The empirical within-state mean of y is used only as an analysis reference for centered error; it is not a deployable baseline, fitted controller or model input. The research-only score r_i+a_i*p_i substitutes the actual prefix to inspect error combination; it is not a learned/deployed controller. Actual64 best and actual16 ranking are research-only references. No outcome is passed back into a model or optimizer.

## Metrics, ties and primary exploratory rule

At every state/context calculate tail MSE, squared mean error, centered error MSE, fixed-source-constant MSE and within-state tail variance. Check MSE=bias²+centered MSE. Define **centered benefit=variance(y)−centered MSE**. A constant's centered prediction is zero regardless of which constant is chosen.

Measure pairwise ordering accuracy over the120 unordered candidate pairs: score1 when predicted and actual strict order agree,0 when they disagree,0.5 for any predicted or actual tie. This convention is finite for constant forecasts/flat targets. Neutral reference0.5. Record actual-tail tie fraction. Pairs are dependent descriptive elements, never statistical replications. Define **tail rank advantage=pair accuracy−0.5**.

The single intersection screen is centered-benefit paired95% lower>0 **and** tail-rank-advantage lower>0. Label `within_state_tail_information_detected` only if both pass. If centered-benefit upper<0, label `tail_centered_error_worse_than_constant`; otherwise `within_state_tail_information_not_established`. These are exploratory labels, not generalization success. All other95% intervals are unadjusted descriptive diagnostics; do not count the two primary components as independent confirmations.

Also report fixed-constant minus learned absolute MSE; original, corrected, constant, actual16 and actual-prefix-plus-predicted-tail chosen64 returns/regrets; corrected-minus-original and corrected-minus-constant returns; corrected-versus-original candidate ordering accuracy; original16 prefix MSE; corrected/constant64 forecast MSE and centered64 error benefit; survival minimum/mean/maximum, sequence/constant disagreements and teacher-free cached counts. Regret reduction and chosen-return gain are algebraically duplicate. A positive centered metric does not necessarily imply better top-candidate selection. No favorable secondary result upgrades the closed commitment screen.

## Aggregation and completeness

Average five scoring students inside each decoder/task/visitor, give student-visited and zero-visited states equal weight, and average three tasks equally inside each decoder. Ten independently pretrained decoders provide the ten paired values, t95 critical2.262,df9. Report task/visitor/zero-scoring subsets. Never use candidate pairs, states or student seeds as independent decoder replications. Every planned decoder/task/visitor/context and required finite numeric metric must exist; reject duplicates, booleans, numeric strings, nonfinite values and incomplete source evidence.

Before analysis, validate the complete source capture and parent hashes using its repository-only validator. Check reconstructed corrected-minus-original return against the prior gain16 per-cell values and pooled summary. This is required arithmetic consistency, not a new positive finding. Save new raw metrics and a separate independent arithmetic audit; do not rewrite the parent.

## Budget, freezing and provenance

Local CPU cap120seconds, estimated<30seconds, zero new real interactions and zero imagined transitions, no fitting. The standing session ledger has431.540seconds left before allocation. Bind exact config/protocol/ledger hashes in a new committed allocation; commit implementation/tests before calculating these metrics. Enforce time checks during validation and each analysis cell; save partial results if exceeded. Do not reduce the grid or silently retry. Keep source revision, dirty state, dependencies, runtime, raw input hashes and360 per-context metric cells. No local .pt files are required for this analysis; do not claim a new binary audit.

## Tests and decision limits

Test error decomposition, invariance of centered errors to additive offsets, perfect/reversed/tied rankings, survival-weighted constant selection, research-reference labeling and exact chosen-return/regret identities. Test strict missing-grid/type rejection, equal visitor weighting, source-hash drift, no environment/model calls and reproduction of the closed gain16. Run focused and full regression tests, then an independently coded reward/centered-error calculation.

If value discrimination fails, propose one later targeted calibration/generalization diagnostic rather than increasing network size. If discrimination survives but selection does not, inspect prefix/tail error combination before policy changes. If all measurements remain uncertain, preserve uncertainty. This branch implements no proposed intervention, controller change, control sweep, training, confirmation collection, learning-to-learn or AGI claim.
