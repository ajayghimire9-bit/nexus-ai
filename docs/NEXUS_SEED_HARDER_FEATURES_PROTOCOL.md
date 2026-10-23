# Frozen recipe, harder features, contract acquisition — protocol

Base: reviewed tip `b23e49f` of `cursor/seed-contract-two-stage`.
Branch `cursor/seed-harder-features-acquisition`. Development only. Do not
rescore the closed contract grid. Do not edit
`src/nexus/seed/local_model_runtime.py`. Standing grant: 900 s this
experiment, carried session
**2806.847834455996 used / 793.152165544004 remaining**, local CPU.

## Frozen recipe

1.5B coder, ChatML, `json_body`, explicit contract when one exists, wired
discovery, and two charged revision stages under three `complete` calls.
Do not compare raw vs ChatML or existing vs contract again.

## Changes before scoring

1. Assess five fresh harder tasks whose requirements are locked here:
   list-of-records sum with missing amounts and an empty list; missing
   fields; empty strings; two interacting predicates; a two-file insert.
   Keep every failure.
2. On the same five tasks, measure contract acquisition. `supplied` uses
   the benchmark contract. `inferred` builds a contract from existing
   source and public examples. If that is incomplete, NEXUS asks and the
   teacher returns the public-field contract (`asked`). Record origin
   separately from coding scores.
3. Persistent improvement is gated. Run the acquired-experience
   comparison only if the supplied frozen recipe is privately correct on
   at least 4 of 5 tasks, including the list-of-records and two-file
   tasks. The comparison reuses `RepairSchemaStore` / retrieved repair
   versus a scratch frozen-recipe run on one held-out inclusive replace.
   Count acquisition cost, harmful reuse and saved `complete` calls. If
   the gate fails, the comparison is `NOT_RUN` and learning research
   stays paused.

## Expected grid

1 inspect, 5 supplied cells, 5 acquisition cells, 0 or 2 transfer cells.

## Gates

`fixed_boundary` remains the default. No ranking promotion. Do not merge
`main`.
