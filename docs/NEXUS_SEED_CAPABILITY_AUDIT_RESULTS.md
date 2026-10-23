# Seed capability/evidence audit — complete pilot, failed improvement screen

Branch: `codex/seed-capability-evidence-audit`.
Actual base `79c65d9ea959da0346027c5f72c717a2550e7d4d`; implementation/protocol
`a88bd8000423fdd98d764e587d336692bcf1507b`; pre-outcome inherited-runtime hash
correction and execution revision `def03419afc4aa9c3203127be0facfd5ade3c581`.
[Architecture/call paths](NEXUS_SEED_CAPABILITY_ARCHITECTURE_AUDIT.md),
[locked protocol](NEXUS_SEED_CAPABILITY_AUDIT_PROTOCOL.md).

**Decision: no learned-investigation promotion.** This is a valid, complete,
negative authored source-development pilot. It is not an invalid execution,
untouched confirmation, a general capability percentage or an AGI measurement.
The broader assessment is coverage-limited; unmeasured capabilities are listed
explicitly below rather than replaced by scripted positives.

## Equalized investigation comparison

Three independently generated source-policy/task seeds, eight assessment tasks
each, 240 method/task episodes. Same 252-candidate grammar, same question budget,
same shortlist including capsule methods, same singleton early stopping. Probe
positions shuffled; no handwritten repository mappings and no target-label
access in the learner. Both source/assessment use supplied list primitives;
this is compositional exclusion, not a new environment-family confirmation.

| Method | Correct tasks /24 | Candidate calls | Oracle questions |
|---|---:|---:|---:|
| Tools / initial policy | 24 | 3149 | 19 |
| Source-prefix index (`cache`) | 19 | 3034 | 19 |
| Learned + source capsules | 19 | 2539 | 4 |
| Learned, capsules reset | 20 | 2345 | 2 |
| Prior reset, capsules kept | 19 | 3034 | 19 |
| Shuffled learned weights | 21 | 2491 | 1 |
| Source frequency | 20 | 3172 | 1 |
| Fixed information gain | 24 | 3149 | 19 |
| Fixed boundary-first | 24 | 2639 | 19 |
| Fixed cost-aware | 24 | 2639 | 19 |

The source-prefix index uses the existing capsule priority mechanism. It is not
a general ordinary patch cache or an optimization that avoids executing cached
pipeline prefixes. Tools/fixed IG and cache/prior-reset are mathematically
duplicate controls. Boundary/cost-aware happen to tie on this sample. These are
not extra independent evidence streams.

Learned accuracy is **79.17% versus 100%** for the strongest fixed policy.
Learned calls are only **3.79% lower**, short of 5%, while accuracy regresses.
Per-policy-seed learned-versus-boundary correct counts: **7 vs 8, 5 vs 8,
7 vs 8**. Paired accuracy difference is **−20.83 percentage points
[−56.69,+15.02]**, exploratory n=3/df2. Calls saved per task are
**+4.167 [−102.196,+110.529]**, with seed differences +43, +11.25, −41.75.
Intervals are conditional on the finite grammar and this task generator.

Capsule reset does not recover full accuracy; shuffled weights are more accurate
than trained weights here. Fewer questions/calls can reflect premature stopping,
not improved learning. Four of the five learned failures ask **zero questions**;
their two tested probes each produce just one output partition among the three
shortlisted hypotheses. The fifth asks one question. This saved-trace diagnosis
supports investigating false certainty in a truncated version space; it does
not prove that changing one mechanism will generalize.

Training used **4653 candidate calls** (3205 support, 1424 probe, 24 source
validation), plus 24 source questions and 24 validation-oracle calls. Source
capsule entry counts were 4/4/3; one seed stores a duplicate program under two
source IDs. Policy snapshots and capsule fingerprints survive exact JSON
save/reload. Capsule hashes remain unchanged during target evaluation.
Learned scalar entries (behavior weights, frequencies and probe credits) are
47/73/86 across seeds, not neural parameters. Canonically serialized complete
policy-plus-capsule states are 2769/3332/3286 bytes; capsule portions alone are
1206/1198/911 bytes. These are serialized storage sizes, not Python heap sizes.
No acquisition break-even is established: quality regresses and the savings
interval includes zero. The first post-run verifier printed a purely
call-count amortization number; it is preserved as `*_verified.json` and
superseded by `*_verified_v2.json`, which explicitly enforces accuracy retention
and reports break-even as null. Raw outcomes/gates were not changed.

