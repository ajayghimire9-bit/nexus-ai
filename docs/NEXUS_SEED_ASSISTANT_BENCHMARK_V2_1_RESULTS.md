# Persistent local assistant v2.1 — completed negative development result

Branch: `codex/seed-persistent-assistant-benchmark-v2`.
Task base: `d4c19e446e1c6e233ef2c8a596bdefd988a29579`.
Original pre-run commit: `474661c94e147f1337b1b6cf0bb6ece51f5a88ec`.
Original incomplete outcome: `b5fec106251b14cf2b2d2e8ae06d5c6cf18089fb`.
**Successful pre-run v2.1 revision: `8fe8192e207bf95fa3b8b153f31913df2c7490e4`.**
Both pre-run revisions were clean and pushed before their respective execution.

## Decision

**FAIL_DEVELOPMENT_SCREEN.** Retained AST capsules did not improve correctness,
candidate executions, model calls or total measured latency over ordinary program
caching on this workload. This is a complete negative source-development result,
not a missing-data failure. Do not interpret working retention as learning-to-learn.

All 144 planned trials completed: 48 per method, two process-cold resets and two
12-request passes per reset. All methods were correct on **40/48 (83.33%)**.
They had zero runtime/transport failures but **16.67% strict task errors**.
The registered 90% minimum correctness and 5% latency-improvement requirements
were not met. No acceptance rule, task, prompt, decoding parameter or model
weight was changed after observing the completed run.

## Comparison

All values include real tool execution. Mean total latency includes process
startup amortized over the 24 requests within a reset block, including abstraction.

- **A — model + tools/retrieval:** 649.879 ms mean total; 623.395 ms workflow;
  40 candidate executions; 22 actual model completions; 26 response-cache hits.
- **B — A + ordinary program caching:** 642.951 ms mean total; 618.018 ms
  workflow; 40 candidate executions; 22 completions; 26 response-cache hits.
- **C — B + NEXUS AST capsules:** 646.677 ms mean total; 620.617 ms workflow;
  40 candidate executions; 22 completions; 26 response-cache hits; six actual
  abstractions and eight cross-binding capsule reuses.

C was 0.49% faster than A and **0.58% slower than B** by point estimate. All
three had exactly the same task-level correctness and the same two error cases.
There is no established capsule speedup or correctness benefit.

Four-file-block paired baseline-minus-C latency differences (positive favors C):

- A: **+3.202 ms**, Student-t 95% **[+2.011, +4.393] ms**;
  bootstrap **[+2.632, +3.820] ms**.
- B: **−3.726 ms**, Student-t 95% **[−5.703, −1.749] ms**;
  bootstrap **[−4.728, −2.723] ms**.

These are the registered exploratory file-block intervals, conditional on ONE
model, four authored schemas and only two reset timings. Files share each reset's
model startup and runtime conditions, so they are not independent timing runs.
Correctness differences are identically zero with degenerate [0,0] intervals:
that is an observed paired tie, not proof of population equivalence.

An explicitly **post-hoc timing-sensitivity audit**, not a replacement endpoint,
uses the TWO independently reset repetition pairs (df=1):

- A minus C: +3.202 ms, 95% **[−6.801, +13.205] ms**.
- B minus C: −3.726 ms, 95% **[−38.219, +30.767] ms**.

Both include zero. The shared-startup file-level intervals must not be used to
claim a general runtime improvement or slowdown. The registered screen still
fails under either view, and the compute path offers no candidate-count savings.
Recorded method orders were B/C/A and C/B/A: randomization happened to put A last
in both repetitions. The small timing sample is not fully counterbalanced.

## Cold, warm and cache accounting

The six benchmark startup-to-ready times were **0.596–0.639 s**, including
hashing/provenance and model loading. This is process-cold startup, not a flushed
OS page cache. Native weight-loading time alone is unavailable. A separate real
integration load is also accounted in overall resources.

The first pass's mean workflow latency was 1.247 s for A, 1.236 s for B and
1.241 s for C. The second pass was entirely response-cached, with mean workflows
0.146 / 0.136 / 0.135 ms. **Those microsecond values are not model inference.**
Uncached requests after the first model request averaged **1.369 / 1.357 / 1.363 s**
of real model-request time (20 per method). Complete workflow medians were
0.193 / 0.172 / 0.183 ms because over half the requests hit the response cache.

Each method used **7,066 input tokens and 314 generated tokens** in 22 actual
completions. All 26 response-cache hits per method recorded zero new input and
generated tokens, measured lookup time, and no fabricated native timings. Native
prompt-cache counters were observable and zero on generated requests; cache hits
mark prompt/KV telemetry unavailable because no runtime call occurred.

