# Persistent local assistant benchmark v2 — locked source-development protocol

Base: `d4c19e446e1c6e233ef2c8a596bdefd988a29579`, verified on GitHub before
creating `codex/seed-persistent-assistant-benchmark-v2`. The main worktree's
untracked `.models/` is preserved. This is a new study version; old raw artifacts
and the earlier primitive-transfer audit branch are not modified or merged.

## Question and registered decision

Does retained parameterized executable knowledge improve correctness or reduce
total user-visible work beyond the SAME local model, tools and ordinary caching?
The competing possibility is that a strong direct planner plus ordinary caching
already does all necessary work; capsules then add overhead. No exhaustive
demonstration-answer search is forced on the baseline to manufacture savings.

Success requires complete data, NEXUS correctness at least 0.90 and both baselines,
at least **5% lower mean total amortized latency than BOTH baselines**, and
positive lower paired 95% Student-t bounds for both baseline-minus-NEXUS
latency contrasts. This is an exploratory development screen, not a claim about
unrestricted language, synthesis or learning-to-learn. Correctness, model calls,
candidate executions and individual failure modes are reported regardless.
No task, prompt, threshold or selection rule changes after inspecting outcomes.

## Runtime and provenance

Use the existing Qwen2.5 0.5B Instruct Q4_K_M GGUF, SHA-256
`74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`.
Read quantization from `general.file_type` in the actual GGUF. Record server
version/build, executable hash, architecture, OS, CPU count and exact settings.
Record model bytes as **disk size**, never model RAM.

One owned persistent `llama-server` per method/cold repetition, CPU only, one
thread, `-ngl 0 --device none --no-op-offload --offline`, one slot, context 2048,
temperature zero, seed 42, maximum 128 output tokens, 30 s startup and 20 s request
deadlines. Paths/host/port/context/backend are configurable. Loopback only; never
adopt an unrelated existing server. No downloads, external APIs, templates or
tiny-codec intent fallback. Timeout/cancellation closes the connection AND stops
the owned process, with no automatic restart of a failed configuration.

The previous `GrammarConstrainedLocalIntentModel` becomes a compatibility
facade over this runtime. Its historical two-mode schema remains legacy only.
The new study uses an explicit `sum / rows / clarify / unsupported` schema.
Raw JSON is validated semantically; a grammar-valid but inconsistent result is
a failure, not silently repaired.

## Three fair configurations

A. `tools_retrieval`: same model, source profiling, role binding, direct bounded
planner, execution and structural validation. Can execute any valid plan without
promotion.

B. `ordinary_cache`: A plus exact/signature program caching. Signature includes
actual column names, operation, minimum and ordering, so changed instructions
cannot retrieve a stale grouped result or threshold.

C. `nexus_capsules`: B plus `ParameterizedAdapterTemplate` ASTs, abstracted from
executed plans and rebound to new columns/minima. Grain, filter presence and sort
direction form the typed compatibility contract. Inappropriate reuse is rejected.

All use the same canonical first valid plan and clarification policy. A direct
plan uses the supplied two-operation grammar; it is not open-ended synthesis.
Source profiles with exactly one numeric and one text column supply role binding.
No demonstrations or expected output rows are provided to ANY method. No
assessment outcome trains a cache, parser, binder or capsule. C stores a template
only after tool execution and structural validation; this is local experimental
memory, not stable-agent promotion. Response wording is explicitly an
execution-backed renderer, not an intent fallback or a neural generation claim.

## Workload and reset rules

`configs/seed_assistant_benchmark_v2.json` is the executable source of truth.
It preregisters four new seeded CSV datasets (36 rows each), with distinct
two-column schemas and mixed-case keys, negative values and malformed numeric
cells. Twelve requests cover exact repeats, new schemas, new paraphrases,
changed thresholds, a vague request, an unsupported action, a correction and
same-file/different-instruction controls. Expected semantics are evaluator
metadata and are NEVER passed to the assistant. The reference computes results
independently in Python; it is not a search tool. All data files and individual
outputs are retained for numerical replay.

Generate files only after this protocol/implementation/config are committed.
These authored cases are explicitly source development, not untouched external
confirmation. Existing v1 tasks stay development/closed historical evidence.

Two cold repetitions. Shuffle the three method orders using seeds 782104 and
782105; record order. Each method/repetition starts a fresh server, response
cache, exact program cache and capsule library. Run the 12-case sequence once
(`cold`) then the identical sequence (`warm`) without resetting within that pair.
Reset EVERYTHING before the next method. This yields **144 planned trials**,
six benchmark server loads, plus a separately labeled real-model integration
check with one load and one generated request plus an application-cache hit.
The integration uses an already-published source example, never new tuning.

