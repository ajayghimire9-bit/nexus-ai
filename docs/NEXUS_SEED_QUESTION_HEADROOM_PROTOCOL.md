# Question-pool headroom — evaluator-only source audit

Branch codex/seed-question-pool-headroom. Starting revision
**2b9bf380f8fbfcf4f74b827202cc3e238db07573**, identical to fetched GitHub.
[Executable configuration](../configs/seed_question_headroom.json).
Commit tested implementation and this protocol BEFORE computing counterfactual
outcomes. One bounded source run, no additional scientific study in this branch.

## Hypotheses and evidence boundary

H-missed: this small teaching pool contains practically useful questions that
the fixed input-variance rule misses. H-pool: useful one-step teaching headroom
is too small, inconsistent across tasks, or not stable across query states.
Both explanations may contribute. Keep all prior negative results closed.

This audit intentionally lets the EVALUATOR compare candidate outcomes using
already inspected SOURCE queries. It does not let an inner learner or runtime
question policy access queries. Oracle selection is an optimistic retrospective
bound, not a deployable learner or unbiased validation. Repeated source reuse
cannot establish learning-to-learn. No new data, neural inference, neural/meta-training,
architecture changes, hyperparameter search or runtime promotion.

## Fixed states and counterfactuals

Verify the previous question-selection artifact, its parent/data hashes, all
source arrays and frozen source-trained constants/normalization. Use the SAME
12 source tasks, four source fitting folds and damping seeds7201/7202/7203.
Do not fit preprocessing or damping again. The original frozen core is never
loaded; all its already saved features and checkpoint evidence remain unchanged.

For each task, use the previous informative rule's recorded order and theta
states immediately BEFORE target budgets1,2,4,8 (prefixes0,1,3,7). These are
fixed reference states, not states reached by a newly optimized oracle policy.
At each state, enumerate every unrequested support candidate:8,7,5,1 choices.
For every damping fit, independently restore the same theta and original
anchor-initialized theta, append ONLY that candidate's support label to the
same observed prefix, compute the SAME cumulative ridge.1 posterior and
apply the SAME frozen scalar damping. Do not chain counterfactual results or
change future reference states. No query/retention tensor enters that update.
Refactor the existing question learner's single-step expression into a shared
helper with exact-equivalence tests; do not add another update algorithm.

Score resulting theta on identical27 query and27 retention rows. Also score
the unchanged pre-update theta (keep). Save theta/proposal, observed indices,
support losses, raw per-query-state MSE, and all scalar errors by task, budget,
candidate and damping seed. The previously selected candidate must reproduce
its old after-update theta and metrics within2e-6. At budget8 the only available
candidate must equal the prior choice; its oracle regret is exactly zero.

## Comparisons and query-state stability

At each task/budget average each candidate's errors across the three damping
fits FIRST. Use one common candidate for those fits. Define:

- variance: the previously fixed informative choice;
- uniform: exact mean error over all remaining candidates, not newly sampled;
- keep: the unchanged current fit;
- query oracle: minimum mean query MSE among the available candidates, ties
  toward the smallest original candidate index. It cannot abstain or use retention
  to pick the winner. Report retention separately.

Original collection code saves three independent authored query starts, each
scored with all nine actions. Verify source record hashes, start seeds, action
order0..8 and disjoint support/query/anchor/retention collection seeds before
using blocks0:9,9:18,18:27. Do not infer episode independence just from feature
hashes. No new seeds are selected or registered here.

Secondary leave-one-query-state-out check: for each of the three blocks, select
the common candidate using only the other two blocks and assess it on the
omitted block. Average the three held-block errors. The omitted outcomes must
not affect that fold's selection. This is cross-state stability within already
inspected SOURCE tasks, not new task/physics validation. These evaluator choices
are never exposed through the runtime selector or a training endpoint.

## Primary contrast and predeclared screens

Per task, average budgets1/2/4/8 with equal weight. Then average the12 tasks.
Primary headroom = variance query MSE minus query-oracle MSE (positive means
questions were missed). Report paired df11 t intervals across12 task clusters
using the existing helper. Damping seeds, candidates, query rows, folds and
budgets are not additional independent core replications. ONE frozen core,
overlapping source fits and reused tasks remain the scope of all intervals.

Query-oracle regret is nonnegative BY CONSTRUCTION. Its interval is descriptive;
a positive value is not independent evidence of generalization. Require ALL
these point-estimate practical screens for label `useful_questions_missed`:

1. Oracle MSE at least5% below variance AND uniform mean MSE.
2. Oracle MSE at least5% below keep mean MSE (not merely less harmful learning).
3. Oracle improves over keep in at least8/12 task-level budget averages.
4. Oracle mean retention MSE no more than variance+.01 over those budgets.

If the screen fails, label `practical_headroom_not_demonstrated`, not proof that
no useful example exists. Independently report secondary cross-state screen:
held-block selection error at least5% below variance AND keep, with positive
improvement over keep in8/12 tasks and retention no worse than variance+.01.
Report paired intervals for both advantages, but do not turn them into separate
confirmations. This secondary screen cannot upgrade a failed primary label.
Report both outcomes regardless of direction, all tasks, all budgets, candidate
heterogeneity, harmful-question fractions, and variance-chosen gain versus
keep. Do not rank next methods or change thresholds after reading results.

## Execution, completeness and accounting

756 counterfactual inner updates =12 tasks x3 fits x(8+7+5+1).900 evaluated
theta states including144 keep states;24300 cached query and24300 retention
rows.756 cumulative solves,1800 support-row and3024 anchor-row presentations.
No new initialization solves;324 prior snapshots are reused, not rerun.
No new question-rule variance solves.96 unique saved teaching labels,0 outer
updates,0 world-model calls,0 real or imagined transitions. Fit, assessment and
analysis time are separate from total host time; hash verification is a
read-only preflight audit, not environment collection. Validate before declaring
completion. Reject omitted tasks/budgets/candidates/seeds/query blocks, invalid
numeric types, nonfinite/missing metrics, changed snapshots and incorrect math.

Same EXPERIMENTAL host/worker, one-use manifest and ledger. CPU/wall30seconds,
sampled RSS2048MiB, zero-interaction allocation under the human standing grant.
Carry **1948.6321034559958s used /1651.3678965440042s remaining**. Enforce caps,
debit actual execution plus the established conservative dispatch rounding, and
preserve partial/invalid captures. Never retry a consumed run silently.

Test synthetic helpful and harmful pools, identical restores, fixed-learner
equivalence, candidate permutation/ties, future-label/query poisoning, cross-
block selection isolation, exact aggregation, expected-grid completeness,
hashes, frozen-state preservation and GUI read-only behavior. Independently
recompute saved arithmetic with stdlib only; preserve all historical artifacts.
Results are separate JSON/report/commit. GUI must say evaluator-only oracle,
never present its selected answers as an agent capability.

One next decision: if headroom and cross-state stability exist, propose a
task-blocked source question-utility learner with permitted meta-training
feedback and simple baselines. Otherwise diagnose pool/utility instability
before adding capacity. No such learner or additional experiment here.
