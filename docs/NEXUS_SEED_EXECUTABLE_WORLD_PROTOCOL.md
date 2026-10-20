# Executable world model — source-development protocol v1

Status at registration: implementation/testing; outcomes not collected. Starting
revision `e381132c79a2d3c71aed883e54b8577ecd0071ec`, newer than the owner's
reviewed `9080b075`. Branch `codex/seed-executable-world-model`. Main unchanged.

## Question and scope

Can a finite history-feature constructor reduce prediction ambiguity when the
initial explicit state omits an observable history dependency? Competing causes:
missing history, temporal order, noisy observations, and unavailable information.
This new owner-requested architecture is NOT justified by the earlier failed
question selectors; those results and their unrun label-reliability audit remain
closed/separate. No control, unrestricted reasoning, AGI or learning-to-learn claim.

## Owners reused before extending

Session/core.py, E1 Journal and storage.py own evidence and persistence;
lab.py owns requests. skill_programs.run owns compatible programs, nn.factory
owns neural construction, nn.ridge owns regression, experimental.py/worker own
allocation, CPU/RSS supervision, immutable attempts and carried ledger. No second
memory database or evolution controller. Graph scalar-effect composition cannot
be expressed by grid-only planning.to_cell; structure.mechanisms.plan is a small
bounded backend, not a replacement for RandomShootingMPC. SeedRSSM/Belief and
frozen readout remain unchanged. A NEW GRU32 baseline is trained on compatible
history tokens rather than comparing against an incompatible frozen sensor net.

## Exact suite and split (single executable config)

`configs/seed_executable_world.json` is checked against locked runtime constants.
16 task seeds971000–971015, four each: earlier-event, latest-event order/reset,
15% corrupted observed-event noise, independent hidden fair-bit control. A fresh
per-task random permutation binds categories to rules. Public categories0–3 are
neutral sensor categories, not names encoding solutions. Entity IDs, task IDs,
episode IDs, timestamps and provenance never enter predictors. Visible flag and
binary action interact with the history condition; distractors share the same
categories. Rules are evaluator-supplied task generators, NOT discovered laws.

Per task:96 source,48 separate source-validation,96 final-scored development
episodes. RNG seed = task_seed*1000000 + role_offset + episode index; offsets
100000/200000/300000. Histories contain2–8 events. All methods receive identical
observations and source labels. These are fresh authored procedural episodes,
NOT untouched external or cross-family confirmation. Final-scored outcomes stay
outside fitting and acceptance. No target adaptation/transfer is scored here.

All source/validation candidates and GRU checkpoints are frozen and their manifest
saved before ANY final-scored episode generation. Each task gets exactly ONE
validation decision: select one candidate on source objective, then accept/reject
on validation. No fallback candidate or repeated validation search. Checks from
the first16 source episodes measure finite retention only, not general forgetting.

## Algorithms (unchanged downstream where feasible)

Fixed: Bernoulli empirical table over visible flag/action; unseen keys=.5.
Induced: same table plus at most one accepted history predicate. Recurrent
conflict requires both outcomes in at least two distinct source episodes per
base key.90 predicates:12 exists/count>=2/last,12 latest-A-after-latest-B,66
pairwise conjunctions of the first12. Source Brier+.001*AST complexity;
ties complexity then canonical SHA256. Accept if validation Brier improves
by at least.02 and retained-source Brier increases at most.01. Unknowns explicit.
Maximum8 library features in interactive runtime, one in this isolated experiment.

All-history: existing ridge1.0 on ALL90 predicates crossed with four flag/action
contexts (364 scalars), source-only RMS scaling. No structure search or validation.
Replay: exact history/base-key empirical lookup, fixed-table fallback; controls
larger raw memory without induction. GRU32:8 input channels, new GRU32+linear
Bernoulli head, Adam.01, exactly200 full96-episode updates/task, BCE loss,
per-task fixed task seed, no checkpoint selection.200 updates is a declared
training opportunity, not evidence that recurrence is optimized or inadequate.
No hyperparameter sweep, historical retraining or residual activation.

Neural numeric residual, graph planning and trace-compressed investigation code
are engineering-tested but INACTIVE scientific ablations in this first study.
Thus no scientific claim for learned investigations, composition or residuals.

## Endpoint, replication, stopping

Primary: per-task final Brier, paired fixed minus induced, averaged over the eight
noiseless earlier/order tasks with equal weight. Practical screen: mean>=.03,
exploratory paired t95% lower bound>0 (df7), finite retention excess<=.01.
Noisy and unavailable groups are separately reported, never hidden or pooled to
upgrade the primary. Report every baseline and per-task Brier/accuracy; secondary
comparisons descriptive, no multiplicity-adjusted superiority claim. Chance
unavailable-bit accuracy=.5, optimal expected Brier=.25. Individual finite tasks
can appear above chance; this is not automatically leakage or success.
Questions-to-success is NOT evaluated: this is fixed-budget prediction, no
measured interactive success threshold. Investigation probes are unit fixtures.

120s wall/CPU cap,2048MiB sampled RSS, <=34,560 newly generated authored sensor/
action observations (16*240*9 worst case),0 imagined transitions,3200 new GRU
optimizer steps. Event observations and terminal action outcomes charged exactly
once; cached reuse across methods adds no new observations. Planning tests are
isolated fixtures, not scientific rollout collection. Unequal compute disclosed:
table fitting,90-candidate enumeration,364-feature ridge and GRU are different.
Carried1971.6321034559958s used /1628.3678965440042s remaining; existing host
charges ceil(wall)+1 conservatively. No reset or replacement of historical weights.

Any missing task/method/episode, duplicate ID, nonfinite prediction, changed
candidate, split overlap or resource failure makes execution invalid/incomplete,
not a negative hypothesis result. Preserve partial files; no automatic retry.
All source/validation/final arrays, predictions, acceptance/rejection traces,
new GRU weights, source/config hashes and resources are saved. Independent
arithmetic verification precedes interpretation. No live promotion from this run.
