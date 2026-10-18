# NEXUS Evolution-2 — Independent Scientific Readiness Audit

Status: **source-only audit**. Not a scientific result. Not an allocation.
Not learning-to-learn or AGI.

Auditor role: independent research auditor, meta-learning scientist, and
RL systems engineer. This review inspects committed Evolution-2 source,
tests, and governance. It does not train models, roll out environments,
select scientific holdouts, or debit the session ledger.

Branch: `cursor/evolution2-independent-readiness-audit`  
Audited Evolution-2 HEAD: `03c776c7239fea0e61d60e61ce26702da8990da5`  
Parent results: Evolution-1 `96c71ae297e6329517d4afb4d3bad50162832c21`  
Implementation ancestor: `f4de1e135dd88ee18ef7a6b05a42c70df917d00e`

**Readiness verdict: BLOCKED**

The synthetic contracts work. They do not authorize, and cannot yet
support, a scientifically valid cross-family test that previous-task
experience improves discovery of useful planning algorithms on unseen
task families.

Scientific ledger remains **305.842 s used / 3294.158 s remaining**.
This audit must not, and did not, change it.

---

## Provenance

Verified on 2026-10-18 before the audit branch was created:

| Location | `cursor/evolution2-cross-task-screen` @ `03c776c` |
|---|---|
| Local | present. Working tree dirty only with unrelated untracked Evolution-1 adapter files, which were preserved and not committed here. |
| Cursor Origin (`origin`) | present at the same SHA. |
| GitHub (`github` / `ajayghimire9-bit/nexus-ai`) | **absent at first inspection** (`git ls-remote` returned no ref). Pushed normally, no history rewrite. GitHub now reports the same SHA. |

The audit branch was created from that verified HEAD. No merge to
`main`. No force push. H12–H17 artifacts, Evolution-1 results, and
Evolution-2 historical illustration files were not modified.

---

## 1. Source-verified findings

Reported Evolution-2 claims were checked against
`src/nexus/evolution2/{tasks,methods,screen}.py`,
`src/nexus/evolution1/toy_loop.py`, and
`tests/test_evolution2_cross_task_screen.py`.

### 1.1 Claims that are source-true as synthetic contracts

| Claim | Verdict | Evidence |
|---|---|---|
| Feedback-dependent proposal changes | **Supported** | `AdaptiveProposer._learn` updates `w ← w + 0.5*(y−w·x)*x/(x·x)`. Withholding `update()` leaves weights at zero and later choices identical. After one `successor_scale` task, persistent `choose()` on a `horizon_scale` context differs from reset. |
| Persistent weights reused across tasks | **Supported** | `PersistentAdaptive` keeps one `AdaptiveProposer`. `freeze()` stores weights, update count, and tie ranks. Eval clones copy that snapshot. `reset_task()` is a no-op. |
| Positive transfer on an authored related family | **Supported as a seed-7 illustration** | Aligned split (`successor_scale` → `successor_dev`) yields `persistent_minus_reset_dev_mean > 0` using the default **mean** score, not best-score. |
| Negative transfer on an inverted family | **Supported as an authored counterexample** | Same frozen weights have lower mean than reset on `inverted_successor`, whose hidden vector `(0.40, 0.05, −0.40, −0.35)` punishes the remaining high-horizon balanced successor arms. |
| Passing source-only tests | **Supported, count stated exactly** | Evolution-2 ships **11** tests. Independently re-collected Evolution-1 toy loop: **24** items (parametrized). **11 + 24 = 35**. That is the reported suite total, not 35 scientific replications. This audit adds **13** source-only checks. |
| Zero scientific execution | **Supported** | `SCIENTIFIC = False`, `MODE = 'synthetic_only'`, `future_protocol()['resource_caps']['real_env_steps'] == 0`, `scientific_ledger=False`. H16 ledger file hash unchanged (`96be8b401a06f48e8eab190058f58a82f6dc1f2eebc6c2fe46f31da1e4bc4625`). |

