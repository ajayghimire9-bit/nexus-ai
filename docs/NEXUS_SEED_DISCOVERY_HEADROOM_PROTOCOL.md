# Discovery headroom: baseline-first source-development preflight

Starting revision: `7c244860015c8a0e9a49203d93cb9bac7f853b75` (local and GitHub
agree). The persistent assistant v2.1 failure is closed. No historical tasks,
outcomes, binaries, seeds or runtime settings are changed. This is NOT the next
learning comparison and does not establish an assistant speedup.

## Question and competing explanations

Does a richer typed data-transformation workload require measurable discovery
after a strong source-free solver has direct compilation, exact constraints,
active disambiguation and ordinary memoization? Alternatively, a supplied finite
grammar may again make discovery cheap enough that inference or normal caching
dominates. Ambiguity alone is not a reason to learn abstractions.

The executable configuration is `configs/seed_discovery_headroom.json`. One
deterministic draw; no task resampling based on difficulty or outcome. This first
stage uses executable teaching examples, not natural-language interpretation.
It makes **zero model calls**. The unchanged persistent assistant direct/tool
baseline remains a required separate gate before any learning study. Do not
represent this exact symbolic solver as a language-model benchmark.

## Workload and information contract

Eight source-design compositions, eight different composition tasks, and four
each of explicit-specification, renamed-schema and exact-repeat controls: 28
tasks. All are authored development, not untouched confirmation. Each schema
has two text and three numeric columns with unfamiliar names. Candidate plans
choose a group column, two numeric operands, addition/subtraction/multiplication,
sum/mean/maximum, and thresholding before/after grouping or no threshold.
Normalization, parsing, arithmetic, filtering, grouping, aggregation and sorting
form seven-to-eight-operation ASTs. Operand order matters for subtraction.

Commutative operand duplicates and the exact maximum/filter-before versus
maximum/filter-after equivalence are removed. These are declared semantics, not
learned abstractions. Source/new compositions have disjoint arithmetic ×
aggregate × filter-placement triples after that canonicalization. Combinations
change operations, not merely fields. Report syntax novelty separately from any
finite behavioral audit; it is not a proof of general semantic independence.

An initial two-row demonstration is drawn normally, without engineering a
collision. Several programs may explain it. Eight public 12-row probe batches
are available; up to three selected probe answers may be requested. Both the
grammar and input probes are public. A 32-row final assessment is separate and
inaccessible to the solver and its question policy. The assessment is opened
only after the plan is locked. No task identifier or true plan enters `solve`.
Providing teaching examples is a declared interface, not hidden model grounding.

## Baseline freedoms and costs

Reuse `real_data_evaluator_worker.evaluate_serialized_adapter_program` for
execution, not historical task metadata or evaluator workspaces. The baseline:

- Compiles complete specifications immediately, with no candidate search.
- Filters the finite grammar against the public demonstration.
- Chooses an unasked probe minimizing expected remaining version-space size
  under the supplied uniform candidate prior, with deterministic index ties.
- Stops on one candidate, budget exhaustion, or no distinguishable probe;
  never forces a minimum number of searches. Remaining ties use canonical order
  and are reported, not upgraded to certainty.
- Reuses exact resolved public problems and cached predicted probe outcomes.
  Exact source-free prefix memoization also reuses normalization, parsing,
  arithmetic and group/aggregate fragments across candidate programs. Candidate
  predictions and actual fragment executions are different counters.
  Caches may not key on evaluator truth, task labels or assessment outcomes.
- Independently validates the selected AST on the teaching demonstration before
  retaining an ordinary cache entry. This is not a scientific promotion gate.

Count grammar construction, actual candidate executions, teaching answers,
signature generation/cache lookup, discovery wall time, public validation,
ordinary retention, final execution, and serialized cache bytes. Predictions
reused from cache are not executed again. Instrumentation/serialization and
memory are disclosed; wall time is not FLOPs. No synthetic weighted-cost score
or forced exhaustive final-assessment evaluation is a primary outcome.

The tiny catalogue is a strong bounded baseline, not proof of an optimal solver.
Its complete-spec fast path is a negative control against fabricated search.
Its explicit input-output contract makes inference unnecessary in this stage;
neural inference costs cannot be inferred from its timings.

## Locked descriptive screen and stopping rule

On the eight new-composition tasks: >=95% exact assessment accuracy; >=50%
initially ambiguous; >=6 distinct new composition triples; median actual
discovery >=10 ms; discovery >=25% of discovery + public validation + retention
+ final execution. The absolute floor prevents a high percentage of a trivial
microsecond workflow being called meaningful. Include one-time catalogue cost
separately and all control timings. No significance claim from eight authored
tasks or correlated machine timings; no model-training replication exists.

If any gate fails, preserve it and do not start abstraction learning. Even a
passing symbolic screen does **not** authorize that comparison: first measure
the unchanged real assistant's direct/tool/cache path with the same information
and allow deterministic tools to bypass neural inference. Do not require an LLM
to perform search that its tools already solve. Do not select new tasks using
assessment results from this preflight.

Only after those gates may a separately locked comparison test learned
substructures against exact caches, full-program schema templates, compiled
grammar/probe signatures and source-free subexpression memoization. Fresh
compositions must be separate from renamed/exact-repeat controls. Charge source
discovery, abstraction construction, fresh validation, failed/rejected proposals,
storage, lookup, rebinding, invalidation and retention checks. Compare cumulative
cost at equal accuracy; report break-even only after actual reuse. No learner
or retained-abstraction comparison runs in this preflight.

## Execution and reproducibility

One run, local CPU, 60 seconds wall and CPU, 1024 MiB sampled aggregate RSS,
zero simulator interactions, zero model inference/training, at most 84 authored
probe answers plus 28 demonstrations and 28 final assessment responses (140
authored response events; table rows and tool executions reported separately).
The existing Sandbox/E1 host reserves before dispatch, enforces
limits and settles failures/partials; no retries. Carry 2186.632103455996 seconds
used / 1413.367896544004 remaining. New runtime debit is additive. The prior v1
missing-debit evidence gap remains disclosed, not fabricated.

Commit tested implementation/config/protocol before scoring. Save raw inputs,
plans, choices, expected outputs, actual stage times, config/protocol/source and
runtime-file hashes. Explicitly distinguish invalid/incomplete from scientific
screen failure. Preserve historical artifacts and model/runtime source bytes.

Pre-run tests (84 passed, 15.85 s; mocks/authored unit fixtures, no registered
outcome collection):

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:$NEXUS_LOCAL_DEPS python3 -m pytest -o addopts= -q \
  tests/test_seed_discovery_headroom.py tests/test_seed_assistant_benchmark_v2.py \
  tests/test_seed_experimental.py tests/test_learning_lab_sessions.py
```
