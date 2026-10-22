# Configuration repair baseline: correct repairs, no discovery bottleneck

The fixed baseline repaired **12/12 three-module Python fixtures**, including
all eight original projects, two renamed controls and two exact repeats. All
168 final checks passed, including 24 unrelated-behavior retention checks.
Median discovery on the eight originals was **0.560646 ms**, versus the locked
10 ms floor; discovery was **0.958716%** of repair wall, versus the 25% floor.
The result is **NO_PRACTICAL_DISCOVERY_HEADROOM**. No learned-repair comparison
was started, and the cheap baseline result is preserved.

## Provenance and delivered code

Branch: `codex/seed-config-repair-baseline`.
Starting local/GitHub revision: `e438d6641827f88654d6abc9c3b5f49e2233e890`.
Protocol, fixed manifest and tested implementation committed/pushed before run:
**`d2eaec0a12a82c591142ae325b892d40eb52cfc5`**.
[Protocol](NEXUS_SEED_CONFIG_REPAIR_PROTOCOL.md),
[executable manifest](../configs/seed_config_repair_baseline.json),
[saved projects, patches, traces and trials](../artifacts/seed_config_repair_baseline_raw.jsonl),
[result](../artifacts/seed_config_repair_baseline.json),
[independent replay and ledger](../artifacts/seed_config_repair_baseline_audit.json).

Config SHA256 `f1ee11c5a62294c2ce870c30d480c3608837adb36d866efc9f904cbeb11401a8`;
protocol `e84d4e7c51bd0f979505362f340a786c223399e58feb348995b48a6872704758`;
raw `564e3d0faf7edf34d78c0d9091e5618c9da19ceeb85a526405bf1c1f26032094`.
Persistent runtime source remains
`967842923d5e43c64732094f8e829d9b6995f07e80dce60ca1ce4c76ca0b3fda`.
Historical artifacts, model weights, earlier worker and main are unchanged.

`seed/config_repair_baseline.py` reuses the existing RepositoryModel for source
search and call navigation. Its source-free AST edits handle explicit-None
defaults, ternaries, conditional reassignment, dictionary missing/null behavior
and the zero boundary. The baseline receives no bug labels or repair locations.
It constructs one patch directly, validates it, and stores ordinary exact-cache
entries. Candidate generation is not deliberately slowed or reordered.

`seed/config_repair_worker.py` compiles and executes actual Python functions in
three separate module namespaces inside bounded subprocesses. Original public
checks record call/return paths and actual exception tracebacks. This is not
the master list-transform interpreter pretending to execute repository code.
The vetted subset does not support arbitrary imports, loops or hostile projects;
the worker is not an OS-grade sandbox for arbitrary generated Python.

## Fixed workload and actual repairs

The entire 12-task manifest was fixed before scoring, including the easy cases.
Four original tasks have one faulty layer; four combine faults across two or
three files. No cases were selected after observing baseline difficulty.

- `parser_or`: repaired one parser expression; final checks all pass.
- `core_or`: repaired one implementation expression; all pass.
- `caller_ternary`: repaired one caller expression; all pass.
- `explicit_null`: repaired missing-versus-None dictionary handling; all pass.
- `parser_core`: repaired two expressions in two files; all pass.
- `all_three`: repaired three expressions across all three files; all pass.
- `missing_floor`: repaired missing-key, zero-floor and caller handling; four
  AST edits across three files; all pass.
- `mixed_three`: repaired three expressions across three files; all pass.
- `renamed_parser` and `renamed_three`: both pass after ordinary direct repair.
- `repeat_parser` and `repeat_three`: both pass with exact patch/public-validation
  cache hits and **no new candidate or public-test subprocess executions**.

Ten newly constructed project patches contain 20 AST edits. Every uncached
original project first reproduced a public failure. The unrelated legacy
function remains semantically unchanged. Internal parser and implementation
checks prevent an output-only compensation patch from satisfying the study.

## Where the effort went

The public examples specify the key, positive default, zero and None behavior.
The strong baseline extracts that contract directly; **zero model calls** were
necessary. This is not measured natural-language interpretation. Request text
is part of the cache key but its causal language contribution was not tested.
No model output or model timing was fabricated, and no runtime fallback occurred.
The prior proposal's neural path was not forced when a direct tool sufficed.

Across all 12 requests, measured stage totals were:

- Public-example contract extraction: **0.0761 ms**.
- Source indexing/search: **1.8250 ms**.
- Fault localization from traces/call graph: **0.0841 ms**.
- AST patch construction: **3.4925 ms**.
- Exact cache lookup: **0.0609 ms**; cache retention: **0.6334 ms**.

