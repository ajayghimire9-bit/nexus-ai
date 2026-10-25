# Wave 24 eight-gap capability suite — locked protocol

Status: **locked before any evaluation-seed outcome was collected.**
Development used seeds 1–3 only (inspected while designing). Evaluation uses
seeds **101–105**, run exactly once by `scripts/run_wave24_agi_gap_suite.py`;
gates are recomputed from raw rows by `scripts/verify_wave24_agi_gap_suite.py`
(exit 0 only if every gate passes; failures are reported, never retuned).

This is finite source development on authored procedural domains. Passing
gates would NOT establish general intelligence or learning-to-learn in the
open world; they establish the stated measurable properties on this suite.

## Suite

- **Source (seen) families:** `INT`, `STR`, `LIST_INT`.
- **Target families (structurally disjoint, never used for training):**
  `CELL_AUTOMATA` (bit tuples, rules 30/90), `NESTED_DICT` (nested records,
  missing keys, corrupted values), `NUM_SERIES` (float series with NaN),
  `GRAPH` (adjacency maps), `STDLIB_BYTES` (base64/binascii/zlib/`bytes`
  callables ingested raw via `inspect`, no per-function wrappers).
- Tools are unwrapped Python callables; faults are real exceptions.
- Tasks: seeded random teacher programs of depth 1–4 (6 for planning), 3
  public pairs + 1 query; messy tasks use corrupted inputs and teachers with a
  try/except step that fires on public data. Teacher answers are used only for
  grading after an answer is locked.

## Cost model (uniform, single meter, nothing hidden)

1 unit per tool application per value (macros charge every primitive step;
recovery charges both attempts), per probe execution, per forward-model
prediction, per policy/model training row, per projection (per 256 atoms),
per law probe/validation application, per self-task proposal, and for all
meta-learning and counterfactual computation. Per-task budget 6,000 units.
The learned system's **total** = eval solving + source law validation + all
probing/training + meta-learning + exploration + exploration counterfactuals.

## Methods

- `fixed`: iterative-deepening exhaustive chain search to depth 4 with exact
  observational-equivalence quotient and on-the-fly try/except recovery
  synthesis; minimal-depth uniqueness certificate.
- `learned` (NexusLearner): same search plus forward world-model pruning
  (per-tool type/mass transition model from unlabeled probes, online updates,
  signature-space reachability planning), probe-discovered algebraic laws
  restricted to source-validated law families, fault-boundary memory over
  input phases, recurrence-gated macro invention, a force-transition policy
  enabled only after leave-one-domain-out validation, and meta decisions
  (retire policy / gate prediction / skip exploration / skip law validation)
  from measured payoff. Certificates are relative to the declared pruned space;
  every witness is re-executed on public IO and the query.

## Predeclared gates (α = 0.05, exact two-sided sign test on paired tasks)

| Gate | Criterion |
| --- | --- |
| G0 | 0 false certificates across all rows (witness re-execution fails). |
| G1a | **Every** eval seed: learned solved > fixed solved AND learned total work (incl. all overhead) < fixed total work (lifelong stream, 8 tasks per depth per domain, 8 domains). |
| G1b | Open-World Arena (default config): evolving solved ≥ 13 and > static, total work < static. |
| G2a | Each of the 5 targets (pooled seeds): transfer solved ≥ fixed, transfer work (incl. target probing) < fixed, sign test p < α favouring transfer. |
| G2b | Pooled: source-transferred learner beats the same learner without source evidence on total work (sign p < α) with solved ≥. |
| G3 | Every seed (4 random domain orders): meta Spearman(position, acquisition work) < 0, below the reset control's, and mean meta work at positions 3–4 < positions 0–1. |
| G4a | Idle exploration accelerates the evaluated stream: sign p < α favouring exploration, solved ≥. Idle cost reported separately. |
| G4b | Every promoted helper has ≥ 3 measured positive counterfactual gains. |
| G4c | ≥ 1 helper retired under distribution shift. |
| G5a | Messy tasks: learned solved ≥ fixed solved and ≥ 1 certified witness whose recovery actually caught an exception. |
| G5b | Bounded projector: time(10⁴) < 1.5 × time(10³) and 10× faster than the exact projector at 10⁴. |
| G5c | ≥ 8 raw stdlib callables ingested without wrappers. |
| G6 | ≥ 1 certified witness using a layer ≥ 2 abstraction. |
| G7 | World model vs fixed: sign p < α favouring the model, solved ≥, type-prediction containment ≥ 0.95, retention of fixed-solved tasks ≥ 0.95. |
| G8a | Docstring-grounded long-horizon planner (depth 4–6, degraded text) solves more than blind fixed search, sign p < α on work. |
| G8b | Goal-directed exploration (goals from own failure logs) solves ≥ and uses less work than undirected exploration on unseen goal-matching tasks. |

