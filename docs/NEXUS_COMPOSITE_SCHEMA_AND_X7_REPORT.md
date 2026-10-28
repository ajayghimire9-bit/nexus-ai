# NEXUS x7 — Compositional Expression Mapping, Held-Out Schema Transformations, Cost-Matched Learning

Status: NOT LOCKED (exploration workflow; validation and confirmation are one-use with committed gates). Branch
`codex/nexus-data-engineering`, starting revision `d23c9fa`.

## 0. Pre-registration (committed before the formal development ablation, validation and confirmation)

### 0.1 State, protection and budget (audited at d23c9fa)

* HEAD = origin = github `codex/nexus-data-engineering` = `d23c9fa`; working tree clean; github has 3 heads; `main` =
  `d7ac8c5` (untouched); `final_sealed` is a seed-registry split (wave30), not drawn here.
* Protected manifests verified (not just counted): `scripts/r1_protected_hashes.py` vs `artifacts/r1_protected_hashes_before.json`:
  912 files, 0 changed; `artifacts/sc_ba_hashes_before.json` 157 ba files, 0 changed; `artifacts/ba_oc_hashes_before.json` 74 oc files,
  0 changed; checker kernels v1–v5 match the pinned hashes. New manifest `artifacts/x7_sc_hashes_before.json`: all 390 frozen sc files
  (src/scripts/tests/artifacts/report) at d23c9fa; they must stay byte-identical. `sc_contract.py` / `sc_mapping.py` are not edited;
  all x7 code is in new `x7_*` files.
* Budget: ledger tally 4,778 s at d23c9fa (equal to the owner's figure). Grant `GRANT-NEXUS-X7-EXPR-MAPPING-14400S` recorded once
  (`artifacts/x7_grant.json`): cumulative allowance 97,190 s, available 19,178 s. CPU only; ≤ 900 s per call (`scripts/x7_exec.py`;
  ledger rows `x7-*`, logs `artifacts/x7_logs/`).

### 0.2 Part 2 — diagnosis of sc dev 13327 (done before this commit; development data only)

`scripts/x7_diag13327.py`, `x7_diag13327b.py` → `artifacts/x7_dev/diag13327*.json` (707 s charged).
* Fields: key / control / numeric fields discovered correctly; control hypothesis = 3 modes, mapped onto the documented modes
  idle / open / disputed through its access words — **not** a state-inference defect.
* Observations: every documented transition observed (5–118 times) — **not** insufficient observations.
* Expressiveness: the documented register program (written by the developer for the diagnosis only, never given to a learner)
  is in GRAMMAR5 and consistent with the learner's own traces (count 0/53, sum 0/53 inconsistent slots) — **not** missing
  expressiveness.
* Failure: every growth step and the full-space learner failed inside `learn_registers` before any acceptance test ran (growth:
  10 s step budgets; full space: the 60 s budget). With a 600 s budget the unchanged search explored 128.7 M backtracking nodes.
  **Search exhaustion**, not acceptance failure. Cause: an occurrence is checked only when every transition of its whole prefix
  is assigned.
* General fix (`src/nexus/x7_regsearch.py`): reset-aware early pruning — after an assigned update that does not read `acc`, the
  register value no longer depends on earlier transitions, so the occurrence is checked as soon as the suffix after that reset is
  assigned. Sound and order-preserving: the search returns the same first solution as the unbounded old search (unit test
  `test_reset_pruning_returns_the_same_register_program`), only sooner. No project-specific branch; the expected answer is unchanged.
  Debug check (dev tag debug0/1): 13327 build now succeeds in 0.6 s (growth path); the project ends independently correct by
  lifecycle relearning after an unrelated x7 arm bug (unknown X5 kinds misclassified as shape evidence) was fixed.

### 0.3 Implementation (all new files)

| component | file | role |
|---|---|---|
| reset-aware register search | `src/nexus/x7_regsearch.py` | `Learner2X`, `Learner3X`, `attempt`, `learn_class_bounded(fix=…)` |
| dependency analysis / pruning | `src/nexus/x7_contract.py` | `reads`, `prune`, `sensitivity`, `infer`, `ContractRunnerX` |
| expression grammar | `src/nexus/x7_expr.py` | AST, MISSING semantics, size/depth, enumeration |
| adapter repair | `src/nexus/x7_mapping.py` | tiers, consistency, separation, `composite_accept`, relearn |
| platform | `src/nexus/x7_platform.py` | generator families, privileged normalisation, `HumanRefX7`, `NexusArmX7` |
| runner / budget | `scripts/x7_run.py`, `x7_exec.py`, `x7_budget.py` | one (project, build group) per call; atomic per-arm files |
| tests | `tests/test_x7.py` | 7 fast tests (semantics, pruning both directions, missingness, versioning, search identity) |

**Part 3 (dependencies).** Required fields come from the executable machine: key and control fields (structural), fields read by
LIVE register updates that use `x`, and `('cur', f)` output sources. Dead registers, identity updates and field bindings without an
x-reading update are removed (exact for this machine language); `sensitivity()` replays original vs pruned on the build stream and
8 counterfactual copies with the removed inputs deleted / redrawn (support, not proof). Fields that cannot be shown unused stay.
Legitimate missingness (nullable at build) stays distinct from mismatch; an unexpected missing numeric field is never zero-filled.
Ablation `NoPrune_Learned`: the contract uses the emitted-code reads (every bound register field on every kind).

**Part 4 (grammar, frozen here).** `E := f(path) | parse(path) | const k | E op E | if present(path) then E else E`; op ∈ {+, −, ×,
guarded ÷}; MISSING propagates (never 0); ÷ by 0 → MISSING. Constants {1, 2, 10, 100, 1000}. Size: leaf 1, operator +1, conditional
+2; bodies size ≤ 5 (≤ 3 leaves, depth ≤ 2); conditionals wrap one body and the raw target field: size ≤ 8, depth ≤ 3. Leaves:
numeric paths (top level and one nesting level) present on every evidence record, excluding key and control fields; parse leaves for
string paths that parse on every evidence record. Tiers: 0 = one path (field selection), 1 = parse or one operator, 2 = two
operators; observational-equivalence dedup on the evidence records + 16 seeded synthetic copies. Caps: 30,000 consistency checks,
300 CPU s per repair, 24 distinguishing queries / 300 attempts, ≤ 2 relearn candidates. Shapes: missing field →
`if present(f) then f else BODY`; new paths (field still present) → `if present(t) then BODY else f`, t a new path present on every
notice record. Detection does not depend only on missing names: a numeric path never seen on that kind at build raises a SHAPE
NOTICE (`B:shape_change` alarm → verification); field removal is a mismatch only for a live dependency.

**Part 5 (acceptance).** `composite_accept` evaluates machine + adapters against the oracle: every kind word of length h, h the
largest horizon with |Σ|^h ≤ 400 (actual words = |Σ|^h, recorded per project — not a fixed "125"), one generic draw per word;
ba_accept's structural delayed-effect tests from loaded (non-zero register) prefixes, with boundary draws (0, 1, sign change,
all-equal) on the adapter's inputs, ≤ 700 runs; 120 mixed old→new histories; the old shape too when the machine was relearned;
the operator then replays the tick, crash-recovers and reconciles independently. Label TESTED_WITHIN_STATED_LIMITS with the exact
scope. Several consistent candidates: queries are spent only on words where live candidates disagree; > 1 left → AMBIGUOUS
(unresolved). Adapters are versioned with observable applicability conditions (presence tests); no hidden fault timestamp is used.
A shape notice whose deployed composite is consistent with the archive and passes `composite_accept` is SHAPE_VERIFIED_BENIGN.

