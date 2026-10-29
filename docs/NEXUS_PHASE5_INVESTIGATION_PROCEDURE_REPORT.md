# NEXUS Phase 5 — Learning to Investigate and Transferring the Procedure

**Status: NOT LOCKED.** Branch `claude/s456-work` (pushed as `codex/nexus-data-engineering`), started from `287069f`.
`main` (`d7ac8c5`) is untouched, and checker kernels v1–v5 are pinned.

**Question:** can experience teach NEXUS how to obtain and use the evidence needed to solve unfamiliar projects, and can it
reuse that investigation procedure across changed schemas, business rules and engines?

§0 is the pre-registration, committed before any Phase 5 source-learning or target outcome. §1 is added after the runs.

---

## §0 Pre-registration

### 0.1 Starting point (verified against source at `287069f`)

- **Phase 4 completions per repetition:** Full 13/13/11, Solved-Only 11/11/11, Fixed-M0 14/13/13 of 24
  (`artifacts/agi4_eval/result.json`). The failure-memory differences were +2/+2/0 projects.
- **Wrong repairs:** none observed in finite held-out data.
- **Requirements:**
  - contract notes were loaded but never used by the learner;
  - the F6 truth was always inclusive (`ge`, `de_phase4/world.py:263`) and F4 always exclusive (`gt`, `:257`), so a global
    boundary preference could not show requirement-conditioned reasoning.
- **Equal-zero loophole:** both Phase 4 rules let a cheaper failure win when both versions solved 0:
  - skill admission, `lineage.py:235`: `sr >= sb and (sr > sb or rr <= (1-sp)*rb)`;
  - improver adoption, `meta_rollout`: equal solved and fewer runs.
- **Meta-rollouts:** each clone was forced to learn two projects.
- **Ledger:** 694 s remaining in the carried mi ledger (`scripts/mi_budget.py`). This phase grants no additional compute.
- **Machine:** 16 GB RAM, 10 cores, a JDK 17 + PySpark 4.0.1 runtime, `llama-server` 0.7.0 with local Qwen2.5 GGUF
  weights (0.5B / 1.5B / 7B) in `~/Projects/nexus-ai/.models`.

### 0.2 What was built (`src/nexus/de_phase5/`, tests `tests/test_agi5_investigation.py`, 9 passed)

**Human engineering** (disclosed): the action implementations, the policy language and its interpreter, the fixed policy
F0, the evidence-record formats, the project generator and the stakeholder simulator.

**Learned from source experience:**
- evidence memory: claim-trust weights over provenance features, counterexamples, action outcomes;
- the Phase 4 repair memory (pi_de, P, prefs, corrected skill admission);
- the **composition** of investigation procedures, built automatically from a minimal seed program.

**World** (`world5.py`):
- **Decision points.** The Phase 4 real-file projects gain requirement decision points whose correct business answer is
  drawn per project:
  - the watermark boundary is inclusive or exclusive;
  - the checkpoint offset is "last committed" or "next to read".

  So remembering one answer is worth nothing.
- **Requirement documents:** `contract.json`, `docs/runbook.json` and `docs/ticket.json` carry structured claims. Each claim
  has a subject (a state-reference expression), an effect at the boundary, a status, a version and a date. The provenance
  features are drawn independently of correctness.
- **Modes per decision point:**

  | Mode | Definition | Correct outcome |
  |---|---|---|
  | explicit | one claim states the boundary | complete |
  | missing | no claim, no boundary row | complete, via the one clarification |
  | conflict_approved | two opposite claims; the approved one is right | complete, via learned trust or the clarification |
  | undecided | two drafts | **abstention** |
  | visible | the golden rows decide | complete |

- **Generator checks:** besides the Phase 4 per-fault identifiability, the visible batch (40–50 rows) must admit **no
  coincidental state-threshold filter** that changes a hidden result. The only intended unknown is the requirement.
  Two-decision projects use out-of-order event times.
- **Stakeholder simulator:** defined from the intended contract only. It answers ≤ 1 probe row with the intended output,
  or "undetermined" for an undecided requirement. It never returns a program, a repair id or a hidden outcome.

**Language.** No language model is used. Reading the local Qwen models for every claim of every target in every arm would
cost an estimated 2–5 s per claim (load + generation on this CPU). That is far beyond the 694 s ledger once source learning
and controls get equal access. Phase 5 reads only the structured claim fields: a **shared structured-contract diagnostic**,
not a natural-language capability. The `text` fields are present but unused, and this coverage gap is reported.

**Actions** (`investigate.py`):

