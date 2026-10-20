# Seed mechanism isolation and fresh learning validation — protocol v1

Base8d0218176307eb1cf119d54d82272c7cabd9c177;branch
codex/seed-mechanism-isolation. Local/remote matched at start;clean research
worktree. Original checkout's two unrelated untracked Evolution files untouched.
No prior result,checkpoint or closed split is changed. Existing source-only
plasticity study stays failed:0.36%versus10%screen. New tasks,not a retry on its
audit. Read master/canonical/reuse/registry/current Seed reports before design.

## Mechanism contracts (correctness,not scientific outcomes)

SAME AdaptiveState/Session/E1 journal/SeedRSSM/Belief/OuterSeedMeta remain.
Repair changes shared parameters only,retaining all scopes. Addition creates
a NEW scope only;an existing scope cannot be replaced. It algebraically leaves
other contexts unchanged. Merge absorbs a scope without fitting and rebases
other existing scopes;it must preserve current-scope and known other-anchor
predictions to1e−5. Reject conflicting merge. Repair has the same finite-anchor
drift gate. Neither promises preservation on every unobserved context.

Keep is a candidate. Shared criterion is final reserved-development MSE plus
fit/storage cost;no misleading comparison of a repair learning curve with
keep's final error. Repair/add need at least.01error reduction;merge may keep
equal error and reduce canonical storage. Cache reviews under post-edit
parameters+same evidence. No new fits or promotions on repeated identical
review. Last four edits reversible if no subsequent learning changed parameters;
rollback never erases observations or refunds work. v2state metadata;legacy v1
loads without inventing prior edit history. GUI rollback remains owner-enabled.

## Fresh hypotheses and gates

H-learning:learned plasticity lowers held-out teaching-curve MSE after1,2,4,8
examples versus fixed D=I protection,feature-scaled replay and no adaptation,
without greater forgetting. Null:failure against any comparator.

H-actions:the learned reward adapter improves nine-action ranking AND paired
closed-loop goal completion versus the frozen neural model and fixed protection.
Numerical loss decrease alone cannot satisfy it. Known-grid greedy is an external
strong controller reference with supplied rules,not a learned same-model method.

Language and selector studies are separately labeled development diagnostics;
they cannot upgrade a failed primary gate. Cross-domain testing is conditional
on BOTH object-world gates,not merely a functioning implementation.

## Executable configuration and data

Single config configs/seed_learning_validation.json. Fixed parent
seed_contract_gui.json SHA cfe06a6737c8e225564ebcaea9ba4678aabd45b61129828e64354e74fa3c8d1b.
GRU,heads,source bank and normalization frozen. Three NEW310-parameter controller
fits,optimizer seeds6201/6202/6203;neutral initialization,Adam.01,64updates,
no checkpoint search. Historical controller/core files never modified.

Eight train,eight development,eight audit task-stream seeds registered in JSON,
spaced10000apart. Each draws a goal and an old goal without scoring outcomes.
Offsets100..107:8new selected-action teaching examples;200..203:4old examples;
300..302:3query states with all9true outcomes;400..402:3old retention states
with all9outcomes. Half teaching starts near goal,half arbitrary;selected
actions cycle(seed+i)mod9. All truth outcomes evaluator-only except selected
support/old labels. No unbudgeted all-action teacher. Cache identical query truth
across methods. Inputs:only current observation,goal,action,frozen h/z.

Feature RMS fitted on train support+old rows only,floor.01,divide by sqrt62;
same scale all methods,never target/query-fitted. Initial residual fits permitted
old4 via ridge.01,common to learned/fixed/replay/no-adaptation. No adaptation
means retaining that starting adapter. A separate frozen-neural control uses
zero residual,not the old-data-initialized no-adaptation baseline.

At each teaching example,fixed/learned use SAME precision update with old4
anchors,lambda9,epsilon.01. Replay makes one full permitted-prefix+old4 gradient
step,.5/trace(H),safe for linear squared error;not the earlier unstable.2rule.
Support/query/retention examples and additional replay computation are logged.
Outer objective is mean query MSE at1/2/4/8 plus.5positive retention degradation
on TRAIN tasks only. Development reports only;final64 is fixed before outcomes.
Audit labels never fit controller,local weights,normalizer or checkpoint selection.

Additional ablation:neutral untrained diagonal D=1.025,matching the controller's
initial state. Report it in prediction curves to isolate learning from simply
changing the update scale. It reuses cached data and adds no environment steps.
Learning screen:mean audit MSE at those four budgets at least10%below ALLfour
baselines;paired interval lower bound above0for each error reduction;mean
forgetting<=fixed+.01. Episodes/goals aggregate inside each registered stream,
then three controller seeds averaged within it. n8fresh task-stream units,
Student-t95%,df7(t2.364624251),conditional on ONE frozen core. Not eight or
three independently pretrained world models. Multiple exploratory comparisons;
no multiplicity-adjusted generalization claim. These are practical development
screens. Report per-budget/per-task/seed results even on failure.

