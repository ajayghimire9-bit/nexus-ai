# Seed hybrid architecture

The user's seven-component design is the implementation target. S0–S1 remains
the preserved symbolic baseline; this branch adds an optional tiny MLP, journal-
derived working state, bounded goal search and experimental existing-controller
question selection. See [locked engineering protocol](../NEXUS_SEED_HYBRID_PROTOCOL.md).

- **Language perception:** optional356-parameter MLP trained on authored movement
  labels; exact parser remains authoritative, unsupported inputs abstain. No GRU
  is added merely to appear neural. No open-ended understanding claim.
- **Working memory:** compact recurrent symbolic state plus existing structured
  concept evidence. Neural recurrent memory is not implemented.
- **New concepts:** existing version-space learner. Neural-guided induction is future work.
- **Reasoning:** compositional typed moves plus bounded BFS for authored grid goals.
- **Questions:** active disagreement, random comparator, optional meta-controller
  adapter using only answered-card evidence. Useful RL remains unestablished.
- **Learning to learn:** existing NEXUS EpsilonGreedyController is reused, not
  replaced. Feedback integration is engineering; improved learning requires a study.
- **Generation:** grounded templates and actual traces. A small trained local
  text generator is not yet implemented.

Seed is a bounded symbolic teaching loop. It infers finite meanings from evidence;
the parser, object schema, grammar and primitive actions are authored.

```mermaid
flowchart LR
  UI[Local Learning Lab] --> API[Loopback Seed API]
  API --> Session[Seed session]
  Session --> Parse[English subset]
  Session --> Neural[Optional tiny local MLP]
  Neural --> Plan
  Session --> Working[Journal-derived working state]
  Session --> Learn[Consistent predicates]
  Learn --> Ask[Disagreement question]
  Parse --> Plan[Typed program]
  Learn --> Plan
  Plan --> World[Authored object world]
  Session --> Journal[Existing E1 journal]
  Journal --> Save[Private JSON revisions]
  World --> UI
  Ask --> UI
```

## Code ownership

- `src/nexus/seed/core.py`: typed moves, parser, 37-predicate grammar, evidence,
  corrections, questions and atomic sandbox execution.
- `src/nexus/seed/storage.py`: append-only JSON revisions, hash links and
  replay-based reconstruction. No pickle or arbitrary executable imports.
- `src/nexus/seed/lab.py`: bounded local session registry and API dispatch.
- `web/learning-lab/seed.html`: real teaching UI, not a fake conversation script.
- `scripts/run_learning_lab.py`: existing shared server with opt-in Seed routes.
- `src/nexus/seed/comparison.py`: authored development comparison, separate from
  private sessions. Its recorded run is incomplete and must not be rerun.
- `src/nexus/seed/perception.py`: bounded JSON-only inference; training reuses
  `nexus.nn.factory.build_mlp` through the precommitted pilot runner.
- `src/nexus/seed/working.py`: compact state derived by recurrent event updates.
- `src/nexus/seed/planning.py`: bounded object-grid BFS, no replacement MPC stack.
- `src/nexus/seed/question_policy.py`: thin existing-controller adapter, no new RL framework.

## Reuse

Seed uses `evolution1.fixtures.Journal/verify_journal` and
`evolution1.catalogue.canonical/digest`. Persistence follows the existing durable
Lab revision pattern without pretending a concept is a strategy-catalogue record.
It adds no generic memory, evolution framework or meta-controller.

The scientific `Work` meter counts environment/model operations. Symbolic labels,
predicate tests and sandbox actions use explicit domain counters instead; they
are not real scientific simulator interactions. No historical model is loaded
as a language model.

## Meaning, action and storage

The version space contains property atoms, negations and two-property positive
conjunctions. Labels remove inconsistent predicates. Questions use permissible
examples on which remaining predicates disagree. Corrections supersede labels
without erasing old events. Contradiction must not trigger a guess.

A concept command acts only when consistent predicates agree on a unique object.
Every clause and boundary is validated before committing the proposed world.
`then` composes existing primitives; it is not learned skill synthesis. Shell
commands, file permissions and research grants are outside the program type.

Restore checks typed events/hashes and replays state. Hash chains detect
corruption, not a local owner rewriting everything. Cancellation is cooperative,
not OS-level sandbox isolation. Private snapshots stay under ignored `runs/`.

## Evidence and boundaries

Cross-scene teaching and process restart passed functional/browser tests.
The active-versus-random comparison is incomplete. No general language, neural,
cross-domain, control, learning-to-learn or AGI result follows. Read
[results](../NEXUS_SEED_RESULTS.md), [charter](../NEXUS_SEED_CHARTER.md), and
[roadmap](../NEXUS_SEED_ROADMAP.md) before extending the learner.
