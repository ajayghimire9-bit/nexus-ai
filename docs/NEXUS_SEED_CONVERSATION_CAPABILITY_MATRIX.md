# Conversation workspace capability and integration matrix

Code audit on `cursor/seed-conversation-correctness-matrix`, parent
`c704ca12d75da570adaf1f39fd2128dcb2c57e5f`. This is an integration inventory,
not a scored result. Chat does not gain a capability merely because a module
exists. Missing chat wiring is an explicit gap.

| Environment | Operational path | Chat integration | Notes |
|---|---|---|---|
| A. CSV transforms | `workspace_conversation` → `skeleton`/`bind`/`TypedDataAdapterProgram` | **Integrated** | One text + one numeric column. Inclusive minimum and one sort. Source files stay read-only. |
| A. JSON transforms | `RealDataWorkspaceAdapter.read_source_records` + same AST executor | **API/lab only** | JSON readers exist in `real_data_adapter_learning.py`. Chat `resolve_source` accepts `.csv` only. |
| B. SQLite joins / nulls | `introspect_relational_schema`, `compile_to_relational_sql`, sqlite3 | **API/lab only** | Not reachable from `/api/seed` `chat_send`. Closed real-data study artifacts stay closed. |
| C. Multi-file bounded repair | `config_repair_baseline.Baseline` + `RepositoryModel` + worker | **API/lab only** | Bounded Python AST edits, not generated-Python. No chat intent. |
| D. Grounded 6×6 world | `Conversation` move/goal over Session world | **Integrated** | Authored objects, known-grid. Altered layouts are possible by editing Session.world. |
| E. Multi-turn conversation | Session journal + workspace blob | **Integrated** | File, pending clarification, last intent/program/bindings, last procedure. Restart via existing save/load. |

## What chat can actually do

Supplied: CSV path, two operations (grouped totals, row listing), inclusive
minimum, asc/desc order, explicit capsules of the executed AST.

Inferred: column roles when exactly one text and one numeric column exist;
follow-up targets from session state; “do the same” vs a fresh request.

Not inferred, and not executed: below/under/less-than/max/negation/between,
conflicting order, multiple files, three-column schemas, JSON/SQLite/repair.

Contributor classes in chat: handwritten parser + vetted adapter (primary);
optional local GGUF for ordinary chat and unclear grain; no learned procedure
unless the user explicitly saved a capsule. Persistence is reuse, not
learning-to-learn.

## Closed evaluations

`artifacts/seed_assistant_benchmark_v2*.json` and the configuration-repair /
real-data studies remain historical. This matrix does not reopen them.
