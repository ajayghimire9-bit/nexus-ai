# Shared NEXUS Learning Brain and four labs

Engineering branch `codex/seed-shared-learning-labs`, starting revision
**7fbc1b4f67b3a820332421762ffcea49b1ab3693**, matching fetched GitHub.
This extends Seed; it does not replace historical research, frozen weights or
the earlier negative learning-rule results. The carried scientific ledger stays
**1943.6321034559958s used /1656.3678965440042s remaining**. No scientific
experiment is authorized or launched by this document or the GUI.

## What is connected

One existing Session/E1 Journal owns teaching evidence, proposed programs,
development checks, accepted skill revisions and rollback. Existing append-only
storage saves and restores that SAME session. There is no second memory database,
evolution framework, server, checkpoint trainer or autonomous worker.

- **Language Lab:** invented words over the existing finite Predicate grammar;
  labeled objects, corrections, disagreement questions and typed “move … then …”
  instructions. This is supplied syntax plus learned finite meanings, not broad
  grammar acquisition or unrestricted language understanding.
- **Coding Lab:** small list programs learned from input/output examples and
  checked on different inputs. Vetted primitives are reverse, sort, unique,
  increment and even-filter; at most two operators. Data is never Python, shell,
  imports or unrestricted executable source.
- **Reasoning Lab:** list patterns and the six existing spatial/attribute
  relations. Relations use the original Relation checker extracted from
  semantic_lessons without changing its public names or behavior. Coding skills
  can execute here on compatible inputs; coordinate rules can execute in Coding.
- **World Lab:** observations, typed actions, goals and the original authored
  movement reward. Learned words identify objects; motion skills compile to
  existing Move programs. Existing bounded BFS is the explicitly labeled known-
  grid reference. This does not promote a new neural controller or alter MPC.
- **Shared Skill Library:** compatible labs reuse the same tested executable
  program and evidence, not a renamed copy. One name has one fixed input schema.
  Named programs have checked revisions and exact provenance. Reuse can save
  candidate checks in a fixture; transferable learning benefit is not established.

The optional small neural representation is the SAME frozen SeedRSSM GRU32,
loaded only through an owner-selected file and expected hash. There is no new
encoder or training. The shared encoder path has7552 parameters within the larger
frozen core;
the GUI reports both counts from actual modules. These are not newly trained
parameters or proof that the representation is useful in another domain.
Objects reuse the existing text/pixel/proprio adapter; lists, points and relations
have explicitly supplied typed sensor adapters.
Serialized text is capped at24 characters and proprioception at12 values; full
inputs remain available to the executable checker. This representation has not
been shown to encode useful coding/reasoning semantics. No pretrained weight or
normalization changes. Inspection never advances a recurrent belief or runs an
encoder. Neural work is accounted separately from authored actions.

Shared prototypes use observed teaching INPUTS only. Existing learned key/query
retrieval orders schema-compatible accepted skills. Reuse-first can propose the
first compatible program in that order; all teaching rows and fresh checks must
still pass. Thus representation can affect proposals, but cannot bypass checking.
Stored vectors have shape/hash validation on replay; their neural computation
requires the recorded binary to independently reproduce. Stdlib replay does not
claim to re-infer those vectors. Saved data cannot grant model-loading permission.

The shared encoder workspace is separate from an attached neural ACTION agent,
so symbolic world edits cannot silently corrupt its h/z observation contract.
An attempted mixed-controller world request fails clearly. No GRU is unfrozen.

## Teaching, checking, questioning and corrections

1. Teach up to8 labeled examples. The finite checker proposes compatible typed
   programs. “Enumerate” checks the catalogue; “reuse first” tests existing
   compatible skills before falling back to that same catalogue.
2. Multiple candidates trigger an unlabeled disagreement question. Zero candidates
   retain any existing tested skill and expose the conflict. Asking never creates
   a teacher answer. Predicates identify examples by properties, ignoring IDs and
   coordinates; relabeling those cannot disguise reused assessment inputs.
3. A unique proposal requires separate, fresh authored development checks. Their
   outcomes can accept/reject the candidate, but cannot fit candidates or update
   the rule selector. One check attempt is consumed even when it rejects. The
   assessment inputs cannot later become teaching examples for that skill.
