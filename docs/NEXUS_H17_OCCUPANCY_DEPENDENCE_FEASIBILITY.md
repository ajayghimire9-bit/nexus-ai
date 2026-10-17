# H17 occupancy-dependence feasibility — SOURCE ONLY, NOT LOCKED

## Verdict and scope

**CONDITIONALLY_FEASIBLE; NOT_LOCK_READY.** A five-state-source factorial
comparison at t=12 can fit the standing interaction ceiling while retaining
ten independent training pairs. Its primary would test dependence on a
specified controller-induced state/library distribution, not identify the
cause of H14/H15. No scientific observations were generated in this task.

This is feasibility analysis, not a protocol, execution permission, new
holdout registration, allocation or authorization. No simulator was
constructed; no environment actions, model inference, imagined transitions,
training or checkpoint deserialization occurred. No historical neural
weights or results changed. Ledger remains **305.842 s used / 3294.158 s
remaining**. Main is unchanged. Compact adaptive autonomous intelligence is
the research goal; these MCC mechanism studies do not establish general
control, learning-to-learn or AGI.

## 1. Verified starting point and evidence

Branch: `codex/h17-occupancy-dependence-feasibility`.
Clean local starting HEAD and GitHub diagnosis reference both matched
**`ac829309ff892418ff3dea5e8429f883a105c00f`**. Origin references were
fetched; the exact diagnosis branch is on GitHub. Its H16 results ancestor
is `9474ec63bafbe03adb2b9557c03edfdca650a385`. No older branch substituted.

Read AGENTS, the master context, current progress/next question, H14/H15
results and mechanism audit, H16 protocol/results/diagnosis, and source for
training, candidate generation, controller execution, wrappers and replay.
The unchanged master context was read in full in the preceding diagnosis;
its SHA256 is `e4556b11d6e09c1102fcdc5450e4eb6b7ed03c5852e1ac869fb19e35566c41d8`.
This task reread its latest evidence and checked it against that base.

Verified parent hashes include:

- H14 raw: `7e4a74ba0a8f21f735b41cc1fbceb4d5c005f68718159c0a2077caa27934959e`.
- H15 raw: `440671d592c888e16f5c43d90de701c83bcae6887b9e0b83d1eb71b4312c7a15`.
- H16 raw: `96be8b401a06f48e8eab190058f58a82f6dc1f2eebc6c2fe46f31da1e4bc4625`.
- H16 derived diagnosis: `3d5782da065e78146fba4e798c3aba8ba392ba3ed8e5b2803fcb25b59f2ddb2a`.
- H16 diagnosis report: `b84630658f5c01f396475cd89d440430a034100b2d0247b554ff62d43768839b`.

The regression checks verify all H16-declared parent/source hashes and
the consumed allocation/usage ledger without running its experiment.
H14/H15 remain closed: **+0.178 [0.009, 0.348]** and
**+0.230 [0.111, 0.349]**. H16 remains closed and inconclusive:
**+0.022890 [−0.014211, +0.059990]**. Multitask selected better than
scratch in both H16 libraries; that does not establish library dependence.
These findings motivate the question, not a search for a positive MCC draw.

## 2. Scientific question and factorial structure

On **one prospectively selected unused physics**, does the relative
same-state L0-versus-redraw selection interaction differ between a
model-independent reference policy and registered learned controllers?
No physics tuple, draw, seed block or exclusion-rule output is selected here.

Proposed factors:

1. State source: reference, multitask-fixed, scratch-fixed,
   multitask-redraw, scratch-redraw.
2. Diagnostic library: trajectory L0 versus independent diagnostic redraw.
3. Scoring model: multitask versus scratch.

Within **every source state**, both models score **both** identical
candidate matrices and share all realized candidate returns. A model is
not evaluated only on the states it visits itself. State source is a
sampling factor, not a privileged model input or model label fed to the net.

Proposed grid: ten new independent model-training pairs, one paired reset
per pair, five state sources, one later time **t=12**, H=16, 16 candidates,
three discrete actions. Two model arms are trained once per pair and
then frozen, shared by all source policies and scoring comparisons.
Model-training pairs, not 50 source states or thousands of candidate
trajectories, are the statistical units.