Baseline cache construction was **0.959 microseconds**. Ten ordinary entries
serialize to **7,444 bytes**, not a measurement of their Python heap size.
There are no learned parameters or learned repair abstractions in this method.

All 32 project subprocesses combined: **900.940 ms** parent-measured wall;
**7.553 ms** child compilation and checks; **3.527 ms** test-body execution.
The **889.850 ms process/IPC overhead residual** dominates. It includes process
startup, imports, transport/child serialization and shutdown; it is not pure
startup or neural inference. Profiling overhead for the original checks is
inside recorded test time and never counted as discovery. Parent serialization
and other orchestration are included in complete repair/study wall even where
they are not separately timed stages.

Median repair wall: **56.556 ms** on original projects, **57.496 ms** on renamed
controls, **0.0454 ms** on exact repeats. The two repeat timings are descriptive
cache behavior, not a replicated general speedup result. Repair wall totals
**572.656 ms**; evaluator-only final assessment is separate and included in
the project-process/study totals. No private outcome is returned to the baseline.

## Boundaries and limitations

The supplied count contract and known syntax family make a direct repair rule
possible. The AST rules were authored before scoring, not learned by NEXUS.
The eight authored projects are not independently pretrained-model replications
or a representative sample of arbitrary repositories. No timing confidence
interval or general coding claim is warranted. Numeric parsing, default/null
and zero handling are covered; arbitrary precedence, unit conversions, hidden
APIs and novel semantic contracts are not demonstrated.

Correct repair is established on this development bank, but learned repair
discovery is neither tested nor justified by its costs. Even eliminating the
initial reproduction run would not change the fact that measured discovery
itself is well below the absolute 10 ms floor. Do not remove easy cases, add
mandatory search, lower the threshold, or reuse these final tests to select a
learned candidate. Previous studies remain closed.

## Tests, independent replay and resource accounting

**120 targeted tests passed before scoring (16.24 s); 126 passed afterward
(16.26 s)**. Focused tests cover multi-file repairs, unrelated-code preservation,
missing/null handling, real execution, changed requests and exact caches,
assessment isolation, unsupported-contract abstention, forbidden effects/loops,
missing grids, stage accounting and corruption rejection. This is not a claim
that the entire historical test suite ran.

The precommitted independent verifier passed on its first invocation. It
reconstructed all endpoints, expected values, hashes, cache receipts, source
storage sizes and stage arithmetic, then replayed all saved patches in **12
additional bounded subprocesses** (168 saved-case function calls). These are
read-only reproducibility checks, separate from the measured run, not new tasks
or extra evidence of learning. Corruption tests reject missing tasks, modified
patches, forged cache receipts, NaN timings, changed summaries and altered
retention references.

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:$NEXUS_LOCAL_DEPS python3 -m pytest -o addopts= -q \
  tests/test_seed_config_repair.py tests/test_seed_candidate_identifiability.py \
  tests/test_seed_discovery_headroom.py tests/test_seed_assistant_benchmark_v2.py \
  tests/test_seed_experimental.py tests/test_learning_lab_sessions.py
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
PYTHONPATH=src:$NEXUS_LOCAL_DEPS python3 scripts/run_seed_discovery_headroom.py \
  --study config_repair
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:$NEXUS_LOCAL_DEPS \
  python3 scripts/verify_seed_config_repair.py
```

One scientific pilot, no retries: **1.093451 s wall**, **1.075004 s worker and
waited-child CPU**, **96.140625 MiB** sampled aggregate RSS. Sampling every
100 ms can miss peaks and shared pages can double-count. Caps were 60 s CPU/wall
and 512 MiB sampled RSS. Actual measured executions: **20 public project
processes +12 final project processes**, **288 project function calls**. Cached
validation receipts add zero executed tests. Zero simulator steps, model calls,
training updates or learned-library promotions. No model was loaded, so RSS
does not measure model memory.

Conservative debit **3 s**; E1 events 102–104 anchor to the prior published
ledger. Latest accounted balance: **2193.632103455996 s used /
1406.367896544004 s remaining**. The inherited v1 missing-debit gap is unchanged.
No main merge, paid/GPU service, security-setting change or historical rewrite.

## One next recommendation

Test an exact-equivalent **persistent worker for public validation only**,
with fresh module namespaces per request and strict state-isolation checks.
Keep final evaluation in separate isolated processes. This targets the measured
process overhead; it is engineering, not a claim of learning-to-learn. Do not
start a learned-repair study on this cheap bank. No such worker experiment ran
in this branch.