These demonstrations are **synthetic contracts**. They are not evidence
that NEXUS learned to improve its algorithms.

### 1.2 What the implementation actually does

- Catalogue: 12 fixed planning configs (`Rule` × `Generator` × `{4,8,16}`).
- Proposals per task: 4. Slots 0–1 are forced Evolution-1 anchors
  (IID flat H16, IID successor H16). Slots 2–3 are the only free choices.
- Features: `x = (1, S, B, h, S*O/16, h*A/16)`.
- Update: one-step normalized linear SGD, `y=0` on explicit failure.
  Weights start at zero. Tie-break is a shuffled catalogue rank.
- Methods: fixed, random, reset-adaptive, persistent-adaptive,
  evolutionary mutation. No retrieval / guarded-memory / similarity method.
- Default split: 6 train + 2 development + 2 shifted tasks; holdout
  family generated then excluded. 40 synthetic lookups per method.
- Persistent training updates: 24 (6 tasks × 4 receipts). Frozen eval
  does not write the global vector.
- Scores: authored linear functions of `(S, B, h)` plus a tiny instance
  offset. Explicitly not H12–H16 returns.

### 1.3 Capability distinctions (must not be conflated)

| Capability | Present in Evolution-2? | What would count |
|---|---|---|
| 1. Memory of previously successful configurations | **No dedicated method.** Persistent weights are a linear preference, not a stored winner table. | Retrieval of prior winning fingerprints, optionally gated by task similarity. |
| 2. Within-task adaptive search | **Yes, by construction.** `ResetAdaptive` learns inside a task and discards weights. Local eval updates are a separate flag. | Beat equal-budget random/evolution on the *same* task after its own feedback. |
| 3. Transferable improvement in the proposal policy | **Contract only.** Persistent weights change later `choose()`. On authored related tables, mean score rises; on inverted tables, it falls. | Frozen persistent policy beats reset, random, fixed, evolution, *and* retrieval on a new family, with family-level independence. |
| 4. Genuine algorithm discovery | **No.** The catalogue is closed. No new operator, horizon, or update rule can appear. | LEVEL 3: a new planning operator that was not in the 12-arm vocabulary and that independently outperforms incumbents. |

A better weight vector over a fixed catalogue is **not** algorithm
discovery. Persistence of that vector is a **LEVEL 2 candidate**, not
LEVEL 3 or LEVEL 4, and not learning-to-learn.

---

## 2. Scientific validity concerns

### 2.1 Task generation and family leakage

`successor_dev` hidden weights `(0.21, 0.33, 0.07, 0.11)` are within
0.03 of training family `successor_scale` `(0.20, 0.36, 0.06, 0.10)`.
`holdout_horizon` is likewise a near-copy of `horizon_scale`. Public
`(O, A)` differ; the scoring rule does not.

Instance 0 versus instance 1 only adds a constant offset. **Ranking
inside a family is identical.** Two instances are not independent
family-level replications.

The default mixed train set (`successor_scale`, `horizon_scale`,
`balanced_scale`) teaches conflicting linear preferences, then
evaluates on a successor-like development family. That can wash
transfer. The published “helps” illustration therefore uses a
**non-default aligned split**. Selecting the split after seeing that
the mixed screen is weaker is acceptable for a contract, not for a
locked scientific protocol.

### 2.2 Hidden bias favoring the adaptive policy

`hidden_score` is exactly

`clip(w0 + ws·S + wb·B + wh·h + offset·(instance+1))`.

The proposer’s first four features are `(1, S, B, h)`. The oracle
lives in the same linear span the SGD rule can represent. Context
features `(S·O/16, h·A/16)` are unused by the oracle. This is not a
neutral lookup table. It is an **aligned linear teacher** for this
exact update.

A random or evolutionary method that cannot represent that teacher
is structurally disadvantaged. A retrieval method that stored the
winning config would also do well, and is not implemented.

Hidden weights were chosen so persistence helps on the related family
and hurts on the inverted family. That is a valid contract
counterexample. It is not an independent sample from a task
distribution.