### Why all five sources, and why only one later time?

A reference plus one learned source is sufficient to define an effect,
but source choice could favor one arm or mode. Reference plus both fixed
controllers avoids choosing the generating model but omits occupancies
induced by redraw. Reference plus all four learned policies retains the
generating-arm × generating-mode distinctions as secondary diagnostics.
It prevents selecting the best-looking source after observing outcomes.

All five at both t8 and t12 cost **100,760** real steps with even one reset
per pair; that exceeds the ceiling. The recommended feasible grid retains
the policy factorial and drops the temporal comparison. t12 is the endpoint
of the previously studied prefix window, after later decisions can affect
occupancy; it is not selected for a favorable H16 interaction (the t12
H16 point estimate was smaller). This choice is informed development design,
not independent confirmation of any previous metric. It cannot measure a
time course. One reset per pair gives sparse occupancy coverage, a real
limitation that the ten-seed interval does not remove.

## 3. Resolve library identity and coupling explicitly

For each abstract training-pair/reset key `(s,k)`, define one **L0**.
It is the actual initial library used by every corresponding learned
trajectory. All five sources use the same reset and attached L0. The
reference policy ignores L0 when acting but is assigned that same library
for subsequent diagnostic scoring. Thus libraries are **coupled across
sources**, not drawn separately for each source.

- Fixed generators repeatedly score the unchanged full L0 and execute its
  currently selected first action. No sequence shift, warm start, extra
  candidates or successor lookahead is introduced; retain H14's rule.
- Redraw generators use L0 at decision0, then generation-only matrices
  `G(s,k,j)` at decisions1–11. Those matrices are shared between multitask
  and scratch redraw generators, with no arm term.
- The reference generator uses model-independent seeded discrete actions.
- At t12, **diagnostic redraw** `R(s,k,12)` is shared across all five
  sources and both scorers. Its RNG namespace must be independent of
  L0, reference actions and all generator redraws. Do not silently use
  a generator's current/previous matrix as its diagnostic redraw.

Seed namespaces and collision-free tuple encoding must be defined in a
later lock, including tests against closed streams. No concrete seeds or
fresh library arrays are generated here. For each source state, realized
L0/R returns are generated once and shared between scorers. They are
**not shared across different source states**, even with identical arrays.

Freeze all model scores and choices before exposing simulator candidate
returns. The scorer accepts observation and sequences only. Simulator
state and physics are evaluator-only; no ground-truth score leakage.

### Important coupling limitation

Learned trajectory states depend on L0, whereas reference actions do not.
With trajectory L0 as the diagnostic L0, the primary changes the joint
distribution of **state and initial library**, not only the marginal state
distribution. Coupling libraries avoids proposal imbalance; it does not
make L0 independent of occupancy or remove that history dependence.

An independent diagnostic anchor library could isolate a different,
state-marginal question, but would no longer mean reuse of trajectory L0.
The recommended design explicitly keeps trajectory L0 and accepts this
narrower estimand. It must never be reported as a pure occupancy causal
effect. Additional independent-library crossing is not added in this task.

## 4. Mechanisms and the one candidate primary statistic

At common state `x_p` produced by source policy `p`, library `b` and model
`a`, let `S_a,p,b` be the actual return of the candidate with maximum saved
predicted score. Let `O_p,b` be the best actual return among its candidates.

`S_a,p,b = O_p,b − Regret_a,p,b`.

Within each source and library:

`S_mt,p,b − S_sc,p,b = Regret_sc,p,b − Regret_mt,p,b`.

The shared oracle cancels. Define:

`D_p = (S_mt,p,L0 − S_sc,p,L0) − (S_mt,p,R − S_sc,p,R)`.

Let `P` contain the four learned sources. The **one** candidate primary is

`I_s = mean_{k,t} [ (1/4) Σ_{p∈P} D_s,k,t,p − D_s,k,t,reference ]`.

For the recommended grid k has one value and t=12 only. The general
formula ensures additional nested measurements could not be counted as
new independent replications. Use equal source weights, not visitation
frequency or a favorable posthoc source. Average inside each pair first;
then mean across ten pairs and two-sided Student-t 95%, df9 (locked-recipe
critical value 2.262, unless a later protocol explicitly specifies greater
precision). No H14/H15/H16 pooling or cross-study paired subtraction.