Pilot sizing diagnostic only: seed-level SD of saved calls/task is 42.817.
A normal-approximation 80%-power calculation for a 5% boundary-policy effect
(5.498 calls/task) suggests roughly **477 independent policy/task seeds**.
This estimate is highly uncertain at n=3, ignores future family shifts and is
not a scientific allocation or locked final sample size. **No confirmation is
justified or registered after this accuracy failure.**

## Actual broader capability checks

Six real executable authored projects, public tests visible to the existing
agent, private tests outside its workspace. No winning patch menu was provided
to `SymbioticAgentLoop`; its own synthesis operators remain bounded/scripted.

| Project | Public-loop outcome | Fresh private result |
|---|---|---|
| Python multi-file fractional fee | Failed after 3 attempts | Failed: 90.1 vs 81, 0.3 vs 0 |
| Python left-rotation feature | Failed, 0 proposals | Nonempty case fails; empty case passes |
| Python documented quota constant | Solved, 1 attempt | Pass |
| Python inclusive limit with retention | Solved, 1 attempt | Pass, including over-limit rejection |
| TypeScript credit arithmetic | Solved, 1 attempt | Pass |
| TypeScript stable-distinct feature | Failed, 0 proposals | Nonempty case fails; empty case passes |

**3/6 projects** pass all private cases; this is a coverage sample, not an
estimate of general coding performance. A second independent worker replay
re-executed all six final patches/11 private cases with identical results,
0.612642 s wall/0.764932 s child CPU. It performed no new search or training.

Actual JSON adapter returns east=10. SQLite adapter returns west=8/east=4 with
null handling. These are narrow supplied adapter APIs, not arbitrary natural-
language joins or discovered workflows. The existing regression suite separately
checks joins, ordering, cancellation and selective undo; do not relabel those
unit fixtures as fresh scientific transfer.

Real Z3 returns unsat for x>3 and x<1. Real SymPy returns x=5 for 3x+2=17.
Inputs were explicitly formalized by the benchmark author. No automatic
language-to-proof or causal-reasoning capability is established. Lean is absent
from the host and remains BLOCKED, not mocked.

Six chat turns preserve their full responses/cards. Five clarify/decline or
fall into the finite word parser; conflicting sort directions correctly ask
which order is intended. The runtime was explicitly disabled on these turns:
their results assess command/parser behavior, **not** the available language
model's ordinary conversational ability. General conversation remains UNMEASURED.
No keyword-based conversational accuracy was manufactured.

A separate real frozen Qwen GGUF CPU call returned exactly
`{"op":"rows","min":4,"order":"desc"}`. It processed **227 input /14 output
tokens**, 0 application/prompt cache tokens; startup **0.735316 s**, request
**0.942657 s**. This is one restricted structured-intent probe, not evidence that
the model solved the coding tasks or learned new language. Weight SHA matches
before/after. An explicit saved procedure and dialogue journal reloaded into a
new workspace and executed against a second CSV. That proves this bounded
persistence/rebinding path; it does not demonstrate improved learning methods.

## What learns, what persists, what remains unknown

1. **Usable today:** finite teaching/skills, authored-world actions, vetted data
   operations, explicit solver commands, bounded Python/TypeScript repair and
   local-model intent inference when installed. Arbitrary natural conversation
   and broad coding are not established.
2. **Changes from experience:** this pilot learns source hypothesis weights,
   operator frequencies and probe priorities, retaining source-validated capsule
   entries. Existing optional reward/meaning adapters are separate pathways.
   Nothing in this pilot modifies GRU/RSSM/readout/GGUF weights or the live agent.
3. **Unfamiliar tasks:** finite-program accuracy and the actual six coding
   outcomes above, with failures. New repository families, unrestricted language
   and autonomous formalization remain unmeasured.
4. **Beyond caching:** no useful advantage demonstrated over strong simple
   fixed policies. Prior persistent-runtime studies also failed their cache
   advantage screen. This pilot's prefix index is not a complete ordinary-cache
   benchmark for arbitrary assistants.
5. **After capsules clear:** learned prior gets 20/24 versus fixed 24/24.
   Useful learning-to-learn is not established.
6. **Retention:** stored policy/capsules, restart and file preservation pass;
   one coding boundary retains rejection behavior. General old-task retention
   after neural learning or conflicting corrections is not newly measured here.
7. **Efficiency:** fewer failed-policy calls do not justify a cheaper useful
   learner; no credible break-even or energy saving established.
8. **Gemini:** **NOT RUN**. No authorized interface/credential plus spending
   allocation was established. `seed_capability_gemini_inputs.json` contains
   public-only controlled/practical inputs, tool/attempt rules and metadata
   requirements. It is a handoff bundle, not an executed competitor benchmark
   or a working paid API client.