Application-response caching is enabled equally. Runtime prompt reuse is
disabled equally (`cache_prompt:false`, RAM cache disabled); available native
cache counters are still recorded, not inferred. A response-cache hit reports
zero NEW input/generated tokens, measured lookup wall time, no runtime timings,
and a creation-request reference. Cache state never crosses configurations.
Unknown runtime telemetry stays null; known sums and unavailable counts are both
reported. Timing repetitions are not independent task samples.

## Measurements and statistics

Each raw trial contains intent, chosen AST, output, correctness, failures and
measured source profiling, interpretation, retrieval/binding, search, execution,
validation, abstraction and response construction time. Record total workflow
latency plus unattributed bookkeeping. Record cold startup separately and add it
to the first user-visible request. For the primary total-work comparison allocate
startup uniformly over the 24 requests within that reset block; the sum is the
same measured work, not a free startup. Cold/warm request means remain separate.
Source-file creation and supervision overhead remain in overall host wall/CPU,
not falsely assigned to inference.

Count actual model completions, application hits, unknown failed-call outcomes,
input/output tokens, candidate executions, questions, abstraction AST visits,
retained program/cache bytes and measured abstraction time. No weighted cost
proxy is equated to measured latency, memory or FLOPs.

Aggregate repeated trials and requests inside each of the **four file blocks**
before paired Student-t intervals (df=3) and 10,000 file-block bootstrap samples
(seed 90213). Report means/medians and all per-case failures. These intervals are
exploratory and conditional on one pretrained model, this authored grammar and
only four file blocks; neither timing repetitions nor paraphrases add model
replications. Two simultaneous latency comparisons use conservative 95% intervals
as descriptive evidence; no broad generalization claim follows from the screen.

Compute a descriptive cumulative break-even along the preregistered sequence,
including all measured abstraction/startup costs. Require savings to stay
positive for the remaining sequence; return null if no sustained break-even.
Do not extrapolate a lucky transient crossing or ignore correctness tradeoffs.
Explicitly measure whether same-file/different-request model intents change
actual programs/outputs. This is a bounded causal input manipulation, not proof
of general language understanding.

## Allocation, enforcement and failures

Standing owner grant (2026-10-16) and the current explicit request authorize
local CPU work within the smaller of **480 s wall / 480 s CPU / 2048 MiB summed
RSS** and remaining session allowance. Zero environment interactions and zero
weight updates. Maximum 144 task actions (not simulator steps), at most 67
successful generation requests including the integration check if every request
reaches execution. Preserve timeouts/errors instead of retrying or shrinking the
grid. Missing trials mean INCOMPLETE, not an inconclusive scientific comparison.

Reconcile the existing host ledger with the latest explicitly recorded carry
**2078.632103455996 s used / 1521.3678965440042 s remaining**; do not reset on this
new branch/date. The intervening v1 real-data artifact contains no trustworthy
session debit: disclose that provenance gap rather than inventing an exact
cost or copying its cached token timings as fresh usage. New work has a durable
one-use reservation, registration hashes and settlement in the existing Sandbox /
E1 journal. Unsettled reservations consume their full cap. No old grant is reused.

The supervisor launches the worker in its own process group, samples worker and
server descendants every 0.1 s, sums their CPU maxima and RSS plus host-Python RSS,
and kills the whole group at a cap. CPU RLIMIT is inherited by the server.
Aggregate CPU/RSS enforcement is sampled and can overshoot by a sampling interval;
record any overshoot and mark execution incomplete. Shared pages can be counted
more than once in RSS: report a sampled sum, not unique physical usage. Model
file size and Python-only RSS are never substituted. Preserve raw JSONL and logs
on failure; no automatic second scientific run.

## Verification and release

Mock tests cover lifecycle, cache isolation, unavailable telemetry, malformed
intent, request dependence, timeout/cancellation, inappropriate capsule reuse and
independent arithmetic. The separately labeled live integration check and the
144-case benchmark occur only AFTER the pre-run commit. The independent verifier
reconstructs summaries and reference outputs from raw trials and saved CSVs,
without model calls or benchmark result-builder imports.

Commit results separately, report negative/incomplete outcomes, and push. No
merge, checkpoint replacement, stable promotion, paid service or architecture
sweep. One next recommendation must follow the actual evidence.
