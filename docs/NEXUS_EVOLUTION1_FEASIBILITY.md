# NEXUS Evolution-1 — feasibility, not an experiment lock

## 1. Decision, provenance and current capabilities

**FEASIBLE_WITH_GATES — NOT_READY_FOR_SCIENTIFIC_EXECUTION.**
The next milestone is a source-only typed planner-catalogue and evaluation-broker
harness with deterministic contract tests. No discovery engine or experiment
is implemented by this document. No new scientific result is reported.

### Mission clarification and continuation provenance

The expanded human request names this direction **NEXUS Evolution**: a compact
CPU-first system that improves how it learns and plans. Human-level AGI, a
chatbot and a trading product are not this milestone's targets. The seven
desired abilities (learn dynamics, predict/plan, detect weaknesses, propose,
independently test, retain transferable changes and improve proposal strategy)
are research objectives, not established present capabilities. AGENTS.md and
MASTER_CONTEXT.md retain the historical vision and safeguards unchanged; this
report does not silently rewrite those instructions.

This clarification continues the already pushed feasibility revision
`cea4beab1316e698ddfcce5203ef0ecc8c2092c3` on the same requested branch.
Both remotes were refreshed. The reviewed older exclusion-audit revision
`4a86031542229dbe738067c1d34532a553b1d69a` is followed by the dependency-closure
work cited below. No restart from that older branch is needed. Uncommitted
source-contract prototypes from a subsequent task are preserved locally and
excluded from this feasibility commit; they are not reviewed executable
components or evidence for the claims here.

Branch: `codex/nexus-evolution1-feasibility`. Actual starting revision:
`02243916dd8833690cd59f89c866551747b1293f`, matching the fetched GitHub
`codex/h17-seed-dependency-closure` reference. Main was not used as the research
base. The interrupted `codex/h17-seed-ingress-audit` branch is preserved at that
revision; its working tree was clean, with no partial ingress files to move.
No H12–H17 branch is merged or modified. AGENTS and MASTER_CONTEXT were read
earlier in this continuous session; their unchanged hashes and current research
instructions were checked again. The compact adaptive cross-environment goal
remains an aspiration, separate from demonstrated capabilities.

Repository evidence, not new reproduction:

- `src/nexus/world/dynamics.py` supplies residual/direct MLP dynamics with
  explicit dimensions and normalization. The legacy FiLM detached-context and
  shuffled-transition GRU limitations remain documented there; Evolution-1
  must not silently treat those paths as validated adaptation mechanisms.
- `src/nexus/world/planning.py` supplies random-shooting MPC, episode RNG reset,
  survival-weighted rollout scoring and inference counters. Family lookahead
  implementations are in `bellman_backup_control.py`, `acrobot_lookahead.py`,
  `mountaincar_lookahead.py` and `mountaincar_continuous_lookahead.py`.
  The common decision mechanism has improved control with **separately trained
  family world models**. The original three-action successor method costs
  `3 + 3*16*16 = 771` imagined transitions per decision. Matched-search evidence
  supports Pendulum and MountainCar; Acrobot did not clear its practical rule.
  See `NEXUS_LOOKAHEAD_GENERALIZATION_SYNTHESIS.md`.
- Nearest-neighbor and prefix-max tree reuse failed their registered rules:
  respectively −14.751 [−37.142,+7.641] and −9.832 [−31.108,+11.445]. Neither is
  reopened or included as a new mechanism to retune. Prediction improvement
  also did not ensure control transfer in the latent-context sequence.
- `src/nexus/evolution/{mutate,loop}.py` already search actor–critic architecture
  configurations, train candidates, retain elites and compare returns. This
  is existing architecture search, not proof of better learning algorithms.
- `src/nexus/meta/{controller,schema,schedule,loop,reward,matched}.py` already
  implement random/heuristic/LinUCB selection, typed research actions, cost
  ranking and feedback/assessment separation. LinUCB is correctly labelled a
  contextual bandit, not meta-RL. Synthetic bandit performance is not evidence
  of transferable planner discovery. Existing action kinds concern architecture
  and training choices; they are not the proposed planner catalogue.
- `src/nexus/memory/store.py` is a mutable SQLite experiment store, not an
  immutable provenance ledger. `src/nexus/world/memory.py` stores snapshots and
  retrieves by current-probe prediction MAE; this does not establish useful
  algorithm-search memory or control transfer. Its fixed64×64 reconstruction
  and partial byte accounting require a separate audit before broader reuse.
