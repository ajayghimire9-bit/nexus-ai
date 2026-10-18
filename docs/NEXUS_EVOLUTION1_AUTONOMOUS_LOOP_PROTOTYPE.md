# Evolution-1 first feedback-driven toy loop

Status: **FUNCTIONAL_NON_SCIENTIFIC_PROTOTYPE — NO_GENERALIZATION_CLAIM**.
Branch: `codex/evolution1-autonomous-loop-prototype`.
Starting revision: `e4daa4ea8c89e43c5d296910c0f14e6e3608c4fa`.

Both remotes were refreshed. GitHub/local ancestry was verified through
feasibility`aee1362`, contracts`3ac0c5f`, adapter review`d5339de` and resource
ledger`e4daa4e`. The interrupted task-metadata branch had no new commit; its two
untracked prototypes are preserved and excluded from this branch's commits.
No H12–H17 result, allocation, checkpoint, root instruction or main branch is
changed. This milestone implements the central feedback loop instead of another
scientific preparation layer. It does not instantiate a real environment.

## Architecture and bounded cycle

`src/nexus/evolution1/toy_loop.py` composes the existing catalogue, fixture
broker, reservation ledger, journal, auditor and promotion/rollback harness:

1. The trusted host supplies one synthetic training table. The proposer receives
   only the public context and remaining catalogue configurations.
2. Two shared starting probes are fixed across methods: IID flat H16 and IID
   successor H16. The adaptive policy may learn from their permitted receipts.
3. The proposer chooses the remaining two probes from experience. Each proposal
   reserves its registered quota before the broker reveals scalar feedback.
4. Training receipts update the adaptive policy; immutable attempt records bind
   receipt, variant and before/after learning state. Failed candidates have an
   explicit null score and learning target0; they still consume budget.
5. After all four slots finish, freeze the highest **observed training** score
   candidate. The proposer does not search all twelve rows or see unchosen rows.
6. A separate development gate compares that frozen candidate with the initial
   incumbent. It cannot call the proposal policy or deliver an update to it.
7. A positive fixture gate is signed with the existing test auditor, then the
   host promotes the candidate reference. A later reference-integrity mismatch
   invokes rollback; a rejected gate preserves the incumbent without promotion.

The default budget is four proposals out of twelve. The training API permits
only2–6 slots, never exhaustive twelve-row search. A fixed operation plan
determines completeness; missing proposals cannot shrink the expected grid.
The gate checks resource completion, attempt uniqueness, history and broker
chains, receipt bindings and the selected training winner before reading its
development scores. A gate instance may be consumed once; a failure does not
trigger another candidate chosen from development feedback.

## Exact proposal rules

All methods share the same two probes, seed, public context, catalogue and
feedback opportunity. No LLM or neural model is used.

- **Fixed:** choose the remaining highest horizon, breaking ties toward flat
  search and then IID generation. Feedback does not alter its decision rule.
- **Random:** sample uniformly from remaining variants using its seeded local
  Python RNG. Feedback does not alter its learned state.
- **Adaptive:** normalized linear SGD on shared configuration features. A seeded,
  precomputed catalogue permutation breaks ties; choosing an arm does not draw
  new randomness. Its six weights start at zero.

For successor indicator S, balanced-generation indicator B, H/16=h, public
observation dimension O and action count A, the fixed feature vector is:

`x = (1, S, B, h, S*O/16, h*A/16)`.

Prediction is`w·x`. Choose the remaining arm with the largest prediction, then
its fixed tie priority. For an accepted training score y in[0,1], or y=0 for
an explicit failed candidate, update with the fixed rule:

`w ← w + 0.5*(y − w·x)*x/(x·x)`.

This is a simple contextual linear bandit-style estimator without an optimism
bonus; common probes provide initial exploration. Its update rule is fixed.
Weights share evidence across catalogue configurations. It does not discover
new source code or improve the update rule itself. No learning rate was selected
using scientific outcomes. Changing the learned weights is permitted toy policy
learning, not neural/world-model training.

## Feedback boundary and history

The update API accepts exactly`TrainingFeedback`: variant identity, finite
training score/null failure, failure flag and broker event hash. Replayed event
hashes are rejected. Gate results, arbitrary dictionaries, extra assessment
fields and malformed scores cannot enter that API. `run_training` has no
development/final data argument. `DevelopmentGate.assess` has no policy argument.
Changing only development scores leaves the complete training trajectory,
weights and history identical; an adversarial test verifies this intervention.
There is no final-evaluation fixture in this prototype.

These are logical API boundaries in trusted Python, **not OS-level secrecy**.
A malicious same-process host could inspect private objects, encode assessment
data as counterfeit training feedback or reconstruct a gate. The receipt types
and shared test HMAC key do not stop that. The supplied runner does none of
those things. Production capability isolation and an independently held
evaluation/signing authority remain required. No security settings were changed.

