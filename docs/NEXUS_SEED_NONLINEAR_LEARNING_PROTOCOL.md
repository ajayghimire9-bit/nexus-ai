# Seed nonlinear-feature learning rule — locked development protocol

Base `cf3f54cebe580a14ec191c48659f79e371cc1b72` verified against GitHub.
Branch `codex/seed-nonlinear-learning-rule`. User explicitly authorized execution
through EXPERIMENTAL mode. No historical evaluation is reopened.

Question: does source-trained context-conditioned plasticity improve the held-out
1/2/4/8-example adaptation curve beyond a source-trained static rule, fixed
protection, stable full-prefix replay and no new-task adaptation? Competing
explanations: contextual update control helps; source-tuning a constant diagonal
is sufficient; none outperform replay; improved MSE fails to improve actions.

## Fixed implementation and data

Reuse ActionReadout.adaptation_features (32 nonlinear units plus bias), the
existing PlasticityController(width=33), correction(), LessonTask, curve(),
scale_features(), Belief and SeedRSSM. No new core/encoder capacity. Readout6301
is the first registered old head, not selected by observed performance. Verify
its hash and the core hash in configs/seed_nonlinear_learning.json. All core,
memory-bank and readout tensors stay exactly frozen. No historical retraining.

Twelve source goal tasks, four development goals, eight final development-audit
goals; exact coordinates and seeds in the executable JSON. They are disjoint by
new-task goal within this outer-learning study. All use a common prior goal(0,0)
for four old anchors and separate retention queries. Previous core/head fitting
may have included all goal coordinates: this is not unseen-world-model physics.
Initial state identities (object position/attributes plus goal) must be fresh
against the three prior study artifacts and disjoint across all new roles and
control resets. Only identities, not old outcomes, influence rejection sampling.

Each task: eight separately reset observed support actions, four old-anchor
actions, three query resets×all9 actions, three retention resets×all9 actions.
Eight support actions cycle `(task_seed//10000 + i) mod9`; same across methods.
Support/query/old/retention collection seeds use offsets100/200/300/400. Half
start near the goal using the existing world_at policy, half arbitrary. Collisions
resample attributes first, then positions, deterministically without outcomes.
Information-reward proxy is off; existing distance/goal reward is unchanged.
Every actual clone.step counts as an authored interaction, including oracle
queries. All records include next proprioception, reward, done/truncated and
float32 feature/label arrays with hashes. Context/recurrent inputs use observed
data only; evaluation futures never enter the model or inner update.

Freeze RMS feature scaling on source support+old rows only. Label units remain
raw reward squared. Therefore primary MSE is **not target-normalized**; all
methods share the same source-feature normalization. At task start every method
receives the same old-anchor ridge residual (.01 damping). "None" means no NEW
task adaptation, not zero residual. Frozen readout is a separate zero-residual
external reference. Fit no preprocessing on development/audit.

## Learners and source budget

Three paired outer seeds6401/6402/6403. Learned rule:165 trainable parameters;
static:33 biases, its context weights frozen exactly zero. Both use identical
initial bias N(0,.01), zero initial context weights, same source task permutation
stream, Adam .01 and exactly64 updates. Outer objective is mean query MSE at
budgets1/2/4/8 plus .5×mean old-task forgetting. Both receive the same source
query/retention labels. No development tuning, architecture search, early
checkpoint choice or gradient clipping. Choose the final update for all seeds.
Different trainable capacity and compute are reported, not called matched FLOPs.
Only source query outcomes train outer parameters. Inner updates never see queries.

Fixed unit protection and curvature-scaled full-prefix replay retain the existing
mathematics; no retuning them from current results. No-adaptation is unchanged.
Save rule weights/checkpoint hashes before collecting audit outcomes. Development
and audit use frozen rules; only standalone residual theta learns support labels.

Primary metric: equal average of query MSE at1,2,4,8 (not trapezoidal AUC).
Average outer seeds inside each of eight audit tasks. Paired Student-t intervals,
df7, across tasks; conditional on one frozen core/readout. Do not count actions,
query states or outer seeds as independently pretrained worlds.

Require >=10% lower mean primary MSE than EACH static/fixed/replay/none baseline,
with each paired error-reduction95% lower bound>0. This is an intersection screen;
individual intervals are exploratory/unadjusted. Forgetting must be no worse
than fixed+.01 raw reward². Report per-budget regret and optimal-action rate.

## Actual control, interpretation and limits

At budget8 only: two fresh paired resets per audit task,20steps maximum. Same
resets and planner seeds for all methods. Three outer seeds averaged inside
tasks. Evaluate learned/static/fixed/replay/none plus unchanged frozen readout,
frozen world, greedy, random, latent MPC references. Theta stays fixed through
episodes, Belief advances once per actual observation. Greedy knows coordinates;
it remains a strong supplied-information reference. No budget-zero/action loss
is hidden by an MSE result.

Non-regression requires learned-minus-static/fixed/replay/none/frozen-readout
return CI lower bounds>=−.1 and mean goal differences>=−.05. Overall screen
requires learning, retention and control checks. Passing remains conditional
development evidence, not general learning-to-learn or broad control. A failure
is retained; do not extend epochs or tune/retest this final audit. No new GUI
policy promotion or historical model replacement follows any result.

## Resource and execution lock

Worst case **7,984 real authored interactions** =24×66 collection+8×2×20×20
control. Maximum **68,208 imagined transitions** and6,192 posterior-prior rows.
Six outer learners×64=384 Adam updates; source support examples3,072;
source query evaluations41,472; source retention evaluations41,472. These are
processing counts, not new environment interactions. Baseline evaluation/replay
work is accounted separately. No cached call is counted as executed simulation.

Allocate≤180 wall seconds,≤180 process CPU seconds,≤12,000 real interactions,
≤100,000 imagined rows,2,048MiB RSS stop threshold; CPU only. On macOS memory
is the existing sampled-RSS watchdog, not a byte-exact kernel limit. Parent
process deadline plus child pre-step/forward checks enforce the smaller cap.
Use existing EXPERIMENTAL Journal, grants, reservation, process group termination
and ledger. No parallel runner/new authorization framework. This is a vetted
registered study adapter, not arbitrary code execution; default MLP isolation
rules remain unchanged. The adapter's trusted internal evaluator owns final
development queries; they are not dispatched to the source-fitting API.

Carry1910.6321034559958seconds used/1689.3678965440042remaining. Debit measured
host wall conservatively by floor(wall)+2; record both actual and conservative
debit. No session reset. Persist progress on failures; no retries under a new ID.
Complete requires every locked seed/task/method/budget/episode and finite metric,
all frozen equalities and exact resource reconstruction. Incomplete is not a
negative scientific finding. Protocol, adapter, tests and config must be clean
and committed before the single run. No reserved confirmation accessed.