Including the separately labeled integration check: **146 client requests,
67 actual model completions, 79 application-cache hits, 21,440 input tokens and
956 newly generated tokens**. No token telemetry was missing. The integration
check made one real completion (242 input / 14 output tokens), then a cache hit.
No templates or tiny codec were substituted for model inference.

The same response-cache policy and explicit `cache_prompt:false` applied to
every configuration. Server, response cache, exact cache and capsule library
were reset between configurations. Configuration order was randomized and
recorded; timing repetitions were not counted as new task/model replications.

## Where the work went

All three strong direct planners needed only one candidate execution for each
executed task. They did not need example-output-guided search. Ordinary caching
already matched the reuse opportunity; capsules did not reduce execution count.
These are learner tool-call counts. Reference assessment is separately timed in
each raw trial and included in overall host resources; independent post-run
verification executions are not mislabeled as new learner interactions.

Across 48 requests, C's measured abstraction took **0.0866 ms** in total,
program search **0.1565 ms**, and retrieval/binding **0.7072 ms**. A's total search
was 0.9489 ms; B's 0.3366 ms. These sub-millisecond totals cannot explain broad
end-to-end inference differences. Do not attribute OS/model timing noise to
learned knowledge.

B and C each had **26 ordinary program-cache hits**, with a maximum 4,283
serialized program-cache bytes. C additionally retained up to **1,758 serialized
capsule bytes**. These are serialized storage sizes, not Python heap or model
memory. All methods could execute a plan without promotion; C alone retained
anti-unified AST skeletons across bindings. No stable-agent promotion occurred.

Against B there was **no sustained measured break-even** over the 12-task
sequence. The descriptive crossing against A was at task 1, before any retained
capsule had been reused, and therefore is not evidence of amortization benefit.
Cold-start and inference timing variation dominate this apparent crossing.

## Language and failure analysis

Two strict failures occurred for every method, on every reset/pass:

1. `unsupported`: the model returned `clarify`, not the registered `unsupported`
   subtype. It safely asked a question and executed nothing. This satisfies
   safe non-action, but not the frozen exact-subtype correctness criterion.
2. `inappropriate_reuse`: the model requested ascending order despite the user's
   “largest first.” Every method faithfully executed that wrong model intent.
   This was a shared interpretation error, not a capsule binding error.

No subtype or threshold was relabeled to raise the score after evaluation.
The same-file/different-instruction control changed actual programs and outputs
in **12/12 paired controls**, demonstrating a narrow causal effect of request
text through model intent. It does not establish general language understanding.

The model receives a supplied two-operation grammar, four labeled intent examples
and column profiles. Unique numeric/text roles are supplied by generic schema
profiling. Some evaluation wording is near the examples. No demonstration outputs,
expected assessment rows, task IDs or reference programs enter the assistant.
The direct planner is handwritten over this bounded intent grammar; the capsule
library is not an open-ended program synthesizer or a trained learning rule.
The correction case is self-contained wording, not a test of conversation-history
understanding. Evaluator separation is an API/code-path boundary here, not an
OS-security isolation claim. The assistant executes vetted operator dictionaries,
not arbitrary model-generated Python.

## Runtime, provenance and resource costs

Qwen2.5 0.5B Instruct Q4_K_M, actual GGUF `general.file_type=15`; weight SHA-256
`74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`.
Disk bytes: 491,400,032, **not resident memory**. llama.cpp 0.7.0, build 11669,
commit `620d2225c`; executable SHA-256
`9dc31a8a15f81b8f252e68d1918419e0bbbf5008bd42d00dd8721a58834e384a`.
Recorded platform: macOS 26.6.2 arm64, 10 logical CPUs. One math thread,
CPU-only device, context 2048, one slot, temperature 0, seed 42, output cap 128.
Loopback server uses an ephemeral API key that is not stored in artifacts.

Completed v2.1 host wall: **94.971192 s**; aggregate waited CPU **109.348487 s**;
sampled peak summed RSS **898.359375 MiB**, below 2,048 MiB. RSS includes host
Python, worker Python and model-server descendants; shared pages may be counted
twice. It is not unique physical memory or a per-model peak. Per-process peaks
were not persisted separately. All owned processes exited; no GPU, external API,
new environment simulation or weight training was used.

Conservative v2.1 debit **96 s**. Include the preserved initial incomplete attempt
(2 s) and startup diagnostics (10 s): **108 s additional accounted execution**.
Latest carried ledger: **2186.632103455996 s used / 1413.367896544004 s remaining**.
The old v1 real-data study has no trustworthy session debit; this provenance gap
was disclosed before execution and not filled using stale cached timings.