Attempt dataclasses, tuple histories and journal events are immutable through
their public interfaces. Snapshots bind RNG, public context and complete toy
memory references, including replay guards and adaptive tie order. Rollback
restores the last accepted incumbent reference, not necessarily the original;
archives and failed attempt history remain retained. It does not load/restore
a real controller or erase the search policy's record of unsuccessful attempts.
Durable storage and external log anchors remain separate requirements.

## Resource accounting and failure labels

Every proposal reserves the same conservative logical credits: one step and
1536 imagined transitions. These are **synthetic budget tokens**, not executed
environment/model work. The broker separately charges each variant's exact
analytic fixture cost and one declared CPU unit; these are not measured CPU
seconds either. Resource-ledger physical work is zero because feedback is a
scalar fixture lookup. The journal retains the source fixture hash for that
cached declaration. All methods get four receipts and identical quota limits.

Mock monotonic clock values test the reservation state machine; they do not
measure or equalize real CPU use. Gate comparison consumes two scalar lookups
under its separate one-comparison limit. Future CPU efficiency is untested.
Resource exhaustion or a duplicate proposal stops before another receipt and
produces an incomplete run, with no development gate or promotion. A properly
evaluated failed candidate is a valid negative observation, not missing data.
Scientific inconclusiveness is not an execution failure label.

## Deterministic evidence and counterexamples

The crafted`aligned_signal` example with public toy seed7 produces these
catalogue indices in the tests:

- Adaptive with feedback:`[2, 8, 11, 10]`.
- Same adaptive policy with all feedback withheld:`[2, 8, 7, 11]`.

Both see identical first probes and use identical tie priorities. Before the
third choice, only feedback access differs. The weights change only in the
fed condition; the withheld condition retains six zero weights and zero
updates. This isolates a feedback-driven change in the toy proposal rule,
rather than attributing a changed choice to random draws or exhaustive search.

Three explicitly authored examples are included, with all tables available for
reproduction. They are not statistical replications or hidden scientific tasks:

- `aligned_signal`: training and development preferences align.
- `heuristic_counterexample`: an exceptional flat configuration violates the
  adaptive model's coarse structural preference; the fixed heuristic wins.
- `development_reversal`: good training scores select a candidate that fails
  the independent fixture gate. It is not called generalization or promotion.

The saved runner will contain the raw attempts, policy states, resource/broker
journals, gate contrasts, archive transitions and summary scores for all three
methods. A separate withholding run is included. This is40 training and18
development scalar lookups in one demo, not scientific interactions. The
default retention check is a snapshot serialization round trip; adversarial
tests supply a mismatched observed reference to exercise rollback.

Implementation and this description are committed before generating the saved
CLI example. The script refuses to generate that artifact with uncommitted
relevant source. Its provenance records the exact implementation commit, code
hashes and Python version. Unrelated preserved prototypes remain separately
visible in the recorded full working-tree status; do not claim a wholly clean
tree. `--check` requires source hashes to match both current bytes and that
recorded commit, then reproduces the entire deterministic payload.

## Future scientific comparison — design only, not locked or authorized

The prototype establishes functional feedback use, not the central transfer
hypothesis. A later study must test whether learned proposal statistics improve
discovery on unfamiliar tasks against strong equal-budget methods.

Proposed structure, with **no physics tuples or numeric scientific seeds chosen**:

- Meta-training: new Pendulum and Acrobot source task instances, disjoint from
  all closed suites. Fit independent family-native models under one fixed
  training recipe and share the same source data/models across comparators.
- Development: physics-disjoint tasks within those two families. Gate the
  frozen proposal strategy; no development outcome becomes an online update.
- Final: two new family candidates, bounded2D inertial navigation and a discrete
  queue/resource-allocation process. Both need separately reviewed adapters and
  history-absence checks; neither is implemented or registered here. Their
  instances and rewards must be fixed by the evaluator before any access.
  Existing familiar families must not be relabelled untouched families.

Use at least ten independent **model/search bundles**, each with independently
trained family models and a separately seeded proposal trajectory. Repeated
episodes, candidate queries or student seeds on the same model are averaged
within a bundle, never counted as extra independent replications. Counterbalance
training-family order. Fit target-family local models only through the trusted
evaluator under matched budgets; transfer of the selected planning rule does
not imply sharing incompatible world-model weights.

Compare adaptive memory with uniform random search, fixed H16 flat and successor
planners, equal-budget population evolution, and the same adaptive proposer with
learned statistics reset between training families. Match candidate catalogue,
proposal counts, public feedback history and actual CPU/real-interaction caps;
include model training, selection, replay, validation, failures and cache costs.
Do not claim equal compute from equal imagined counts or toy CPU units.