### 2.3 Proposer updates, persistence, and frozen eval

The update equation is correctly implemented and deterministic.
Concerns:

- Only two free observations per task after shared anchors. Both
  adaptive methods see the same two anchor receipts first.
- `ResetAdaptive.reset_task()` preserves tie-rank and RNG state while
  zeroing weights. That is fairer than reshuffling ties, but later
  free choices still inherit the training-time tie permutation.
- `PersistentAdaptive.eval_clone()` constructs `PersistentAdaptive()`
  with default seed 7, then overwrites weights. Fine at seed 7; a
  different training seed would still spawn a default-seed shell.
- Frozen eval (`local_updates=False`) compares transferred weights
  against **zero weights plus tie order**, not against a within-task
  learner that is allowed to adapt on the new family. The
  `local_updates=True` flag exists, but the illustration uses frozen
  eval. That comparison attributes any mean gap to persistence, which
  is correct for “does memory change choices,” weaker for “does
  memory beat within-task search on a new family.”

### 2.4 Candidate selection and tie-breaking

Adaptive `choose` maximizes `w·x`, then `-tie_rank`. Fixed maximizes
`(horizon, flat, IID)`. Random uses `Random.choice`. Evolutionary
returns `available[0]` until a parent exists, then mutates one axis
and falls back to `available[0]` after eight misses.

`available[0]` is catalogue order (flat/IID/H4 first), not a scored
or diverse start. This is **not** an equal-competence evolutionary
search baseline. It is a weak mutator charged four lookups.

### 2.5 Actual feedback observations

Default screen, persistent arm:

- 24 training receipts (global writes).
- 8 development + 8 shifted receipts to eval clones only.
- 0 global writes after `freeze()`.
- 40 lookups, matched across methods.

That is a tiny observation budget for claiming a transferable
proposal policy. Two free choices per task cannot identify a six-
dimensional linear model. Cross-task persistence is doing most of
the statistical work — on oracles that share that six-dimensional
span.

### 2.6 Synthetic oracle isolation

`hidden_score` is not an `update()` argument. Proposers accept
`TrainingFeedback` only. That contract holds.

Isolation is **not** a process or API boundary. `FAMILY_SPEC` and
`hidden_score` are ordinary importable Python. `public_view()` omits
hidden weights but includes `role` (`train` / `development` /
`shifted` / `holdout`). Methods currently receive `context`, not
`public_view`, so role leakage is latent, not used.

Evolution-2 does **not** reuse Evolution-1’s `FixtureBroker`,
`ReservationLedger`, `DevelopmentGate`, or promotion/rollback
harness. Evaluator integrity is weaker than the Evolution-1 toy loop.

### 2.7 Random baseline fairness

`StatelessWrapper.eval_clone` returns `self`. Random’s RNG therefore
continues from training into development and shifted tasks. That is
one shared stream, not independent per-task evaluation seeds.
Fixed is deterministic, so identity sharing is harmless.

### 2.8 Resource charging

Matched lookup counts are enforced (`unmatched_lookup_budget`).
There is no measured CPU, no real-step meter, no imagined-transition
meter, and no reservation-before-call. Evolution-1 already showed
that post-call quotas are insufficient. Evolution-2 counts Python
loop iterations.

### 2.9 Metric and statistical rules

`run_screen` reports `transfer_benefit(..., key='mean')` by default.
`future_protocol()['primary']` is
`mean_over_dev_instances(best_persistent - best_reset)`.
The implemented illustration and the proposed scientific primary
**do not match**.

`classify_transfer` accepts `n >= 1`. A one-instance interval can be
labeled `e2_persistence_helps_transfer`. The proposed `n=10`, `df=9`
rule is not enforced.

No confidence interval is computed on the illustration (`n=2`
instances, ranking-identical).

### 2.10 Negative-transfer counterexample

The inverted family is a real design contribution: persistence can
hurt. It is still authored. Detection, relevance estimation, and
selective reset are **not implemented**. There is no comparison to
reset-on-failure.

