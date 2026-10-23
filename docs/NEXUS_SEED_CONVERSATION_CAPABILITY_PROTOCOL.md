# Conversation capability matrix v1 — source-development protocol

New versioned development evaluation. It does not reopen assistant-benchmark
v2/v2.1, configuration-repair, or real-data confirmation artifacts. Passing the
finite suite is not AGI and not learning-to-learn.

Parent revision at protocol lock: `cursor/seed-local-conversation-workspace`
`c704ca12d75da570adaf1f39fd2128dcb2c57e5f`. Implementation and this protocol
must be committed before scored execution.

## Question

After conversational-correctness fixes, which environments are operational, and
do retained NEXUS procedures help on later CSV tasks relative to the same tools
and an ordinary exact cache?

## Integration classes (locked)

See [the audit](NEXUS_SEED_CONVERSATION_CAPABILITY_MATRIX.md). Chat-integrated:
CSV tools, 6×6 world, multi-turn conversation. API/lab only: JSON readers,
SQLite, bounded config repair. Unavailable through chat: joins, generated
Python, arbitrary repository repair.

## Methods (CSV scored comparison only)

1. `tools` — workspace parser + vetted adapters. No response cache, no capsule.
2. `ordinary_cache` — the same tools plus an exact `(source_sha256, intent)` output cache.
3. `nexus_procedures` — the same tools plus explicit executed-AST capsules.
4. `nexus_reset` — matched later-task control: same prior budget, then a fresh
   workspace with no loaded capsules.

All methods see the same files, requests, seeds and budgets. Model weights stay
fixed and unused on scored CSV tasks so method differences are cache/procedure
behavior, not sampling. A separate optional live-model probe is not a scored
family.

Ordinary cache is allowed. Direct compilation of the two-op skeleton is allowed.
No method is forced to search.

## Task families (not equivalent evidence)

| Family | Meaning |
|---|---|
| exact_repeat | Same grain and roles, possibly another file |
| renamed_schema | Same grain, different column names |
| new_composition | Missing values or a fresh request that must not inherit state |
| inappropriate_reuse | Schema that must be refused |
| unsupported | Comparison the workspace must not execute |

Cross-interface reuse (CSV capsule applied to SQLite/JSON/repair/world) is
**not** scored; chat cannot do that. Substantially new mechanisms are **not**
in this suite.

## Manifest

`configs/seed_conversation_capability_v1.json` is the locked task list. Tasks
were chosen for coverage before outcomes. Do not add, drop or retune a case
because a baseline was slow or wrong.

CSV files are generated from the manifest after protocol commit. Expected
semantics are the two-op grammar already used by `assistant_benchmark_v2.reference`.
Public learning feedback is the conversation text; final checks use file/world
outputs only.

## Coverage probes (descriptive, not an aggregate)

JSON API sum, SQLite table read + adapter, one `config_repair_baseline` fixture,
one world goal through chat, one save/reload/reuse conversation. Each probe
records integration class and actual status. No “AGI percentage.” No weighted
total.

## Metrics

Per task: correctness against the independent reference, status
(success/incorrect/clarification/abstention/unsupported), whether an action
wrote an output, clarification usefulness (asked before acting when expected),
retention (capsule used), model calls/tokens (expected 0 on scored CSV),
candidate executions, wall seconds, library bytes. Cold start of a process is
recorded once, not as a task family.

Report each environment separately.

## Resources and authority

Standing 2026-10-16 local CPU grant: **900 seconds wall**, 100k interactions,
no paid services. Carried scientific ledger from canonical state remains
2193.632103455996 s used / 1406.367896544004 s remaining; this development
evaluation must stay inside the 900-second experiment cap and must not debit
closed studies. Local CPU only. No merge, no historical overwrite.

If a runner requires a one-run approval record, cite this standing grant and
this configuration hash. Do not fabricate a human reply.

## Verification

Independent verifier replays saved CSV programs or recomputes
`assistant_benchmark_v2.reference` from raw records without new model
inference. Repair/world probes replay saved files or Session world. Preserve
failures and partial runs.

## Success rules (development, not confirmation)

- Unsupported and inappropriate cases: no output file, clarification or
  unsupported status.
- Fresh no-inherit: executed minimum is null after a prior `at least 5`.
- Exact repeat transfer: tools and cache/procedures may all succeed; a
  procedure benefit is a later-task reduction in adapter executions or
  successful reuse, not a higher score on an easy first task.
- A test-suite pass is not evidence of capability or learning benefit.
