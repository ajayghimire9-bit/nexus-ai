# Learn, ask or retain: mechanism implemented; improvement screens FAILED

Branch `codex/seed-learn-ask-retain`; starting revision
**2f4e09a86b58b1b2dbe021cb1900790afeed992f**, matching fetched GitHub.
Protocol and tested code locked before execution at
**268589acd9429308022afc097379842dd37e6e76**.
[Protocol](NEXUS_SEED_LEARNING_CHOICE_PROTOCOL.md),
[configuration](../configs/seed_learning_choice.json),
[raw results](../artifacts/seed_learning_choice.json),
[verification receipt](../artifacts/seed_learning_choice_verification.json).
Raw SHA256: `278d9ce6b101eff24a5542af0a6745e33944aaafb1711595501ab16213837595`.

## Implemented behavior

The optional advisory uses a learned source-only update-utility predictor plus
an explicit check of proposed damage to observed memory anchors. It returns
**learn**, **ask**, or **retain**, with reasons, evidence and remaining budget.
Learn installs a cumulative residual correction. Asking or retaining leaves
the previous fit unchanged and keeps all revealed labels available for later
proposals. Asking emits a request for another labeled example; it invents no
answer and cannot exceed the available label budget. Decisions are immutable
records, and prior fit snapshots permit exact rollback.

This source experiment operationalizes asking as waiting for the next scheduled
example. It does NOT choose a more informative example or establish that asking
improves teaching efficiency. The finite concept questioner remains separate;
no new autonomous questioning policy is promoted into Session or the live agent.

Known-memory damage is measured on available initialization anchors, with total
MSE excess capped at .01. Those anchors are not the hidden retention set and
cannot guarantee preservation of all old knowledge. The utility error scale is
training residual RMSE, not a calibrated confidence interval. Protecting memory
and predicting beneficial learning are distinct problems.

Reuse: prefix_consistency support traces/features/ridge, cumulative posterior,
update_diagnosis trajectories/intervals, and the same EXPERIMENTAL host/worker,
ledger and Lab. Two backwards-compatible helper options support one selected
predictor fit and support-only policy roll-in. Original defaults remain exact.
No parallel memory, optimization, planning or resource framework was introduced.

## Controlled comparison and result

Four source folds, nine training and three excluded tasks each. Each refit gets
the same72 cases/fold, six features, ridge1 and source-only preprocessing.
Reference traces always apply full proposals; roll-in traces follow the OLD
frozen selector. Both are built without query access, then permitted training
queries label utility. New fitted policies are evaluated sequentially on the
excluded tasks. There is one roll-in pass, not iterative policy optimization.

Mean held-task query MSE over1/2/4/8 examples, lower is better:

- Reference-state refit: **.201847528**.
- Policy-roll-in refit: **.207066748**.
- Protected roll-in learn/ask/retain: **.210911036**.
- Cached constant damping: **.180187275**.
- Cached feature-scaled replay: **.187016215**.
- Cached bounded protection: .184388324.
- Cached unit cumulative: .189456479.
- Cached prefix selector: .189899377.
- Cached original consistency selector: .201847528.
- Cached no adaptation: .200636930.

**H-coverage FAILED:** roll-in is2.59% worse on average, although it wins3/4
fold means. Reference-minus-roll-in difference **−.00521922
[−.04533882,+.03490038]**. Task95050000 shifts from .077161 to .265407 and
dominates the negative aggregate. One refit did not demonstrate improvement;
this does not rule out training-state coverage as a contributing mechanism.

**H-protection FAILED:** protected error is1.86% above unprotected roll-in;
roll-in-minus-protected **−.00384429 [−.03114889,+.02346032]**. Only1/4 fold
wins. **Strong-baseline screen FAILED:** protected error is17.05% above
constant damping and12.78% above replay. Reference-minus-protected contrasts:

- Constant damping: **−.03072376 [−.05404637,−.00740115]**.
- Replay: **−.02389482 [−.03983058,−.00795906]**.
- Bounded protection: −.02652271 [−.04791582,−.00512960].
- Reference refit: −.00906351 [−.02433051,+.00620350].
- No adaptation: −.01027411 [−.02646239,+.00591418].

Positive differences favor the protected learner. These are unadjusted,
exploratory n12 task-cluster intervals conditional on ONE frozen core, overlapping
training folds and a repeatedly inspected source bank. They are not independent
world-model replications or fresh confirmation. Cached damping seed results
were averaged within tasks; three seeds do not multiply the statistical units.
Duplicated reference/original-selector results are not independent evidence.

At1/2/4/8 labels:

- Reference refit: .199184 / .199212 / .204303 / .204691.
- Roll-in refit: .225676 / .225705 / .195669 / .181217.
- Protected roll-in: .200637 / .212151 / .219077 / .211779.
- Constant damping: .195193 / .179183 / .173685 / .172688.

A better final-prefix roll-in point estimate does not replace the registered
learning-curve metric. Source RMSE scales rise from reference .026–.047 to
roll-in .036–.079. There was no threshold tuning after observing this result.

Fold means reference / roll-in / protected:

- Fold0: .245148 / .236031 / .245137.
- Fold1: .161919 / .227337 / .198183.
- Fold2: .216704 / .189726 / .216704.
- Fold3: .183620 / .175173 / .183620.

## Memory versus learning

Decisions: **4 learn,80 ask,12 retain**, across96 opportunities. Six asks and
three retentions arise from known-memory risk;74 asks and nine retentions from
uncertain benefit. There are no confident predicted-harm decisions. Only two
tasks receive updates:95010000 at prefix4, and95050000 at2/5/7. Ten tasks retain
their original fit throughout. Raw records preserve every decision and task.

All four installed candidates satisfy the observed-anchor cap. Final hidden
retention MSE is **.067612**, versus unprotected .077705 and constant .072084:
the registered retention tolerance passes. This numerical retention advantage
does not repair the new-task query failure or prove preservation everywhere.

Protected task95050000 has curve MSE .158896, better than unprotected .265407
but worse than reference/no-adaptation .077161 and constant .148310.
Task95020000 misses the unprotected gain (.326126 protected versus .247049
unprotected); task95090000 misses the reference gain (.220407 protected versus
.194835 reference). These patterns show the cost of overly conservative
decisions and imperfect benefit prediction; they do not identify a sole cause.
No live promotion or general learning-to-learn claim is justified.

## Integrity and cost

All four reference refits reproduce the original consistency coefficients
exactly. Their twelve sequential fit trajectories also match exactly. This
isolates the training-state change in the coverage comparison and checks the
two helper extensions. The seven cached conditions reuse verified prior
summaries;108 historical baseline trajectories are NOT billed as new execution.

One CPU dispatch: **2.284774s** wall, .859815s worker-body wall,1.591276s process
CPU,280.8125MiB peak sampled RSS. Caps30s wall/CPU,2048MiB sampled RSS; sampling
on macOS is not kernel-hard memory enforcement. Conservative debit4s. Carried
ledger **1943.6321034559958s used /1656.3678965440042s remaining**.

Eight new small ridge fits,576 training utility cases,72 training initial and
576 training cumulative solves;36 evaluation initial and288 cumulative solves;
324 evaluation snapshots.864 teaching-row presentations,39852 query and8748
retention scalar row scores. All are arithmetic on previously saved SOURCE
arrays. **Zero new real interactions, imagined transitions, frozen-world-model
forwards or Adam updates.** The eight ridge fits are new learning computation,
not zero training. No historical checkpoint was retrained or replaced.

The verification receipt records source/config/protocol/parent hashes, the
precommitted clean execution SHA, frozen-state equality, raw/worker/receipt
agreement, journal chain, historical artifact preservation and resource counts.
All767 historical artifact files at the starting revision are byte-identical.
Saved state and normal equations verify without Torch, NumPy, private binaries,
model fitting or new data:

```sh
python3 -I -S scripts/verify_seed_learning_choice.py
```

Focused pre-run tests passed100 in20.88s, then54 in6.66s after the final small
helper cleanup. The relevant regression suite passed544 in58.91s before that
cleanup; the post-run suite and saved-evidence tests are recorded in the receipt.
Final settled-file regression: **555 passed in65.24s**, including saved-result
tests and fresh-worker fixture isolation. The repository checker passes52 current
documents,204 links and the explicit preservation chain; whitespace checks pass.

Relevant regression command (no scientific experiment entry point):

```sh
env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:/Users/ajayghimire/Projects/nexus-ai/.deps \
python3 -m pytest -o addopts='' -q --tb=short tests/test_seed*.py \
tests/test_learning_lab_sessions.py tests/test_learning_lab_release.py \
tests/test_repository_layout.py tests/test_planning.py tests/test_expr.py \
tests/test_factory.py tests/test_evolution2_planner_quality.py
```

Toy tests cover useful updates as well as memory conflicts, rollback, finite
typed evidence, budget exhaustion, withheld labels, future labels, excluded
tasks and corrupt/missing cells. A fresh-clone replay requires tracked JSON,
not .pt files; an explicit missing parent fails rather than silently skipping.

An initial post-run regression exposed synthetic fixtures counting unrelated
earlier pytest process CPU against their worker cap. They now run in fresh
subprocesses, matching production. Neither the scientific worker nor its
resource meter, algorithms or recorded results changed, and no experiment was
rerun. A subsequent layout-only failure during current-document editing was
resolved by refreshing the explicit change receipt; all767 historical artifacts
remain untouched. Final outcomes are recorded in the verification receipt.

Chrome passed8 read-only GUI checks: honest screen labels, decision counts,
scope qualifiers, curve, strong comparisons, mobile layout, no browser errors
and immutable raw data. Screenshot inspected at private
`runs/seed-learning-choice-gui.png`. No simulation or live promotion occurred.

## One next scientific experiment, not executed

Test **informative question selection versus random question selection**, holding
the stronger constant-damping learner fixed and matching all label/compute
budgets. The present80 asks only wait for predetermined examples; they cannot
establish useful question choice. Register a separate teaching-only candidate
pool, keep answers hidden until requested, and assess future prediction on
independent query rows. This isolates whether asking can improve learning
without conflating it with another update-rule change. No additional experiment
or architecture search ran here.