---

## 3. Fair baseline specification (design only)

Do not execute this screen from this audit.

### 3.1 Question

Can experience from previous **task families** improve NEXUS’s
ability to propose useful **already-defined** planning configurations
on an unseen family, compared with, and distinguished from:

1. remembering winning configurations,
2. adapting inside the new task,
3. transferring a proposal preference,
4. inventing a new operator (out of scope; catalogue stays closed).

A positive result would be **LEVEL 2 proposal-policy transfer**, not
genuine algorithm discovery.

### 3.2 Methods (equal accounted budget)

| ID | Method | Memory | Must receive |
|---|---|---|---|
| A | Fixed planner | None | Same anchors + same two free slots, ignored feedback. Lock the rule: highest feasible horizon, then flat, then IID. |
| B | Equal-budget random | None | Independent per-task RNG. Do not share the training stream into eval. |
| C | Memory-reset adaptive | Within-task only | Zero weights at each new task; local updates allowed on that task’s receipts only. |
| D | Persistent adaptive | Cross-task weights, frozen before development | No development/shifted writeback to the global vector. Optional local clone updates as a **secondary** analysis, not the primary. |
| E | Equal-budget evolutionary search | Within-task population / parent only | Start from a scored or random parent, not `available[0]`. Persist no fitness across tasks. Same 4-proposal cap. |
| F | Guarded-memory / similarity retrieval | Store `(public context, winning variant, score)` | Retrieve nearest stored winner only if a predeclared similarity gate fires; otherwise fall back to C. This separates retrieval from a learned proposal policy. |

Every method: same catalogue, same public context, same 4 proposals,
same two shared probes, same receipts for proposed arms only, same
real/imagined/CPU caps. Persistent memory is the only extra state
for D. Retrieval memory is the only extra state for F.

### 3.3 Smallest meaningful real environment set

Do not treat extra seeds of one simulator as extra families.

Smallest set that could support a **family-level** claim:

- **Train families (2):** Pendulum and Acrobot. Different observation
  layouts, action kinds, reward symbols, reward timing, and root-
  survival rules (Evolution-1 adapter review).
- **Development family (1):** discrete MountainCar, new unused
  physics, not a Pendulum seed and not a closed MCC holdout.
- **Untouched holdout family:** reserved, **not chosen in this
  audit**. Do not use H12–H16 confirmation physics, unused MCC
  `(0.0015, 0.0014, 0.055)` from H16, or any registered exclusion.

That is three families. Two would be the absolute floor (train on
Pendulum, develop on Acrobot), but then there is no separate
negative-transfer family. A fourth shifted family should be
specified only after adapters and meters exist, and only from a
predeclared unused pool — not by peeking at outcomes.

Independence unit: **independently trained world-model + search-seed
bundle**, `n=10`, Student-t 95%, `df=9`. Episodes, candidate
trajectories, and student seeds sharing a decoder are not extra
replications.

### 3.4 Frozen-planner alternative if training is infeasible

If new model training cannot fit the standing caps, the only honest
smaller test is:

> Evaluate the 12 catalogue variants using **independently frozen,
> genuinely evaluated planner outcomes** that were collected under a
> locked evaluator for a purpose other than this screen, on physics
> that remain unused and unexcluded.

This audit found **no such complete unused grid**. H12–H16 returns
must not be recycled as success labels. Fabricating labels is
forbidden. Therefore the smaller test still requires **new
authorized collection** after adapters and meters exist. It is not
available today.

Existing source-family checkpoints may be **read** for integrity
hashes. They may not be reused as teachers or label oracles for
held-out families. Context-checkpoint loading was already listed as
unverified in the Evolution-1 adapter review.

---

## 4. Negative-transfer assessment (design; do not implement from hidden outcomes)

Persistence can hurt. The inverted synthetic family already shows
the qualitative failure mode: transferred `w` keeps proposing arms
the new oracle punishes.

