# Source-trained question acquisition — locked development pilot

Base4bd8f381e80eddeae88299ecc0c382cec4409387, matching fetched GitHub.
Branch codex/seed-source-question-acquisition. Previous negative studies remain
closed. No historical neural weights, live policy or main changes.

## Hypothesis and scope

A small source-trained, pre-answer utility predictor may choose useful teaching
examples on excluded task programs with a fixed learner. Unlike the preceding
full-signature benchmark, targets receive at most8 of16 possible input labels;
final prediction uses the other8 inputs. This is one supplied finite Boolean
program family, not unrestricted concept discovery, control or AGI. A new linear
selector fit is not neural retraining or proof of general learning-to-learn.

Separate two questions: (A) useful transfer beyond simple query policies and
(B) superiority beyond stronger source-informed and model-based selection.
Do not relabel A as B, or declare success just because the code fits a model.

## Registered tasks, supplied prior and source-only supervision

Executable [config](../configs/seed_source_acquisition.json), exact validation.
Catalogue:910 unique executable4-bit Boolean functions. Four inputs a/b/c/d;
14 distinct monomials (AND of1–3 variables). A function is XOR of TWO or THREE
different monomials, optionally negated. Use foundation.programs' existing
and/not/eq interpreter, not eval or a new symbolic engine. Enumerate monomials
by degree then lexicographically; combinations by term count then order;
nonnegated before negated. Its full truth tables are a SUPPLIED hypothesis
class available to all methods, not learned world models or target identities.
Record catalogue hash and all executed interpreter instructions.

Eight independently fitted source selectors; seeds1745000001–1745000008.
Assignment RNG1745000900 shuffles each of four groups (2-term/nonnegated,
2-term/negated,3-term/nonnegated,3-term/negated). For each repetition draw16
source functions with counts6/6/2/2, then8 target functions with counts3/3/1/1;
remove draws from the global lists. All192 source/target functions are distinct,
including across repetitions. No old response table or question bank is reused.
This biased term-count mixture is explicit; do not call it unknown universal
function sampling. Sign and family strata are not selector inputs.

Source IDs1745100000–1745100127,16 per repetition. Collect16 labels each.
Target IDs1745200000–1745200063,8 per repetition. For every task, shuffle input
indices0..15 with RNG(task+200000); sorted first8 are the teaching pool, other8
the final query inputs. No pool/query input or record overlap. Target rule
indices are evaluator-only. Source labels may identify a function for permitted
source supervision; target identities never enter features, fitting or choices.
Query INPUTS/distribution are public to all policies; query LABELS are hidden.

Source training uses one fixed shuffled support order (RNGtask+700) per task.
At prefixes0..7 construct every remaining candidate's ten features BEFORE its
source label is used. Label is source query MSE before minus after one reveal
and the fixed update. Total4608 supervised utility cases. Reuse nn.ridge with
fixed regularization1.0 and its training-only RMS scaling, one10-coefficient
model per repetition. No hyperparameter search, architecture changes or target
cases in fitting. Source prefixes are random, not learned-policy roll-ins;
distribution mismatch is a disclosed limitation, not permission to refit later.

Ten features, fixed order: intercept; four input bits; current candidate
prediction; prediction variance p(1-p); minimum normalized Hamming distance to
observed inputs (1 if none); observed positive-label fraction (.5 if none);
remaining-pool fraction. No hidden candidate answer, evaluator identity, future
updated model, query outcome or retention outcome. Normalization and ridge fit
use only that repetition's source cases.

## Fixed learner and eight comparisons

The learner always maintains the SAME uniform version space over910 supplied
functions, filtered only by observed teaching labels. Predict by uniform mean.
Never change its prior, hypothesis class or update rule between methods.
All source-fitted acquisition models freeze BEFORE any target observations;
all64 target acquisition paths lock BEFORE final query labels are collected.

1. Learned ridge utility, argmax predicted gain, lowest pool-index tie break.
2. Candidate prediction variance, same tie break.
3. Model-based expected query-MSE improvement under the uniform version space.
4. Source-informed expected query-MSE improvement: source labels identify each
   SOURCE function; fit counts over the four programme groups, Laplace+1 per
   group, then uniform weight inside each group. Condition those weights on the
   observed prefix. Expected losses use the unchanged UNIFORM learner's before/
   after predictions. This is a strong simple source-trained acquisition control,
   not a privileged teacher or a different target learner.
