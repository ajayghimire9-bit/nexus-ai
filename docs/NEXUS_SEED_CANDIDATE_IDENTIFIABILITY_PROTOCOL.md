# Saved-candidate identifiability audit

Base `a323805c1ec48e38442acb97718d0bd0db015f12` agrees with GitHub.
The attached older persistent-runtime request is already completed by v2.1;
this task does not rerun it. The owner's current equivalence/probe/cost decision
table governs this audit. Both completed studies remain closed and unchanged.

## Scope and hypotheses

Recover the nine recorded unresolved candidate sets. Possibilities: justified
normal forms explain their ambiguity; distinct programs need better probes;
or both kinds of resolution are cheap and this grammar lacks practical
discovery cost. A bounded unsuccessful witness search is **UNKNOWN**, never
proof of equivalence. This is a saved-source analysis, not a new learning study.

Reuse `discovery_headroom.Plan`, its grammar and vetted AST executor. Do not
modify the persistent runtime, baseline algorithm, previous artifacts or weights.
Two sound equivalence rules only: commutative operand ordering for addition and
multiplication; maximum followed by a >= threshold equals filtering by that
threshold before maximum. Keep other programs distinct unless an actual proof
is supplied. Existing grammar already incorporates those two rules.

## Reconstruction and information boundary

Config pins the raw/config/result hashes and exact nine case IDs. Reconstruct
survivors using only each public demonstration and already-selected probe
responses. Because historical raw data omit explicit response bodies, the
evaluator-side bridge recovers those old responses with the saved truth program
at **only the recorded queried inputs**. These are reconstructions, not new
teacher answers. Verify the recovered candidate counts against frozen records.
Neither assessment rows nor outcomes enter reconstruction or probe construction.

The probe constructor receives only surviving programs, column names, threshold
and declared bounds. It receives no true program, answers, case ID or assessment.
Program predictions on proposed inputs are hypothetical, not observed rewards.
No generated probe is submitted to a teacher or used to rescore the old tasks.

## Probe construction and endpoints

Use the legal integer range 0..15 from the preflight generator, with declared
boundary values 0,1,5,9,10,11,15. First try singleton rows, then equal pairs,
zero-mixed pairs, one-mixed pairs and different-group pairs in that fixed order.
This includes nontrivial grouped effects and threshold boundaries. At most 2048
input candidates (the enumerator itself contains 1715). Stop immediately when
every inequivalent representative has a unique predicted response. Ordinary
direct witness construction is allowed; no artificial minimum search.

Report a concrete separating input and each candidate prediction, remaining
partition sizes, actual program executions, construction time, reconstruction
cost and all failures. A full singleton partition guarantees discrimination
conditional on truthful answers and this finite candidate set; it is not an
observed learning improvement or user-answer accuracy.

The seven original request IDs are the descriptive primary units. Renamed/repeat
controls of task_02 are additional records, not independent replications. No
confidence intervals or generalization claim. Measure normal-form equivalents,
concrete differences and unknowns separately. No majority conclusion from the
three correlated versions of one request.

Apply the owner's decision table. If all seven resolve and median **recorded
discovery + added witness construction** is below the previous 10 ms practical
floor, recommend preparing a different practical task family. This sum is a
cross-run cost estimate, **not a new end-to-end timing trial**. Also report
new-construction-only time and total audit execution. Otherwise a majority of
proven equivalents suggests canonicalization; actual differences suggest probe
construction. Unknowns prevent claiming a resolved audit. These labels do not
upgrade either previous failed screen or authorize a learning study.

## Resources and integrity

One source-only run, 30 seconds CPU/wall, 1024 MiB sampled aggregate RSS, zero
new answers, simulator steps, neural inference or training. Use the existing
Sandbox/E1 host and existing process-tree meter, not a parallel resource system.
Carry **2188.632103455996 s used /1411.367896544004 s remaining**. Preserve
partials and do not retry. The inherited old v1 missing-debit gap remains.

Commit config/protocol/tested code before analysis. Save source/config/input
hashes, all recovered programs and witnesses. An independent arithmetic verifier
must reconstruct candidates and check witness predictions, partitions, complete
grids and summary values without calling the new witness constructor or the AST
executor. Changes to hidden assessment outcomes must not change constructed
probes. Saved-source evidence never becomes untouched confirmation.

No neural runtime/model changes, no library promotion, no main merge. Depending
on the result, prepare exactly one next task; do not automatically collect data
for another practical task family during this audit.

Pre-run targeted suite: **101 passed in 15.53 seconds**, using authored fixtures,
saved-result arithmetic checks and mocks. No registered audit run in pytest:

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:$NEXUS_LOCAL_DEPS python3 -m pytest -o addopts= -q \
  tests/test_seed_candidate_identifiability.py tests/test_seed_discovery_headroom.py \
  tests/test_seed_assistant_benchmark_v2.py tests/test_seed_experimental.py \
  tests/test_learning_lab_sessions.py
```