Compare any future guard to a **reset-on-failure baseline**:

> After the two shared probes on a new task, if the persistent
> policy’s mean receipt is worse than the reset (or random) policy’s
> mean on those same probes by a predeclared margin, discard `w` for
> the rest of that task and behave as C.

That baseline is simple, predeclarable, and does not require a
similarity model.

One bounded additional method, specified now, not tuned later:

1. **Relevance.** Maintain per-family snapshots
   `(public context centroid, frozen w, probe residual mean)`.
   On a new task, compute distance between the new public context
   `(O, A, episode_steps, imagined_cap)` and stored centroids.
   If minimum distance exceeds a locked threshold, do not load any
   snapshot; start from zero (C).
2. **Disagreement.** On the two shared probes, compute
   `r = y − w·x`. If both residuals have the same sign and
   `|mean(r)|` exceeds a locked threshold, mark the snapshot
   irrelevant for this task.
3. **Reduce or reset.** If irrelevant: shrink `w ← (1−λ)w` with
   locked `λ∈{1}` first (full reset; the strongest, cheapest guard).
   Partial shrink is a later competitor, not the first screen.
4. **Preserve.** Never overwrite other families’ snapshots when
   resetting the current task. Write back a family snapshot only
   after that family’s own training block, never after development.

Primary comparison remains D versus C. Secondary: D+reset-on-failure
versus D-blind versus F. Do not add guards after seeing holdout
outcomes. Do not implement this method in the present audit.

---

## 5. Exact proposed resource budget (not allocated)

Standing limits that bind any later request:

- 900 s wall per experiment
- 100,000 new real-environment interactions per experiment
- 3,600 s session; **3,294.158 s remain**
- local CPU only
- no paid services
- H17 still blocked for new scientific seed registration

### 5.1 Full model-and-search screen (family-level, n=10)

Using Evolution-1 feasibility arithmetic, not new measurements.

| Quantity | Estimate | Notes |
|---|---|---|
| Independent training runs | 10 bundles × 2 train families = **20** models | Residual 2×64 class, ~5k parameters. |
| Real environment steps | **≥ 200,000** if 10×5 methods×(4 train + 2 dev) tasks×4 proposals×200-step episodes | Exceeds 100,000. E1 full-study figure was 206,400 even before a fifth/sixth method. |
| Imagined transitions | **10^8 order** if H=16 / 1536 cap on every proposal | E1 planning-alone extrapolation ~612 s for 1.1×10^8. |
| Model training | 20 models × ~20 epochs on ~1k transitions | Cheap relative to planning; not free. |
| Proposal attempts | 10 × 6 methods × 6 tasks × 4 = **1,440** | Matched. |
| CPU / wall | Planning-dominated; **likely > 900 s** if H=16 is used throughout | E1 said a 900 s cap may yield `incomplete_budget`. |
| Storage | tens of MB for logs + ~0.4 MB raw weights; checkpoints outside Git | Integrity manifests required. |

**This design cannot be authorized under the standing experiment
limits.** Splitting into sequential jobs to evade the 100,000-step
cap is not allowed.

### 5.2 Smaller frozen-model, short-episode screen (still not authorized)

If, after adapters exist, one frozen source model per train family is
separately authorized and planner configs are scored on **one 16-step
prefix** rather than 200-step returns:

| Quantity | Estimate |
|---|---|
| Real steps | 10 × 5 × 6 tasks × 4 proposals × 16 ≈ **19,200** |
| Imagined | 10 × 5 × 6 × 4 × 256 (H=4) ≈ 3.1×10^5, or ×1536 (H=16) ≈ **1.8×10^6** |
| Model training | 0 new, if reuse is separately justified |
| Proposal attempts | 1,200 (5 methods) or 1,440 (6) |
| CPU / wall | uncertain; possibly inside 900 s if imagined stays near 10^6 |
| Independent runs | 10 search seeds on shared frozen models — **this weakens the independence unit** |

