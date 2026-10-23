# Six-area comparison — development results

Branch `cursor/seed-six-area-comparison`. Protocol/implementation `b50a642`
committed before scoring. This results commit is separate. Base reviewed
`a47c070`. Closed scoped-id and capability-audit artifacts were fingerprint-
checked and not rewritten. Not confirmation. Not learning-to-learn. Not AGI.

Independent verifier: `valid: true` on the expected grid (12 investigation /
12 coding / 3 reuse / 3 retention / 2 reasoning / 6 language), 3128 execution
events, 15 `final_files` replays. Reuse-loop cells recorded completion totals
but not `model_trace`; those costs were taken from the saved totals. Coding
cells reconstructed from traces. Historical hashes unchanged. Gemini NOT RUN.

Standing grant debit: wall **55.153081 s**. Session ledger after this run:
**2369.450522455996 used / 1230.549477544004 remaining**.

The intended loop (request → language → memory → proposal → sandbox → tests
→ explanation) ran. Procedure/repair memory and learned investigation policy
were scored as separate improvements.

## Learning-to-learn (investigation)

One seed, two length-3 in-grammar assessments plus one out-of-grammar square
task. Capsules cleared on `capsules_reset`; policy structure destroyed on
`shuffled`. `identified` counts only `identified_within_catalogue`.

| Method | Identified /2 | Assessment match /2 | False certainty /3 | Calls | Questions |
|---|---:|---:|---:|---:|---:|
| fixed_boundary | 0 | 1 | 2 | 486 | 2 |
| learned | 0 | 1 | 2 | 576 | 1 |
| capsules_reset | 0 | 1 | 2 | 571 | 1 |
| shuffled | 0 | 1 | 2 | 499 | 2 |

Learned did not beat the fixed policy on accuracy and used more calls.
`advantage_vs_fixed` is false. Reset stayed near learned, so this grid does
not show a memory-only win either. Learning-to-learn is unestablished.

## Unfamiliar coding

Privately authored IDs, not the closed scoped-id or widening sets. Same
installed Qwen 0.5B, public tests and budget. Public pass is not complete
correctness.

| Spec | model_tools | model_tools_cache | nexus_repair_memory |
|---|---|---|---|
| py_clip_hi_src (bug) | solved / private pass | solved / private pass | solved / private pass |
| py_slug_join (new function) | failed | failed | failed |
| py_levy_then_credit (multi-file) | failed | failed | failed |
| py_retry_last (documented API) | failed | failed | failed |

Only the inclusive-maximum bug fix passed independent tests. New-function,
multi-file and documented-API tasks did not. Cache did not help different
requests. Repair memory did not improve these four cells over model+tools.

## Knowledge reuse and retention

Source `py_clip_hi_src` then different instance `py_age_cap`. Unpatched
`age.py` fails the assessment cases.

| Condition | Later private | Path | None (unpatched) |
|---|---|---|---|
| model_tools | pass | live loop | fail |
| model_tools_cache | pass | live loop (exact miss) | fail |
| nexus_repair_memory | pass | applied schema, no new complete() | fail |

Repair memory transferred without another model call. The local model also
solved the later instance from scratch, so accuracy does not isolate memory.
One success is not a 100% rate.

Retention on the source clip task after later work: unpatched fails; exact
cache and repair memory still pass. That is persistence of a stored patch,
not learning-to-learn.

## Reasoning

Both authored programs already implement the required net sum and half-open
constraint. The worker executed them and both passed. This checks sandbox
execution, not that the model discovered the reasoning.

## Language

Actual local-model turns. Scoring is real-state plus needed question.

- `paraphrase_help`: generic offer; does not name a registered capability.
- `spelling_workspace`: “The coding workspace is not selected.” Describes
  empty state; scorer did not mark a named resource.
- `ambiguous_fix` and `missing_then_list`: ask which coding workspace.
  Follow-up still asked the workspace question instead of listing repos.
- `factual_selected`: names none and repeats the pending question.
- `beyond_tools`: asked which workspace instead of refusing the flight.
  A leftover pending clarification captured this turn.

Unsupported-request handling failed on this grid. No keyword accuracy score.

## Resources

- Wall 55.153081 s; request wall from traces/totals 47.529 s.
- 17 counted completions, 1582 generated tokens, 5999 input tokens.
- Model sha256 `74a4da8c…` unchanged. Cold startup 0.76676 s.
- Closed `local_model_runtime.py` hash unchanged. No paid services. GPU unused.

## Capability status

| Area | Status |
|---|---|
| Unfamiliar coding | 1/4 families passed; new-function and multi-file failed |
| Language | mixed; unsupported request captured by pending clarify |
| Reasoning | sandbox execution passed on authored programs |
| Knowledge reuse | repair applied without a new complete(); model also solved later |
| Learning-to-learn | unestablished (learned more expensive, same match) |
| Retention | cache and memory still pass source; unpatched fails |
| Gemini | NOT RUN |

## Next

Highest-value next task: a later instance the first-round model cannot already
solve, so repair memory is the only private pass, and a conversation turn that
clears pending clarification before unsupported requests. Do not retune this
closed grid as confirmation. Do not merge `main`.
