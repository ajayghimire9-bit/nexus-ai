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

---

## §1 Results (NOT LOCKED)

**Commits:** protocol `bdf4570`, r1 rerun deviation `1073d0f`, pre-evaluation freeze `684cc19`, results: this commit.
**Raw data:** `artifacts/agi5_src/r*.json`, `artifacts/agi5_eval/rows_*.jsonl` (936 rows = 72 targets × 13 arms),
`artifacts/agi5_eval/result.json`, `artifacts/agi5_demonstration.json`.

### 1.1 Budget and execution events

| Stage | Used (charged wall s) | Ceiling after recorded transfers |
|---|---|---|
| s1 dev | 154 | 160 |
| src (incl. the killed r1 attempt, 32 s) | 124 | 140 |
| eval | 197 | 280 |
| rep | 1 | 20 |
| **Total** | **476** | **600** |

- The carried ledger now has **218 s**.
- **Events:**
  1. Stage 1 went 4 s over its ceiling: direct dev runs bypassed the job runner. This was recorded as a transfer.
  2. Source lineage r1 was killed at its 32 s cap with no artifact and no output. It was rerun once, alone, with a 40 s cap
     funded by a recorded eval → src transfer.
  3. The evaluation ran once (SQLite 162 s, Spark 35 s), with every row written and the one-use claim made once.
- **Searches:** 7 real searches per target. A2 / A3 / A5 of a lineage share one search; each arm is attributed its measured
  cost.

### 1.2 Source learning

The learned procedures were composed automatically from the seed `[search, submit_or_abstain]` (inspect
`artifacts/agi5_src/r*.json` → `policy`, `library`, `policy_log`):

| Lineage | Learned program | Library |
|---|---|---|
| r0 | `search → call proc2 → ask(first) → search → submit` | proc1 = [search, ask(first)]; **proc2 = [read_all, resolve(none)]** |
| r1 | same shape | proc2 = [read_all, resolve(**learned**)] |
| r2 | same shape | proc2 = [read_all, resolve(**learned**)] |

- **Validation replay** (16 projects): the learned procedure scored 15 / 16 / 15 correct, 0 wrong. F0 scored 14 (1 wrong) /
  16 / 15. Cost was 20.7 / 12.9 / 17.8 vs F0's 19.7 / 20.1 / 17.8 cost-seconds.
- **Coverage:** every edit type was proposed and executed in its own comparison. Adoptions came from the exhaustive
  insertions; no sampled delete / swap / wrap / parameter / call / inline edit was adopted.
- **Placebo history:** the placebo learner adopted almost nothing and stayed at or near the seed.
- **Development ablations** (validation replay, every lineage): **stored-answer reuse** scored 7–10 correct with **5–8 wrong**,
  against 15–16 / 0 for the procedure. Remembering the answer loses because the business decision reverses.
- **Failure-memory demonstration** (`agi5_demonstration.json`, r0): on validation projects 57502 and 57503, the claim
  records learned from **refuted** source submissions lower the learned-trust margin to 0.07. So the conflict is not
  trusted, the question is asked, and the result is correct. With those records removed (counterfactual), trust resolves
  the conflict and the submission is wrong. r2 has one changed decision, and r1 none.
- **Rebinding:** the same stored procedure proc2 binds at run time to decision points on `log_pos` / `offset` /
  `event_ts` / `recorded_at` columns and on checkpoint or watermark state references. On the target set's held-out column
  names (`evt_time`, `kafka_offset`, `seq_no`, …) it completed 10 / 12 single-decision projects, like every arm.

### 1.3 Target evaluation (72 one-use projects; each lineage arm reported per r = 0 / 1 / 2)

| Arm | Verified / 72 | Accepted wrong repairs | Justified abstentions (of 14) | Questions | Unnecessary questions |
|---|---|---|---|---|---|
| A1 Fresh, F0 | **45** | **0** | **14** | 51 | 0 |
| A2 Memory, F0 | 48 / 48 / 48 | **4 / 6 / 1** | 10 / 9 / 14 | 37 / 41 / 41 | 0 |
| A3 Memory, learned procedure | 44 / 48 / 47 | 0 / 6 / 1 | 14 / 9 / 14 | 48 / 39 / 38 | 0 |
| A4 Placebo history, learned procedure | 14 / 4 / 4 | 9 / 0 / 0 | 10 / 14 / 14 | 0 | 0 |
| A5 A3 without its stored procedures | 39 / 38 / 38 | 0 | 14 | 58 | 13 |

**By kind** (A1 → A2 r0 / r1 / r2):

