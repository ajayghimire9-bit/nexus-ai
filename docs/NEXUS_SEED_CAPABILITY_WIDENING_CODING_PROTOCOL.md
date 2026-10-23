# Capability widening and coding-proposer pilot — locked development protocol

Base: reviewed tip `c8b3101c128e6eae2f18da257ee42bc323822dc7` of
`codex/seed-capability-evidence-audit`. Branch
`cursor/seed-capability-widening-coding`. This is an authored
source-development pilot, never confirmation. Closed audit artifacts
(`artifacts/seed_capability_audit*.json`, `*_verified_v2.json`) stay unread as
new scores. Historical 19/24 failures may be replayed only as development
diagnostics.

Executable source of truth: `configs/seed_capability_widening_coding.json`.

## Questions

1. Does completeness-preserving widening remove false certainty when the
   shortlist agrees on tested probes, and can it recover a correct candidate
   that starts outside the shortlist, without claiming universal equivalence?
2. Does a real local-model structured patch proposer, using only public tests,
   repository context and docs, produce and revise code that the existing
   worker can execute?
3. Does retained source-acquired experience help later *different* coding
   tasks beyond exact-repeat cache reuse?

Competing explanations: useful widening, extra call budget alone, leaked
assessment probes, manufactured model output, target-specific menus.

## Investigation comparison

Shared `EqualizedControllerConfig` except `enable_widening`. Learned priors
may reorder candidates only. Methods:

- `no_widening` — existing controller
- `boundary_first_widening`
- `cost_aware_widening`
- `learned_widening`
- `capsules_reset_widening`

Three independent task-generation seeds. Source length-two tasks may train
answer-only priors. Assessment uses length-three compositions plus
out-of-grammar tasks scored as uncertainty, not as identification failures of
the same kind. Families include cases where a fixed boundary heuristic is
insufficient (homogeneous shortlist probes).

Metrics: correctness (identified and assessment match), false certainty
(certainty claimed and wrong or alternatives remained), unresolved /
budget_exhausted, questions, candidate/probe calls, runtime, widening
overhead (widening-on minus matched no-widening calls).

## Coding comparison

Fresh projects, not the six historical audit IDs.

- A. Deterministic AST/CST operators only
- B. Same local model + repository tools + public-test feedback; acquired
  memory disabled
- C. Hybrid NEXUS loop (AST + local model)
- D. Persistent reuse only if a source-acquisition / later-different-task
  sequence exists

Include a bug fix, a new function, a multi-file feature and a documented
unfamiliar API. Comparable attempt/token/time budgets. Invalid proposals and
budget exhaustion are recorded. Private tests stay in the evaluator.

## Natural language

Actual local-model conversation and instruction-following, separate from
parser-only tests. Rubrics are explicit; full responses are preserved.
Subjective judgments are labeled. No keyword accuracy score is manufactured.

## Verification

Reconstruct costs and summaries from raw events. Replay final coding
artifacts without new inference. Confirm private assessment occurs after the
locked choice. Detect missing/duplicate evidence. Reject forged outcomes,
counters and summary tables. Verify historical audit artifacts and Seed
checkpoint hashes remain unchanged.

## Gates and claims

No automatic promotion. Learning-to-learn remains unestablished unless a
later-different-task gain beats ordinary cache/templates with acquisition
counted. Gemini is NOT RUN unless an authorized interface already exists.
If the standing 900 s experiment / remaining session budget is insufficient
for live assessment, implementation and development checks still complete
and the exact blocked step is named. Unavailable resources are never a pass.

## Screen (development only)

Investigation: widening methods must not increase false certainty versus
`no_widening` on the same tasks. Coding: report solved/failed/blocked
separately; do not treat public-test pass as complete correctness.