Even this reduced screen is blocked today: no executable adapters,
no meters, no unused independently evaluated outcome grid, H17
blocked, and prefix return is not the same scientific target as
episode return. It is recorded so a later grant can choose
consciously. It is **not** an allocation.

### 5.3 What this audit consumed

| Quantity | Amount |
|---|---|
| Real environment steps | 0 |
| Imagined transitions | 0 |
| Model training / inference | 0 |
| Scientific proposal attempts | 0 |
| Scientific ledger | **unchanged** 305.842 / 3294.158 |
| New holdouts | none |
| Storage added | this document, one test module, status pointers |

---

## 6. Feasibility under current limits

| Screen | Standing 900 s / 100k / local CPU | Scientific validity | Feasible now? |
|---|---|---|---|
| Current synthetic illustration | Yes (unit tests only) | No — aligned authored oracles | Already run as a contract. Not science. |
| Frozen unused planner-outcome grid, no new collection | Yes | No complete unused grid exists; H12–H16 labels forbidden | **No** |
| Frozen-model 16-step catalogue screen | Possibly, if adapters/meters exist | Weak independence; prefix ≠ episode; still needs unused physics | **No — gates missing** |
| Full n=10 family-level model+search | **No** — exceeds 100k and likely 900 s | Would be the first design that *could* speak to LEVEL 2 | **No — over budget and gates missing** |

A design that exceeds standing limits is not authorized by this
audit and cannot be treated as the next automatic experiment.

---

## 7. Remaining blockers

Critical boundaries. None is waived.

| Gate | Exact blocker |
|---|---|
| Real task adapters | Evolution-1 adapter review verdict **BLOCKED_RUNTIME_GATES**. Family inference from `obs_dim`/`n_actions` is unsafe. Root survival and reward timing differ by family. Untracked `src/nexus/evolution1/adapters.py` is **metadata / plan-preview only**; `runtime_ready` is hard-False and `require_runtime()` raises. Balanced generators are not implemented. |
| True resource metering | Evolution-2 charges lookup counts. Evolution-1 `ReservationLedger` is unused. No process CPU meter, no pre-call real/imagined reservation on the Evolution-2 path. |
| Checkpoint integrity | No Evolution-2 checkpoint protocol. Historical world-model binaries are not rehashed here. Context-checkpoint loading remains an unverified fail-closed item from the adapter review. |
| Evaluator isolation | Oracle and hidden weights are importable. No OS/process isolation. No signed receipts. Evolution-1 broker/journal/gate not wired. |
| Hidden-data leakage | Linear oracle in proposer features; near-copy families; `role` in `public_view`; holdout object exists in `default_split()` even though `run_screen` refuses to consume it. |
| Promotion and rollback | Evolution-2 has no incumbent/candidate promotion harness. A higher mean on a synthetic table cannot become a new controller. |
| Exclusion registration | H17 remains **BLOCKED_INCOMPLETE_EXCLUSION_COVERAGE**. New scientific seeds/physics cannot be registered from this audit. Closed H12–H16 splits stay closed. |
| Independent one-run authorization | `future_protocol()` is `authorized=False`, `locked=False`, `executed=False`. No configuration hash, no allocation record, no consumed-or-fresh one-run grant for Evolution-2. The standing coding grant does **not** cover a real multi-family screen that exceeds caps or lacks adapters. |

---

## 8. Independent evaluation rules (for a future locked protocol)

Specified now so later work cannot shop a metric.

**Single primary hypothesis.** On a predeclared unseen development
family, the mean over `n=10` independent model+search bundles of
`(best score in 4 proposals under persistent adaptive − best score
under memory-reset adaptive)` is positive, with a Student-t 95%
interval entirely above 0, and the persistent arm also at least
matching the predeclared practical margin versus random and versus
guarded-memory retrieval.

**Primary metric.** Mean bundle-level best-score difference
`D = best_D − best_C` on the development family only. Report A, B, E,
and F as required baselines. Do not promote on mean-of-four if the
locked primary is best-of-four.