Proposed primary: final-family normalized return difference versus every strong
control, with a practical margin0.05 of each predeclared analytic reward range.
Pair and aggregate tasks/episodes inside independent bundles. For the five
contrasts use familywise95% Bonferroni intervals (individual99%, df9 for ten
bundles), also report exploratory95% intervals, family/task failures and
source-retention changes. A point estimate or one successful family cannot
override a failed primary or retention gate. Record `inconclusive`,
`development_screen_failed`, `negative_transfer`, `incomplete_budget`,
`invalid_integrity` and `invalid_leakage` explicitly.

The existing first-screen worksheet is97,600 interactions for two training
families and development. At its old assumptions each new final family adds
60,800; adding48,000 retention steps yields267,200 for two final families.
That is an estimate, not an allocation, and exceeds standing100,000-per-experiment
authority. The earlier10–25 minute first-screen CPU estimate remains uncertain
and may exceed900s. No real experiment follows from the toy runtime. Integrated
budgets, family adapters, exclusion closure, isolation and statistical rules
need separate independent review and explicit authorization where limits require
it. Do not split the study to evade those limits or reuse expired allowances.

## Verification, limitations and next milestone

Initial focused adversarial tests: **23 passed in0.11s**. After adding the
deterministic example/accounting check, the combined source-only suite passed
**344 tests in8.15s** (including24 toy-loop tests). Tests cover informative versus
withheld feedback, failed/duplicate budget handling, gate isolation, forged/
incomplete histories, rollback, resource stops, reproducibility and baseline
counterexamples. The15-file read-only adapter snapshot still matches.

No model inference, world-model training, simulator construction or scientific
experiment ran. Policy updates operate on synthetic scalar rewards only. No
scientific holdout or target seeds were registered; no authorization was made.
Session ledger remains **305.842s used /3294.158s remaining**.

Remaining barriers: independently enforced information access, real CPU/work
meters, complete source/data/checkpoint provenance, actual family adapters,
strong evolutionary/reset baselines and independent model/search replications.
The crafted examples do not measure generalization, control improvement,
learning-to-learn or proven self-evolution.

One next scientifically necessary milestone: prepare an independently reviewed,
bounded **cross-task proposal-policy development screen** against memory-reset
and equal-budget evolutionary search, resolving those runtime/coverage gates
before any scientific collection. Do not execute that screen in this branch.

## Saved example and consistency review

Implementation committed before saved CLI execution:
`f4de1e135dd88ee18ef7a6b05a42c70df917d00e`.
Artifact: `artifacts/evolution1_toy_loop.json`, SHA-256
`f017e98dbff9a33cde38a5203d25c5bf6a14a39104e7fb9b3eea8c7428360df7`.
It records Python3.13.5 and an empty relevant-source status. Full working-tree
status honestly records the two preserved, untracked metadata prototypes; neither
is imported by the loop or included in its committed source hashes.

One saved demo's exact summaries (rounded for readability; raw floats retained):

- `aligned_signal`: adaptive training total2.54, fixed2.06, random1.85. Adaptive
  and fixed find training score0.84; random finds0.69. Fixture development gains
  over the incumbent are0.60,0.60,0.50 respectively; all pass the toy gate.
- `heuristic_counterexample`: adaptive total1.90 and best0.60, fixed2.29 and
  best0.99, random1.40 and best0.60. Development gains0.30,0.85,0.30. The fixed
  heuristic beats adaptive under the same four-proposal allowance.
- `development_reversal`: training totals match the aligned fixture, but every
  development gain is−0.35. All three gates reject; the incumbent is preserved.

Adaptive trajectories are`[2,8,11,10]`; fixed`[2,8,5,11]`; random`[2,8,6,3]`.
The withholding intervention is`[2,8,7,11]` and retains zero learned weights.
These are one-seed, hand-constructed functional examples. No confidence interval,
empirical generalization claim or real efficiency ranking is justified.

Reproduction:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_evolution1_toy_loop.py --demo
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 scripts/run_evolution1_toy_loop.py --check
PYTHONDONTWRITEBYTECODE=1 python3 scripts/audit_evolution1_adapters.py --check
```

`--demo` prints JSON without writing or overwriting files. `--check` passed,
matching the full saved payload and source hashes against both current bytes and
the recorded implementation commit. The source-only adapter check also passed.
The raw artifact retains every training attempt and journal, all typed budget
charges, gate outcomes and incumbent/archive transitions, rather than summaries
alone. The scalar-lookup counts40/18 include the withheld-feedback run.

The consistency review checks expected proposal counts against the resource
plan, immutable history bindings, development-counterfactual invariance, no
assessment type in policy updates, failed/duplicate charges, negative gate
outcomes and rollback tests. This was a source/reproduction audit in this task,
not an external scientific evaluator or OS-isolation test. All scientific
execution counters and the preserved session ledger remain unchanged.
