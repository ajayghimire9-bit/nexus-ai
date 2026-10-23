# Capability follow-up — development results

Branch `cursor/seed-capability-followup`.
Protocol `4607542`. This results commit is separate.
Base `1bc5bd4`, product parent `e3d21b6`. Artifact hash
`df3e216aa8c542d8864b14a8e44657a0e1e308493240fdac29f8753d6ccaae3c`.
Verifier `valid: true` on 29/29 scored cells plus 6 frozen
conversation reviews. The original 90-cell map was not rescored.
Not confirmation. Not learning-to-learn. Not AGI.

API-audit hash unchanged
(`17ca8b1d867649209c50dc21ccc9569917f305d2338d27110975f1b21fad3b5f`).

## Commands

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_capability_followup.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_capability_followup.py artifacts/seed_capability_followup
PYTHONPATH=src:.deps python3 scripts/verify_seed_capability_followup.py artifacts/seed_capability_followup/seed_capability_followup.json
```

## 1. Knowledge conflicts

| Method | Update | Unrelated newer | Ambiguity |
| --- | --- | --- | --- |
| dump_all | 0 | 0 | 0 |
| timestamp_sort | 0 | 0 | 0 |
| provenance | 1 | 1 | 1 |

Harbor v2 (06:30, version 2, effective 2026-10-15, supersedes v1)
was ingested **earlier** than v1. Timestamp sort picked v1 (09:00).
Dump-all included the later weather bulletin. Provenance kept v2,
dropped weather, and reported the two Mora watches as a conflict
with no replacement. Ingestion time was not used as freshness.

## 2. Inspectable mathematics

| Method | passed / 6 |
| --- | ---: |
| calculator_direct | 2 |
| interpret_compile | 1 |

Units (`3.2 L → 3200 ml`) passed the existing calculator. The
structured statement computed the same 3200 but failed validation:
`unknown` was `[]` and the unit was `milliliters` rather than `ml`.
That is the point of inspectability — a usable number is not a valid
interpretation.

Algebra emitted `4n - 5 = 19` (not executable). Word and percent
produced prose or `25% * 64`. The trap compiled `12 - 3 / 2` and
failed `expression_represents_problem`. Underspecified unit price
asked on both routes.

The 1.5B did not fill quantities / relationships / unknown. A richer
prompt did not beat the calculator on this fresh set.

## 3. API use versus coordinated editing

| Family | direct | nexus |
| --- | ---: | ---: |
| coding_api | 0/2 | 0/2 |
| coding_coord | 0/2 | 0/2 |

API: `high_cut` called `clip_hi(bag.nums, bag.hi)` — the name was
present (`required_call` true, coverage true on direct) and the
arguments were unbound. Extract dropped the caller. Helper generation
was not required on this family.

Coordinated: `under` was written in `app.py` as yes/no, not a Boolean
in `util.py`. `pack_ok` never appeared. Helper and caller were both
absent. Extract was `ineligible_optional_or_nullable` and fell back
to direct. Same docs and public tests on both methods.

## 4. Conversation review (frozen transcripts)

Agent review of the capability-map replies. Methods were identical.
Not an independent human. Keyword presence was not the score.

| Dimension | passed / applicable |
| --- | ---: |
| Relevance | 5/6 |
| Factual accuracy | 3/5 |
| Clarification | 0/1 |
| Correction handling | 1/1 |
| Naturalness | 4/6 |

Fails: invented high/low-tide split; invented “harbor pigeon”;
copied “A estuary”; refusal on “Book the later one.” South-cliff
correction and beginner salinity held.

Unresolved-referent detector: 3/3 (later-one asks; named ferry does
not; later-one after dawn/dusk options does not). Frozen model
reply remains a refusal. A booking keyword is not sufficient.

## Cost

20 model calls (18 inference), 86.787 s wall, combined RSS
2082.094 MiB. Frozen debit **0**. Product chat unused. Metal unused.
Process cleaned up. Original map not rewritten.

## What came from where

Provenance resolution, statement validation, the calculator, extract
routing and the referent detector are programmer-supplied. The model
produced ordinary text, malformed statements, and unbound API names.
Retrieval was not used on the provenance corpus (authored records).

## Next three changes

1. Narrow the math statement schema the same way API IDs narrowed
   selection — empty `unknown` and string `missing` should be
   rejected before compile. That is still not schema learning.
2. Live-test ID-schema assembly on the fresh API tasks. Selection of
   `clip_hi` already happened; wiring `item['bag']['nums']` did not.
3. Keep coordinated edits on a route that can write the helper file.
   Extract marked both coord tasks ineligible, so C never differed
   from direct.

Do not tune on this follow-up and rescore it. Independent human
review of the six conversation transcripts is still pending.
Experience-transfer remains unrun.