A positive I would mean that relative L0-versus-redraw selection quality
is larger under the specified equal-weight controller-source mixture than
under reference prefixes. A negative I means the opposite. It does not
mean multitask necessarily beats scratch in every source, L0 has better
available candidates, or the controllers earn higher closed-loop returns.

Proposed two-sided directional evidence rule for a later lock: interval
entirely above/below zero and matching mean sign; otherwise
`occupancy_dependence_not_established`. Invalid/incomplete data must get
a separate execution status, never this scientific label. A zero margin
would test detectable dependence only, **not practical usefulness**; this
feasibility does not invent a control-success threshold. Any practical
margin and final rule require explicit review in the later protocol.

Keep these separate:

- **Opportunity:** `O_p,L0 − O_p,R`, available returns independent of
  scorer selection, conditional on source state and libraries.
- **Relative ranking:** D and its regret identity, oracle canceled.
- **Occupancy:** recorded position/velocity distributions after each
  generator acts, not the number of states or an oracle ranking metric.
- **Controller-induced distributions:** jointly shaped by model, search
  randomness, prior actions and reset. These can differ by arm and mode.
- **Closed-loop return:** not the primary here. Prefix rewards may be
  recorded for accounting, but no full-episode claim follows.

Per-source D, model regret, oracle opportunity, ranking correlation, top1,
first-action in-library regret and source occupancy summaries are secondary.
Report all four learned-source contrasts, even if their mixture cancels.
Do not declare any one a replacement primary or select its favorable sign.
If formal per-source tests are later desired, prespecify a multiplicity
rule; otherwise label them exploratory with unadjusted intervals.

## 5. Availability and prospective model construction

H14/H15 saved reset states, actions, observations, scores, rewards, candidate
seeds/fingerprints and chosen residuals. The mechanism audit identifies
**no saved model checkpoint manifest and no later unchosen candidate
returns**. They do not consistently save full native intermediate states
and wrapper snapshots. H16 saves later float32 states, full candidate arrays,
realized return vectors and scores, but no checkpoint reconstruction bundle.

Source inspection of `h14_candidate_reuse_runner.train_seed_models` and
the delegating H16 function finds in-memory model construction with no
weight-save call. Local filename inventory found 953 checkpoint files,
including paths containing `lookahead_h16`. Those are older horizon-16
controllers, **not evidence of H14/H15/H16 checkpoint identity**. No
hash-backed mapping to their experimental model pairs exists in these
artifacts. Filenames alone cannot authorize substitution. None was loaded.

Therefore historical pairs are **unavailable for verified reuse**. The
prospective experiment needs new model pairs on a new target, not recovery
training on consumed holdouts or replacement of historical checkpoints.
Use the same H10 algorithm: residual (64,64), three existing source physics
×512 transitions, 15 source-pretraining epochs, target128 train +32
validation, target normalization, 20 multitask fine-tune/scratch epochs,
Adam0.001, batch128 and existing state/termination loss. Source validation
is 32 rows carved from the1536 collected source rows; no extra collection.
The target pool is shared by both model arms. Checkpoint selection retains
the existing source/target validation behavior; do not select on diagnostic
query returns. Training is not allowed in this feasibility task.

Each future pair is initialized/trained once, frozen before state collection,
and shared across all five state sources. Models **do not** need separate
training for each generator or scoring library. The independent training
seed identifiers, actual initialization values, fresh collection streams
and validation split provenance must be committed later. Save model,
normalization, dataset and dependency hashes outside large tracked binaries;
save a Git-tracked manifest and exact replay records. Never call the old
consumed H14/H15/H16 execute entry points.

## 6. Exact restoration, stochasticity and termination

Use H16's **reset-plus-stored-action-prefix**, not direct `.state` assignment.
Record one live prefix per source. To realize each candidate, reset to its
registered seed and replay the **stored** actions, without replanning or
calling a model during replay. Count every such action. Verify reset
observation/state, prefix rewards and flags, endpoint observation/raw-state
representation and TimeLimit elapsed steps. Keep prefix/source identities
with the records; different sources are not assumed to have equal endpoints.

