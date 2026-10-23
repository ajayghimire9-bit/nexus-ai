# Capability milestone — development protocol

Base: reviewed tip `33b9fde` of `cursor/seed-guarded-template-reuse`.
Branch `cursor/seed-capability-milestone`. Development only. Do not rescore
closed reuse, interrupt, or six-area grids. Do not edit
`src/nexus/seed/local_model_runtime.py`.

## Repair labels and verification

AST operators carry an explicit family (`compare_op_swap`, `or_to_explicit_none`,
`insert_function`, …). A ledger updates those labels from observed **public**
outcomes only. The verifier reconstructs family scores from saved execution
records and replays final patches in the bounded worker. Private tests stay
assessment-only.

## Ranking

Three rankers on fresh repositories, same AST candidate pool and budget:

1. `fixed_diagnostic` — public tests beat mixed request cues and misleading docs.
2. `source_frequency` — family success counts from two source solves.
3. `learned` — outcome-updated family rates from those same source solves.

Assessment cues: mixed request, misleading exclusive documentation, and two
simultaneous defects. Closed task IDs are refused.

## Token interface, unconfounded

One new-function task. Four cells: raw vs symbol editing at 128 and 512
tokens. Revision budget is 2 in every cell. Only interface and `max_tokens`
change. Total generation budget is reported as `2 × max_tokens`.

## One realistic repository feature

`py_invoice_slug_feature` requires file discovery, a new function, coordinated
edits, public-test revision and independent replay. Record which parts the
local model generated and which existing operators supplied. Passing is not
required for the milestone to be measured.

## Conversation quality

Explanation, paraphrase, correction, document/tool question, and topic change.
Score factual content, attribution and workspace state — not keyword presence.

## Investigation policy

`fixed_boundary` remains the default. Learned investigation is not re-run and
not promoted.

## Expected grid

2 ranking sources, 9 ranking cells, 4 token cells, 1 feature cell, 5 language
cells.

## Gates

No automatic promotion. Learning-to-learn unestablished. Do not merge `main`.
