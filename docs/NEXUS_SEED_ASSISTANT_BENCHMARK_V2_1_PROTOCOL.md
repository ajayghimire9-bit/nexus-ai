# Persistent assistant benchmark v2.1 — infrastructure-only development revision

This is a separately versioned source-development study, not a retry under the
consumed v2 allocation and not confirmation. It inherits every scientific rule
in [the v2 protocol](NEXUS_SEED_ASSISTANT_BENCHMARK_V2_PROTOCOL.md). The executable
manifest is `configs/seed_assistant_benchmark_v2_1.json`. Code rejects changes to
cases, file seeds, runtime decoding/settings, model hash, order randomization,
cold repetitions or success thresholds relative to v2.

## Why another version is legitimate

The original pre-run commit was
`474661c94e147f1337b1b6cf0bb6ece51f5a88ec`. Its integration server exited before
any completion or dataset generation. The incomplete result was committed
unchanged at `b5fec106251b14cf2b2d2e8ae06d5c6cf18089fb`: 0/144 trials, 2-second
debit, no observed task outcomes. The original run ID remains consumed; its
artifact is not overwritten or relabeled a scientific negative result.

Three startup-only technical checks then succeeded, in 4.735246, 0.614863 and
0.618189 seconds. The latter two checked inherited file-size and core-dump
limits, within the same conservative 10-second debug allocation. No completion
was requested, though the backend's implicit model warmup work is not token-
instrumented. These were engineering checks, not three independent research
replications. The initial failure remains unexplained; do not claim it was
causally fixed. The runtime now includes the exit code in startup errors.

## Changes and unchanged quantities

Add inferred field types to ordinary-cache signatures so identical column names
with changed roles cannot retrieve an incompatible program (no registered file
changes types). Add an ephemeral API key to the owned loopback server and client requests;
never store the secret in artifacts. This protects the local completion endpoint
without changing prompts or task information. Make run/config/artifact identifiers
version-specific and bind the worker to its new durable reservation. Improve
saved-output verification by re-executing the saved bounded programs. Record
evaluator-assessment time separately from the user-visible tool workflow.

The original 12 requests, four file generators, all expected semantics and all
thresholds remain unchanged. No task dataset or outcome existed at amendment
time. The supplied two-operation grammar, role-binding rules and model weights
are fixed. No tuning, new architecture, teacher labels or expected answers enter
the assistant. Retain the strong direct planner even if it defeats NEXUS.

## Allocation and stopping

Standing human CPU authority plus the current explicit request authorize one
new bounded source-development attempt: **480 seconds wall / 480 seconds CPU /
2048 MiB summed sampled RSS**, zero real-environment steps, zero weight updates.
Carry **2090.632103455996 seconds used / 1509.367896544004 seconds remaining**:
original carry plus 2 seconds for the incomplete attempt and 10 for diagnostics.
No grant or debit is reset. The same existing Sandbox/E1 reservation and
supervisor enforce caps and retain partial logs. The new ID is
`seed-assistant-benchmark-v2p1-1`. No further scored attempt is scheduled if it
fails. All 144 planned trials, technical integration, metrics, statistical units,
five-percent latency threshold and minimum 0.90 correctness rule remain fixed.

Commit and push this protocol, config and tested changes BEFORE execution.
Keep v2 incomplete results and all older artifacts intact. Report source-
development results honestly, independently replay arithmetic/outputs, and
commit outcomes separately. No merge or live-agent promotion.