H16's actual code uses `float32` for observation **and raw state** and
`array_equal`; it does not prove bitwise equality of native float64 hidden
state. Proposed record mocks retain that convention explicitly. A future
runner should additionally record/check native state for stronger identity
if that stricter contract is registered before collection. Do not silently
claim the old float32 gate is stronger than it is. Signed-zero differences
are rejected by the proposed bit-preserving record comparison.

The inspected stack is deterministic, with fixed physics, no noise or
observation/reward transforms beyond the frozen wrappers. The dense-height
wrapper returns `sin(3*next_position)` and suppresses goal termination;
TimeLimit remains200. At t12 plus H16 the elapsed count is28, far below200.
Record inner goal flags separately; expected outer terminated/truncated
flags remain false. This is a source-based feasibility argument, not a
new simulator validation. H16's earlier empirical restoration success is
specific to its stack and physics, not a guarantee for the proposed run.

Future real-stack restoration/reward checks must be included in a guarded
execution budget, not an uncounted preliminary episode. A stochastic
wrapper, RNG-state dependence, unexpected termination, dtype/shape drift,
wrong elapsed count or restoration mismatch is fail-closed. Do not retry
with a new reset, reseed until success, resample physics, or switch restoration
method after seeing failure.

## 7. Exact prospective resource arithmetic

All numbers are proposals, not executed costs or allocated budgets.
For ten pairs, K resets, P sources and time set T:

- Source collection: `10*3*512` =15,360, validation included.
- Target training: `10*128` =1,280; target validation: `10*32` =320.
- Reference generation: `10*K*max(T)`.
- Controller generation: `10*K*(P−1)*max(T)`.
- Prefix replay: `10*K*P*2*16*sum(T)`.
- Candidate realization: `10*K*P*len(T)*2*16*16`.
- Diagnostic imagined scoring: `10*K*P*len(T)*2*2*16*16`.
- Controller-generation imagined scoring: controller generation steps ×256.

No score cache, duplicate-state cache, candidate-prefix tree sharing or
step-zero score reuse is assumed. Both arms share actual candidate
realizations; charging them twice would overcount. Reset calls do not add
actions. Training forward passes are compute, not imagined environment
transitions; their wall time is included in the future run cap.

**Recommended five-source, K1, t12 grid:** source15,360; target train1,280;
target val320; controller generation480; reference generation120;
prefix replay19,200; candidate realization25,600.
Total **62,360 real**, leaving **37,640** below the standing ceiling.
Imagined: diagnostic51,200 + generator122,880 = **174,080**.
Fifty comparison states,100 libraries,200 model/library scoring cells;
1,600 actual candidate trajectories. These are not replications.

Alternatives calculated, not selected based on outcomes:

- Five sources, K1, t8+t12: **100,760 real**,225,280 imagined. **Reject**:
  over budget even though only760 steps over; do not raise the ceiling.
- Five sources, K2, t12: **107,760 real**,348,160 imagined. **Reject**.
- Reference + both fixed controllers, K1, t8+t12: **67,240 real**,
  122,880 imagined; feasible but omits redraw-generator distributions.
- Five sources, K1, t8: **55,760 real**,133,120 imagined; feasible but
  shorter occupancy-generation period and no temporal comparison.

Wall time cannot be known exactly from source. Observed parent runtimes
were H14 4.285s, H15 4.437s and H16 2.065s including their respective
training and evaluations. A cautious **5–30 seconds** planning estimate
is reasonable on the same local CPU, but is not a benchmark or promise.
Propose a **300-second total hard cap**, below900 and the remaining3294.158;
checkpoint I/O, real-stack checks, failures and training must be charged.
The eventual cap would also be bounded by the then-remaining session
allowance. No budget is reserved here and the ledger is not modified.

## 8. Incomplete, invalid, negative and inconclusive outcomes

The future expected grid must come from the locked configuration, never
the rows that happen to exist. Require distinct training pairs and exact
reset/time/source/library/arm sets with finite numeric values. Keep IDs
integer, reject booleans/numeric strings, duplicates and extra rows.
Persist full candidate order, matrices/fingerprints, predictions, choices,
all rewards/returns, frozen model hashes and source-prefix records.