4. Corrections explicitly supersede an earlier teaching reference. The original
   evidence stays. An old tested revision remains until a replacement passes.
5. Rollback restores an earlier accepted revision only if it remains compatible
   with active teaching evidence. No history is deleted. Running/inspection do
   not provide new learning feedback.

These GUI checks are user-authored and visible, not a hidden scientific test
service. Research confirmation still requires its own frozen protocol, datasets,
trusted evaluator and resource allocation. Existing EXPERIMENTAL controls remain
unchanged. The old list_transfer scientific gate is neither invoked nor bypassed.

## Learning-rule selection

The original EpsilonGreedyController sample-mean functions are extracted into
meta/kind_statistics.py. Both the original controller and this adapter call the
SAME functions; exact parity is tested. This makes source-only replay possible
without importing Torch, NumPy or old RL runners. No parallel bandit is added.

Two permitted rules: exhaustive finite enumeration and reuse-first. The adapter
explores unseen rules, then uses epsilon=.1 and historical mean source feedback
within input schema. Current validation labels do not enter its randomness.
Only a LATER, newly revealed teaching example scores a prior proposal. Feedback
is exact-match error(before) minus error(proposal) minus .001×candidate checks;
an absent prediction has loss1. It is computed before the next proposal, recorded
in the teaching event and independently recomputed on restoration. Corrections,
old duplicate examples and assessment outcomes do not earn feedback. There is
no client-supplied scalar reward endpoint. Changing rule statistics is functional
bookkeeping, not proof of a better learning procedure.
Candidate-check counts are a cost proxy, not FLOPs or equal wall time; requests
also report measured latency and actual encoder work separately.

## Run it locally

From a normal Seed installation with optional dependencies and recorded core:

```sh
nexus serve --mode labs --port 8782 --seconds 900
```

Open `http://127.0.0.1:8782/labs`. The launcher selects the recorded parent core
from seed_memory_aware.json and the original loader verifies its hash. Missing
binaries fail clearly; no new weights are substituted. A fresh clone can run
the shared symbolic labs without any neural libraries or binaries:

```sh
python3 -I -S scripts/run_seed_shared_gui.py --symbolic --port 8782 --max-runtime-s 900
```

The page explicitly labels encoder-disabled mode. New/save/load use the existing
Session storage and expected revision hash. A shared session is usable from
all four tabs. GUI controls cannot start training, run research experiments,
change evaluator rules, increase resource caps or execute arbitrary source.
The same loopback, origin, header, body-size,500-request and900-second server
limits apply. Additional library bounds:32 names,128 teaching events,64 active
teaching rows/name,8 examples/request,16 integers/list and2 operators/program.

## Engineering verification and proposed research

Focused and relevant regression tests exercise all four adapters, executable
cross-lab reuse, corrections, rejection, rollback, rule feedback, exact sample-
mean parity, property-level split isolation, deterministic replay, checkpoint
hashes, optional frozen encoding and GUI save/load. Ordinary tests use explicitly
authored fixtures; they do not execute a scientific study. A small reproducible
demo may record authored action counts separately from scientific interactions.
All previous artifacts remain byte-identical. See the separate engineering
receipt for actual commands and outcomes after verification.

One implementation-ready scientific question: **does informative questioning
with a fixed strong learner reduce examples needed versus random questions?**
Compare shared-memory/rule variants only after this has measurable headroom.
Design a separate source/development/final split by semantic program/task, not
merely input IDs; withhold later examples and all query labels until their roles
permit access. Use1/2/4/8 answer budgets and fixed candidate-check limits. Strong
references: fixed enumeration, fixed reuse-first, random question selection,
no shared library and shared verified library. Average repeated inputs and
teacher-order seeds within independently generated task streams. One frozen
neural core cannot support independent pretrained-model claims. Predeclare
accuracy, exact-match success, retained-old-task error, label/compute costs,
minimum effect and complete-grid rules. No numerical holdouts, allocations or
scientific lock are created here; no comparative result is claimed.

The intended architecture is now executable at a bounded authored level.
General language, useful neural transfer, robust noisy skill induction,
continual learning and learning-to-learn remain unestablished.
