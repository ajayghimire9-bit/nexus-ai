# Next Seed learning-to-learn test: nonlinear features, existing update rule

Status: implementation-ready scientific proposal,NOT registered or executed.
No new scientific teacher labels,task seeds or allocations are created here.
The spatial transfer screen passed against frozen ranking; greedy remains
stronger and cross-diagonal control remains weak. Do not tune on that sample.

## Falsifiable question

Does learning a small context-conditioned update procedure across source tasks
reduce the1/2/4/8-example held-out adaptation error more than source-tuned static
protection,stable replay and no adaptation,while preserving old-task knowledge
and improving action decisions? A useful frozen action scorer is not this result.

## Existing code to reuse

ActionReadout.adaptation_features exposes its frozen32-dimensional nonlinear
state/action basis plus a bias. No new encoder or GRU capacity is added.
ActionReadout.adapted_scores accepts a standalone33-dimensional residual.
At zero residual scores equal the old frozen path. No adapter is installed in
GUI rank(); no historical head is trained or overwritten.

PlasticityController(width=33),context(),correction(),LessonTask,
learning_benchmark.update/curve/scale_features already support these dimensions.
Use those APIs,not another optimizer/memory framework. Query labels may train
the outer controller on SOURCE tasks only. Inner updates accept teaching rows
and permitted old anchors,never query outcomes.

## Proposed controlled design

Fresh authored goal/task streams disjoint by registration and initial-state
identity from previous learning/readout/transfer audits. Source/development/final
roles must be frozen before collection. Choose a shared method-independent
teaching action sequence; eight observed action outcomes per task. Hold query
states/actions and old-task retention episodes separate. Freeze feature scaling
from source teaching/old-anchor rows only. Do not normalize on audit data.

Compare context-conditioned learned positive diagonal,source-trained STATIC
positive diagonal,unit fixed protection,curvature-scaled full-prefix replay and
no adaptation. The static learned diagonal is crucial: improving fixed default
parameters is not evidence of context-dependent learning-to-learn.
Use identical initial residual,source data,teaching prefixes and old anchors.
Report update/example/wall costs. Tune no method on final queries.

Use at least3 independently initialized outer learners and8 final task streams,
averaging outer seeds inside tasks; all share one core and cannot establish
independent pretrained-model generalization. A later replication across new
cores is separate. Predeclare matched source optimization/tuning opportunities
and one common final checkpoint. Preserve earlier failed plasticity models.

Primary screen proposed: >=10% lower mean normalized prediction-learning-curve
MSE than ALL strong baselines,positive paired task-level95% error-reduction
intervals,and forgetting no worse than fixed+.01. Primary comparisons form an
intersection screen; report exploratory unadjusted intervals explicitly. Actual
action-regret and fresh closed-loop return/goal checks must accompany error
metrics. Specify a non-regression margin before execution. No claim of useful
learning-to-learn if error improves but decisions or retention fail.

## Bounds and remaining work

Propose <=20,000 authored steps,<=200,000 imagined rows,<=180 CPU seconds,
within remaining standing authority. These are estimates,not an allocation.
Before execution:freeze exact task/seeds/sampling rules and method tuning
budgets;derive worst-case totals;bind the new feature projection into existing
collection;test source/query isolation and complete grids;commit the executable
protocol. Only then collect once. No indefinite epoch extensions,automatic
rank-four adapter or change to evaluation rules follows a failure.
