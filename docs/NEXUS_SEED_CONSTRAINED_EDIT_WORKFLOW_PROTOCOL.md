# Constrained function edits and one generated-code feature — development protocol

Base: reviewed tip `aa2b015` of `cursor/seed-boundary-state-workflow`.
Branch `cursor/seed-constrained-edit-workflow`. Development only. Do not
rescore the closed boundary-state grid. Do not edit
`src/nexus/seed/local_model_runtime.py`.

The last pilot accepted teacher-labeled `Lt→LtE` and passed conversation
file-switch, but the model never queued an edit. Failures were
`height.ok` (path/suffix) and `insert_function` on an existing symbol.

## Changes before scoring

1. NEXUS plans the edit: exact file path, existing or new symbol, and
   replace versus insert. The model returns only `function`. Source-hash
   checks and an explicit preview stay in the assembler.
2. Report raw proposal validity, deterministic normalization and final
   three-point / assessment correctness separately.
3. One `formatted_identifier` feature (`py_tag_colon_feature`) is locked
   before outcomes. The existing AST catalogue must be shown unable to
   pass its public tests. AST-only and AST+constrained share tools, docs
   and budget.
4. Conversation requires source-backed contents, an operation change
   (totals → rows), a topic change, then a return to the same file.
5. Learned ranking and acquired-memory comparison stay paused until a
   generated solution can be executed and revised.

## Expected grid

1 semantic cell, 2 feature cells, 4 language cells.

## Gates

No ranking, investigation or memory promotion. Learning-to-learn
unestablished. Do not merge `main`.
