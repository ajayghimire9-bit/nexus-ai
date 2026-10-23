# Capability follow-up — locked development protocol

Branch `cursor/seed-capability-followup`.
Base `1bc5bd4` (capability-map results). Product parent `e3d21b6`.
The original 90-cell screen is **not rescored**. Uncommitted extraction
work on this checkout is preserved and not rewritten. Do not merge
`main`. Do not edit `local_model_runtime.py`. Do not debit the frozen
CPU ledger **3564.568 s / 0 s debit**. Do not spend product
`chat_usage.json` or Metal.

This is four targeted repairs from the capability map, not a new AGI
percentage and not learning-to-learn. Ranking policy stays paused.
Acquired solution memory stays empty.

## 1. Knowledge conflicts

Do not sort by ingestion timestamp and call that freshness. Each
document stores subject, source version, effective date, ingested-at
and explicit `supersedes` when available.

- An older ingestion can still be the current fact if it supersedes
  or has a later version and effective date.
- A newer unrelated bulletin does not replace a different subject.
- Same-subject rows with different content and no replacement
  relationship are reported as a conflict.

Methods, all offline: `dump_all` (current cite), `timestamp_sort`
(naive), `provenance` (this adapter). Fresh corpus, not the harbor
07:00/09:00 map docs.

## 2. Inspectable mathematics

Before execution the model must produce quantities, units,
relationships and the unknown. The host validates that statement,
then compiles. A syntactically valid expression that omits a required
operation fails `expression_represents_problem`.

Methods, live, fresh tasks: `calculator_direct` (existing JSON
expression route) versus `interpret_compile`. Gold answers are used
only to score, not to compile.

## 3. API use versus coordinated editing

Two families, scored separately, same tools and public evidence on
both methods.

- `coding_api`: select and bind a documented API. Helper generation
  is not required.
- `coding_coord`: generate a helper and make the caller use it.
  Helper presence, caller presence, required call, types and behavior
  stay independent.

Methods: `direct` and `nexus` extract routing. Closed map IDs unused.

## 4. Blinded conversation review

Frozen capability-map replies are reviewed on five dimensions:
relevance, factual accuracy, clarification, correction handling,
naturalness. Methods were identical on that screen. This is an
**agent review of frozen transcripts**, not a second independent
human. Keyword presence is not the quality score.

`Book the later one` must ask when no prior option exists. A booking
keyword is insufficient. The unresolved-referent detector is
programmer-supplied and tested offline.

## Budgets

Standing grant: **900 s** wall, 80 live model calls, local CPU
(`-ngl 0 --device none`), temperature 0, seed 42. Knowledge and
conversation review do not use the model. Planned live cells: 20.
If the cap is hit, save a partial grid. Do not drop hard tasks.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_capability_followup.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_capability_followup.py artifacts/seed_capability_followup
PYTHONPATH=src:.deps python3 scripts/verify_seed_capability_followup.py artifacts/seed_capability_followup/seed_capability_followup.json
```
