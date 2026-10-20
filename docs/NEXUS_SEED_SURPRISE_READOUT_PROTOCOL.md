# Seed: nonlinear action readout and one-use investigation

Registered before collection. Parent: `abd8a43` (negative validation preserved).
Reuse `action_readout.ActionReadout/features/fit`, `Belief`, `SeedRSSM`,
`SeedLatentPlanner`, `AdaptiveState`, vetted structural edits and `OuterSeedMeta`.
No replacement memory, recurrent model or meta-controller stack.

## Hypotheses and fixed experiment

H-action: the existing 34→32→32→1 nonlinear residual head, fitted on separate
balanced source states, reduces fresh immediate ranking regret without an
unacceptable full-episode control regression versus frozen reward ranking.
Counterhypothesis: lower fitted reward error fails to produce useful decisions.
The historical 64-state audit and the completed validation audit remain closed.

Executable source of truth: `configs/seed_surprise_readout.json`. One frozen
aligned core and its frozen source retrieval bank, verified by hash. Three fresh
head seeds, Adam .003, weight decay .0001, 800 updates, batch128, source only.
Do not train the GRU or add rank-four capacity in this experiment. The rank-four
module is implemented and functionally tested only; no automatic activation.

Source128, development32, final64 authored states. Four equally represented
strata: boundary, interior, one-move goal and macro goal. Placement is determined
by geometry before outcomes, never by model predictions. All nine outcomes are
collected once from cloned identical states. Disable authored information bonus.
Current posterior and retrieved memory enter the reused readout. Prediction
features never receive true future outcomes. Development calibrates only the
frozen scorer surprise scale, not architecture, fitting or checkpoint selection.
All three fixed heads and their hashes are saved before opening final states.

Control: eight independent goal/reset streams, four paired episodes per stream,
20-step cap. Compare three heads, frozen ranking, random, known-grid greedy and
unchanged latent MPC (Seed H4/16 candidates/pruning,48 imagined states/decision).
All methods use identical episode resets; random/planning seeds are specified
in runner. Each full trace preserves actual rewards, actions and terminal status.
No evaluation updates. Greedy has supplied positions/goal, not learned knowledge.

Average head seeds inside each task, then use paired n8 task-level Student-t
intervals (df7, t=2.364624251). Conditional on ONE frozen core; head seeds are not
independent world models. Primary screen: >=30% lower mean final-state regret,
goal rate no more than .05 below frozen, and lower 95% return-difference bound
>=−.10. This is a development screen, not a general-control claim. Greedy victory
is an ambitious secondary outcome, not required. Report all comparisons.

## Surprise and edits

Scale is RMS frozen reward error from the development set, epsilon1e−6. A surprise
greater than3 requests investigation only. Bind the scale to scorer/data hashes.
No audit residual enters calibration. No surprise flag automatically installs an
edit. Assess edits with G=Lkeep−Lcandidate−forgetting−.0001cost; require G>.01
and forgetting<=.01. Reserve each assessment set before scoring and consume it
even on rejection. A candidate batch may share one set; later decisions may not.
Final-audit leases are prohibited. Legacy session assessment labels are retired.
Repair, scoped addition and algebraic merge remain distinct and reversible.

H-credit diagnostic: credit from subsequent source-learning loss reduction,
forgetting and cost may select better edits than random, fixed repair or a
historical-best rule. This is a SOURCE-BANK diagnostic, not new confirmation.
Use first40 source states as separate nine-label task banks. Pad existing
34-dimensional readout features with zeros to62 for existing vetted edit APIs;
do not claim this is the deployed reward representation. Each task uses actions
0:3 as fit,3:5 as one-use edit assessment,5:7 as subsequent teaching and7:9 as
future probes. Query labels never fit or accept edits. Alternate existing/new
scope status to expose merge/add eligibility. Thirty-two source proposals per
policy, then eight held-out source-bank tasks with no policy updates. Adaptive
uses forced initial coverage then epsilon.2. Random has same opportunities;
fixed always repairs; historical-best balances first8 then commits to source
empirical mean. Rejected/invalid proposals pay costs. Report actual future gain,
not acceptance rate. These task banks are heterogeneous action subsets of a
single state, a weak functional test of credit, not broad learning-to-learn.

## Resources and validity

Max6496 real authored steps (2016 cloned-outcome +4480 control), <=7000 cap.
At most55776 imagined candidate transitions, <=100000 cap; posterior-prior
model rows and cached source fitting are reported separately. Head training
307200 cached example presentations and2400 optimizer updates. Meta proposals
use cached source rows, no extra environment/model calls; cost accounting is
logical fit steps and teaching labels, not FLOPs. Local CPU cap180s; carried
session1901.632103456 used,1698.367896544 remaining. Standing user grant applies.
One run only; no retries/retuning. Record partial failures and consumed work.
Complete exact seed/state/method grid, finite metrics, matching checkpoints,
unchanged core/bank and valid reward accounting are required before any pass.
No old checkpoint replacement, Pendulum execution, reserved splits or main merge.