| Kind | A1 | A2 r0 / r1 / r2 |
|---|---|---|
| two-decision held-out combinations | 8 / 24 | 11 / 10 / 9 |
| Spark engine transfer | 6 / 8 | 6 / 7 / 8 |
| held-out schema names | 10 / 12 | all arms 10 / 12 |
| seen single combinations | 16 / 20 | all 16 / 20 |
| multi-step | 5 / 8 | all 5 / 8 |

**Pre-registered contrasts** (paired over 72 projects, lineage-averaged, Holm over 3):

| Contrast | Mean | p (Holm) | Reading |
|---|---|---|---|
| Experience A2 − A1 | **+4.2 pp** (+3 projects per lineage) | 0.077 (0.154) | fails the rule: more accepted wrong repairs (4 / 6 / 1 vs 0) |
| Procedure A3 − A2 | **−2.3 pp** (−4 / 0 / −1) | 0.124 (0.154) | no gain |
| A3 − A4 placebo | +54.2 pp | < 0.001 | the placebo history yields no usable procedure (see 1.4) |
| Removal A3 − A5 (attribution) | +11.1 pp | 0.001 | removing the learned stored procedures removes their contribution |

**Cost on the same correctly completed projects** (cost-seconds = wall + 2 × questions):
- A2 vs A1: **31 % / 21 % / 30 % cheaper**, mostly fewer questions (A2 lost 2 / 0 / 0 and gained 5 / 3 / 3 projects).
- A3 vs A2: −42 % (r0 dearer) / 0 % / 0 %.

**Where the wrong repairs came from:**
- In A2, 9 of the 11 come from **undecided** requirements (two draft claims) and 2 from approved / draft conflicts. In
  every case **learned trust** resolved a conflict it should have left open.
- A3 r1 / r2 have the same 6 / 1, because their learned procedure also resolves by learned trust.
- A3 r0's procedure learned `resolve(none)`. It made no wrong repairs, but it lost the trust-dependent completions.
- **Diagnosis:** the trust weights absorb uninformative provenance cues (source file, version, date) besides status. Those
  cues separate two drafts, and no source record taught that two drafts are undecidable: undecided source projects produce
  only "undetermined" answers, never a trust record.
- A4 r0's 9 wrong repairs come from its seed-like procedure plus `resolve` on explicit-looking claims, under the placebo
  repair memory.

### 1.4 What the evidence establishes

**Established:**
- A complete, inspectable evidence → action → revision → submission / abstention cycle on real `.sql` / `.py` projects, with
  a bounded clarification. It uses 0 unnecessary questions whenever the procedure reads before asking.
- Fresh F0 had **0 wrong repairs and 14 / 14 justified abstentions**.
- Investigation procedures can be **composed automatically** from a minimal seed. They reached F0-equivalent structure
  (search → read + resolve → ask → submit) in all three lineages, and they rebind to new schemas.
- Remembering answers is markedly worse than remembering how to obtain them (dev ablation).

**Not established:**
- A learned procedure that **beats** the strong fixed policy (A3 − A2 = −2.3 pp).
- A safe experience gain. Experience adds about 3 completions but brings accepted wrong repairs through over-confident
  trust.

**About the placebo:** the A3 − A4 difference does **not** isolate history content from compute. The placebo learner, given
permuted feedback, adopts no procedure at all. The result shows that procedure learning needs real feedback; the placebo
arm is weaker than "deliberately competent".

**Attribution:**
- **Human:** the primitives, F0, the policy language, the stakeholder and the generator.
- **Language model:** none.
- **Learned:** the evidence weights, the repair memory, and the composition / selection of the procedures.
- **External validity:** untested; no external projects, and Spark is engine transfer of the same generator.

**Break-even:**
- **Training cost:** about 31 s per lineage, plus 154 s of shared development.
- **Saving:** about 12 questions per 72 projects (≈ 0.35 cost-s per project) for the experience arm.
- So repaying training needs on the order of 90 projects, and the wrong repairs mean it should not be deployed as is.

### 1.5 Protection

`artifacts/agi5_protected_hashes_after.json`:
- 0 violations;
- 1,578 frozen files (Phases 1–4) unchanged;
- checkers pinned;
- `main` = `d7ac8c5`;
- the 9 additions are this phase's run logs.

### 1.6 Recommended next experiment

**Calibrated trust with abstention-aware evidence.**
- Restrict trust to provenance features that are validated on held-out source conflicts. Learn "undecided" from
  stakeholder "undetermined" answers as negative trust evidence.
- Require the learned-trust resolution itself to pass the corrected admission rule against "ask first" on validation.
- Then rerun the same frozen comparison on fresh one-use targets. The carried 218 s covers roughly one evaluation of this
  size, without new source lineages, so new lineages need an explicit allocation.
