# E3.9 — Planner-evidence readiness review

## Scope declared before the audit

Starting revision: `7c09c082125e386575bc8675165ccadd59f2bad1`, matching
GitHub's E3.8 branch. Branch: `codex/e3-9-planner-evidence-readiness`.
Preserve the two unrelated untracked Evolution-1 adapter files. No new
scientific experiment, collection, neural inference, training, seed allocation,
or protocol lock is authorized by this document. Existing standing authority
covers this coding and source-only integrity work. The carried research ledger
stays 786.2472080430296 seconds used / 2813.75279195697 remaining.

Question: can the new planner-evidence interface support an auditable fresh
feedback study without leaking closed returns or understating computation?
E3.8's negative result stays closed. Do not fit another feature representation
to its 36 training pairs. This review does not test whether planner evidence
improves selection.

## Reuse and changes

Keep `AdvantagePredictor`, `StrategyGenerator`, `EpisodeContext`,
`planner_adapter.score_open_loop`, `RandomShootingMPC._score_batch`, and
`ReservationLedger`; no replacement learner, planner, memory or meter.
Keep `full_policy_source`'s locked historical profiles unchanged.

Two concrete issues corrected:

1. `StagedStudy` previously inferred its task/episode coverage from supplied
   cases. Removing a whole group could shrink its expected grid unnoticed.
   A registered real study now needs separately locked `planned_tasks` and
   `planned_episodes`, unique conditions, and an exact Cartesian case grid.
   Boolean authorization flags must actually be booleans; a real protocol
   revision must be a lowercase 40-digit SHA. The synthetic contract profile
   remains explicitly synthetic. The coordinator checks policy integrity
   immediately after each host call, before starting another case.
2. `planner_evidence` now snapshots proposals and the observation, provides
   read-only model inputs, and copies model outputs. A model that writes to
   these inputs fails, and its reserved work is not free. Operation names
   satisfy the existing ledger's ASCII constraints. These are trusted-code
   boundary checks, not protection against arbitrary hostile Python.

   The adapter also checks each reserved operation's model kind and imagined
   row count against the actual candidate batch before dispatch. A ledger
   planned for one row cannot silently meter a larger batch as one row.
   Declared neural-forward counts still require trusted-host verification.

Deterministic tests compare the recorded interface with the existing scorer:
scores within absolute tolerance 1e-12, relative tolerance 0; selected indices
must match exactly. FakeStepModel only. No equivalence claim for actual learned
checkpoints is made until a separately metered inference check runs.

## Integrity audit and reproducibility

`configs/e3_9_planner_evidence_readiness.json` pins the existing fit manifest,
source-array inventory code, and unregistered draft. The auditor reads only
file bytes, JSON metadata and the AST literal `LOCKED_ARRAYS`. It checks the
four expected Pendulum/Acrobot bundle0/1 checkpoint files and eight train/val
arrays against recorded hashes, with independent expected axes. It never
deserializes checkpoint binaries or arrays and never imports NEXUS runtimes.
Hash equality verifies bytes, not behavioral equivalence or model quality.

Run after committing implementation:

```
python3 scripts/audit_e3_9_planner_evidence_readiness.py --require-checkpoints
```

The output is exclusive-create; a requested audit with missing/wrong local
files exits nonzero and records the failure instead of silently skipping it.
Repository-only tests use synthetic files and do not need untracked binaries.
Historical artifact hashes are checked before saving the new audit artifact.

## Proposed compute accounting — not an allocation

The old draft's per-case cap 294,912 is 192 × 1,536 controller-imagined rows.
Two evidence sets of 16 candidates × H16 cost **512 extra rows and 32 model
calls** at every evidence decision. Reusing already available forecasts is
allowed only with an attested cache receipt and exactly matching sequences,
model/context fingerprint, observation and reward semantics. No free reuse is
assumed here. Actual neural forward counts must be verified, not inferred from
model-call counts.

An illustrative upper-bound grid of four existing source models, three
training plus four evaluation episodes/model, five conditions, eight shared
probe steps and 192 remaining steps would cost **27,104 real interactions**.
If every condition computes evidence at every remaining decision, controller
search costs 41,287,680 imagined rows, evidence adds 13,762,560, for a total
**55,050,240**; per-case combined cap **393,216**, not 294,912. Extra candidate
generation beyond the controller budget must also be charged. This is a
worst-case sizing illustration; no seeds or episode cases are registered.

The scientific design must choose evidence frequency before collection.
One-time selection after a common probe and per-step contextual switching are
different interventions. A comparison must disclose whether baselines receive
equivalent useful search opportunities under the same total budget, rather
than burn dummy calls to claim matched compute. No runtime is asserted from
this arithmetic; measure a separately registered small frozen-model check
before allocating a real study. Existing elapsed control clocks exclude this
new evidence path.

## Readiness decision and next milestone

Verdict: **BLOCKED_FRESH_STUDY_NOT_READY** even if every local file hash passes.
The real metered worker is not bound/reviewed; task/seed grids and independent
fit/evaluation roles are empty; evidence frequency, comparator compute,
analysis/success criteria and a configuration-specific allocation are not
locked. `StagedStudy` consumes trusted receipts but does not itself enforce a
process wall-time limit or prevent a dishonest callback's unmetered work.

Four models mean only two existing pretrained models/family, not ten new
independent replications. Fresh episodes cannot change that limitation.
Known-model means may use legitimate training feedback only; an unfamiliar
model requires a source-family prior, never a target oracle mean. E3.2/E3.4
evaluation outcomes, consumed E2.17 and H17 stay unavailable.

One next milestone: bind and audit a fail-closed metered host for a fixed
post-probe planner-evidence comparison, including proposal costs and an
isolated checkpoint-inference correctness check, before fresh collection.
Do not infer useful learning, control transfer or learning-to-learn from this
readiness review or passing engineering tests.

## Recorded outcome

Committed implementation/protocol: `6c440ab36aea703802c5d40650697579a5dc8379`.
Explicit `--require-checkpoints` audit exited 0: all **four checkpoint files
and eight source arrays** match. No checkpoint load or inference occurred.
All **368 prior research JSON files** retained their hashes; a separate
checksum replay reconfirmed them after writing the audit artifact. Verdict
remains **BLOCKED_FRESH_STUDY_NOT_READY** for the reasons above.

Artifact: `artifacts/e3_9_planner_evidence_readiness.json`, SHA256
`58a9c11758e0a13d09f68c35697374ecbad1b19c9755780436fae897a931c0f9`.
Configuration SHA256:
`cac784caee641719aa64ae542ce17ede04e9eb6b081356248434e8f97fc3fb21`.
The audit command took approximately 0.254 seconds as observed by the process
tool; this is engineering file inspection, not a scientific execution clock.
New scientific real/imagined transitions, neural inference and model training:
all zero. Carried scientific ledger unchanged.

Tests: the two-module focused run initially passed 37 tests in 1.33 seconds.
After adding the underdeclared-reservation check, the **27-module relevant
regression suite passed 503 tests in 10.72 seconds**. Exact module list and
invocation are recorded in `artifacts/e3_9_test_report.json`. This is not the
entire historical suite: the known legacy learned-inference benchmark was
excluded from this source-only task. No historical outcome was recomputed.
No new allocation, model/architecture change or success claim follows.