## Actions

After8teaching examples,freeze each adapter. Same fresh reset seeds task+1000..1003,
12steps maximum,each method gets9one-step neural candidate scores/decision.
Methods learned/fixed/replay/no-adaptation ×3controllers,plus cached frozen
neural and known-grid reference. SAME frozen core/observation contract/reward,
no online updates or outcomes leaking into action scores. This is explicitly
one-step adapter control,not a retuning of the unchanged latent H4/H16 planners.
Count each actually executed episode once;identical method replications are
not independent world-model units. Success requires>=10%lower action regret,
>=.10greater goal fraction versus BOTH fixed/frozen,and positive paired return
interval lower bounds versus BOTH. Known-grid need not be beaten,but is reported.

## Few-example semantics: separate diagnostic

Six unary predicates from SAME37-program catalogue;six explicit relational
primitives(left/right/above/below/same color/same shape). New words and objects;
8support/10query examples per lesson. Same53-dimensional frozen encoding with
observable partner geometry/equality fields for relational inputs,no target
program ID. All four numeric learners plus full symbolic consistency at1/2/4/8.
Symbolic abstention counts as no correct answer,reported separately. Equal
teaching-label budgets;search/neural costs differ and are disclosed. Catalogue,
relational primitives and geometry fields are supplied,not invented by Seed.

Instruction check:four invented verb→primitive bindings inferred from observed
displacements,1/2/4/8examples per word,held-out objects and "please ... the ...
then ..." compositions. Use SAME Move executor. Syntax and candidate directions
supplied. Neural per-word direction heads,not the deployed shared semantic block;
unlabelled query observations pooled for inference,no query outcome used.
One unique direction answer/word is repeated over eight objects;32maximum
demonstrations cached across controllers. Symbolic displacement learner can
already infer that binding after one example. This is not arbitrary language,
new primitives or evidence of fewer examples than the symbolic learner.

## Autonomous learning-action selection: separate diagnostic

Reuse SAME OuterSeedMeta/EpsilonGreedyController,not a second meta-framework.
12source unary tasks train choices;8different tasks assess. Actions:ask actual
label,test concept(reserve actual label),repair,add scope,keep/stop. Feasibility
and cost checks fixed. Each decision pays one fresh revealed probe. Probe
gain/(labels+.1local-update count) updates policy ONLYon source tasks;final
two hidden query rows never available to proposer or updater. Assessment policy
frozen. Adaptive/random/always-ask share8decision/16label caps,not identical
spent compute. Unused allocation,early stops and fit counts reported;not free
repeated oracle access. Score final MSE and improvement per actual cost;require
no worse final MSE AND>=10%better efficiency than both baselines to call useful.
This tiny-bandit selection is not an unrestricted autonomous scientist.

## Transfer gate

Only if both registered object gates pass,freeze rule/checkpoints and evaluate
seven fixed new list-permutation tasks from JSON,1/2/4/8examples. Same62-dimensional
update interface,padded observed list coordinates,three scalar output heads,
no rule retuning. Otherwise record NOT_RUN_OBJECT_SUCCESS_GATE_FAILED;do not
call this an incomplete run or claim transfer. Unit fixtures may validate the
interface regardless,without scientific evaluation.

## Bounds,provenance and stopping

CPU180seconds;maximum12000new authored interactions INCLUDING teaching/query
oracle labels and control steps;maximum100000imagined action rows. Standing
Worst-case source-only derivation,without early-goal assumptions:6960world
steps plus720supervised answers(including conditional list phase)=7680total;
48816imagined action rows. Encoder and posterior-prior work counted separately.
human authority2026-10-16;carried ledger1895.6321034559958used /
1704.3678965440042remaining. Do not reset budget. Record ceil command debit
plus startup allowance. Body check before each model/fit/episode stage;stop
and save partial/invalid result with exact costs. No silent seed reduction,
retuning,restart or additional run on same registered data.

Commit tested protocol+implementation before outcomes. Save raw traces,fresh
registrations,query truths,predictions,scaler,controller weights/hashes,source
revision,resource counters and gates. Verify parent weights/bank and historical
artifacts. Distinguish source development from untouched confirmation. No Gym
physics,old holdouts,H12–H17 reruns,paid compute,main merge or arbitrary code
evolution. Preserve negative outcomes. Tests for query isolation,stable replay,
exact operations/rollback/caching/legacy state,paired seeds,frozen core,
complete expected grids and transfer blocking precede execution.