Stream lengths: G1 and G2 use the lifelong stream (8 tasks per depth 2–4 per
domain, plus messy recovery tasks where the domain has corrupted inputs). G2's
length was raised from 4 to 8 per depth after dev seed 3 showed target law
probing not amortized over a 12–18 task stream (a dev-data design decision,
made before any evaluation seed was run).

Known limitations declared in advance: no local LLM is available in this
environment (grounding is symbolic TF-IDF over the tools' own docstrings);
parameterized guard predicates are not implemented; development observations
suggest G5a and G8b may fail.

---

# v2 (locked before any seed 201–205 outcome)

Run: `python3 scripts/run_wave24_agi_gap_suite.py --suite v2` (seeds **201–205**, once),
then `python3 scripts/verify_wave24_agi_gap_suite.py artifacts/wave24_agi_gap_suite_v2.json`.
Development used seeds 1–5 only. The v1 gaps are re-run on 201–205 as a regression;
the v1 G4a/b/c, G6 and G8b gates are **superseded** by the stricter v2 definitions below.

## New mechanisms

- **Skeletons** (`wave24_skeletons.py`): MAP / FILTER(pred, fitted c) / FOLD / ITERATE_UNTIL_STABLE /
  WINDOW / GUARD(pred, c, A, B) over generic Python element operations; thresholds fitted on
  public inputs; faults raise. Loop, macro and recovery costs are charged exactly (actual step counts).
- **Wake-sleep** (`wave24_wake_sleep.py`): wake logs certified derivations and residuals; sleep runs on
  a governed metabolic allowance (15% of wake work since the last sleep): refactor derivations with
  promoted abstractions, compress recurring sub-derivations across distinct tasks (macro-of-macro and
  skeleton-in-macro raise the layer), shadow-replay each candidate (promote only if total replay work
  strictly drops and no replayed task loses its solve), then targeted residual bridges. No blind rollouts.
  Metabolic share 0.15 and 4 candidates per sleep were selected on dev seeds 1–5 (vs 0.10 / 3).
- **Learned skeleton relevance** P(skeleton type | domain-agnostic I/O signature) with charged fallback.
- **Semantic spec parser** (`wave24_semantic_spec.py`): compositional clause grammar → ordered stages,
  edge-case pre/post-condition oracles, rounding constraints. Spec texts AND parser were written by the
  same author; evaluation applies a seeded paraphraser. This is a capability demonstration, not
  held-out natural-language understanding. No local LLM is available.
- **Wild External Arena**: (a) **QuixBugs** (third-party, MIT, vendored in `fixtures/quixbugs/`):
  11 held-out **eval programs** (hash split fixed before inspection; repair engine frozen after a dev
  check), real AST single-edit repair with line-event cost, Ochiai fault localization vs source-order
  search, graded on the benchmark's own held-out tests; (b) physical-law discovery (7 laws, noisy
  public points, MDL form selection vs linear fit, hidden-point grading); (c) messy-data NL specs (8a).

## Declared world assumption for gaps 4/6/2/3

Self-evolution can only pay off when tasks share structure. v2 streams are **idiom streams**: per seed,
each family has 4 latent idioms (recurring 2–3 step sub-pipelines, half drawn from a seeded
cross-family pool of generic skeleton compositions when valid for that family); tasks compose 1–2
idioms (+ an occasional primitive), primitive depth 2–7. Uniform random streams (v1) remain in the
regression run.

## v2 gates (seeds 201–205; α = 0.05 unless stated)

