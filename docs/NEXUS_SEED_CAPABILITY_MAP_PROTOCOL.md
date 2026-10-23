# Balanced capability map — locked development protocol

Branch `cursor/seed-capability-map`.
Base committed SHA `76ee543` (recovery-policy tip). Product parent
`e3d21b6`. Uncommitted extraction/API-audit work is preserved on this
checkout and is not rewritten. Do not merge `main`. Do not edit
`local_model_runtime.py`. Do not debit the frozen CPU ledger
**3564.568 s / 0 s debit**. Do not spend product `chat_usage.json` or
Metal.

Executable source: `configs/seed_capability_map.json`.
Runner: `scripts/run_seed_capability_map.py`.
Verifier: `scripts/verify_seed_capability_map.py`.

This is an initial capability screen, not a statistically definitive
benchmark and not AGI. Closed six-area, conversation-capability and
extraction task IDs are unused. Previously inspected tasks were used
only to design the harness.

## API audit (preserved, not rescored)

Wrong API selection, qualified names, unsupported notation and wrong
argument shape remain separate outcomes. Contract-ID schemas narrow
the output space; they are not learned schema discovery. Helper
presence, caller presence, required call, types and behavior remain
separate checks.

## Methods

A. `model_alone` — same 1.5B coder, no tools or documents.
B. `tools_cache` — same model, vault, calculator and coding worker,
   simple fixed orchestration, ordinary exact cache. Acquired solution
   memory empty.
C. `nexus` — current routing: eligible-always-extract when the public
   contract is eligible; vault cite for documents. Same information,
   tools, decoding and budgets as B.

B and C are identical for conversation, mathematics and logic in this
screen (same calculator and prompts). Those C cells reuse B and are
labeled `identical_to=tools_cache`. Coding and knowledge differ: C
uses extract routing and deterministic vault citation.

Programmer-supplied: arithmetic AST calculator, extract route, vault
retrieve/cite, ordinary cache. Not learned schema discovery.

## Tasks

Six fresh tasks in each of conversation, mathematics, logic, coding
and knowledge (30). Easy and harder cases. Public examples specify
the requirement; hidden tests check those requirements. No solution
programs are supplied for mathematics or logic.

Conversation subjective quality is **pending human review**. Automatic
checks are explicit rubric acts, not a keyword quality score. Full
replies are stored.

## Budgets

Standing grant: **900 s** wall, 180 model calls, local CPU
(`-ngl 0 --device none`), temperature 0, seed 42. Frozen research
ledger leftover is not used. If the cap is hit, save a partial grid.
Do not drop hard tasks to finish a prettier table.

Estimated unique completions if B/C reuse holds: about 70–110. At
~5 s/call that is 350–550 s plus startup. The 900 s cap should cover
the planned grid; if it does not, the verifier reports missing cells.

## Learning

Do not resume the paused ranking policy. This screen does not
establish learning-to-learn. A separate future protocol is
[experience transfer](NEXUS_SEED_EXPERIENCE_TRANSFER_NEXT.md). Do not
run it here.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_capability_map.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_capability_map.py artifacts/seed_capability_map
PYTHONPATH=src:.deps python3 scripts/verify_seed_capability_map.py artifacts/seed_capability_map/seed_capability_map.json
```
