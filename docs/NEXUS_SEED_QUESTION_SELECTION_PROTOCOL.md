# Fixed-learner question selection — locked source exploration

Starting branch codex/seed-shared-learning-labs at
1bf505c0415c5c2b8dd0a9dbfcac511f283ec4e3, matching fetched GitHub.
New branch: codex/seed-informative-questions. The executable configuration is
[seed_question_selection.json](../configs/seed_question_selection.json).
Commit this protocol and tested code before scoring. Run once through the
existing owner-controlled EXPERIMENTAL host; preserve partial/invalid attempts.

## Question and competing explanations

H-question: input-only information selection reduces mean query MSE after
1,2,4,8 labels versus random questions with the SAME frozen constant-damping
learner. Null: this input geometry provides no useful teaching advantage, or
selects unrepresentative/high-noise examples. A gain would support label choice
on this source bank, not a learned question policy or learning-to-learn.

The previous learn/ask/retain study failed and merely deferred labels. This
study changes only their order. It uses the 12 existing SOURCE tasks, not new
validation or the finite symbolic lab task catalogue. All old outcomes remain
closed. No worlds, neural inference, training or checkpoint changes.

## Data and learner fixed in advance

Verify the previous sequential artifact hash, its source-parent hashes, all
source array hashes, source-only fold scales and 12 constant checkpoint hashes.
Use its four task-blocked folds: nine fitting tasks, three excluded tasks. Use
only the excluded tasks for this comparison. Existing source arrays contain
eight teaching candidates, four initialization anchors, 27 query rows and 27
hidden retention rows per task. Query/retention rows never enter selection or
fitting. Their already inspected status makes this exploratory source reuse.

The unlabeled pool is exactly the eight old support_x rows. Only a requested
row's support_y is revealed. No replacement or new labels. Report pool hashes
and revealed indices. An oracle adapter owns labels; the selector receives
only normalized candidate inputs, anchor inputs and selected indices. All
methods receive the same four labeled old-task anchors. These are outside the
new-example budget and are disclosed separately. Check row identities and
do not falsely claim simulator-episode independence from feature hashes.

Freeze the source-only scale and three source-trained scalar damping fits per
fold (7201/7202/7203). Initialize theta from anchors by existing ridge .01.
At every reveal, compute the existing cumulative ridge .1 proposal, centered
on the initial fit, using all revealed rows plus anchors. Apply the unchanged
theta <- theta + g*(proposal-theta). Keep original float32 learner arithmetic.
No gate fitting, clipping, hyperparameter selection or live promotion.

## Selectors

Informative: deterministic maximum linear posterior input variance with ridge
.1 and unit prior precision. For observed input matrix X (anchors plus revealed
inputs), score each unqueried x by
v(x) = (x.x - (Xx)'(.1 I + XX')^-1(Xx))/.1.
Compute scores in float64, clamp only numerical negatives within 1e-8 to zero,
fail on other invalid values, choose the first maximum in original row order.
This is a fixed information heuristic, not calibrated outcome uncertainty.
No label, query input, teacher answer or hidden retention is needed.

Random: ten permutations per task, Python Random(question_seed + task_id).
Use the registered seeds8101..8110; average these and damping fits INSIDE tasks.
Original-order: indices0..7, a replication reference using the same learner.
The informative/original orders do not depend on damping seed or outcomes.
Precompute orders once per task; evaluating cannot change later choices.

Equal new labels and learner update counts per trajectory; all share the same
60-second/2048-MiB cap. Random choice is cheaper. Disclose the extra variance
solves rather than claiming equal FLOPs. Ten random permutations are Monte
Carlo integration, not ten independent pretrained models.

## Metrics, aggregation and decision

Primary per-task value: mean query MSE at1/2/4/8 labels, first averaging the
three damping fits and, for random, ten orders. Average the12 task values with
equal weights. Positive contrast = random minus informative error. Use the
existing paired t interval with df11; it is descriptive and conditional on ONE
frozen core, overlapping source fits and repeatedly inspected source tasks.
No seed/order/row is an additional pretrained-core replicate. One primary
comparison; all budget/fold/retention intervals are unadjusted exploratory.

Source screen requires all: at least5% lower primary MSE than random, paired
95% lower bound>0, informative wins at least3/4 fold means, final hidden retention
MSE at most random+.01. Failed screen is negative/inconclusive evidence, never
invalid execution. Missing cells/nonfinite values/provenance errors invalidate
execution, not the hypothesis. Report all task/budget errors, forgetting from
budget0, exact label schedules, theta snapshots, support residuals, work counts
and selection/fit/evaluation wall time. Original-order trajectories must match
all previous constant-damping snapshots within2e-6. All8 labels are eventually
the same; at budget8 only damping/order effects can differ. Low-budget curves
are correlated, not independent replications. No control-performance claim.

## Bounds and independent audit

432 trajectories (12 tasks x3 fits x[1+10+1 orders]),3456 inner updates,
3888 evaluation snapshots. Score104976 cached query rows and104976 retention
rows; these are arithmetic reuse, not executed environment interactions.
96 selection solves/768 candidate variance scores (432 still-available scores),3456 cumulative solves,
432 anchor solves. No outer updates, model forwards, imagined or real steps.
Wall/CPU60seconds, sampled RSS2048MiB through the SAME host; stop/save on cap.
Carried session1943.6321034559958 used /1656.3678965440042 remaining.
Debit actual host execution plus the existing conservative whole-second charge.

Before execution test oracle budget/duplicate checks, future/query poisoning,
label-independent orders, fixed learner equivalence, exact replay, complete grids,
finite types, correct intervals, hashes and zero-label reproducibility on toy
arrays. Independently verify saved source arithmetic and summaries without fitting,
worlds or neural imports. GUI replays recorded results; it cannot execute the
study or silently enable a live question policy. Preserve old artifacts bytewise.

One next decision only: if useful, separately validate the frozen selector on
new tasks; otherwise investigate pool coverage before expanding learner capacity.