| Action | What it does |
|---|---|
| read(source) | reads structured requirement claims from one document |
| search | the Phase 4 repair search; its unresolved disagreements become decision points with rebindable options |
| search_more | a second search at twice the budget |
| resolve(trust) | applies matching claims by executing each option on a distinguishing boundary row; trust = none / newest / learned |
| ask(target) | the single clarification (1 row, cost 2.0 cost-s) |
| submit_or_abstain | submits if every decision point is resolved, otherwise abstains with the reason |

- A **Phase 5 closure extension** re-checks every Phase 4 "unique" verdict with single-row probes built from every visible
  row. In dev it found a missed disagreement in a two-filter project, which the frozen Phase 4 gate had passed as unique;
  the frozen gate is not modified.

**Policy language:** sequencing; `if` over observable conditions (has_candidate, unresolved, multi_unresolved, conflict,
undecided, asked, claims_seen, trust_memory); bounded `repeat`; `call` to stored procedures. No statement sees family ids,
generator internals, hidden tests or reference programs.

**F0**, the strong fixed policy: read all documents → search → search_more if there is no candidate → resolve(learned) →
ask(first unresolved) → submit or abstain.

**Procedure learning** (`policy_learn.py`):
- Source experience is executed once (Live backend) into caches. Candidate programs are evaluated by replay on validation
  projects, with memory frozen from the training projects.
- **Proposals** (simple, automatic, no model). Each cycle has two parts:
  - exhaustive enumeration of single insertions and **type-valid producer→consumer pairs** (each primitive's
    consumed / produced state types) on the program with stored procedures inlined;
  - sampled edits of every other type: delete, swap, change a parameter, wrap in a condition, call a stored procedure, inline.
- Each edit runs in **its own comparison** and is adopted only by the corrected rule. The coverage record counts whether
  the edited statement actually executed.
- An adopted block is stored as a procedure. It has a typed interface, applicability (the observable conditions true at
  entry in every helped project), provenance (cycle, edit, validation and source projects) and utility (the admission
  record). It is rebound to a new project's schema at use time by replaying the repair path.
- **Primary learned procedure:** composed from the minimal seed `[search, submit_or_abstain]`, not from F0.

**Corrected admission** (`admission5.py`), used for both policy adoption and skill admission:
- quality must be preserved (no more wrong repairs, no fewer correct outcomes);
- a quality gain is a benefit;
- an efficiency claim needs the **same non-empty set** of correctly completed projects, with no project lost;
- **never when both complete 0**;
- costs are kept separately as SQLite runs, Spark runs, wall s and questions. Decisions use cost-seconds = wall +
  2.0 × questions.

**Development history** (dev seeds 59000–59999 only, 23 metered runs, 154 s):
- A generator fix decorrelated two-filter projects (out-of-order arrival).
- **Coincidental thresholds:** these turned data sparsity into spurious decision points, so the visible batch was raised to
  40–50 rows and the coincidence check added.
- **The Phase 5 closure extension** was added.
- **Trust weights:** they now need about 3 consistent conflicts. One record had caused a wrong repair.
- **Procedure learning:**
  - random proposals stalled at "always ask";
  - stored procedures blocked refinement, which was fixed with inline + proposals on the inlined program;
  - typed exhaustive pairs were added.

  After this, two dev lineages composed `search → [read all, resolve] → ask → submit` automatically. That matches F0's
  validation cost (14.8 vs 14.8 cost-s), against 20.8 for "always ask".
- **Dev ablations** (validation replay):
  - Solved-Only evidence gave 3 wrong repairs where failure-including evidence gave 0;
  - reusing stored **answers** gave 8 correct / 4 wrong against 12 / 0 for the procedure.

**Disclosure:** Stage 1 reached 154 s against its 150 s ceiling. Direct `mi_exec` development runs do not check stage
ceilings. This is recorded as a 10 s transfer from the report stage, and every later run goes through `scripts/agi5_jobs.py`.

### 0.3 Partitions (`seeds5.py`; fresh ranges, disjoint at import)

- **Development:** every Phase 4 project and every Phase 5 dev / scratch build (agi5de/dev 59000–59999).
- **Source, lineage r** (agi5de/source 57400 + 300 r): 40 training, 16 validation, admission projects. Every source project
  has **one** decision point (watermark or checkpoint, every mode), base column names, 0–1 extra fault and SQLite only.
- **One-use targets** (agi5de/target 58400–58471): 36 target types × 2 independent instances = 72 projects.

  | Kind | Types | Projects |
  |---|---|---|
  | seen single combination | 10 | 20 |
  | held-out schema names | 6 | 12 |
  | held-out two-decision combinations, never in source | 12 | 24 |
  | multi-step (2 extra faults) | 4 | 8 |
  | Spark engine transfer (held-out names) | 4 | 8 |

  The analysis label `expected_outcome` is "abstain" for undecided requirements or for more than one decision needing the
  single question.