### 0.4 Part 6 — exposure table and the X7 definition (frozen here)

| transformation (lifecycle value field unless noted) | where seen before | class |
|---|---|---|
| rename `<f>_amount` (X6), nested `<f>_info.amount` (X6P), rename + exact decoy (X6D), gradual migration (X6M) | ba / sc src, dev, val, test | previously tested |
| event-kind rename `_V2` (X5), new kind (X3), legitimately missing (LM) | oc / ba / sc | previously tested |
| unit shift ×100 (A-stream D1, `oop_env` minor units), A-stream nested `{value, unit}` (X4) | u5 / oop | previously tested (other stream) |
| products / differences of record fields, ÷ by a `cents` constant (`qty × price`, `(imp − exp) × rate / cents`) | u5 / t7 A-stream VALUE formulas | primitives known in another subsystem; never a lifecycle schema change |
| XD1 `gross − fee` (missing field) | x7 dev | declared development family |
| XD2 nested `meta.milli / 1000` (missing, gradual) | x7 dev | declared development family |
| XD3 field present, ×10, marker `<f>_v2` → `f / 10` | x7 dev | declared development family (present-field meaning change with a marker) |
| XR distractor removed + renamed | x7 dev | declared development family (dependency pruning) |
| **X7a** `major + minor / 100` (field decomposition, 3 leaves, mixed operators + constant; gradual p = 0.7) | nowhere in src / dev / val | new composition of known primitives; mechanism withheld from solver dev |
| **X7b** field present but now a per-unit rate, new `<f>_qty`: `if present(qty) then f × qty else f` (trigger used as an operand) | nowhere in src / dev / val (lifecycle) | new composition of known primitives; mechanism withheld from solver dev |

Disclosure: the developer (Claude) designed both X7 generators and knows their specification; X7 is not unknown to everyone and is
not globally novel. The grammar was frozen before any X7 instance was generated for a NEXUS arm; X7 code paths run only in
`x7_pcheck` (platform check of generator, oracle and simulated human — no NEXUS arm, refused by the runner) and in the sealed
confirmation. Dev bodies are ≤ 2 leaves; X7a needs 3; X7b's conditional uses its trigger as an operand (XD3's marker is not).

### 0.5 Part 7 — platform validation and arms