| Gate | Criterion |
| --- | --- |
| V2-G0 | 0 false certificates in every v2 row. |
| V2-G4a | Every seed: ≥ 1 helper promoted by sleep AND used in a certified stream answer. |
| V2-G4b | Every seed: evolved first-attempt stream solved > no-evolution. |
| V2-G4c | Every seed: evolved total work (stream + ALL sleep/shadow/bridge + setup) < no-evolution total. |
| V2-G6a | Every seed: ≥ 15 certified answers whose witness uses a layer ≥ 2 abstraction. |
| V2-G6b | Depth ≥ 5 tasks: evolved solved > layer-1-capped evolution (pooled) and ≥ on every seed. |
| V2-G2 | Skeleton + policy + relevance transfer beats law-reliability-only transfer in solved AND total work (pooled). The no-source control is reported. |
| V2-G3a | Every seed: meta late-domain (positions 3–4) acquisition work < reset control's. |
| V2-G3b | Useful-branch ratio (on-path / expansions) rises from positions 0–1 to 3–4 for meta: sign test over (seed, order) pairs, p < 0.05. |
| V2-G8a | Semantic parser beats keyword retrieval per task on solved (sign test p < 0.01) with less work. |
| V2-G8b | Goal-directed sleep (re-attacking own failure residuals) beats undirected self-training AND no self-training per task (work, unsolved = +10⁶), p < 0.01, solved ≥. |
| V2-W1 | QuixBugs eval programs: learned correct repairs ≥ fixed, > 0, with less work. |
| V2-W2 | Law discovery: MDL correct > linear correct. |

Known risks from dev (declared, not tuned away): V2-G4c failed on dev seed 5; V2-G6a was 12 on dev
seed 5; V2-G2 transfer equalled the no-source control on dev; V2-G8b vs undirected was p≈0.02 on dev
seed 5 and noisy elsewhere; V2-G3b was not significant on one dev seed.

---

# v3 (locked before any seed 301–305 / held-out QuixBugs / held-out MBPP outcome)

Run once: `python3 scripts/run_wave24_agi_gap_suite.py --suite v3`
→ `artifacts/wave24_agi_gap_suite_v3.json` + `artifacts/wave24_agi_gap_suite_v3_llm_transcript.jsonl`,
then `python3 scripts/verify_wave24_agi_gap_suite.py artifacts/wave24_agi_gap_suite_v3.json`
(exit 0 only if every gate passes). Zero retuning after the run.

## What changed from v2 (owner corrections accepted)

- **Forbidden crutches removed.** No skeleton library (`wave24_skeletons` SK_MAP/FILTER/FOLD/ITERATE/
  WINDOW are not used by any v3 arm), no authored regex spec parser, no idiom streams, no surface-type
  relevance suppression (every arm keeps every original tool; transfer can only add candidates).
- **Real external benchmark for NL grounding, wake-sleep and hierarchy: MBPP** (974 human-written
  tasks, CC-BY-4.0, vendored in `fixtures/mbpp/`, sha256 `ccf64cea…a9f`), split by
  sha256("mbpp-split:<id>") parity into dev 515 / eval 459 (`split.json`, sha256 `7b36520d…678`)
  before any solver ran. Solvers see the task text and the FIRST assert; the remaining asserts and the
  challenge asserts are hidden and used only for grading. Reference solutions are never shown to a
  solver; they were used once, on DEV only, to validate the grader sandbox (514/515 dev references
  pass; the miss is an exponential-time reference exceeding the 20,000-line per-call budget).
- **Fair LLM accounting.** NEXUS is no longer required to use less raw work than unverified 1-shot
  Qwen. It is compared with (a) unverified 1-shot Qwen on held-out correct solves and precision, and
  (b) a verified-sampling Qwen baseline (same sandbox verifier, no fault localization, no
  counterexample feedback, no twin, no library) on correct solves and work per verified correct solve.
- **Pooled statistical dominance** replaces "every seed / no ties" for evolution.

## Model, hardware and cost model