- Early source/reference termination: incomplete, no replacement state.
- Missing candidate or short rollout: incomplete; no NaN-dropping mean.
- Nonfinite score/return, changed weights, reward or restoration mismatch:
  invalid/incomplete execution, no scientific directional label.
- Time/interaction cap: save partial raw records and attempted/actual counts;
  never silently reduce seeds/sources or extend a consumed allocation.
- Complete negative primary: evidence that the mixture attenuates/reverses
  relative selection interaction on that specified joint distribution.
- Complete zero-crossing primary: dependence not established, not proof
  of equivalent occupancies or identical ranking behavior. Inspect all
  prespecified source summaries without replacing the primary.

No outcome automatically warrants a larger network or a new positive-result
search. Opposite source effects can cancel in the mixture; a null mixture
does not prove absence of source-specific effects. Ten independent model
pairs still leave substantial uncertainty about other physics and resets.

## 9. What this adds, and what it cannot identify

H16 held comparison states common across models but sampled only reference
prefixes; H14/H15 let library, state and future controller decisions coevolve.
The proposed factorial puts both scorers and both libraries onto states from
**all five** source policies on one common new physics. It can distinguish
same-state ranking/opportunity differences by source without comparing
each model only on its own favorable occupancy.

It cannot identify a causal mediator of the old H14/H15 return DiDs. Those
use other physics and closed trajectories; this statistic uses candidate
sequence commitment, not receding full-episode value. Source-policy effects
include dependence on the same models being evaluated and L0/state coupling.
Equal source weights are an artificial diagnostic mixture, not a deployed
occupancy distribution. Compounding world-model error, stability, source
history and eventual closed-loop rewards remain separate hypotheses.

## 10. Mock checks and remaining lock requirements

`src/nexus/h17_occupancy_feasibility.py` contains only draft dimension/resource
arithmetic and synthetic-record contracts, not a runner, checkpoint loader,
holdout selector or allocation writer. It reuses stdlib H16 arithmetic and
stays outside the eager-importing world package.

Focused tests cover same-observation/candidate/realized-return pairing,
source identities, mean-within-training-pair grouping, equal controller
weights, three-way primary algebra, oracle cancellation, replay-record
identity, exact resource totals, missing/duplicate grid cells, termination,
nonfinite/wrong-type values, dtype/elapsed/reset drift, and forbidden
simulator/neural imports. These tests do not validate an actual environment,
new training implementation or new state-restoration execution.

Actual command and result:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_h17_occupancy_feasibility.py tests/test_h16_selection_mechanism_diagnosis.py -p no:cacheprovider
```

**66 passed in 0.73s**:36 H17 feasibility checks plus30 H16 diagnosis
regressions. Earlier intermediate runs were64 and65 passed as tests were
added. No historical simulator/training runner tests were executed. A
separate stdlib-only call printed the recommended and alternative resource
counts. Git whitespace checks pass. These are source-only engineering
costs, not scientific execution; the session ledger is unchanged.

Before a final protocol lock, resolve and commit:

1. A deterministic unused-physics exclusion rule covering every closed and
   active MCC registry, including H16, without outcome-guided selection.
2. Fresh disjoint environment/library/training RNG namespaces and complete
   tuple-to-seed mapping, avoiding historical redraw aliases.
3. Checkpoint/data manifests and frozen-parameter checks for newly trained
   pairs; no replacement of historical artifacts.
4. Explicit float32 versus native-state restore contract, wrapper whitelist,
   reward check, complete-grid schema, pre-operation meters and partial saves.
5. Final grid, primary directional/practical interpretation and all secondary
   reporting commitments, including acceptance of L0/state dependence.

The core scientific comparison and coupling choice are specified here;
there is no remaining freedom to pick a favorable source after results.
Operational rules are not finalized, and no real restoration test has been
performed for new physics. Thus this document is **not ready to serve as
a locked executable protocol**, though the reduced design is scientifically
coherent enough for a separate lock-review task. Standing limits are not
authorization for collection in this task.

## One recommendation

Advance the **five-source, one-reset, t12 design** to a separate protocol-lock
review only after its exclusion/seed mappings and checkpoint/restoration
contracts are complete. Do not run it from this feasibility branch.