5. Source-static order: mean source utility by input, global mean if unobserved.
6. Original sorted teaching-pool order.
7. Exact uniform-random expectation: evaluator averages loss over all subsets
   of each budget. There are8/28/70/1 subsets at1/2/4/8. Since the learner depends
   only on the observed set, these equal random-permutation marginal means.
   This has more assessment compute, not more actually collected labels.
8. Keep/no teaching, uniform prior prediction at all budgets.

Each executable policy reveals8 unique labels through the existing LabelOracle.
Record scores BEFORE reveal, answers, posteriors and snapshots1/2/4/8. At8 all
non-keep methods must yield identical final learner predictions/loss, including
uniform expectation. Eight is secondary: it cannot show acquisition superiority.

## Endpoints and locked screens

Primary: mean final query MSE across budgets1/2/4; average8 targets INSIDE each
source-trained selector repetition, then equal-weight eight repetitions. Report
all budgets, task-level results, source fits, coefficients, scales, and costs.
Paired exploratory95% t intervals across8 fitted selectors (df7,t2.364624251).
They share one finite catalogue/learner and without-replacement task allocation;
they are not independent world-model replications or broad confirmation. Do
not treat input labels, utility cases or64 target tasks as training replicates.

Heuristic-transfer screen requires at least5% lower primary MSE than EACH of
variance, source-static, original-order, uniform expectation and keep; positive
paired interval lower bound versus variance; wins in at least6/8 repetitions;
and no more than.005 absolute MSE disadvantage versus EACH model-based method.
Strong-advantage screen separately requires at least5% lower MSE AND positive
paired interval lower bounds versus BOTH model-based and source-prior controls.
No automatic promotion even if either passes. Model fitting, low training loss
or beating random alone cannot pass. Missing/nonfinite cells are invalid;
complete negative results remain failures. No post-result threshold changes.

## Budgets, costs and integrity

Hard cap60s CPU/wall,4000 authored labels,2048MiB sampled RSS, CPU only.
Planned collection3072:2048 source labels +512 target support +512 final labels.
Pools are collected fully for pairing, so policy label exposures do not prove
lower actual collection. Eight new ridge fits, no neural updates/forwards,
simulator collection or imagined world-model transitions. The host's updates
counter means eight numerical selector fits here. Parameter count10/selector,
plus10 source-derived scaling values; static/prior state reported separately.

Record all source utility construction and fit work, target score/update work,
exact-uniform subset work, public programme executions, CPU/wall/RSS. Matrix
entries materialized by indexed reads and logical feature/scorer counts are
proxies, not FLOPs or complete CPU instructions. Counterfactuals reuse source
labels; do not call them new collection. Source-static does not require ridge
features or solve; source-prior requires source identity/group work but not
utility case generation. Report those splits instead of charging every method
the learned selector's complete fitting cost. Host source-only reconstruction
and cached assessment validation are engineering checks included in host wall;
independent post-run tests/GUI verification are separate.

Carry1990.6321034559958s used /1609.3678965440042s remaining; debit
ceil(host wall)+1 via existing Sandbox/E1 journal. No ledger reset, automatic
retry, target-driven tuning, extra fits or follow-up sweep. Save partial data
and costs on caps/failure. Register numeric IDs and offsets against the frozen
JSON/YAML config registry; document coverage limits for implicit external runs.
Hash both old neural JSON checkpoints before/after and every frozen source fit.

Commit protocol/config/tested implementation before one run. Tests use known
toy tables, not registered task outcomes: answer-free feature/choice invariance,
source/target separation, source-only scaling, fixed-learner consistency,
exact uniform expectation, independent expected-risk arithmetic, complete grid,
label budgets, frozen hashes and numerical aggregation. Verify saved arithmetic
independently after the run; the GUI validates that saved audit's raw-result hash
and displays its receipt without numerical refits. The explicit verifier still
requires the existing NumPy dependency (`nexus-ai[seed]` or the workspace's
installed dependency path). Update GUI and current documents; commit
results separately and push without merging main. No next experiment in this
branch, regardless of whether the predictor passes or fails.
