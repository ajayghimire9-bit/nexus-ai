# Configuration repair: fixed baseline-first development workload

Base `e438d6641827f88654d6abc9c3b5f49e2233e890` verified against GitHub.
Branch `codex/seed-config-repair-baseline`. Prior studies remain closed; their
artifacts, thresholds and persistent-runtime source are unchanged.

## Question and workload lock

Does locating and repairing inconsistent configuration handling consume practical
discovery work after the baseline has direct contract inference, source search,
call-graph navigation, traces, AST edits and exact patch caching? Alternatively,
ordinary deterministic tooling may already solve this family cheaply.

`configs/seed_config_repair_baseline.json` fixes ALL 12 tasks before scoring:
eight original projects, two renamed-field controls and two exact repeats.
No difficulty-conditioned task generation, subset selection or post-result
manifest changes. Four originals are single-layer problems; four combine faults
in two/three files. Fault syntax varies: truthiness defaults, ternaries,
conditional reassignment, dictionary missing/null differences, direct indexing
and a minimum-one clamp. Each project has cfgparse.py, engine.py and app.py.
An unrelated legacy function must preserve its original falsy-value semantics.

The domain is integer counts and numeric-string counts, including zero. Missing
or None uses the requested positive default. This supplied contract does not
test novel algorithm discovery, arbitrary Python repair, or unit conversion.
The manifest's bug labels/locations/cohort/default are evaluator-side recipes;
the baseline receives only request text, source files and six public tests.
Final tests include internal parser/implementation checks so an output-only
compensation patch is insufficient, plus two unrelated-behavior retention checks.

## Strong baseline, no compulsory inference or search

Reuse `master.coding.RepositoryModel` for source/symbol/import/call indexing.
Search source for the identified option; navigate calls reachable from app.run.
Run public tests first and retain actual errors/tracebacks. Construct a single
direct AST repair applying source-free null/default and zero-bound rules along
that reachable path. No forced enumeration or repeated tests. Preserve unrelated
functions. Revalidate with public tests and retain only public-valid patches.

Public tests identify the key, default, zero and None semantics. Let the baseline
derive this contract directly instead of requiring a neural call. The measured
interpretation stage is **public-example contract extraction**, not demonstrated
natural-language understanding. Request text is in the exact cache key, but no
causal language claim is tested here. If those examples do not identify the
supported contract, abstain; do not invent model output or silently claim a
model-backed answer.

This deliberately follows the owner's strong-tool rule rather than forcing the
earlier proposal's model path. The persistent runtime remains byte-identical,
but this pilot needs zero model calls. It cannot establish neural interpretation
cost or general local-model coding performance. No synthetic stand-in inference
timings are recorded. Existing real-model v2.1 evidence is not rerun.

Exact cache key includes complete request, original source, public tests and
derived contract. A hit can reuse its public validation receipt. Final tests
always execute independently after the returned patch hash locks, and never
update the baseline cache. Cache insertion, lookup, storage and reused receipts
are charged/labelled. Unknown contracts, worker errors and malformed results
are incomplete/invalid, not silent successful repairs.

## Execution boundary audit

The existing master ExecutionSandbox is a list-transform interpreter, not a
general multi-file Python executor. It cannot verify these repairs. Reuse the
existing black-box worker's safe builtins, with a dedicated vetted three-module
CPython fixture worker: no arbitrary filesystem/network calls, external imports,
decorators, loops or generated unrestricted Python. Import dependencies are
resolved explicitly among the three module namespaces. Code runs through real
compile/exec in a separate isolated-mode Python subprocess, under inherited host
limits plus a 2 s CPU /3 s parent timeout. Source, AST and test counts are bounded.
This is NOT an OS-grade sandbox for hostile arbitrary code; only the authored
fixtures and vetted AST edits are in scope. No historical evaluator is modified.

## Metrics and predeclared gate

Record every project, input/public/final cases, failing traces, source search and
call graph, AST edits, unified diff, locked source hash, public/final results,
cache hits and failures. Timings: contract interpretation, source index/search,
fault localization, patch construction, validation compile/test bodies, ordinary
cache lookup/retention, and complete repair wall. Report subprocess wall minus
child internal work as **process/IPC overhead residual**, not pure startup.
Constant launch overhead is not discovery. Include evaluator-final cost and
whole bounded-worker costs separately, not as hidden free work.

Primary units: the eight original projects; renamed/repeat controls are separate.
No independent model replications or timing confidence intervals. Discovery is
source indexing/search + fault localization + patch construction. Require >=90%
exact all-final-tests success, median discovery >=10 ms, and discovery >=25% of
complete repair wall before considering learned abstractions. Small absolute
work remains cheap even if its proportion is high. Controls/retention failures
must be reported individually. All fields must exist and be finite. No task
expansion, threshold reduction or extra patch search after reading outcomes.
Even a passing gate only permits preparing a separate learning comparison.

## Resources and sequence

Commit tested code, this protocol and executable manifest before the one run.
60 s CPU/wall, 512 MiB sampled aggregate RSS, local CPU, zero simulator steps,
neural inference/training, learned abstractions or new human labels. Up to 12
requests and 36 bounded project subprocesses. Carry **2190.632103455996 s used /
1409.367896544004 s remaining**, preserving prior debit gaps. Use existing
Sandbox/E1 host and process-tree meter; save partials, no automatic retries.

Independently reconstruct saved arithmetic, exact grid, patch/input hashes,
retention and cache accounting; verify actual saved Python executions separately
from fixture unit tests. Preserve all historical results and keep main unchanged.
No learned-repair study follows in this branch, regardless of result.

Pre-run targeted tests: **120 passed in 16.24 s**, on authored unit fixtures,
saved evidence and mocks; the registered 12-task manifest was not run in pytest.

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:$NEXUS_LOCAL_DEPS python3 -m pytest -o addopts= -q \
  tests/test_seed_config_repair.py tests/test_seed_candidate_identifiability.py \
  tests/test_seed_discovery_headroom.py tests/test_seed_assistant_benchmark_v2.py \
  tests/test_seed_experimental.py tests/test_learning_lab_sessions.py
```