- The old `ExperimentAction` carries feedback and assessment seed fields;
  `meta/loop.py` avoids assessment feedback in controller updates, but passes
  seed-bearing actions and writes both fields into records. Logical exclusion
  from an update is not a sealed evaluator boundary. `reward.py` also uses
  task-specific scales and mixed cost terms that are not a ready-made universal
  cross-family objective. Do not run the legacy loop unchanged for Evolution-1.
- Latest H17 certificates cover76 historical registry records and299 artifact
  root seed schemas. Actual RNG-call dataflow remains unverified. H17 is still
  blocked/unlocked/unauthorized, not a failed or completed scientific test.

This inspection establishes reusable engineering components and gaps. It does
not establish autonomous self-improvement, general control, learning-to-learn
or AGI. No checkpoints were deserialized, retrained or replaced here.

Capability classification, based on source inspection and repository-reported
experiments, **not independent numerical reproduction in this task**:

- **World-model learning — implemented with recorded verification.** Residual
  models fit observed transitions; prediction confirmations exist. That is
  learning model weights, not changing the learning algorithm.
- **Action/outcome prediction — implemented with recorded verification for
  specified state/action inputs.** Dynamics and reward rollouts predict
  consequences of candidate actions. Predicting arbitrary optimal actions is
  not established; actual decisions are selected by a planner.
- **Planning — implemented with bounded multi-family evidence.** Lookahead
  results use family-specific models. Universal reliable control is absent.
- **Model transfer — implemented with mixed/negative evidence.** Fine-tuning,
  snapshot retrieval and context inference exist; useful algorithm/weight
  transfer across all families is not established.
- **Experience memory — implemented, but the Evolution use is unverified.**
  SQLite experiment history and bounded predictive snapshots exist. Memory
  retention does not prove useful search-policy transfer or forgetting safety.
- **Online adaptation — implemented in earlier bounded suites.** Drift and
  update mechanisms were evaluated, with inconsistent control benefit.
  The current frozen controllers do not update their networks online.
- **Meta-controller behavior — implemented, scientific scope limited.**
  Random, heuristic and LinUCB policies choose research actions. Their presence
  or synthetic scores do not establish transferable meta-reinforcement learning.
- **Algorithm selection — partly implemented, Evolution test unimplemented.**
  Existing controllers select architecture/training configurations; the sealed
  cross-family planner-discovery comparison proposed here has not run.
- **Algorithm modification — bounded architecture/configuration mutation
  implemented.** Autonomous discovery of a better learning update or safe
  unrestricted source modification is neither demonstrated nor permitted.
- **Continual learning — replay, memory and retention-oriented code exist;
  general continual improvement remains unverified.** No claim of resistance
  to catastrophic forgetting across arbitrary environments follows.

## 2. What “self-evolution” would mean

Keep four claims separate:

1. **Parameter optimization:** tune horizon, candidate count, penalty or learning
   rate inside an unchanged algorithm. Ordinary HPO, including learned HPO.
2. **Policy learning:** train a policy that chooses actions or computation from
   observations. It need not invent a new algorithm.
3. **Algorithm search:** select/compose materially different vetted decision
   rules, such as flat shooting versus explicit successor backup. Selecting a
   named operator is algorithm selection, not inventing its source code.
4. **Improvement of the search procedure:** prior permitted experience changes
   the proposal policy, and that change improves discovery on new tasks at
   matched budgets against equal-history controls. A better final configuration
   or a lucky search run alone does not demonstrate this.

Evolution-1 proposes bounded, evidence-driven algorithm selection first.
The proposal-policy update rule itself stays fixed; its learned statistics may
change. Do not call this recursive code self-modification or discovery of a new
learning rule. A subsequent claim about improving the search update rule would
need its own held-out meta-test and fair baseline, not a renamed success here.

## 3. Related work and possible differentiation

Targeted primary-source review, not an exhaustive novelty or priority claim:

- **AlphaEvolve:** LLM-generated program changes are evaluated and accumulated
  through an evolutionary pipeline. NEXUS proposes a much smaller, local typed
  operator library, with no generated executable source or external model API.
  Algorithm search plus an archive is therefore not novel by itself.
  [DeepMind report](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/).
