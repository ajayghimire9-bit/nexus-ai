# Phase 1–7 bounded workbench

The owner requested an end-to-end implementation across all seven phases. This
extends existing Seed modules rather than replacing the architecture. Frozen
GRU/RSSM/readout checkpoints, historical results and research boundaries remain.
The attached roadmap predates the two completed investigation studies; its
“Phase3 unrun” statement is superseded by their actual artifacts and the new
independent-tree replication. The attachment itself is preserved.

## What is implemented

1. **Structured knowledge:** existing `structure.state/features/learning` graph,
   explicit unknowns, bounded observation history, conflict checks, source-only
   feature construction, separate one-use assessment, retention and rollback.
   The workbench exposes typed graph requests and pure inspection.
2. **Mechanisms:** existing typed preconditions/effects, known failures,
   uncertainty, bounded BFS composition/planning and legacy skill adapter.
   Supplied mechanisms are labeled supplied. Numeric residual support remains
   optional; no historical neural weights are retrained by this workbench.
3. **Investigations:** existing source decision-tree fitting, freeze/hash,
   metered question callbacks and version-space checker. Fixed, hybrid,
   greedy and random controls are implemented. Studies live in read-only
   evidence; a source tree is never promoted by a GUI score.
4. **Grounded language:** existing finite concept teaching, checked skills,
   source wording and attributed text. NEW: multiword command phrases reference
   separately verified skill revisions, with explicit replacement and durable
   evidence. Arbitrary prose cannot execute a program or grant permissions.
5. **Program growth:** existing checked list macros plus NEW typed-expression
   subtree discovery: conditions, scalar/list/temporal compositions, lexical
   binding checks and multiple retained functions. A proposed function must
   compress source representation and pass disjoint one-use assessment examples.
   Rejection, repeated-review prevention, capacity8, persistence and per-function
   rollback work. Macro execution can be slower; storage and search benefits
   are distinct from reduced interpreter instructions.
6. **Mixed curriculum:** existing six operator stages plus NEW generated source
   exercises in coding/reasoning/language/world. The existing kind-statistics
   update tracks VERIFIED answers and bounded epsilon exploration schedules
   weak practice families. At most8 exercises/request,48/session; attempts
   persist and cannot be resubmitted for free feedback. They are public source
   exercises, not scientific holdouts or proven cross-domain transfer.
7. **Local product:** existing chat/labs/save/restore plus a seven-phase view,
   richer typed programming/library UI, source lesson answering in chat, shared
   session links, taught phrases and explicit pure tools. Read-aloud uses an
   installed local browser voice only; absent voices produce a clear unavailable
   message and no remote service. No microphone recognizer/model is installed
   or claimed. General conversation and unrestricted coding remain unproven.

These are working bounded workflows. They do not make the scientifically
unfinished parts of all seven phases “solved.” In particular: novel open-ended
grammar induction, general tool use, autonomous scientific curriculum discovery,
robust cumulative library benefit, general learning-to-learn and AGI have not
been demonstrated. No result or capability is fabricated to fill those gaps.

## Try the connected workflows

Start the existing bounded local host:

```sh
python3 -I -S scripts/run_learning_lab.py --allow-seed --port 8785 --max-runtime-s 900
```

Open `/chat` and `/foundation` (the Phase1–7 workbench). Use the same session
link; returning to chat restores the active shared Session without replaying
commands. Saved sessions still require their hash receipt after a host restart.

In chat:
- `Show phases`
- `Generate lessons`, then `Answer lesson 1: <JSON answer>`.
  Each lesson displays its executable program and inputs. Numbers remain fixed
  within the latest batch even when answered out of order.
- Teach/verify a skill through the existing example/check conversation, then
  `Teach phrase "turn the numbers around" as reverse`.
- `Run phrase "turn the numbers around" on [1, 2, 3]` executes the checked
  revision. `Replace phrase "..." as skill` explicitly versions a replacement.
- Checked expression functions also accept a taught phrase: `Teach phrase
  "count distinct items" as f_<id>`, then `Run phrase "count distinct items"
  on [3, 1, 3]`. A rollback disables phrases referencing that revision, so
  language cannot continue using a reverted improvement silently.
- `Write code to sort and remove duplicates on [3, 1, 3, 2]` still runs real
  bounded typed code, with equivalent explanatory Python displayed.

In the foundation workbench:
- Inspect all seven phases and the same graph/journal. Repeat inspection to
  verify no state advancement.
- Submit `structure_observe`, `structure_install`, `structure_plan`, source
  example/review or rollback as typed JSON in the graph panel. Its authored
  observation/mechanism examples are explicitly supplied, not learned discoveries.
- Execute typed JSON with named inputs: conditions, maps, bounded repetition,
  assertions, functions and existing skills share one instruction meter.
- Select `expression_propose` in advanced operations. The sample contains
  three distinct contexts sharing a count-of-distinct-items subtree. Propose
  returns actual source-discovered candidates and source execution cost.
- Select `expression_review`: its different input/task checks either retain
  or reject the proposal. Successful function names appear in `active_expressions`
  and are usable through `{"op":"call","name":"f_<id>","value":{"op":"var","name":"x"}}`.
- `expression_rollback` removes the active pointer while preserving the journal;
  an accepted revision can be restored. Failed/reused assessments cannot train
  later proposals or overwrite earlier retained functions.
- `tool` accepts only `execute`, `retrieve`, `inspect_graph`, `phrase`.
  Unknown tools, shell/network/training/grant requests and recursive tool dispatch
  are rejected. These are finite local tools, not unrestricted external agents.

## Data engineering and integrity

All additions use existing `seed_foundation` events in Session/E1 Journal.
Derived proposals, reviews, aliases and exercise results are recomputed during
restore; clients cannot forge acceptance or omit an assessment. Source examples,
assessment inputs and task IDs are checked for reuse. New functions are data-only
typed programs; free-variable analysis permits only explicit x input and rejects
unreviewed recursive/function dependencies. Literal records are never traversed
or executed as code. Existing skills and frozen recurrent state are preserved.

Counts expose source fitting, proposal checks, storage-node savings, actual
interpreter instructions, source curriculum rewards and research-host resources
separately. Engineering unit/GUI fixtures are not registered research results.
The one authorized scientific run here is the separately committed replication.
No scientific execution starts from chat, lesson generation, tools or inspection.
