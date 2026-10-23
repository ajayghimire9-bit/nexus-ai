# Balanced capability map — development results

Branch `cursor/seed-capability-map`.
Protocol/implementation `9906be6`. This results commit is separate.
Base `76ee543`, product parent `e3d21b6`. Artifact hash
`f3b2d0e8a66832154f19f5ade8ab2c02b34fc393a44eaedb42a95e417d305edc`.
Verifier `valid: true` on 90/90 cells. Not confirmation. Not
learning-to-learn. Not AGI. Do not tune on this screen and rescore it.

API-audit artifacts are unchanged
(`17ca8b1d867649209c50dc21ccc9569917f305d2338d27110975f1b21fad3b5f`).

## Commands

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_capability_map.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_capability_map.py artifacts/seed_capability_map
PYTHONPATH=src:.deps python3 scripts/verify_seed_capability_map.py artifacts/seed_capability_map/seed_capability_map.json
```

## Per-area (passed / 6)

| Area | A model alone | B tools+cache | C nexus |
| --- | ---: | ---: | ---: |
| Conversation | 4 | 4 | 4 (reuse B) |
| Mathematics | 1 | 2 | 2 (reuse B) |
| Logic | 2 | 2 | 2 (reuse B) |
| Coding | 2 | 2 | 2 |
| Knowledge | 1 | 5 | 5 |

Conversation quality is **pending blinded human review**. Automatic
checks are rubric acts. B and C were identical for conversation,
mathematics and logic and were reused.

## What helped

Knowledge is the only area where tools clearly beat the unaided model
(1/6 → 5/6). C’s deterministic vault cite won the competing-pilot item
that B’s generated answer missed, and lost freshness because retrieve
returned both current `07:00` and stale `09:00`. Token overlap was not
the score.

The calculator helped `2.5 kg → 2500 g` (`expression_represents_problem`
true). Algebra returned a broken expression (`SyntaxError`); the tool
did not invent a correct `(22-7)/3`. Underspecified crossing time asked
for clarification on all methods.

## What did not

Logic: only Reed-Moss-Kelp order and the unweighed box (no certainty)
passed. Relations, counterexample 6, contradiction, and the 4-hour
plan failed.

Coding: optional missing-value and inclusive-cap repair passed on
direct. New-function behavior passed public and private; coverage
failed because “returns wage” was parsed as a required API. Nested
list, `trim_span` composition and the two-file `above`/`pass_gate`
task failed. Extract did not add a private solve; it lost public on
the bug repair. Helper/caller/call stay independent: coordinated
edit had helper and caller both absent.

Conversation automatic fails: paraphrase (“ocean” vs required “sea”)
and “Book the later one.” (refusal, no question). Follow-up,
correction to south cliff, topic return, and beginner salinity passed
the rubric. Full replies are in the artifact.

## Cost

74 model calls (70 inference), 187.184 s wall, cache hits 0, combined
RSS 2125.859 MiB (`ps` sample). Frozen debit **0**. Product chat
unused. Metal unused. Process cleaned up. Cold start is in startup
status, not a task family. Acquired solution memory empty. Ranking
policy not resumed.

## Next three changes (from the complete grid)

1. Mathematics: the model must emit a valid expression before the
   calculator can help. Algebra/word/percent/steps all failed that
   step.
2. Knowledge freshness: citation dump includes stale rows. Rank or
   filter by timestamp before rendering. That is adapter work, not
   schema learning.
3. Coordinated two-file edits and documented API composition remain
   the coding bottleneck. Extract routing did not fix them on this
   set and can lose a public pass.

Experience-transfer is still a separate unrun protocol.
