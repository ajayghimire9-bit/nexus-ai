# E3.12B — Balanced operator headroom, locked development protocol v1

Base ed89b49547f39f787387192036268fef60eca0ef, verified against GitHub after
fetch. Branch codex/e3-12b-paired-operator-headroom. Preserve all earlier results,
closed seeds and the two unrelated untracked evolution1 adapter files.

## Competing hypotheses

H-stable: training feedback identifies a mutation operator whose fresh-episode
return beats equal-probability operator choice. H-variable: useful differences
exist but reverse across resets, preventing a model-specific constant choice.
H-credit: return saturation/cost normalization selects differently from a simple
raw-return mean. H-small: these operators have little decision-quality headroom.
These may coexist. E3.12's changed probabilities but identical sampled choices
do not settle any of them. This follow-up uses new episodes, no retuning of
closed E3.12 outcomes and no architecture changes.

## Immutable mechanics and reuse

Use the SAME four frozen source residual MLP64x64 checkpoints, normalization,
source physics and reward functions pinned in E3.9 inventory. All four checkpoints
and eight source arrays must hash-match before/after. No neural fitting, new
physics, support/probe collection, reserved confirmation or H17 activity.

Reuse existing StrategyGenerator's mean structural mutation credit and
measured_mutation bridge, generated_strategies.execute, full_policy_source
controllers/operation_plan, TaskSpec wrappers, post_probe Host/Dispatch,
ForwardCheckedStep, DecisionJournal and ReservationLedger. New operator_headroom
is pure data-boundary/statistics glue; SAME runner adds --operator-headroom.
No replacement/parallel learner, memory, planner or meter.

For every context execute three complete paired200-step policies: fixed parent
(successor H16 anchor), switch(parent,flat H16 anchor,threshold.25), canonical
rank_blend(parent,flat H16 anchor). Each starts from an exact simulator/RNG/
time-limit restoration and uses identical per-tick planning seeds. The two
operators are existing executable grammar, not newly invented algorithms.
Planner H16 and1536 imagined-row per-decision upper budget are unchanged. This
catalogue-budget planner is not historical16-candidate-controller parity.

All three paths are executed once, regardless of selector decisions. This
balanced full-information study measures selection headroom and transfer of a
simple learned preference; it does not measure bandit sample efficiency. The
parent path is shared for both paired credits and counted physically once.
Bridge pair IDs include operator kind, documenting two legitimate uses of the
same parent receipt; no duplicate physical-evaluation claim. Each child is
independently evaluated, never a forecast or uncharged duplicate.

## Training, frozen choices and baselines

Per model, collect eight training contexts, evaluate BOTH children, and update
the existing structural-credit mean after each matched pair. Credit remains
tanh((child_return-parent_return)/100)/(1+parent_CPU_s+child_CPU_s); no rule,
temperature, exploration or return scale tuning. Update order switch then
rank_blend; record measured CPU values for deterministic replay. CPU costs
include receipt/capture overhead; timing sensitivity remains a limitation.

Primary selector: choose the operator with larger mean **observed training
return** across eight paired training resets, frozen for all four query episodes.
This is a strong simple model-specific baseline, not another neural predictor.
Secondary selector: argmax of existing final structural-credit probabilities,
also frozen. Exact ties choose switch. Record both choices, full training means,
credit probabilities and training-feedback hash BEFORE query path evaluation.
Query outcomes never update either selector or choose checkpoints.

Query comparisons: training-mean, credit-argmax, fixed switch, fixed rank-blend,
fixed parent, equal-probability uniform-expected return and retrospective best
of the two operators. Uniform expected return is arithmetic mean of the two
executed paired returns, **not** another executed controller or episode. Best
is an explicitly hindsight diagnostic upper reference, unavailable to selectors.
No selection using query labels; predicted scores are never treated as rewards.

## Fresh registration and resource allocation

Executable source of truth configs/e3_12b_operator_headroom.json. Eight training
episodes0..7 and query8..11 for each source family/model. For family index f,
model b, episode e: offset=f*100000+b*20000+e*1000. Reset seed2161000000+offset;
planner seed2162000000+offset+tick, tick0..199. No RNG draws for proposal choice.
The retained proposal_seed73512 initializes existing empty credit state only.
Audit all9648 identifiers against available artifact/config metadata, original
source-array seeds and conservative H17 reservations. Missing external history
is not claimed covered. E3.11/11B/11D/12 cases remain closed.

Four source models, twelve contexts each, three paths/context,200 steps/path:
144 physical episodes and28,800 real transitions. Training19,200, query9,600.
No validation/support/probe/diagnostic interactions beyond these paths. Cap
44,236,800 imagined rows and1,440,000 calls/forwards. Actual work logged by
pre-call tickets and checked forward hooks, separately from logical reuse.
Matched opportunities/caps are not matched FLOPs; operator counts may differ.

One run, local single-thread CPU, **450-second hard cap** (estimated200–260s
from closed E3.12 measurements), no automatic retry. Standing2026-10-16 grant,
carried session1276.541573125001s used/2323.458426874999s remaining. Enforce the
smaller cap and remaining allowance. Commit exact config/protocol/allocation
hashes and tested code before outcomes. Timeout/failure saves partial results
with unreported-work upper bounds, never a complete negative scientific label.

## Prespecified primary analysis and labels

Within each model average the four query episode returns, then compute primary
training-mean minus uniform-expected. Analyze families separately using the TWO
independent pretrained source models per family. Exploratory95% paired t interval
df1, critical12.7062047364. Never pool families as interchangeable replicates
or count episodes, operators or reused parent paths as independent models.
All intervals unadjusted exploratory. Report each model and every episode.

Selection screen requires BOTH families: mean primary gain>=1 point, both model
gains>0, and interval entirely above0. Otherwise selection remains unestablished.
Finite-suite headroom screen: mean hindsight-best minus uniform-expected>=5
points in BOTH families. This does not establish learnability or an executable
oracle controller. If selection passes label exploratory_training_mean_selection_
screen_passed; else if headroom passes label headroom_visible_selection_not_
established; otherwise stable_operator_selection_not_established. Do not upgrade
the primary result because a secondary credit comparison happens to pass.

Report credit-minus-uniform and credit-minus-training-mean; selectors against
parent/fixed operators; sign stability of switch-minus-blend across training
and query; hindsight regret and winner rate. Hindsight-best minus uniform is
exactly half the absolute paired operator gap; regret reductions and winner
rates are related diagnostics, not independent scientific replications.

## Correctness and interpretation

Require exact config-derived seed/model/role/condition grids;200 finite contiguous
transitions per path; correct rewards/termination/tick seeds/restoration; recorded
choices reconstruct only from complete training data; no query updates; frozen
models/normalization; observed forwards and raw journal resource sums reconcile.
Preserve all historical JSON by byte hash, with no silent skipped integrity
checks. Tests use pure callbacks/authored transitions, no scientific environments
or model inference. Independent saved-data audit is separate from collection.

If stable training means help but the credit rule does not, investigate the
credit transformation as a separate future intervention. If hindsight headroom
exists without stable selection, investigate context-dependent operator quality
rather than increasing architecture automatically. If little headroom exists,
do not claim the learning system failed to exploit useful information. No
general control, continual-learning, learning-to-learn or AGI claim. Commit
results separately, push the branch, keep main and previous artifacts unchanged.