Platform check (`HELPER`): corrected simulated human vs the reference on every tick, plus resume from a mid-stream checkpoint, with
late-format counts, on the 16 dev-ablation projects, the 14 sc-dev recheck projects and the 8 `x7_pcheck` projects (X7a ×4, X7b ×4).
Required: 0 wrong rows everywhere, every transformation exercised (format counts > 0).

Primary arms (identical workloads, same A-stream programs per project, same operator randomness, same fallback = full-space learner
after growth, same reset-aware learner, same dependency pruning, same adapter search where expression mapping is on):

| arm | lifecycle growth | adapter search | role |
|---|---|---|---|
| A Expression_Learned | learned (ba records, unchanged) | tiers 0–2 | the candidate |
| B FieldOnly_Learned | learned | tier 0 only | isolates expression mapping (A vs B) |
| C Expression_Hand | hand-written | tiers 0–2 | growth policy (A vs C) |
| D Expression_Shuffled | frozen shuffled-experience | tiers 0–2 | growth policy (A vs D) |
| NoPrune_Learned (dev only) | learned | tiers 0–2 | dependency pruning off (emitted-code reads) |
| NoMapping_Learned (dev only) | learned | none (relearn only) | mapping repair off |
| Frozen_SC (reference) | sc d23c9fa SchemaRepair_Learned, unchanged code | field mapping (sc) | historical implementation baseline |
| Fixed_Policy, Conventional (reference) | — | — | as in sc |

A and B share one lifecycle build (identical code path until repair); C and D build with their growth policy. The growth policy is a
lifecycle growth policy only; the adapter search is identical in A / C / D and is not a learned policy.

### 0.6 Part 8 — splits, gates, analysis, budget

* Development ablation (`x7_dev` tag `ablation`): 16 projects 13404–13419 = XR, XD1, XD2, XD3 × the 4 domains; groups L (A, B,
  NoPrune, NoMapping), H, S; plus the 14 sc dev projects of the sc ablation (13301 13302 13303 13305 13306 13309 13311 13313 13315
  13317 13319 13321 13327 13328), group L (A, B). 14/14 is a development target, not a gate.
* Validation (`x7_val` 13461–13468, one-use): X6, XD1, X3, XD3, X6P, XD2, X5, X6M (2 per domain; **no X7**); groups L, F.
  **Gate:** A 8/8 independently correct, 0 incorrect healthy claims, 0 human repairs, crash recovery identical 8/8. Revision policy:
  at most one disclosed revision, then fresh `x7_val_b` (13471–13478, same design); confirmation only after a passing gate.
* Confirmation (`x7_test` 13481–13496, one-use, sealed blobs + committed manifest): X7a ×4, X7b ×4, X6/X6P/X6D/X6M, X3, X5, X3, X5
  (each group of 4 covers Logistics, Clearing, IoT, Energy). Groups L, H, S, SC, F (arms A, B, C, D, Frozen_SC, Fixed_Policy,
  Conventional). Called "generalization to held-out compositions (X7) and fresh instances of known classes", never unseen.
* Decision rules:
  1. Full-system objective: A 16/16 independently correct, 0 silent, 0 human repairs, crash identical 16/16 → PASSED; else the
     negative verdict stands.
  2. Expression capability beyond FieldOnly: supported iff A is independently correct on ≥ 5 more X7 projects than B, B correct on
     no X7 project where A is not, and A ≥ B on the 8 regression projects (exact one-sided sign test over all 16, p ≤ 0.05);
     rejected iff A ≤ B on X7; otherwise inconclusive.
  3. Growth policy: A vs C and A vs D by exact sign tests over 16 projects; supported only at p ≤ 0.05 (predeclared as
     under-powered: expected inconclusive unless large); CPU and query costs reported side by side (the learned rule previously used
     more CPU than the hand rule).
  4. Coverage vs cost: independently correct projects at matched lifecycle CPU budgets (≤ 5, 10, 20, 40, 80, 160 s) and matched
     membership-query budgets (≤ 1k, 2k, 4k, 8k, 16k) per arm; Wilson 95 % intervals for k/n.
* Recorded per (project, arm): independently correct, false healthy claims, wrong accepted adapters, abstentions, human
  interventions, detection delay, recovery delay, CPU / wall / memory (ledger), oracle use (build labels, spot, incident, mq),
  failed attempts, checking / replay / fallback costs, solving stage (field selection, expression synthesis, lifecycle relearning,
  full-space fallback, human assistance), adapters with applicability conditions, provenance and acceptance scope.
* Interruptions: per call one 840 s alarm; the running arm is TIMED_OUT, later arms of the group NOT_RUN; crashes recorded; all count
  as not independently correct; no completed (project, arm) is ever rerun; dev attempts are kept per tag.
* Budget estimate (available 19,178 s; 18,308 s at this commit): dev ablation ≈ 2,400 s + debugging reserve 1,000 s; validation ≈
  450 s; confirmation ≈ 3,500 s; reporting ≈ 100 s; ≥ 8,000 s held in reserve. If the remaining budget at the freeze cannot cover
  validation + confirmation with a 30 % margin, the confirmation is declared a pilot before any evaluation data is opened.