## Files, tests and reproduction

Implementation: `local_model_runtime.py`, `assistant_benchmark_v2.py`, the legacy
model facade in `real_data_adapter_learning.py`, versioned manifests/protocols,
the supervised runner, independent verifier and descriptive analysis script.
All are under existing `src/nexus/seed/`, `scripts/`, `configs/` and `docs/`.

- `artifacts/seed_assistant_benchmark_v2_1.json`: primary summary, registration,
  configuration/protocol/source/model hashes and resource samples.
- `artifacts/seed_assistant_benchmark_v2_1_raw.jsonl`: every startup, integration
  result and all 144 trials, including the incorrect results.
- `artifacts/seed_assistant_benchmark_v2_1_inputs/`: all four CSVs with hashes.
  A scoped Git attribute preserves their evaluated CRLF bytes on checkout;
  no data normalization was performed after evaluation.
- `artifacts/seed_assistant_benchmark_v2_1_analysis.json`: labeled post-hoc audit.
- `artifacts/seed_assistant_benchmark_v2_1_ledger.json`: eight new E1 resource
  events, preceding-history anchor, reservations, settlements and carried balance.
  The legacy E1 hash envelope says `synthetic_fixture`; payloads explicitly say
  `experimental_local` and contain real measured-host debits. The envelope label
  is not a claim that the measured trials were synthetic mocks. Hashes attest
  consistency, not external authentication of an owner with filesystem access.
- `artifacts/seed_assistant_benchmark_v2.json`: preserved incomplete original.

Before the successful run, **67 targeted tests passed in 15.34 s**. These were
mock orchestration, authored tool fixtures and relevant host/legacy regressions,
not scientific outcomes. The live integration check is recorded separately in
raw data. This is not a claim that the repository's entire historical suite ran.
After adding saved-output, accounting-corruption and archive-entry-point checks,
the final targeted run passed **72 tests in 16.03 s**, with no skips. An initial
mock-lifecycle test failed because its subprocess mock also intercepted a
platform-metadata subprocess; the mock was isolated before the pre-run commit.

Commands executed (local dependencies and model supplied through paths):

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:$NEXUS_LOCAL_DEPS python3 -m pytest -o addopts= -q \
  tests/test_seed_assistant_benchmark_v2.py tests/test_seed_experimental.py \
  tests/test_learning_lab_sessions.py \
  tests/test_seed_real_data_adapter_learning.py::test_skeleton_ast_controls_instantiation_and_sql_directly \
  tests/test_seed_real_data_adapter_learning.py::test_real_data_workspace_readonly_source_and_separate_output \
  tests/test_seed_real_data_adapter_learning.py::test_historical_three_way_record_without_live_inference \
  tests/test_seed_real_data_adapter_learning.py::test_historical_artifact_hash_verification_does_not_rerun_closed_study

PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:$NEXUS_LOCAL_DEPS python3 scripts/run_seed_assistant_benchmark_v2.py \
  --study-version v2_1 --model "$NEXUS_MODEL_PATH" --executable llama-server

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 \
  scripts/verify_seed_assistant_benchmark_v2.py artifacts/seed_assistant_benchmark_v2_1.json
python3 scripts/analyze_seed_assistant_benchmark_v2.py \
  artifacts/seed_assistant_benchmark_v2_1_raw.jsonl \
  --verify artifacts/seed_assistant_benchmark_v2_1_analysis.json
python3 scripts/analyze_seed_assistant_benchmark_v2.py \
  artifacts/seed_assistant_benchmark_v2_1_raw.jsonl \
  --verify-ledger artifacts/seed_assistant_benchmark_v2_1_ledger.json
```

The independent verifier re-executed saved AST programs and independently
calculated reference outputs from saved CSVs, rejected forged correctness in a
regression test, and exactly reproduced all registered means/intervals. No
model or new data collection was used for verification.

Post-run safety maintenance also disables the old v1 benchmark/report entry
points: they cannot silently regenerate closed evaluations with the changed
runtime. The old verifier now checks the pinned historical artifact bytes and
explicitly says it does not revalidate scientific claims; `--write` is refused.
Two former live-model default tests were converted to read-only historical
checks. This does not alter old artifact bytes or the v2.1 executed candidate.
Use the recorded pre-run commit to inspect exactly what ran.

## One next recommendation

Preregister a richer multi-step workflow with independently demonstrated program-
search headroom, keeping this persistent runtime and strong semantic/exact-cache
baseline fixed. This two-operation direct compiler already solves each executed
task in one candidate; it cannot establish that retained knowledge improves
discovery. Do not increase model size or retune these closed scores to create a win.