- **Darwin Gödel Machine:** an archive of coding agents grows through empirical
  evaluation of self-modifications using foundation models. This is different
  from a small planner selector; it is not evidence that NEXUS has self-improved.
  Evolution-1 intentionally excludes agent/tool/source rewriting.
  [Zhang et al.](https://arxiv.org/abs/2505.22954).
- **POET:** jointly generates challenges and optimizes/transfers solutions.
  Evolution-1 holds the evaluation distribution fixed; letting the proposer
  invent easier tests would confound the intended comparison.
  [Wang et al.](https://arxiv.org/abs/1901.01753).
- **Meta-RL:** RL² learns a recurrent learning procedure from task experience.
  A contextual proposal bandit with an archive is a cheaper initial comparator,
  not an implementation of that meta-RL mechanism.
  [Duan et al.](https://arxiv.org/abs/1611.02779).
- **Online HPO:** population-based training jointly adapts model populations
  and hyperparameter schedules. Scalar schedule changes remain HPO; use an
  equal-budget population baseline rather than claiming them as a new principle.
  [Jaderberg et al.](https://arxiv.org/abs/1711.09846).
- **Adaptive computation:** ACT learns computation depth; Hyperband allocates
  resources to configurations. Budget allocation is an established research
  axis. Neither makes raw forward-call counts interchangeable with CPU time.
  [Graves](https://arxiv.org/abs/1603.08983),
  [Li et al.](https://arxiv.org/abs/1603.06560).
- **Learning to optimize:** learned recurrent optimizers can exploit structure
  across training problems. Evolution-1 does not learn an optimizer or copy
  that result by using a bandit. Its cheaper first target is a planning-strategy
  selector. [Andrychowicz et al.](https://arxiv.org/abs/1606.04474).
- **Automated algorithm configuration:** ParamILS searches parameterized
  algorithm configurations over problem instances. A catalogue search or an
  archive alone is therefore established methodology, not a novelty claim.
  [Author-maintained project and paper](https://www.cs.ubc.ca/labs/algorithms/Projects/ParamILS/).
- **Continual world-model learning:** Continual-Dreamer studies selective
  experience replay, forgetting and transfer. Frozen family models in this
  proposal do not implement continual world-model learning; retention must be
  measured separately. [Kessler et al.](https://arxiv.org/abs/2211.15944).

Potential differentiation is empirical: a compact memory-conditioned proposer
that transfers a compute-limited planning decision rule across distinct dynamics,
with sealed evaluation and honest end-to-end accounting. This combination is a
candidate contribution only if it beats strong controls; neither its ingredients
nor this document establish novelty or a competitive advantage.

## 4. Proposed architecture and information boundaries

The future system has five separate responsibilities:

The requested functional components map to these responsibilities as follows:
**Performance Monitor** computes permitted training-only failure/cost summaries;
**Improvement Generator** proposes a catalogue configuration;
**Experiment Evaluator** is the trusted broker and independent evaluator;
**Evolution Memory** stores immutable success, rejection and failure records;
**Meta-Learner** updates proposal statistics from permitted training feedback.
The monitor cannot read held-out outcomes; the generator and meta-learner may
share an implementation but have different responsibilities. No additional
neural module is justified merely by naming these five components.

1. **Verified training-memory view.** Append-only, content-addressed records of
   permitted training attempts: variant/parent/operator hashes, observation
   features, task-interface description, reward, failures, real/model/CPU cost
   and exact code/data provenance. Exclude historical closed evaluation returns
   as optimization labels. Reuse their methodological warnings, not their scores.
2. **Compact proposer.** Start with a fixed linear contextual-bandit rule over
   vetted variant descriptors, retaining statistics across training tasks.
   Public inputs may include action/observation dimensions, remaining budget
   and permitted training diagnostics. No hidden physics, validation task IDs,
   query seeds, validation outcomes or final-family descriptions are inputs.
   Existing LinUCB mathematics is reusable; the old seven-action schema is not.
3. **Typed planner catalogue.** Canonical immutable configurations refer to
   human-vetted pure operators by hash. No code strings, imports, filenames,
   shell commands, network calls, task IDs or arbitrary expression evaluation.
   Human review introduces a new operator outside the search loop.
4. **Trusted budget/evaluation broker.** Owns tasks, seed capabilities, reward
   definitions, meters, hidden data and failure rules. It validates proposals
   before reserving costs and returns only allowed training feedback. Hidden
   validation is an audit/gate, not a reward channel to the proposer.
5. **Archive and promotion auditor.** Archive every attempt, including failures.
   Update an incumbent only on permitted training evidence, provisionally.
   Independently evaluate a frozen winner, then promote/reject/roll back its
   immutable pointer. Restoring a pointer also restores RNG, context and memory
   state; historical weights and records remain immutable.

The loop is observe verified training records → propose → reserve budget →
evaluate → retain/reject/archive → update proposer from training feedback →
freeze a winner → independent transfer/retention audit. No automatic new study
after a failed gate. A validation/final score never enters the next proposal.

**Security boundary:** a Python type or Boolean “hidden” flag cannot stop a
process that can read the repository's secret files. In a future implementation,
the proposer/variant worker must have no shell, write access, network, environment
factory, evaluator object or hidden-file capability. The separate trusted
evaluator supplies only finite public training inputs through a narrow message
interface. Hidden material is outside its mounted/readable filesystem and logs.
These are future deployment requirements; no permissions are changed here.
Do not claim that a same-process mock proves filesystem isolation.

## 5. Mutation space and scope

**One first mutable mechanism: planning-strategy selection.** The selector
chooses from vetted candidate-search/backup configurations while dynamics
learning, data collection, replay and exploration remain fixed. The structural
contrast is flat shooting versus successor backup; horizon and stratification
are explicit configuration dimensions, not separately claimed inventions.
Learning transferable proposal preferences across this library would improve
the selection procedure only if the matched controls below are beaten.
Changing a horizon alone is HPO. An aggregate win without structural attribution
must be called configuration-selection improvement, not discovery of a new
learning algorithm. The scalar-matched ablation below is required for a stronger
algorithmic claim. This limitation is part of the design, not a success label.

Initial library: two decision rules (flat shooting / one-step successor backup),
two candidate distributions (IID / balanced first action) and three horizons
(4/8/16): **12 canonical variants**, at most four active archive parents.
All choices are prospective design suggestions, not selected by H12–H17 results.
Do not add failed tree-reuse approximations or retune their closed hypotheses.

The broker fixes an imagined-transition cap, not the proposer. For action count
`A`, horizon `H` and cap `B`, flat shooting gets `floor(B/H)` candidates;
successor backup gets `floor((B-A)/(A*H))` tails for each root action. Invalid
zero-candidate configurations are rejected. Report the actual count, not padded
work. Identical caps are not equal FLOPs or latency. A five-action task must
not inherit the three-action771 formula unchanged.

Candidate components and what would constitute a different mechanism:

- Horizon or an uncertainty-penalty coefficient: scalar HPO.
- IID versus stratified candidates, or flat search versus successor backup:
  algorithm selection in a vetted library. A learned observation-dependent
  candidate generator would be policy learning and a separate mechanism.
- Exploration epsilon: HPO. A learned exploration rule changes data collection;
  source experience and real interactions must then be matched. Defer initially.
- Risk-sensitive scoring or calibrated model disagreement: algorithmic changes,
  but single-model prediction residuals are not automatically epistemic
  uncertainty. Defer ensembles and calibration to a separate study.
- Replay-priority exponent: HPO. A new adaptive sampling/update rule may change
  the learner; defer it while decoders remain frozen inside discovery.
- Compute allocation: fixed horizon/candidate pairs are HPO; a state-dependent
  allocation policy is an adaptive algorithm. It may choose below an external
  cap, never edit that cap or the cost meter. Defer initially.

Fixed initial model architecture, loss, normalization, data collection, rewards
and source training procedure avoid crediting stronger models or more data to
the searcher. Network weights are family-specific, not transferred between
incompatible tensors. Any later learning-algorithm mutation requires a new study.
If any benefit is attributable only to horizon/candidate-count selection, label
it improved HPO. Evidence for an operator-level improvement needs a separately
budgeted scalar-matched structural ablation; choosing an operator name or winning
the first aggregate screen is insufficient to establish that attribution.

## 6. Task families, transfer and forgetting

Design three families; no physics tuples or numerical seeds are selected:

- **A — Pendulum:** fully actuated nonlinear rotational dynamics. New source
  and development tasks would be registered separately from all closed suites.
- **B — Acrobot:** coupled, underactuated dynamics. Again, fresh training and
  development tasks, not reuse of the earlier confirmations.
- **C — proposed bounded2D inertial navigation:** translation, drag, bounded
  disturbances and obstacles, with five fixed commands. This is a proposed new
  adapter, not an implemented environment or present result. A separate audit
  must verify its absence from historical suites and freeze its simulator and
  reward semantics before it can serve as a family-held-out test.

A/B supply permitted search training. Separate A/B development tasks provide
a gate for the fixed method, with no feedback to its online proposer. Counterbalance
training family order across future independent search units. C is held out from
proposal training, tuning and development; an evaluator custodian registers its
instances/seeds later. Existing Pendulum, Acrobot, CartPole, MountainCar and MCC
families are **not untouched families**. Current reserved/closed splits remain
excluded, including both earlier latent-confirmation splits and all H12–H17 work.

The worksheet assumes200-step continuing episodes: Pendulum's published cost
and the existing Acrobot **dense upright-height** reward with goal termination
disabled, not Gymnasium's−1/step Acrobot benchmark. Preserve those definitions
for all comparators. The proposed navigation adapter must likewise define
bounded continuing dynamics and reward before registration. Unexpected early
termination is an integrity/incomplete condition, not free extra trials or an
implicit reward change. Record actual steps; do not pad counts with fake data.

The trusted C evaluator may fit a fresh family-native world model using the same
predeclared data/training recipe and an identical budget for all controllers.
That source fitting is charged and disclosed. No C reward reaches the proposer;
the algorithm variant is frozen first. This tests transfer of a planning rule
with a new local model, not zero-shot world-model weights or task-free adaptation.
One final family cannot establish universal cross-family generality.

Forgetting is separately measured on fresh A/B retention episodes: compare
the universal incumbent saved before and after the second training family,
without task-label routing to hide regressions. Proposed retention tolerance:
no more than0.02 of the family's analytic return range lost, with a paired
lower confidence bound above−0.02. Fixed decoders do not imply no planner
forgetting. Archive persistence alone is not a retention result.

## 7. Strong baselines, promotion and statistics

All search methods get the same12 variants, source datasets/models, six
proposal slots per training family, public history access, candidate limits
and CPU/interaction-accounting rules. Two common fixed anchors consume slots;
four subsequent proposals are selected without duplicate evaluations per task.

- Uniform random search without replacement.
- Equal-budget evolutionary search, population at most4, tournament2,
  one legal operator-coordinate mutation; unchanged mutation rule.
- Memory-conditioned linear-bandit proposer.
- The same proposer with learned statistics reset at each family boundary;
  the evaluation budget and incumbent/archive rules remain identical. This
  isolates statistical transfer, not removal of every form of archive memory.
- Two non-search baselines: fixed H16 flat MPC and fixed H16 successor backup,
  each using the same external compute cap. They use less search overhead;
  report that advantage. These are prospective compute-capped baselines,
  not replacements for the historical16-candidate controllers/results.

Report raw200-step returns, decision latency, model error as diagnostic,
proposal overhead, memory bytes, failed attempts and search quality versus
charged budget. Do not compare raw Pendulum and Acrobot returns directly.
Normalize return differences by a **fixed analytic task reward range** supplied
by the trusted specification before data; reject undefined/zero ranges.
Do not fit normalization to final outcomes or use a posthoc best candidate as
the reference. Suggested practical margin:0.05 of that range, intentionally
substantial. Training progress is not independent promotion evidence.

Use ten independent **search/model-bundle** replications, each with independently
initialized family models and an independent proposal trajectory. Pair methods
within bundles using identical task/reset/planner seed schedules where defined.
Average episodes and tasks inside a bundle; with more student/search seeds on
one model, average those too. Shared weights are not additional replications.
Inference is conditional on the finite task suite and its reward definitions.

Proposed full claim requires memory-minus-control mean at least0.05 and a
positive simultaneous interval against **all five** controls (random, evolution,
reset, fixed flat, fixed successor). Use Bonferroni familywise95% paired
Student-t intervals: each99%, df9, critical value `t_(1-.05/(2*5),9)`.
Report ordinary95% intervals as exploratory too, plus per-task/family effects
and negative transfer. No result-dependent comparator selection or episode
pseudoreplication. Failure to beat the reset ablation prevents a claim that
prior learned proposal statistics caused the benefit. Retention is an additional
gate, not a substitute for the primary comparison.

Labels: `development_screen_failed`, `inconclusive`, `negative_transfer`,
`transfer_screen_passed`, `incomplete_budget`, `invalid_integrity`, or
`invalid_leakage`. A complete nonsignificant run is inconclusive, not incomplete.
Missing cells, nonfinite results or mismatched hashes invalidate promotion;
never silently drop them or select a winner using the final task scores.

## 8. One falsifiable first experiment and budget estimates

**First scientific experiment proposed, not locked:** does retaining proposal
statistics from the first training family improve discovery on the second,
as judged on independent A/B development tasks, versus random/evolution/reset
and the two fixed planners? This is a necessary development screen for the
larger unseen-family hypothesis, not that hypothesis's confirmation.

For fair, inexpensive feedback, a trusted worker would precompute the entire
12-variant training matrix before replaying the already-frozen search methods.
Each method may reveal only its six selected rows per family; unrevealed labels
and all development outcomes are inaccessible. Charge recorded cost for every
revealed row even when physically cached. Publish actual collection once and
per-method charged budgets separately. Caching tests selection using a fixed
feedback matrix, not online changes to the environment or the model.

Planning worksheet (counts only, **not allocation or authorization**):

```json
{
  "status": "feasibility_only",
  "protocol_locked": false,
  "execution_authorized": false,
  "holdout_seed_ids": [],
  "independent_bundles": 10,
  "training_families": 2,
  "variant_count": 12,
  "proposal_slots_per_family": 6,
  "source_train_steps": 1024,
  "source_validation_steps": 256,
  "episode_steps": 200,
  "development_conditions": 6,
  "development_tasks": 2,
  "source_collection_steps": 25600,
  "training_matrix_steps": 48000,
  "development_evaluation_steps": 24000,
  "first_screen_total_steps": 97600,
  "imagined_cap_per_decision": 1536,
  "first_screen_imagined_upper_bound": 110592000,
  "future_final_collection_steps": 12800,
  "future_final_evaluation_steps": 48000,
  "future_retention_steps_upper_bound": 48000,
  "full_campaign_steps_upper_bound": 206400,
  "plain_mlp_estimates": [
    {"family": "pendulum", "obs_dim": 3, "n_actions": 3, "parameters": 4868},
    {"family": "acrobot", "obs_dim": 6, "n_actions": 3, "parameters": 5255},
    {"family": "proposed_navigation", "obs_dim": 4, "n_actions": 5, "parameters": 5125}
  ],
  "source_weight_bytes": 404920,
  "future_navigation_weight_bytes": 205000,
  "proposed_bandit_features": 8,
  "proposed_bandit_matrix_vector_bytes": 6912,
  "compact_source_row_bytes_upper_bound": 78,
  "compact_source_payload_bytes_upper_bound": 1996800
}
```

Arithmetic: source=`10*2*(1024+256)`; matrix=`10*12*2*200`;
development=`10*6*2*200`. Source datasets are identical across methods;
logical charges cannot disguise extra physical collection. Source training at
a suggested20 epochs/batch128 adds3,200 optimizer updates and409,600 training
examples across20 models; it is not free and not run here. Planning upper
bound=`(48000+24000)*1536`; count training/validation inference separately.

Historical Pendulum lookahead spent68.146s on12,324,000 imagined transitions
(`NEXUS_BELLMAN_BACKUP_CONTROL_RESULTS.md`). A simple proportional estimate for
110,592,000 is about612s **for planning alone**. Allow roughly10–25 minutes
end-to-end on comparable hardware, with substantial uncertainty from batching,
family adapters, training and I/O; this is not a runtime measurement or promise.
A future900s cap may therefore yield `incomplete_budget`. Profile only under
a separately authorized scope; do not shrink seeds/episodes after results to
declare completion. Track process CPU seconds and elapsed time, one CPU worker,
all method overhead and memory; equal imagined states are not equal compute.

Future C assessment estimate:10 bundles ×1,280 source/validation steps plus
6 conditions ×10 bundles ×4 task conditions ×200 steps =60,800 real steps.
Fresh retention before/after across6 conditions ×10 bundles ×2 families ×200
steps ×2 snapshots costs at most48,000 more (disclose exact caching).
Together with development this is a **206,400-step study**, exceeding the
standing100,000-per-experiment grant. Full-study execution needs explicit
approval of an integrated budget; splitting jobs must not evade that limit.
No part is allocated here, and current instructions authorize no experiment.

Development fails if memory does not meet the proposed comparison rule or
training-order sensitivity reverses its effect. Stop before C; possible causes
include a small/uninformative catalogue, no transferable reward structure or
an adequate random/evolution baseline. Do not increase search trials or alter
metrics on the same held-out sample. If development passes, lock the separate
independent assessment and retention protocol before access; never recycle a
failed final family as new confirmation for a revised selector.

## 9. Reproducibility, costs and commercial possibilities

### CPU-first parameter, memory and storage worksheet

Analytic estimates only; no model was constructed or profiled. For a plain
64×64 residual MLP with observation dimension O, A one-hot actions, and state
plus termination heads, parameter count is
`64*(O+A+1) + 64*65 + (O+1)*65` from `world/dynamics.py` and `nn/factory.py`.
This gives **4,868** for Pendulum (O=3,A=3), **5,255** for Acrobot (O=6,A=3),
and **5,125** for the proposed navigation interface (O=4,A=5). These are proposed
plain-MLP sizes, not a recount of every historical FiLM checkpoint.

Twenty A/B models total101,230 parameters, **404,920 bytes** of float32 weights.
Ten later navigation models add205,000 weight bytes. A model under Adam needs
roughly four times its weight bytes for weights, gradients and two moments,
plus buffers, temporary tensors, Python/framework overhead and serialization.
Train sequentially on one CPU worker; no GPU or external inference API is needed.
Actual process peak RSS is unknown until a separately authorized profile.

A proposed12-arm,8-feature linear bandit stores12 covariance matrices and12
vectors: `12*(8*8+8)*8 = 6,912` float64 bytes, before inverses, metadata and
archive storage. It is not a neural meta-RL agent. Its update cost is negligible
relative to planning in this small design, but must still be metered.

At O≤6, compact source rows with two float32 states, int64 action/seed/episode,
float32 reward and two byte flags use at most78 bytes per row: **1,996,800
bytes** for25,600 rows. Policy strings, task metadata, copies and actual NumPy
layout add overhead; this is not the current dataset's measured memory.
Allow roughly10–100 MB for logs and selected traces depending on serialization;
full imagined trajectories and duplicate datasets may exceed this estimate.
Parameter/optimizer payloads are small, but file headers and manifests mean
checkpoint file sizes exceed raw weights. Keep checkpoint binaries outside Git,
with paths, hashes, source/configuration and normalization metadata recorded.
Do not estimate storage as zero because the neural networks are small.

The earlier10–25 minute development estimate includes uncertain training/I/O
overhead; planning alone extrapolates to about612 seconds. Source learning is
suggested20 epochs on1,024 transitions per model (3,200 updates at batch128
across20 models). Search variants must share these frozen learned models and
data; random and evolutionary baselines receive the same feedback opportunity.
Fixed planners avoid search overhead and may win on cost. If the full proposal
cannot fit an approved cap, first complete the source-only broker/adapter tests;
do not reduce scientific replication after inspecting outcomes or pretend a
synthetic fixture test establishes cross-family transfer.

Before any future run, independently verify checkpoint reconstruction/hashes,
source/validation separation, full seed exclusions, reward semantics, budget
meters and all expected cells. Save configuration/operator hashes, immutable
parent pointers, ordered proposals, allowed feedback, RNG states, elapsed/CPU
time, training and imagined counts, dependency versions, and failed/partial
attempts. A candidate cannot suppress a failed attempt or modify archive bytes.
Promotion changes only a versioned incumbent pointer after independent checks;
rollback preserves the rejected record. The SQLite store can support queries,
but immutable manifests and a sealed evaluation broker must be added separately.

Potential commercial paths, **not present products or market evidence**:
simulation-based planner selection for constrained robotics; reducing compute
for an independently verified controller; reproducible evaluation tooling for
small control teams. Each requires downstream safety validation, realistic
latency/robustness tests and evidence of customer benefit. No real-money trading,
paid services, deployments, performance guarantees or revenue claims follow.
Adaptive software agents would additionally need a separately validated action
and reward interface; no chatbot wrapper demonstrates that capability. Trading
research would require leakage-safe market data, transaction/risk modeling and
independent prospective evidence; simulation control findings do not imply
profitability. No trading system, software-agent product or robotics deployment
is implemented here.

Major risks: decoder quality confounds, reward-scale artifacts, archive leakage,
winner's curse from repeated testing, small family count, negative transfer,
history-dependent feedback, nonstationarity, CPU-cap censoring, model exploitation,
insufficient task diversity and incorrect reconstruction of frozen context.
A larger search space makes selection overfitting easier; it is not progress.
Human-defined rewards and operators bound what can be discovered. This initial
system does not create new learning rules, prove continual improvement or AGI.

## 10. Immediate milestone and work actually performed

One next milestone: implement and adversarially test a **source-only typed
planner catalogue plus sealed-message evaluation-broker contract**, using
deterministic fixtures. Demonstrate forbidden-field rejection, no hidden-data
capabilities, proposal determinism, precise analytic cost bounds, rollback,
complete logs and equal-budget policy interfaces. This is the prerequisite
before requesting a scientific protocol/runtime-readiness review.

This branch adds this feasibility document and deterministic source-only
consistency tests only. No planner/proposer implementation is changed, no model
is trained or loaded, no environment is constructed, no seed selected, no lock
or allocation created, and no experiment executed. Existing ledger stays
**305.842 seconds used /3294.158 seconds remaining**.

Protected source-of-truth hashes:

- `AGENTS.md`: `6ccda31c10dfc40ea8c6f42b085efa9ad45aab0af5094521e7a5cc9b1947daca`.
- `docs/MASTER_CONTEXT.md`: `e4556b11d6e09c1102fcdc5450e4eb6b7ed03c5852e1ac869fb19e35566c41d8`.
- `artifacts/research_session_h16_same_state_library_usage.json`:
  `ff4c51e2f00f9789219daeeb362a9c57d14da3619ae20d92578e4c1b38d39117`.
- `configs/h17_occupancy_draft.json`:
  `4eb9401465744e2f29d026b9a42f6480015c1774cf66f676018eeaf256b45f0f`.
- `artifacts/h17_seed_dependency_coverage_validated.json`:
  `42eee2ea11e4ffbc4a870af77f7faf84472797fda5a9052888f62094b2ebc6bf`.

Primary-source literature was checked2026-10-18. Literature summaries and
prospective calculations are not experimental observations. Test commands and
actual results are recorded after the source-only checks below.

Verification completed:

- Focused `tests/test_evolution1_feasibility.py`: **23 passed in0.03s**.
- Combined feasibility and existing source-only H16/H17 audit regression tests:
  **194 passed in7.00s**. This is not the scientific environment/model suite.
- Checks independently recompute source/validation, evaluation and full-study
  counts, reject altered/missing cost components and invalid numeric types,
  verify three-/five-action search-cost arithmetic, and verify protected hashes.
  They do not demonstrate a working optimizer, security sandbox or improved control.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest tests/test_evolution1_feasibility.py tests/test_h17_seed_dependency_closure.py tests/test_h17_reservation_closure.py tests/test_h17_exclusion_coverage_review.py tests/test_h17_exclusion_registry_audit.py tests/test_h17_protocol_readiness.py tests/test_h17_occupancy_feasibility.py tests/test_h16_selection_mechanism_diagnosis.py -p no:cacheprovider -o addopts='' -q
```

Expanded-request review on2026-10-18: the same combined command now passes
**196 tests in7.82s**, including two new source-only checks for the parameter/
storage worksheet and extended primary-source references. The previous23/194
counts above describe the original feasibility revision, not the updated run.
The25 feasibility tests are included in the196; no separate new focused-only
run is claimed. `git diff --check` passed. Protected instruction, ledger and
H17 artifact hashes remain unchanged. The partial fixture-contract code from
the intervening continuation was not imported by this review's test selection
and is not staged or shipped as part of this feasibility update.

Verdict remains **FEASIBLE_WITH_GATES — NOT_READY_FOR_SCIENTIFIC_EXECUTION**.
One next engineering milestone remains the source-only typed catalogue and
sealed-message broker contract with adversarial fixture tests. No seed, target,
lock, permission record or resource allocation is created by this update.