9. **Missing:** general public-test-guided synthesis, family-disjoint learning
   evidence, live-proposal calibration, useful automatic curriculum, broad
   retention and cost-equivalent real assistant comparisons. The pilot does not
   satisfy every requested broad capability benchmark or preregister final
   confirmation; those gaps are explicit.
10. **One next implementation:** add an equivalence-aware, completeness-preserving
    investigation fallback: when the prioritized shortlist yields no informative
    probe, widen the evidence-consistent hypotheses before declaring certainty.
    Apply the same fallback to learned and fixed controllers; test it later on
    newly authored whole-family exclusions. No such experiment ran here.

## Integrity, costs and reproducibility

- **889 prior tracked artifacts** match their base Git blobs exactly. Both
  grounded-core JSON checkpoints and three readout JSON checkpoints verify
  against their saved manifests; no historical model was reloaded for training.
  Qwen's 491,400,032-byte GGUF is local-only, not bundled in GitHub.
- Event audit checks every expected grid identity, choice-before-assessment,
  source-only training, full call reconstruction, independent primitive outputs,
  policy replay, per-case worker outcomes, duplicate/missing evidence and
  summary consistency. Hashes cannot attest physical execution against a
  malicious owner replacing a whole log; OS sandbox security is not proved.
- **34,803 execution events**, 240 episodes; raw file **13,344,473 bytes**.
  12 public worker invocations/12 top-level cases, with 13 recorded Python
  function entries and 13 returns; 6 private workers/11 cases. TypeScript's
  compiler and Node children are actual subprocesses, included in host CPU/RSS.
  Pipeline and primitive opcode counts are different: 78,225 opcodes reported
  for assessment-task candidate calls only, not all training/evaluator work.
- Full pilot wall **5.385016 s**, all waited-descendant CPU **5.810909 s**,
  sampled aggregate RSS **922.578125 MiB**. RSS is sampled at 100 ms, shared
  pages can double-count and short child peaks can be missed; no energy claim.
  Host debit **7 s**, zero new environment collection, zero imagined transitions
  and no neural optimizer updates. Pure Python source-prior updates are real
  learning computations and are included, not neural training.
- Reconciled 17 documented external seconds plus 1 conservative previously
  uncharged conversation second; preserved rejected pre-reservation runtime-hash
  preflight and charged another conservative 1 s. Latest E1 chain independently
  verifies **2219.632103455996 s used /1380.367896544004 remaining**.
  Older unavailable telemetry remains unavailable. Assessment replay and routine
  correctness tests are reported separately from scientific-run budget debit.
- Final relevant suite: **149 passed in 4.92 s** (nine files). Earlier runs:
  139 passed, then 28 focused preflight tests, then 147 passed; a full-history
  GUI API timeout was corrected with an allowlisted focused read-only route,
  followed by 37 focused tests and the final 149. One command referenced a
  nonexistent runtime-test filename and ran zero tests; no pass is claimed for it.
- Strengthened historical v2 verifier passes its original artifact and all three
  tamper self-checks, without replaying its scientific comparison as a new study.
  GUI JavaScript passes `node --check`; focused HTTP API test passes. No screenshot
  or interactive browser usability test was performed.

From the research branch, with existing dependencies on PYTHONPATH:

```sh
python3 -m pytest -o addopts='' -q tests/test_seed_capability_audit.py tests/test_seed_combined_investigation_engine.py tests/test_seed_symbiotic_workbench.py tests/test_seed_workspace_conversation.py tests/test_seed_conversation_capability.py tests/test_seed_config_repair.py tests/test_seed_assistant_benchmark_v2.py tests/test_seed_state_contract.py tests/test_seed_adaptive_runtime.py
python3 scripts/verify_seed_learned_investigation_policy_v2.py
python3 scripts/analyze_seed_assistant_benchmark_v2.py artifacts/seed_capability_audit_raw.jsonl --verify-ledger artifacts/seed_capability_audit_ledger.json
python3 scripts/run_learning_lab.py --port 8786 --max-runtime-s 300
```

Open `http://127.0.0.1:8786/experimental?study=capability_audit` for recorded
results. The page never launches an experiment. New verifiers write with `x`:
they refuse overwriting their saved receipts. For repeat arithmetic checks,
import `verify_records(records, config, result['summary'])`; for explicit saved
patch re-execution import `replay(config, records)` from
`scripts/replay_seed_capability_tools.py`. Neither retrains or performs inference.
The published scientific runner refuses another run of this closed attempt.
