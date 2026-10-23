# Selective reuse — development protocol

Base: reviewed tip `e6515fa` of `cursor/seed-interrupt-and-transfer`.
Branch `cursor/seed-selective-reuse`. Development only. Do not rescore the
closed interrupt or six-area grids as confirmation. Do not edit
`src/nexus/seed/local_model_runtime.py`.

The interrupt/transfer pilot applied `Lt→LtE` automatically, including when
the later requirement was exclusive. Invalid snippets were still rejected, but
revisions did not always see the staged source and the precise validation
error. Valid-edit rate was not separated from private-test correctness.

## Changes before scoring

1. A retrieved repair is a **proposal**. Before applying a boundary transform,
   check the current request and **public** tests only. Inclusive and exclusive
   must yield different decisions (`apply` vs `refuse`). If the requirement is
   still ambiguous, ask or abstain. Private tests stay in the evaluator.
2. Edit generation uses the existing structured patch actions. Prefer
   `insert_function`, `insert_after_symbol`, or a unique symbol replace. A
   revision prompt includes the current staged source and the exact validation
   error. Incomplete snippets are not accepted as whole modules. Report
   structurally valid edits separately from functional private-test pass.
3. Fresh later tasks, predeclared:
   - `py_width_ok` — same repair (inclusive).
   - `py_keep_exclusive` — opposite behavior.
   - `py_pair_label` — unrelated family.
   - `py_cutoff_ambiguous` — clarification (`Fix the cutoff check.`).

Compare gated memory with the ordinary automatic template and the same local
model solving from scratch. Count correct reuse, harmful reuse, unnecessary
abstention and total completions/tokens.

## Investigation policy

`fixed_boundary` remains the default and is **not** re-run here. The learned
policy's lower call count on the previous diagnostic is not useful because it
solved fewer tasks. No promotion.

## Expected grid

2 coding cells, 1 genuine AST source, 12 transfer cells (4 later × memory /
template / scratch).

## Gates

No automatic promotion. Learning-to-learn unestablished. Do not merge `main`.