- **No external projects:** no independently authored DE projects fit this real-file substrate. This coverage gap is
  reported. Spark targets are engine transfer of the same generator, not external validity.

### 0.4 Arms (cross-project state frozen at entry; within-project adaptation only)

| Arm | Memory | Procedure |
|---|---|---|
| A1 Fresh | empty | F0 |
| A2_r | lineage r's repair + evidence memory | F0 |
| A3_r | lineage r's memory | lineage r's automatically learned procedure + library |
| A4_r | **placebo history** | the learned procedure trained on that history |
| A5_r (attribution) | A3's memory | A3's procedure with every stored-procedure call removed |

- **Placebo history** (specified before evaluation): the same source projects and executions, with every feedback
  association permuted:
  - claim-agreement labels shuffled across records;
  - counterexamples reassigned to random projects;
  - each validation project's verified combination moved to a random combination of that project;
  - the repair memory replaced by the Phase 4 matched placebo.

  The validation caches are rebuilt with the placebo repair memory (real, charged). It has no target access and is not
  deliberately disabled.
- **Equal access** for every arm: primitives, documents, checker / `de_accept_v2`, actions, one 1-row question, and budgets
  of 2.5 s SQLite / 10 s Spark per search.
- **Shared searches:** a search is shared only between arms with an identical repair memory (A2 / A3 / A5 of one lineage).
  Each arm is attributed the search's measured cost; the ledger charges the single real execution.

### 0.5 Endpoints, contrasts, decision rules

- **Unit:** the target project. Lineage arms are averaged over r = 0, 1, 2 per project. Repeated arms on the same projects
  are not independent evidence. Per-lineage counts and per-kind breakdowns are reported.
- **Primary endpoint:** verified completion (the independent evaluator runs the submitted file on 2 hidden batches; an
  undecided requirement makes every submission wrong).
- **Primary contrasts:** two-sided paired sign-flip permutation test over projects, Holm-corrected over 3.

  | Contrast | Measures |
  |---|---|
  | A2 − A1 | the value of experience |
  | A3 − A2 | the value of the learned procedure |
  | A3 − A4 | history vs placebo |

- **Minimum worthwhile effect:** +10 pp verified completion with no more accepted wrong repairs, or ≥ 20 % lower
  cost-seconds on the same correctly completed projects.
- **A positive "learned procedure" claim** requires A3 − A2 to meet that effect with Holm p < 0.05 and wrong(A3) ≤ wrong(A2).
  A gain from exposing contracts alone is an interface improvement: it appears in A1 as well.
- **Secondary:** accepted wrong repairs (target 0), justified abstentions, unnecessary / useful / undetermined questions,
  requirements and probes used, cost (SQLite runs, Spark runs, wall, questions), source-learning cost and break-even
  workload, held-out kinds, and A3 − A5 (does removing the learned procedure remove its advantage?).
- **Expectation, stated before outcomes:**
  - on single-decision targets all arms should be close, because F0 already reads, probes and asks;
  - the experience effect should appear on two-decision combinations with an approved / draft conflict plus a missing
    requirement, which need learned trust **and** the question;
  - A3 can at best match F0 unless it learns a better question target.

### 0.6 Budget freeze (charged wall s; `artifacts/agi5_allocation.json`, guard `scripts/agi5_budget.py`)

| Stage | Plan |
|---|---|
| s1 dev | 154 (ceiling 160) |
| src | 3 lineages × 32 s cap = 96 (ceiling 100); dev measured ~15 s for 30 / 12 projects |
| eval | 72 targets × 7 searches; measured ~0.3 s per SQLite search and ~0.5 s per Spark search + 4 s warm-up; predicted ~170 s (ceiling 320) |
| rep | ≤ 20 |
| **Total** | ≤ 600 of the 694 s ledger; ≥ 94 s reserve |

- If a ceiling is reached, unfinished rows are reported as not run. A crashed target job may resume only rows never
  written. One-use rows are never rerun.

### 0.7 Commands

```
python scripts/agi5_jobs.py var/agi5_jobs/src.json var/agi5_jobs/src_status.json 3 200   # scripts/agi5_source.py R 40 16
python scripts/agi5_eval.py freeze
python scripts/agi5_jobs.py var/agi5_jobs/eval.json var/agi5_jobs/eval_status.json 2 600 # scripts/agi5_eval.py run sqlite|spark
python scripts/agi5_eval.py score ; python scripts/agi5_protect.py artifacts/agi5_protected_hashes_after.json artifacts/agi5_protected_hashes_before.json
```

**Not attempted:** curriculum editing (the source order is fixed and exogenous), and improving the improver. No claim is
made about the algorithm that proposes policy changes.
