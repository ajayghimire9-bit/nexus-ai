# Sequential consistency selector: source screen FAILED

Branch: `codex/seed-sequential-consistency`. Starting revision:
**fb0ae7457a04bd06db801bb2c2af71a3a201b1a1**, matching the fetched GitHub base.
Tested implementation and [protocol](NEXUS_SEED_SEQUENTIAL_CONSISTENCY_PROTOCOL.md)
were committed at **24579015a3e9f476d0ee8caa2f18881f3a6773b8** before the single run.
[Executable configuration](../configs/seed_sequential_consistency.json),
[raw results](../artifacts/seed_sequential_consistency.json),
[verification receipt](../artifacts/seed_sequential_consistency_verification.json).
Raw SHA256: `10bfc72819c38d4b558d6939bb0bdcc40e48ebac9af5eedd0539ee3d46c6344f`.

## Question and boundaries

Does the frozen consistency-only utility predictor's uncertain local-regret
advantage survive actual sequential learning? Unlike the preceding audit's
fixed full-update reference states, this experiment recomputes support-only
features from each policy's current fit after its own update/retain decisions.
The full-feature audit's failure remains unchanged; the consistency group is
an explicitly selected exploratory lead, not a replacement primary outcome.

Use the original twelve source tasks, four folds with nine training and three
excluded tasks, and the saved source-fitted predictors, normalization, damping
coefficients and protection bounds. No predictor is fitted here. At each prefix
the candidate assimilates all observed labels and old anchors using the existing
cumulative residual solve. The consistency predictor either takes the full
candidate or retains the current fit; query and retention labels are evaluator-only.
All seven methods see the same teaching prefixes and evaluator rows. Three saved
constant-damping fits are executed separately and averaged within each task.

This is reused-source development, not fresh validation or a control test.
There is ONE frozen feature extractor. Twelve task clusters, overlapping
training folds and three damping fits do not create independent world-model
replications. No live adapter, runtime policy or historical checkpoint changed.

## Registered outcome

Complete, finite execution; **source screen FAILED**. Mean query MSE over
1/2/4/8 examples, lower is better:

- Consistency selector: **.201847528**.
- Prefix-mean selector: .189899377.
- Trained constant damping: **.180187275**.
- Feature-scaled replay: **.187016215**.
- Bounded fixed protection: .184388324.
- Full unit cumulative updates: .189456479.
- No adaptation: .200636930.

The consistency selector is12.02% worse than constant damping,7.93% worse than
replay and9.47% worse than bounded protection. It beats damping in only1/4 fold
means, below3/4. The registered5% improvement conjunction fails. Its error is
also .60% above no adaptation as a point estimate.

Reference-minus-selector differences, positive favors the selector; exploratory
paired task-level95% intervals:

- Constant damping: **−.02166025 [−.05193234,+.00861183]**.
- Replay: **−.01483131 [−.03078809,+.00112547]**.
- Bounded fixed: −.01745920 [−.03807150,+.00315309].
- Unit cumulative: −.01239105 [−.05357002,+.02878792].
- Prefix selector: −.01194815 [−.05611705,+.03222075].
- No adaptation: −.00121060 [−.01028114,+.00785994].

These intervals include zero. The practical screen fails, but the data do not
establish population-level harm. Intervals are conditional on saved source fits
and the repeatedly inspected task bank, without correction for exploratory
selection. They are not confirmation intervals for unfamiliar environments.

At1/2/4/8 examples, query MSE is:

- Consistency: **.199184 / .199212 / .204303 / .204691**.
- Constant damping: .195193 / .179183 / .173685 / .172688.
- Replay: .196656 / .190058 / .182187 / .179164.
- Bounded: .187813 / .175627 / .197112 / .177001.
- Unit cumulative: .226568 / .176015 / .179949 / .175294.
- Prefix selector: .225940 / .176015 / .182349 / .175294.
- No adaptation: .200637 at all budgets.

Fold means, consistency / constant / replay / bounded:

- Fold0: .245148 / .204966 / .226886 / .220415.
- Fold1: .161919 / .183361 / .160249 / .166542.
- Fold2: .216704 / .184469 / .204867 / .194826.
- Fold3: .183620 / .147953 / .156062 / .155770.

Final retention MSE .080683 versus constant .072084 passes the registered
constant+.01 tolerance, despite numerically worse retention by .008598.
Passing that tolerance is not evidence of zero forgetting. Replay is .078623,
bounded .066879, unit/prefix .077707 and no adaptation .082170. Raw records and
the GUI retain every task, prefix, fit replica and failure; none are omitted.

## What the decision traces show

The consistency selector takes only **11 of96** proposed updates; the prefix
selector takes54. Nine tasks never update. Nonzero consistency decisions are:

- Task95010000: prefixes1–4; its curve error exceeds no adaptation by .040068.
- Task95080000: prefixes2–3; curve error exceeds no adaptation by .000032.
- Task95090000: prefixes1–5; curve error improves on no adaptation by .025573.

Retaining task95050000 avoids a large damping error (.077161 versus .148310),
but the same retention behavior misses gains on95020000 (.326126 versus .229832)
and95110000 (.224316 versus .143186). No single aggregate hides these tradeoffs.

Post-hoc stored-vector comparison: first-prefix predictions reproduce the
preceding reference audit exactly on all twelve tasks. On its full-update
reference states, the frozen predictor would apply53/96 updates; sequential
decisions differ in42 cases. Thus later learner-state inputs differ after
retention, with much more conservative decisions. This is compatible with
induced-state distribution mismatch. It does not isolate that mechanism from
the binary action set, myopic utility labels or task heterogeneity, and does
not prove refitting will help. No outcomes were used to change this run.

All **84 recomputed baseline trajectories** reproduce their parent's fit vectors,
query MSE and retention MSE exactly (maximum difference0). This includes all
36 constant-damping replicas and twelve each of replay, bounded, unit and none.
The failure is therefore not explained by an accidental change to those baselines.
The frozen selector does not establish useful learning-to-learn improvement.

## Execution and reproducibility

One host dispatch: **1.986353s** wall, .423006s worker-body wall,1.210119s worker
process CPU,285.67MiB peak sampled RSS. Limits30s wall/CPU and2048MiB sampled
RSS, CPU only. macOS sampling is not kernel-hard memory enforcement.
Conservative debit3s; carried ledger **1939.6321034559958s used /
1660.3678965440042s remaining**. Tests and read-only replay are reported separately.

Executed108 trajectories,972 snapshots,864 inner residual updates,108 initial
solves,576 cumulative solves,96 consistency calls,96 prefix calls and96 feature
constructions. There are36 constant-scalar reads,432 normalization row appearances,
864 teaching presentations,432 initialization-anchor rows,2592 cumulative-support
and2304 cumulative-anchor appearances. Query and retention each have26244
executed scalar row scores. Existing replay/protection counters are saved too.
Equal label budgets do not mean equal computational cost.

**Zero** new environment interactions, imagined transitions, frozen-world-model
forwards, predictor fits or outer optimizer updates. Cached source arrays are
reused; baseline arithmetic was executed rather than billed as cached execution.
No historical binary is required. All frozen state needed here is tracked JSON.
The report does not claim to have audited availability of every historical .pt file.

The receipt checks the clean execution source hashes, parent/config/protocol
hashes, reservation/settlement chain, raw/worker agreement, frozen state hashes,
historical artifact preservation and unrelated-work preservation. All764 historical
artifact files at the starting revision are byte-identical. Saved-trajectory
validation runs without Torch, NumPy, fitting or collection:

```sh
python3 -I -S scripts/verify_seed_sequential_consistency.py
```

Pre-execution focused checks:83 passed in21.96s; final pre-lock checks31 in4.54s.
Post-run saved-result/host checks70 in19.34s. Relevant regression suite:
**512 passed in54.29s** using:

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:/Users/ajayghimire/Projects/nexus-ai/.deps \
python3 -m pytest -o addopts='' -q tests/test_seed*.py \
tests/test_learning_lab_sessions.py tests/test_learning_lab_release.py \
tests/test_repository_layout.py tests/test_planning.py tests/test_expr.py \
tests/test_factory.py tests/test_evolution2_planner_quality.py
```

After documentation/navigation updates, focused sequential/saved/layout checks
passed40 tests in5.78s. The stdlib repository checker passed50 current documents,
196 local links and the preservation chain (2012 unchanged original files,
18 explicitly evolved paths). Git diff whitespace checks passed.

Tests cover evolving-fit feature math, future/query isolation, altered held-task
outcomes, frozen hashes, exact baseline reproduction, missing grids, corrupted
scores/predictions and stdlib fresh-clone verification. Chrome GUI passed8 checks:
failed-screen label, replication qualifier, seven conditions, curve, refresh,
mobile overflow, browser errors and immutable raw data. Screenshot visually
inspected at private `runs/seed-sequential-consistency-gui.png`. The Lab card is
read-only recorded evidence, not a new experiment or promotion.

## One next experiment, not executed

Compare **one bounded policy-roll-in refit** of the same small utility predictor
against an equal-budget reference-state refit. Build training-only utility cases
at states reached by the existing selector, retaining the same nine-source/
three-excluded folds,72 cases per training fit and strong damping/replay controls.
Keep excluded-task outcomes evaluator-only. This tests whether training-state
coverage contributes to the observed failure; one roll-in iteration is not
converged on-policy learning. Register its exact protocol before fitting. No
architecture growth, extra source collection or second scientific run occurred here.