Qwen2.5-1.5B-Instruct Q4_K_M GGUF (sha256 `6a1a2eb6…407e`) via llama.cpp `llama-server`
(b10000, CPU-only build). **This run is CPU-only** (Linux x86_64 cloud container, 4 vCPU, no GPU);
the engine records `backend` in every telemetry row and can never label a CPU run as Metal. One
engine serves every arm; prompts pre-fill the assistant turn with a ```` ```python ```` fence and stop at
the closing fence (same for every arm). Work = executed Python line events in candidate code
(sys.settrace; per-call budgets 20,000 MBPP / 5,000 QuixBugs; fault-localization traces capped at
200 events per test) + LLM units (1 per evaluated prompt token + 4 per generated token). A
deterministic response cache (sha256 of model, system, user, prefix, stop, temperature, seed,
max_tokens) **re-charges the original token counts on every hit**, so caching saves wall-clock only.
The locked run starts with an empty cache; its transcript is saved for model-free replay.

## Held-out evaluation sets

- **QuixBugs**: the 11 eval programs of `fixtures/quixbugs/split.json` (unchanged since v2), test split
  seed 301 (`split_tests(p, 301)`: one failing test as bug report + ~40% public, rest hidden).
- **MBPP**: the first 32 eval tasks in the outcome-blind order sha256("mbpp-v3-eval:<id>").
- **Procedural**: seeds 301–305 (Pieces C and D).

## Arms

QuixBugs (k = 2 LLM proposals): `qwen_standalone` (greedy, unverified, graded on public + hidden);
`verified_sampling` (greedy, then T=0.8 sample; first public-passing patch); `nexus_cegis` (Ochiai FL
lines in the prompt → verify → counterexample-guided repair → FL-ordered single-edit mutation
fallback, 20,000-line budget, ≤ 2 plausible patches, adjudicated by a docstring-only Qwen twin on 16
fuzzed inputs). **NEXUS on QuixBugs = `nexus_cegis`.**

MBPP (k = 2): `standalone` (greedy, unverified); `verified_sampling`; `nexus_frozen` (untrained NEXUS
cascade: greedy → CEGIS repair carrying the observed result/exception); `nexus_evolved` (**NEXUS on
MBPP**): learned state from dev wake-sleep — the helper library (`artifacts/wave24_mbpp_dev_library.json`,
sha256 `df514e1d…808`) and the strategy allocator — then execution-only helper composition (no LLM),
library context in the prompt only for near-duplicates (TF-IDF ≥ 0.8), allocator-chosen follow-up
(resample vs CEGIS by failure signature), verified answers admitted online using the public test only,
sleep every 8 tasks on a 15% metabolic allowance (anti-unification rounds + one targeted residual
bridge when affordable). Hidden tests are never consulted by any arm before its answer is locked.

## Piece A — skeleton-free hierarchy (`wave24_helpers.py`)

Helpers are real `def`s taken only from verified programs: verified solutions, their auxiliary functions,
and anti-unified abstractions `def helper_k(v0, …)` lifted from alpha-normalised expression subtrees that
recur across ≥ 2 distinct verified solutions, promoted only if every refactored solution re-passes its
verifying tests (charged) and description length (AST nodes) drops. Layer = 1 + max callee layer.

## Piece B — wake-sleep on the natural MBPP stream (`wave24_mbpp_evolve.py`)

Dev training (`scripts/train_wave24_mbpp_library.py`, dev split only, salt "mbpp-v3-train", 58 tasks,
k = 2, explore both follow-up strategies on every failure state, admission re-checked on all dev tests,
sleep every 10): 25/58 dev tasks correct, library of 26 verified helpers (23 layer-1, 3 layer-2:
`radix_sort→counting_sort`, `max_similar_indices→maximum`, `check_Odd_Parity→is_odd`), 2 correct
execution-only compositions, 0 anti-unified abstractions promoted (4 rejected: no compression / failed
re-verification). The artifact was produced by a cache-replayed re-run of the training stream after the
extraction fix below (identical completions, all re-charged); the dev cache is committed as
`artifacts/wave24_v3_dev_llm_cache.jsonl` (sha256 `5c594cc6…ec3`).

## Pieces C + D — procedural (`wave24_v3_procedural.py`)

C: adapter discovery = force-role fingerprinting of every raw operator from unlabeled probes (select /
translate / transmute / condense / branch) + try/except recovery synthesis; portable schemas = role
bigrams recurring on certified source witnesses of ≥ 3 distinct tasks; a schema binds to a concrete
pair only after that pair appears on a certified witness in the target family (one occurrence instead
of two); macro-induced ambiguity falls back to the primitive space (charged). Arms: experienced
(source-trained law evidence, LODO-validated policy, strategy statistics, schemas; keeps learning),
amnesiac (same learner and in-family learning, no source experience), fixed (exhaustive). Target
streams: depths 2–4 × 5 (+ messy recovery tasks), seed + 2000.
D: strategies = space-preserving solver configurations {full, no_predict}; signature = (input kind,
output kind, mass relation, any tool faults on a public input); choice = highest posterior solve rate
(± 0.05) then lowest expected work counting the charged fall-back to `full`; the first occurrence of each
coarse signature runs the alternative as a charged shadow. Meta (persistent, source-trained) vs reset
(fresh learner per family, always `full`), 3 random orders of the 5 targets per seed.

## v3 gates (α = 0.05)

| Gate | Criterion |
| --- | --- |
| v3_execution_complete | The single launch finished inside its wall cap. |
| v3_zero_false_certificates | 0 procedural false certificates AND every verified code answer (all non-standalone arms) re-passes its public tests on the verifier's independent re-execution. |
| v3_independent_regrade_matches | The verifier's re-grading of every stored answer/patch equals the recorded `correct`. |
| v3_code_vs_unverified_qwen | Pooled held-out (11 QuixBugs + 32 MBPP): NEXUS correct > standalone correct AND NEXUS precision (correct/plausible) > standalone precision. |
| v3_code_vs_verified_sampling | Pooled held-out: NEXUS correct > verified-sampling correct AND NEXUS work per correct < verified-sampling's (paired permutation p reported). |
| v3_mbpp_evolved_dominates_frozen | Held-out MBPP: evolved correct > frozen correct AND evolved work per correct < frozen's AND one-sided paired sign-flip permutation test on the work-per-correct difference p < 0.05 AND 0 false certificates. |
| v3_layer2_helper_in_heldout_answer | ≥ 1 correct held-out MBPP evolved answer contains a discovered helper of layer ≥ 2. |
| v3_transfer_experienced_beats_amnesiac_and_fixed | Pooled seeds × 5 targets: experienced solved > amnesiac AND > fixed; experienced target-side work (stream + setup) < both. Source training work reported separately (as in v1 G2). |
| v3_meta_late_useful_branch_share | Late families (positions 3–4), paired by (seed, order, position): meta on-path/expansions > reset's by majority, exact sign test p < 0.05. |
| v3_meta_late_work_per_solve | Pooled late meta work per solve < reset's AND paired sign test on work per solve p < 0.05. |

## Dev decisions (dev data only) and declared risks

- Extraction salvage: dropping a trailing line cut by the token limit (dev: no-code greedy outputs
  fell to 8/57); identical for every arm.
- Library prompt context only at similarity ≥ 0.8: on dev, lower-similarity exemplars from a small
  library flipped 5 otherwise-solved tasks to failures and fixed none.
- MBPP mutation repair not used: 1/25 dev greedy failures repaired correctly (+1 wrong) at ~400 units.
- QuixBugs FL trace cap 200: identical top-3 Ochiai lines on all 20 dev programs at 8% of the cost.
- Procedural strategies restricted to space-preserving configurations: on dev seed 2 dropping recovery
  synthesis produced certified-but-wrong answers in a smaller space.
- Dev evidence on the 1.5B CPU model: greedy MBPP success ≈ 36% (dev slice); after a greedy failure,
  resample 3/35 and CEGIS 2/38 correct. Procedural dev seeds 1–3: experienced = amnesiac solves on all
  three (74/74, 73/73, 75/75) with mixed work (+11%, −6%, −22%), experienced > fixed in solves and work
  on all three; meta vs reset late work per solve worse on seed 1 (1244 vs 1234), better on 2–3.
- **Expected to be at risk:** v3_transfer (strictly more solves than amnesiac), v3_mbpp_evolved_dominates_frozen
  (few library hits expected on 32 tasks with a 26-helper CPU-trained library), v3_layer2_helper_in_heldout_answer,
  v3_code_vs_verified_sampling (FL and CEGIS prompts are longer than resampling prompts), both meta gates.
- Disclosure: during v3 harness development the buggy source of `kth.py` (an eval program) was opened once
  to check the file format; nothing was tuned on it. No eval MBPP task was viewed.
- Not re-run in v3 (wall budget): the v1/v2 regression gaps and the open-world arena; their recorded
  results stand. The v1/v2 skeleton/idiom/regex modules remain in the repo as history and are unused by v3.

## Budget allocation (standing grant)

Per AGENTS.md (human standing grant of 2026-10-16: ≤ 900 s per experiment, ≤ 3600 s per session) and the
owner's explicit request in this session for one locked v3 run under the 900-second cap. The session
ledger (`runs/experimental/wave24-agi/ledger.jsonl`, including a conservative 600 s carried estimate for
pre-ledger executions) shows 2,250 s used at lock; the runner enforces cap = min(900, remaining − 15) and
records a partial result honestly if the cap is reached. Planned run ≈ 550 s.

## Running the same locked protocol on an Apple M4 (Metal)

`git pull`; `brew install llama.cpp`; place `qwen2.5-1.5b-instruct-q4_k_m.gguf` in `.models/`;
`export NEXUS_EXPLICIT_METAL_GRANT=1`; run the same command with a fresh `--out` path. The engine then
starts `PersistentMetalRuntime` with `n_gpu_layers=-1` and records `backend="metal"`. A Metal run is a
separate replication (different floating-point kernels can change greedy completions); it does not
replace this CPU result.

---

# v4 (locked before any seed 401–405 / fresh held-out MBPP outcome)

Run once: `NEXUS_EXPLICIT_METAL_GRANT=1 python3 scripts/run_wave24_agi_gap_suite.py --suite v4`
→ `artifacts/wave24_agi_gap_suite_v4.json` + `artifacts/wave24_agi_gap_suite_v4_llm_transcript.jsonl`,
then `python3 scripts/verify_wave24_agi_gap_suite.py artifacts/wave24_agi_gap_suite_v4.json --replay`
(exit 0 only if every gate passes). Zero retuning after the run. Branch `codex/wave24-v4-six-arm`
(from `31c8ed0`, which records the v3 verification).

## Question

Do reusable learning/refinement procedures acquired on source families (INT_SEQ, STR_PARSE) make
learning a new family cheaper and more successful **after paying their full acquisition cost**, compared
with fixed refinement, the same learner without source experience, and independent proposals at equal
probe budget — while every arm stays sound?

## World (`src/nexus/wave24_v4_world.py`)

Sources INT_SEQ, STR_PARSE (new). Targets DICT_RECORD, STATE_TRANSITION (new) and CELL_AUTOMATA,
NUM_SERIES, GRAPH, STDLIB_BYTES (unchanged from `wave24_domains`). Tools are unwrapped callables.
Per family stream (generator seed per family): 6 passive, 3 trap, 4 active, 4 subset tasks, kinds
interleaved. Trap/active tasks are *selected*, never authored: public pairs from the ordinary sampler on
which ≥ 2 minimal plain chains agree while disagreeing on the query (e.g. `last_rec` vs `latest` on
time-sorted records, `rev` vs `rotl` on length-2 lists arise naturally). Active tasks add a charged
oracle (20 units per call, ≤ 3 calls, never on the query input). Subset tasks have teacher
`guard(c, P, r)` with c from the generic φ grammar and P raising on ≥ 1 public input; no plain chain
≤ 3 (≤ 2 for > 12 tools) fits. CELL_AUTOMATA and STDLIB_BYTES tools never fault, so those families have
no subset tasks (declared). Gold for every task = the exact reference verdict over the shared space;
a task is dropped if the teacher's answer is outside the reference witness set; active tasks have gold
UNIQUE.

## Shared program space and certificate (`src/nexus/wave24_v4_core.py`)

Minimal-size programs over plain chains (depth ≤ 3) and guards `if c(x): P(x) else r(x)` (P depth ≤ 2,
c a size-1 predicate over total relational features φ — emptiness, zeros, non-finite, None, keys,
`sorted_by:<field>`, numeric tokens, length/bound thresholds, type — r a public-output constant,
identity or tool; guard size = |P| + 1 + |r|; no exception swallowing — an exception in a routed
branch propagates). Size-s level = chains of length s ∪ guards of size s. **ObsEGraph**: classes keyed
by the public signature; each distinct query output keeps its own concrete representative, so
Y_q ⊆ Ŷ_q under composition (the `{0,1,2} → v % 2` regression is a unit test). UNIQUE iff one query
output at the first non-empty level with a verified witness; AMBIGUOUS iff two concrete programs
disagree. Every arm is exact over this space (naive generate-and-test = constrained = Popper on 499
dev tasks, 0 mismatches; a unit test re-checks on dev generator seed 21), so learning can only change
**work** — through sound pruning, enumeration order with the sound early-AMBIGUOUS stop, and probe
design — and, through the probe budget, **solves** on active tasks.

**Popper constraints** (sound): (i) functional-dependency nogoods — a prefix whose public outputs
violate `state_i == state_j ⇒ y_i == y_j` prunes every plain completion (stored as an O(1) nogood);
because a guard's then-branch needs to match only a subset, pruned depth-1 states are still expanded
once for guard partials (a dev bug, fixed and unit-tested); (ii) constraint-based guard generation — for
P with match set S_P and r with S_r, c must be true on all∖S_r and false on all∖S_P, so no guard is
test-executed.

**propose_refinement**(competing_hypotheses, observed_evidence, current_representation, goal,
remaining_budget) → RefinementPlan(candidate_predicate, distinguishing_test, candidate_repair):
invents the φ predicate shared by every public input and false on the query (e.g. `sorted_by:t=True`),
searches generic perturbations (reverse / rotate / swap / drop / duplicate / string-reverse) and 2-step
`a(x)` probes for an input on which hypotheses disagree, preferring φ-preserving, concept-flipping
probes; repair goal returns guard repairs. Active tasks execute the probe (charged) and re-certify with
the observation as a public pair; passive tasks never fabricate an observation and keep AMBIGUOUS.

## Arms (`src/nexus/wave24_v4_agents.py`), identical space, per-task budget 60,000 units

| Arm | Configuration |
| --- | --- |
| 1 literal_fixed_baseline | fixed op order, no Popper, naive generate-and-test guard schedule, no early stop, no probes |
| 2 abstractions_fixed_refinement | + Popper, source role schemas (role n-grams with Procedure C algebraic roles: involution / idempotent / order-dependent from 2-step probes) ordering ops, early AMBIGUOUS stop, fixed designed probes (full preserving scan) |
| 3 learned_refinement_ttt_trm | + TTT fast memory M_t (logistic, `M ← M − η∇ℓ`, reset per family) ranking partials / predicate families / recoveries / probe families, online role bigrams, TRM-style iterative probe revision (each observation updates the shared M_t that designs the next probe) |
| 4 full_nexus_reusable_procedures | + Library 2 priors mined from source trajectories (persistent across families), meta-policy (designed vs independent probe per symptom), DiscoRL-style meta-learned η (grid 0.1/0.3/1.0 on source validation), Tycho admission per procedure kind, transfer-aware curriculum |
| 5 amnesiac_no_source_control | arm-4 code, zero source training |
| 6 independent_proposal_ablation | arm 4 with independent random probes and seeded-random enumeration order instead of TRM/designed probes, same probe budget |
| (row) full_nexus_frozen_zero_shot | arm 4 with no target-side updates (reported, not gated) |

Source acquisition (charged to every arm that uses a source product; arms 4/6 also pay curriculum,
Tycho and meta-training work): generator seed+4000 practice streams, seed+5000 validation streams
(8 tasks per source family), target streams seed+6000. **Tycho**: admit a procedure kind iff
saving-per-validation-task × 100 (declared downstream horizon) − its validation work > 0, with zero
false certificates and no lost validation solve. **Curriculum**: a practice batch from family A is kept
only if mining it lowers validation work on family B.

## Track B — MBPP (`src/nexus/wave24_v4_code.py`)

Held-out QuixBugs is consumed (v2/v3) and is **not** used. MBPP fresh eval slice: eval split minus the
32 v3 tasks, order sha256("mbpp-v4-eval:<id>"), first 32 — no solver has run on these. Dev validation
slice (Tycho only): dev split minus the 58 v3 training tasks, order "mbpp-v4-val", first 12. Arms:
`standalone` (unverified greedy), `verified_sampling` (k = 2), `symbolic` (execution-only helper
composition, no LLM), `nexus_v4` (k = 2; v3 learned follow-up allocator; library offered only if the Tycho
gate admits it; online growth from public tests; sleep every 8 on the 15% metabolic allowance; docstring
twin fuzz check on sampled follow-up candidates — an independent docstring-only twin that passes the
public test and disagrees on a generic fuzzed input makes NEXUS abstain; twin tokens charged).
Qwen2.5-1.5B Q4_K_M via llama.cpp; **Metal** (all layers, owner-approved this session) through
`MetalGrantEnforcer` (4,096 MiB RSS, 30 s per call, 600 s Metal per session), CPU otherwise; backend
recorded on every call. LLM units = prompt tokens + 4 × generated tokens; cache hits re-charge.

## v4 gates (α = 0.05)

| Gate | Criterion |
| --- | --- |
| v4_execution_complete | The single launch finished inside its wall cap. |
| v4_independent_regrade_matches | Re-grading every stored MBPP answer equals the recorded `correct`, and (`--replay`) re-running Track A from source reproduces the row digest. |
| v4_g1_zero_false_certificates | 0 wrong UNIQUE certificates over every arm (incl. the frozen row), every kind, every seed; 0 witness-conservation violations (complete-level arms: every AMBIGUOUS verdict on a gold-AMBIGUOUS task contains the truth); every verified MBPP answer of a non-standalone arm re-passes its public test. |
| v4_g2_full_nexus_beats_controls | Pooled seeds × six targets: arm 4 solved > solved of arms 1, 2, 5, 6 AND arm 4 fully-loaded work per solve (target + setup + its source acquisition) < each control's (each with its own source cost) AND net benefit vs arm 5 = (arm-5 target work − arm-4 target work) − arm-4 source acquisition > 0. |
| v4_g3_disambiguation_and_repair_transfer | For disambiguation tasks (trap + active) and subset tasks separately, vs arm 2 and vs arm 5: arm 4 solve rate higher AND target work lower, each by an exact one-sided seed-level sign test p < 0.05 (seeds are the independent units; ties count against arm 4; 5/5 seeds needed). |
| v4_g4_popper_efficiency | Popper audit (identical exhaustive certifier with/without Popper, no early stop, every target task): candidate evaluations ≤ 85% of the no-Popper count AND 100% identical verdicts and witness sets. |
| v4_g5a_nexus_vs_unverified_qwen | Fresh MBPP: NEXUS correct > standalone correct AND NEXUS precision > standalone precision. |
| v4_g5b_nexus_vs_verified_sampling | NEXUS correct > verified-sampling correct AND NEXUS work per correct < verified-sampling's (paired permutation p reported). |
| v4_g5c_helpers_positive_net_validation_benefit | The Tycho gate admits the helper library on the dev-validation slice (net benefit > 0) AND ≥ 1 correct held-out NEXUS answer uses a library helper. |

Wall-clock ms and peak RSS (Python process; llama-server peak from the Metal ledger) are reported next
to work units for both tracks.

## Dev evidence (dev seeds 1–5 and dev MBPP only) and declared risks

Track A dev, pooled seeds 1–5 (446 tasks): solved — arm 1 327, arm 2 440, arm 3 439, arm 4 438,
arm 5 440, arm 6 425; target work 350k / 245k / 237k / 240k / 239k / 266k; source acquisition 0 / 299k /
299k / 976k / 0 / 976k. 0 false certificates in every arm. Tycho admitted **no** procedure kind on any
dev seed (the projected savings are smaller than the validation cost), Library 1 found 0–1 role schemas
per seed, meta-learned η = 0.1 on every seed. Popper audit: 5.9% fewer evaluations, identical verdicts.
Dev MBPP pipeline check (6 dev tasks, Metal): 22 calls, ≈ 0.9 s per fresh call; the Tycho library gate
on the validation slice gave net −419 (0 composition hits) → library not admitted.
**Expected to fail:** G2 (arm 4 does not out-solve arms 2/5 and pays ~1M source units), G3, G4 (< 15%),
G5b and G5c; G5a uncertain on 32 tasks. These are declared now and will be reported as they fall.

Dev decisions (dev data only): exact shared-space certification for every arm after dev seed 1 showed
that restricted "learned" spaces produced false certificates; Popper partial-expansion fix; grammar
instantiated from all public inputs (exactness bug); identity-recovery guards included; `sorted_by`
feature added so the order concept is expressible; gold-AMBIGUOUS tasks graded as solved on an
AMBIGUOUS verdict (the sound early stop keeps only two witnesses), with witness conservation checked
for complete-level arms under G1.

Deviations from the owner brief, stated plainly: "TRM" is a TRM-*style* shared-parameter iterative probe
revision, not a neural recurrent model; "DiscoRL-style" is a grid-meta-learned TTT step size plus a learned
probe-mode policy; "Stevie/Stitch/babble" is role-level n-gram anti-unification, not lambda-calculus
refactoring; arm 1's literal certified-program cache is not implemented because a cached fit cannot
shorten an exact minimal-level certificate; Popper's cardinality constraint is the functional-dependency
check at public points (no budget-based monotonicity constraint, which would need certified operator
laws); QuixBugs is excluded (consumed).

## Budget allocation (standing grant)

AGENTS.md standing grant (2026-10-16): ≤ 900 s per experiment, ≤ 3600 s per session, local only. This
session's ledger (`runs/experimental/wave24-agi/ledger.jsonl`, rows after the 2026-10-25 session-start
marker, engineering checks included) shows ≈ 237 s used at lock; the runner enforces
cap = min(900, remaining − 15) and saves an honest partial result if reached. Metal: owner approval in
this session, enforced by `MetalGrantEnforcer` (ledger `runs/experimental/wave24-agi/metal_ledger.json`,
9 s used at lock). Planned run ≈ 4–6 min. No paid service, no network.