**Independence unit.** One independently trained world model plus one
search seed. Not episodes. Not shared-decoder student seeds.

**Families.** Train: Pendulum + Acrobot, new unused instances.
Development: discrete MountainCar, new unused instances. Holdout
family: reserved and unnamed until a later independent review. No
H12–H16 physics. No H16 unused MCC tuple.

**Frozen protocol / selection.** Lock hashes, split, catalogue,
proposal count, meters, and labels **before** any real collection.
Development outcomes never update global `w`. Do not retune on
development and then “confirm” on the same family.

**Confidence interval.** Student-t 95%, `df = n−1 = 9`. Require
`n=10` complete bundles. `n<10` is `incomplete`, never a help/hurt
label.

**Labels.**

- `e2_persistence_helps_transfer` — mean `D>0` and interval above 0
  and persist is not worse than random or retrieval by the locked
  margin.
- `e2_persistence_hurts_transfer` — mean `D<0` and interval below 0.
- `e2_transfer_not_established` — interval includes 0, or persist
  beats reset only by retrieving remembered configs (F wins).
- `incomplete` — cap hit, adapter failure, meter failure, or `n<10`.

If F (retrieval) matches or beats D, label the result as **memory of
configurations**, not transferable proposal-policy improvement.
If C with local updates matches D, label it **within-task search**,
not LEVEL 2 transfer.
If a new operator appears, that would be LEVEL 3 and is not this test.

**Preventing repeated holdout selection.** Name at most one
development family before collection. Archive the unused pool.
A failed development family cannot be recycled as a new confirmation
for a revised selector. The untouched holdout stays untouched until
a later, separately reviewed lock.

---

## 9. Readiness verdict

**BLOCKED**

Not CONDITIONAL: the missing pieces are not optional polish. Without
trusted adapters, real meters, evaluator isolation, exclusion
closure, and a budget that fits standing limits, a “real cross-task
screen” would either be scientifically invalid or unauthorized.

Not PASS: the synthetic illustration is working software and honest
about being synthetic. Honesty does not make it ready.

What Evolution-2 **did** establish, and only this:

- The persistent-versus-reset API can be written, frozen, and tested.
- Authored related tables can make persistence look helpful.
- Authored inverted tables can make persistence look harmful.
- That pair is a necessary contract, not LEVEL 2 evidence.

---

## 10. One next engineering milestone

**Implement and test trusted, metadata-bound family adapters plus
pre-call real/imagined/CPU meters and a process-isolated evaluator
stub — source-only, no scientific collection.**

Justification: every scientifically valid screen above is blocked
first by those runtime gates (already named
`BLOCKED_RUNTIME_GATES` in the Evolution-1 adapter review), then by
budget. Building adapters after peeking at a cheap invalid screen
would invert the research order. Keep the catalogue closed. Keep
H17 blocked. Do not lock a protocol, allocate budget, or choose a
holdout in that milestone.

Success of that milestone is still not LEVEL 2 transfer.

---

## Tests added by this audit

`tests/test_evolution2_independent_readiness_audit.py`

Source-only / deterministic checks:

- closed H16 ledger file still 305.842 / 3294.158 and hash-stable
- Evolution-2 sources still declare synthetic-only / H17 blocked
- feedback dependence and persistence
- authored help/hurt illustration is unlabeled science
- oracle lies in the proposer feature span
- development/holdout families are near-copies
- instance offset does not change ranking
- only two free proposals
- mean-versus-best metric mismatch; `n=1` can be labeled “helps”
- random eval-clone identity leak; evolutionary `available[0]`;
  no retrieval baseline
- Evolution-2 does not meter or isolate like Evolution-1
- 24 training updates / 40 matched lookups
- no scientific-stack imports

No model, simulator, or ledger debit.

---

## Reproduction

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:.deps python3 -m pytest \
  tests/test_evolution2_cross_task_screen.py \
  tests/test_evolution2_independent_readiness_audit.py \
  -p no:cacheprovider
```

Do not run a scientific experiment from this branch.
