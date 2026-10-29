# NEXUS multi-world autonomous-learning campaign

Status: **NOT LOCKED** (owner-requested exploration campaign; protocol committed before any source-learning or target
outcome; results are added in later, separate commits).

## 0. Pre-registration (committed before Stage 2)

### 0.1 Starting state and audit

* Start: `565f26c` (the MI-3 endpoint) on `claude/s456-work`, which is pushed as `codex/nexus-data-engineering` on `github`
  and `origin`.
  * The shared Antigravity checkout at `~/.gemini/antigravity/scratch/nexus-ai` is a stale copy of the same branch at
    `18f53b6`, 90 commits behind, with a clean tree. It is not used and not touched.
* No campaign, MI-x or waiting processes were running.
* **Budget:** the carried mi-track balance was 10,694 s (`scripts/mi_budget.py`). The campaign may charge at most
  **4,500 s** of it, with no new grant.
  * The unit is ledger `wall_s` per metered child, charged by `scripts/mi_exec.py`. `child_cpu_s` is recorded separately.
  * Every failure, rejected proposal, admission run, meta comparison, oracle query, verification, development check, test
    and report step is charged.

| stage | ceiling (s) | scope |
|---|---|---|
| s1 | 700 → 600 after the transfer below | worlds, substrate, development checks, tests, calibration |
| src | 1,800 | 3 cohorts × 3 repetitions × ≤ 200 s |
| meta | 600 | 9 improver clones × 60 s, plus staging and freezing |
| eval | 1,000 → 1,100 | frozen one-use target evaluation |
| rep | 400 | analysis, protection, report |

* **Transfer, recorded before any outcome:** 100 s from s1 to eval (`artifacts/agi_allocation.json`). Stage 1 used 578 s; the
  margin is only for resuming genuinely missing evaluation records.
* **Protection snapshot:** `artifacts/agi_protected_hashes_before.json` shows zero differences on all of the following:
  * the 912 / 157 / 74 / 390 manifests;
  * the MI-1, MI-2 and X7 freezes;
  * checkers v1–v5 against their pins;
  * `main` at `d7ac8c5`, with no `final_sealed` claim;
  * 1,106 frozen MI-1 / MI-2 / X7 / MI-3 files.
* **Reuse:**
  * the metering (`mi_exec`, `mi_budget`, ledger);
  * the seed registry (`seed_registry`);
  * the PID job runner and protection snapshot, copied from MI-3 into new campaign files so the MI-3 files stay frozen.

  The MI-x learners are not reused: they parse the mi_ocean event automaton only. The new substrate is general.

### 0.2 Six worlds, 24 mechanism families, 4 levels (`src/nexus/campaign/worlds/`)

| world | state topology / semantics | interaction protocol | verification |
|---|---|---|---|
| A structured data | tables of positional records | labelled I/O pairs + membership queries (4) | finite hidden-test agreement (30) |
| B temporal state | signals and event streams with hidden state | I/O + queries (4); unseen kind in the interface | bounded exhaustive (all streams ≤ 3) + 30 hidden |
| C spatial objects (**held out**) | 2-D grids, objects, occlusion | I/O + 2 queries; test boards larger / differently shaped | exact multi-grid agreement (30 boards) |
| D graphs and planning | adjacency lists, DAGs, routes, corridors | I/O; D4 = demonstration plans, simulator success | D1–D3 hidden agreement; D4 formal plan validity |
| E active causal (**held out**) | deterministic SCMs with confounding | training = observational only; queries = interventions (6) | exact interventional prediction; E4 control success |
| F small programs | integer / list functions | I/O + a buggy draft program to repair, plus queries (3) | bounded exhaustive (all (a, b) ∈ 0..9², lists ≤ 3) + 30 hidden |

**Families:**
* **A:** A1 filter, A2 grouped aggregation, A3 match / join, A4 routing / projection.
* **B:** B1 windows / differences, B2 latches / hysteresis, B3 session / cooldown, B4 coupled registers.
* **C:** C1 component / occupancy statistics, C2 reflect / rotate / transpose / recolour / scale, C3 occlusion restoration,
  C4 gravity / clipped translation.
* **D:** D1 k-step reachability, D2 DAG unlocking, D3 fuel budgets, D4 multi-stage corridor plans.
* **E:** E1 latent switch, E2 do(X) vs observation, E3 lagged / accumulated chains, E4 experiment-then-control.
* **F:** F1 arithmetic, F2 nested guards, F3 folds, F4 composition; each with a draft.

**Levels:**

| level | composition | training examples |
|---|---|---|
| L1 | the atomic mechanism | 5 |
| L2 | composed with a same-world partner | 5 |
| L3 | composed with a cross-world partner | 5 |
| L4 | both partners | 3 (sparser evidence) |

* D4 and E4 scale their own horizons instead of composing.
* Generators reject tasks that cannot be identified: identical training outputs, or outputs that collapse to a single
  value.
* References are independent Python. The substrate interpreter agrees with them on all 100 × (100 or 1,111) exhaustive
  inputs of the F programs (`artifacts/agi_dev/worlds.json`).

### 0.3 Shared substrate and learner state

* **Substrate (`substrate.py`):**
  * Four value types (int, bool, int list, list of int lists).
  * 57 total primitives: arithmetic, comparison, booleans, typed if, list and table operations, `fold`, `scan`, `iterate`,
    `map`, `filter`, `zipw`, `groupsum` and more.
  * Lambdas over x, (acc, x) and rows, closing over task inputs only.
* **Enumerator:**
  * cost-ordered bottom-up search;
  * static typing;
  * subexpression sharing;
  * observational-equivalence dedup over labelled and unlabelled probe contexts;
  * a per-task CPU deadline.
* **Disclosure:** the primitive list is the human-engineered universal machinery. It includes generic operations (`coalesce`,
  `transpose`, `repeat`, `revL`) that are also useful in Worlds C and E. Every arm, including strong scratch, has exactly the
  same primitives, so this cannot favour a learned arm.
* **R:** unary programs T → T′ instantiated as leaves.
* **L:** typed-hole macros with no input names and no free lambda arguments.
* **π:** production costs, plus the effort parameters margin, n_probes, lam_max, feat_k, confirm_q, qsel and fit_alpha.
* **M:** the meta-DSL program `improver.M0`.

* **π0:**

  | parameter | value |
  |---|---|
  | primitive cost | 2 |
  | input / argument cost | 1 |
  | constants 0–2 / 3–5 | 1 / 2 |
  | margin | 1 |
  | n_probes | 8 |
  | lam_max | 6 |
  | feat_k | 8 |
  | qsel | entropy |
  | confirm_q | 4 |
  | fit_alpha | 0.1 |
  | new item cost | 2 |

* **M0:**
  * `propose_L` antiunify (min_uses 2, max_size 8, max_holes 3, top_k 2);
  * `propose_R` closed (min_uses 2, max_size 5, top_k 2);
  * `reweight` counts (lr 1, α 1, cmax 4);
  * `tune` coordinate;
  * `admit` (n_tasks 4, neutral, speedup 0.2);
  * `prune` (max_L 12, max_R 8);
  * `curriculum` progress (ε 0.25);
  * `schedule` (period 6, meta_period 2).
* **M_rand:** M0's structure with random methods for every proposal statement, and parameters drawn uniformly from the
  same bounded space.
* **M's limits:** M can only re-parameterise or restructure these statements (bounded edits). The evaluator, verifiers,
  meter, splits and substrate are outside it.

### 0.4 The agent loop (`agent_loop.py`) and its acceptance rule

1. Observe the labelled pairs. Draw the learner's own unlabelled probe inputs from the world's declared interface.
2. Keep every consistent hypothesis. Nothing predicted by a hypothesis is ever used as supervision.
3. π chooses R features by utility, the costs and the lambda cap.
4. After the competitor margin, measure the prior-weighted entropy of hypothesis predictions on each unlabelled probe, and
   query the most informative one while disagreement remains.
5. The candidate is the lowest-cost consistent hypothesis with no remaining disagreement.
6. A world verifier checks it. On source tasks only, pass or fail is the learning signal.
7. Revise: labels filter the hypotheses.
8. Generate ΔL / ΔR proposals.
9. Update π; the Full cohort also proposes ΔM.
10. Admission runs on separate tasks.
11. Reset.

**Commitment rule (all arms), each part fixed on development data before this protocol:**
* (a) The margin search must complete. A deadline first means abstain.
* (b) Up to `confirm_q` confirmation queries go to the most novel unlabelled probes, those with input values unseen in
  training. A wrong prediction refutes the hypothesis.
* (c) **Chance-fit bound:**

  expected spurious fits = candidates searched × ∏ᵢ (empirical frequency of label i's value) must be ≤ `fit_alpha`.

  Otherwise gather another label, or abstain.

### 0.5 Admission, pruning, meta-edits (development choices made before this protocol)

* **Admission tasks:** separate tasks from the admission family of each source world (A1, B1, D3, F2). There are 4 per
  round, with L1 and L2 interleaved. The baseline state and each proposal are run on the same tasks.
* **Admission decision:**
  * More solves are admitted; fewer are rejected; a new silent error is rejected.
  * With equal solves and at least one commonly solved task, a proposal is admitted only without a slowdown: CPU ratio ≤ 1.2,
    or ≤ 0.8 under non-neutral M.
  * With no commonly solved task (no evidence), a global π change is not admitted. An additive L / R item (MDL-supported, or
    random under M_rand) is admitted only if M's `admit.neutral` is on.
* **Bounded memory:** max_L and max_R by utility. Items that other items reference are never pruned.
* **Meta-edits (Full only):** every `meta_period` rounds, one bounded edit M′ of M is proposed. Its proposals are generated
  from the *identical* random stream and judged on the same admission tasks. M′ is adopted iff its admitted-proposal gain
  (10 × Δsolved + CPU saving) is strictly larger.
* **Improver buffer:** the last 40 verified source solutions. It is a learning working set, never consulted by the solver
  and never saved in an endpoint.

### 0.6 Splits, seeds and panels (`src/nexus/campaign/seeds.py`)

* **Family split:** a seeded permutation per world (`random.Random(f"agi-split-{w}")`):

  | world | learn | admission | withheld |
  |---|---|---|---|
  | A | A2, A3 | A1 | A4 |
  | B | B2, B3 | B1 | B4 |
  | D | D2, D4 | D3 | D1 |
  | F | F1, F3 | F2 | F4 |

* **Worlds C and E:** all 8 families stay outside learning, development and admission. No learner was ever run on a C or E
  task during development; only their generators, references and verifiers ran.
* **Partners:** source and admission tasks only ever compose learning-family mechanisms. This is tested, and checked on
  1,320 sampled pool tasks (`artifacts/agi_protocol_check.json`).
* **Seed ranges:** fresh, at 30000–36599, above every registered range (stop 30000) and every spent seed (29999).

  | range | seeds | use |
  |---|---|---|
  | dev | 30000–30999 | development |
  | source | 31000–33999 | 1,000 per repetition |
  | admission | 34000–34999 | 300 per repetition; Stage 3 uses +150 |
  | source_meta | 35000–35999 | Stage 3 |
  | eval_withheld | 36000–36099 | ONE-USE |
  | eval_heldout | 36100–36299 | ONE-USE |
  | eval_retention | 36300–36399 | ONE-USE |
  | improver_panel | 36400–36499 | ONE-USE |
  | placebo | 36500–36599 | placebo generation |

* **Panels:**

  | panel | tasks | composition |
  |---|---|---|
  | withheld | 16 | 4 per source world, L1–L4 |
  | held-out C / E | 32 | 16 per world, Latin square over family × level |
  | retention | 8 | one per learning family, L1–L4 cycling |
  | improver panel | 12 | 2 per world: source worlds give a learning + a withheld family; C / E give C1, C2 / E1, E2 |

* **Anti-leakage check:** 0 descriptor copies and 0 behavioural copies among the 56 unfamiliar targets. A behavioural copy
  means the source reference reproduces the target on all 30 hidden inputs.
  * 5 familiar-family parameter collisions are disclosed. They are 2 retention and 3 improver-panel tasks of learning
    families, which are familiar by design.
* **Size:** the plan rule (`agi_eval.py plan`, from development timing only: overhead ≤ 0.025 s per episode) fixed the full
  **N = 56** main suite. The predicted cost is 901 s at a 0.6 s per-task CPU cap.

### 0.7 Stage 2: source learning

* **Lineages:** 9, one per cohort × repetition. Each is one metered process with a 200 s cap; the internal budget is 192 s
  measured from process start.
* **Full:** learns R, L and π; M evolves; it picks its own curriculum, and the schedule is logged.
* **Fixed-M0:** identical, but M is frozen at M0.
* **Random-Proposal:** frozen `m_random(Random("agi-mrand-<rep>"))`.
* **Curriculum parity:** both controls replay the Full schedule of their repetition. If they exhaust it they stop, with the
  unused budget recorded. The same admission-seed sequence is used for all three.
* **Freeze:** all 9 endpoints, even if unchanged. Matched placebo libraries are generated at freeze time.

### 0.8 Stage 3: improver versus improver

* For each repetition, clone Full_r's (R, L, π) three times with an empty buffer.
* Each clone gets 60 charged s on the same fixed schedule of fresh `source_meta` tasks (8 learning families × 4 levels) and
  the same admission sequence. There are no meta-edits during this stage.
* The improvers:

  | clone | improver |
  |---|---|
  | M* | the Full endpoint's M |
  | M0 | the original M0 |
  | M_rand | the seeded `m_random` |

* Freeze all 9.
* **Note:** if a Full lineage never adopted an edit, its M* equals M0. That comparison is then a null by construction, and
  will be reported as such.

### 0.9 Stage 4: arms and frozen evaluation

| arm | definition |
|---|---|
| Full_r | the frozen Full endpoint |
| RL_r | R*, L* with π0 and M0 |
| Pol_r | π* with R = L = ∅ |
| Init | (∅, ∅, π0, M0) |
| Placebo_r | π* plus a matched random library: same kind, hole / input types, output type, size, cost and utility; executable and non-constant |
| Rand_r / Fixed_r | the frozen control endpoints |
| Scratch | the strong scratch synthesiser: same enumerator, OE dedup and acceptance loop, with size-ordered costs (every production 1) |

* **Improver panel:** the 9 post-meta learners, plus Full_r as the pre-meta reference.
* **Isolation:** every episode restores the frozen state, with digests checked. Learning happens within a task only (its
  queries); there is no cross-episode learning.
* **Jobs:** each job is a task chunk run under **every** arm, task-major, so machine-speed variation is shared.
  * 8 main chunks with a 105 s cap each, and 2 panel chunks with a 60 s cap each; the caps sum within the ceiling.
  * Rows are appended per (arm, task) and are resumable. A finished row is never rerun.
* **Legacy A0 / A5 / A6:** not run. They parse only the mi_ocean event-automaton episodes. No world here has that
  interface, and a parse failure would say nothing about learning.
* **External validity:** **unmeasured**. The repository's external pack (PROSE string transformations, 4 burned tasks) is not
  expressible in this integer substrate, and no compatible untouched pack exists.

### 0.10 Analysis plan (frozen)

* **Measures:** solves, silent errors (submitted but failing independent verification), abstentions, timeouts, queries and
  CPU.
* **Breakdowns:** by panel, world, family and level. Verification kinds are labelled separately: finite hidden, bounded
  exhaustive, plan validity, interventional, control.
* **Family clustering:** means are taken within (world, family) first and then across families. Each statistic is shown
  per repetition, with a 95 % cluster bootstrap over families (2,000 resamples).
* **Primary signal:** held-out Worlds C and E, Full_r against Scratch and against Placebo_r. The pilot interpretation
  target needs all three of:
  * at least **+10 pp** pooled family-clustered gain over **both** controls;
  * a positive gain against both in at least 2 of 3 repetitions;
  * **0** silent errors by Full on C and E.
* **Policy versus library:** Full, RL, Pol and Init. The interaction term is (Full − Init) − (RL − Init) − (Pol − Init):
  negative means sub-additive, about 0 additive, positive synergistic.
* **Improvers:** M*, M0 and M_rand clones on the 12-task panel, per repetition, plus break-even amortisation of both the 60 s
  meta step and the 200 s source acquisition.
* **Inventory:** the exact code of every R* and L* item, with its birth task, MDL score, admission record, source uses,
  target uses in solved episodes, and target tasks lost against Init or Scratch (negative transfer).

## 1. Results

This section was added after the run (NOT LOCKED). The source endpoints are `324010a`, the meta clones `0c32d0a`, and the
one-use evaluation ran on code frozen at `62204b3`, with the placebo hole-filling fix of `324010a` described in §1.9.

### 1.1 Headline

| question | measured answer |
|---|---|
| Primary: held-out C + E, Full − Scratch (family-clustered, pooled) | **+4.2 pp**, cluster CI [0, +10.4] |
| Primary: held-out C + E, Full − Placebo | **−1.0 pp**, CI [−3.1, 0] |
| Held-out C + E, Full − Init (the same enumerator with π0) | **−2.1 pp**, CI [−4.2, 0] |
| Repetitions positive against both Scratch and Placebo | **0 of 3** |
| Silent errors by Full on C and E | 0 |
| Pilot interpretation target (≥ +10 pp against both, ≥ 2 of 3 repetitions, 0 silent) | **not met** |
| M* versus M0 | **identical**: no meta-edit was ever adopted, so M* = M0 byte for byte in all 3 repetitions |
| M* versus M_rand on the 12-task panel | 1 / 2 / 2 against 1 / 2 / 2 solves: no difference |

* Scratch is the weakest arm, at 1 of 56. Its uniform cost of 1 per production turned out to be a worse prior than π0's
  primitives at 2 and leaves at 1. The fairer scratch comparator is therefore **Init**, which runs the same enumerator and
  acceptance loop with no learned state.
* Against Init, nothing learned transferred to C or E.

### 1.2 Source learning (Stage 2; 1,692 s charged; each lineage ≤ 192.7 s)

| lineage | tasks | verified solves | silent | L / R kept | π effort parameters at end | stop |
|---|---|---|---|---|---|---|
| Full r0 | 108 | 30 | 0 | 10 / 3 | n_probes 6 (else π0) | budget |
| Full r1 | 155 | 46 | 5 | 8 / 3 | margin 0, n_probes 6, lam_max 5, qsel first, confirm_q 3, fit_alpha 0.01 | budget |
| Full r2 | 127 | 35 | 1 | 4 / 4 | n_probes 10, confirm_q 3, fit_alpha 1.0 | budget |
| Fixed-M0 r0 / r1 / r2 | 108 / 145 / 127 | 30 / 36 / 35 | 0 / 2 / 2 | 10/3, 7/3, 4/5 | — | exhausted / budget / exhausted |
| Random r0 / r1 / r2 | 108 / 97 / 127 | 29 / 22 / 28 | 0 / 4 / 0 | 0/0, 0/0, 8/2 | — | exhausted / budget / exhausted |

* **Where solves came from:**
  * Almost all source solves are World F (27 of 30, 38 of 46, 29 of 35) and World A.
  * World B gave 0, 0 and 1 solves; World D gave 0 in every lineage.
  * L3 / L4 compositions were rarely solved, and L4 never.
* **Curriculum:** the progress rule concentrated effort on F.
* **Meta-edits (Full):** 26 proposed, 0 adopted. In every one of the 26 comparisons the edited M produced exactly the same
  admitted-proposal gain as the current M.
  * Most bounded edits (admission size, curriculum, pruning, schedule, reweight parameters at an unchanged archive) do not
    change the proposals generated in that same round. The strict-improvement rule therefore cannot reward them.
  * This is a design limitation of the M-evaluation protocol, not evidence about M's value.
* **Fixed-M0 r0 reproduces Full r0 exactly** (30 of 108, the same items), as it must when M never changes. The other
  repetitions differ through timing: the Full lineage spends part of its budget on meta-comparisons.
* **Random-Proposal:** random items were mostly rejected or pruned. Only r2 kept some (8 L / 2 R), and it had fewer source
  solves than the guided cohorts. Source silent errors (5 in Full r1) all fell under learned relaxations of π0's
  conservative acceptance (margin 0, fit_alpha 1.0). The admission check rejects a proposal only when a new silent error
  appears *on the admission tasks*.

### 1.3 Inventory: what R and L NEXUS actually built (Full endpoints)

**Full r0** (all learned from F3 / F1 source tasks; neutral admission, because no admission task was commonly solved):

| item | birth | MDL | support | uses |
|---|---|---|---|---|
| L0 `mul(3, sum(map(\x. mul(x, x), $0)))` | F.F3.L2.31049 | 3 | 2 tasks | — |
| L1 `mul($0, sum(map(\x. mul(x, x), $1)))` | | 2 | | 1 source use |
| L3 `mul(3, sum($0))` | | 3 | | 1 source use |
| L4 `sum(map(\x. mul(x, x), $0))` | | 2 | | **target: F.F4.L2.36014** |
| L5 `filter(\x. lt($0, x), $1)` | | | | |
| L6 `map(\x. mul(x, x), $0)` | | | | |
| L7 `mul($0, 1)` | | | | |
| L9 `sub(sub($0, mul($1, $2)), $1)` | | | | |
| L10 `sub($0, mul($1, $2))` | | | | |
| L12 `mul($0, 3)` | | | | |
| R2 `map(\x. mul(x, x), $0)` | | | | |
| R8 `mul($0, 3)` | | | | |
| R11 `mul($0, 1)` | | | | |

* **Target reuse:** L1 in F.F4.L4.36012 and L4 in F.F4.L2.36014. Both are **withheld-family F4** tasks solved only with the
  macro.
* **Lost against Init:** E.E1.L1.36116 and A.A4.L3.36002.

**Full r1:**
* L0 `sum(map(\x. mul(x, x), $0))` (born F.F3.L1.32031, MDL 6, 5 source uses);
* L1 `map(\x. mul(x, x), $0)`;
* L2 `groupsum(\x. head(x), \x. last(x), $0)` and L6 `groupsum(\x. last(x), \x. head(x), $0)` (from A2);
* L7 `mul($0, 3)`, L8 `mul($0, $0)`, L9 `sub($0, mul($1, 3))`, L10 `sub($0, mul($1, $2))`;
* R3 `map(\x. mul(x, x), $0)`, R4 `groupsum(\x. last(x), \x. 1, $0)`, R5 `mul($0, 3)`.

  Target reuse: R4 in A.A4.L2.36001, and L0 in F.F4.L2.36014. Lost against Init: C.C2.L2.36101 and A.A4.L3.36002.

**Full r2:**
* L0 `sum(map(\x. mul(x, x), $0))`, L1 `map(\x. mul(x, x), $0)`, L3 `mul($0, $0)`, L6 `mul($0, 4)`;
* R2 `map(\x. mul(x, x), $0)`, R4 `groupsum(\x. last(x), \x. 1, $0)`, R5 `R(L0)`, R7 `mul($0, 4)`.

  Target reuse: L0 and L6 in F.F4.L4.36012 and F.F4.L2.36014; L6 in A.A4.L3.36002; R4 in A.A4.L2.36001. Nothing lost
  against Init or Scratch.

**Character of what was built:**
* Small arithmetic and aggregation idioms from F1, F3 and A2: the sum of squares, a scaled sum, grouped counts.
* The R items are input re-encodings, such as squared-element lists and per-key counts. They are constructed from
  primitives, not selected from human encoders.
* None is spatial, causal, temporal or planning-specific.
* π reweighting moved 8 to 57 production costs. In r1 it raised every L item to cost 4.

### 1.4 Frozen evaluation (Stage 4; one use; 56 main tasks × 20 arms + 12 panel tasks × 12 arms; 695 s charged, including the c1 resume)

Solves out of 56, at a 0.6 s CPU cap per task:

| arm | r0 | r1 | r2 | silent (r0 / r1 / r2) |
|---|---|---|---|---|
| Full | 5 | 4 | 7 | 0 / 0 / 0 |
| RL (R*, L* with π0) | 4 | 4 | 4 | 0 |
| Pol (π* only) | 6 | 4 | 7 | 0 / 0 / 1 |
| Placebo | 4 | 4 | 6 | 0 |
| Rand | 5 | 5 | 5 | 0 / 0 / 1 |
| Fixed | 5 | 4 | 7 | 0 |
| Init | 5 | | | 0 |
| Scratch | 1 | | | 0 |

* **By panel (Full r0 / r1 / r2):**
  * withheld: 4, 3 and 5 of 16;
  * held-out C + E: 1, 1 and 2 of 32;
  * retention: 0, 0 and 0 of 8.
* **For comparison:** Init scored 3 withheld, 2 held-out and 0 retention; Pol r0 had the only retention solve (A.A2.L1).
* **By world:** every solve is in A, C, E or F; **B and D: 0 of 64 tasks for every arm.**
* **By verification kind:** D4 plan-validity and E4 control tasks were never submitted by any arm. All 98 submissions
  were under finite hidden-test, bounded-exhaustive or interventional verification.
* **Outcomes over 1,120 main episodes:**

  | outcome | episodes |
  |---|---|
  | abstain_timeout | 929 |
  | submitted | 98 |
  | abstain_nohyp | 51 |
  | abstain_evidence (chance-fit bound) | 42 |

* **Silent errors:** 2 in total, both on E.E1.L2.36120: `coalesce(last(x0), nth(x1, 1))`, which fails 7 of 30
  interventions, submitted by Pol r2 and Rand r2. Both arms carry relaxed acceptance parameters.

The tasks solved, and by which arm families:

| task | mechanism | solved by |
|---|---|---|
| F.F4.L1.36013 | compose[shift_sorted] | every arm, including Scratch |
| A.A4.L2.36001 | group ∘ project | all except Scratch (19 arm instances) |
| C.C2.L2.36101 | rot90 ∘ rot90 = `revL(mapr(rev, x0))` | 18 of 20 instances (Full r1 lost it) |
| E.E1.L1.36116 | latent switch: `coalesce(last(x0), last(x1))`, discovered with intervention queries | 13 instances, including Init |
| A.A4.L3.36002 | `add(1, len(flat(x0)))` | 10 instances |
| F.F4.L2.36014 | sumsq ∘ filter | 10 instances, all of them carrying a learned or random library, or π* |
| F.F4.L4.36012 | 4 × sumsq ∘ mirror | **Full r0 / r2 and Fixed r0 / r2 only**, via L0 / L1 / L4 / L6 |
| C.C2.L3.36105 / A.A2.L1.36300 | | Pol r2 / Pol r0 only |

### 1.5 Policy transfer versus library reuse (main suite, family-clustered solve rates)

| rep | Full | RL | Pol | Init | Full − Init | RL − Init | Pol − Init | interaction |
|---|---|---|---|---|---|---|---|---|
| r0 | 0.063 | 0.050 | 0.113 | 0.063 | 0.000 | −0.013 | +0.050 | −0.038 (sub-additive) |
| r1 | 0.050 | 0.050 | 0.050 | 0.063 | −0.013 | −0.013 | −0.013 | +0.013 |
| r2 | 0.088 | 0.050 | 0.088 | 0.063 | +0.025 | −0.013 | +0.025 | +0.013 |

* With π0 costs, R and L alone (RL) are slightly worse than nothing in every repetition: the extra productions widen the
  search.
* π* alone is the most consistent positive component (+5.0, −1.3 and +2.5 pp), but its effect is the same size as the
  changes of one or two tasks.
* The combination shows no consistent synergy.

### 1.6 Improver versus improver (Stage 3; 512 s charged including the freezes; 12-task panel)

| rep | M* | M0 | M_rand | pre-meta Full |
|---|---|---|---|---|
| r0 | 1 | 1 | 1 | 1 |
| r1 | 2 | 2 | 2 | 2 |
| r2 | 2 | 2 | 2 | 2 |

* M* = M0 identically (the same digests), because Stage 2 never adopted an edit.
* In 60 s the M0 / M* clones admitted nothing in r0 and r2 (their states equal the pre-meta endpoint) and little in r1.
  M_rand admitted random items but changed no panel solve.
* **Amortisation:** with a gain of 0 against every comparator, no break-even exists, either for the 60 s meta step or for the
  ~193 s source acquisition.

### 1.7 Budget

| stage | used (s) | ceiling (s) |
|---|---|---|
| s1 | 578 | 600 |
| src | 1,692 | 1,800 |
| meta | 512 | 600 |
| eval | 695 | 1,100 |
| rep | 1 at this commit (score, analysis, protection) | 400 |

* Campaign total: **3,478 of 4,500 s**. Child CPU is within 2 s of wall time in every stage.
* The carried mi-track balance is **7,216 s** remaining. There was no new grant. The only transfer is the pre-registered
  100 s from s1 to eval.

### 1.8 Protection

* **After-check:** zero differences in the 912 / 157 / 74 / 390 manifests and the MI-1 / MI-2 / X7 freezes; checkers v1–v5
  are pinned and `main` is unchanged at `d7ac8c5`. No `final_sealed` claim was made.
* The single flagged file is `artifacts/mi_logs/mi-agi-s1-protect-1.log`: the before-snapshot's own log, which was still
  being written while it was hashed. It is not a protected file.
* All other additions are new campaign logs.

### 1.9 Bookkeeping events (disclosed)

1. **Placebo fix (after source learning, before any target data):** no matched placebo existed for Full_r0 L9 (three int
   holes in 7 nodes). `improver.placebo_for` gained a size- and type-preserving hole-filling step, and the freeze was
   rerun.
2. **Evaluation claim race:**
   * Chunk `main-c1` crashed at start-up (`SeedHygieneError`). Four chunks started together, and another chunk claimed the
     one-use ranges between c1's check and its claim.
   * It wrote **0 rows** and opened no task.
   * Each range is claimed exactly once, under `agi-eval`.
   * The chunk was resumed once with the **unchanged frozen code**; the check passes once the claims exist. Its 140 rows are
     the only rows for those tasks, and nothing was rerun.
   * Separately, `mi_exec` exits 0 even when its child fails, so status lines and row counts were checked.
3. The frozen MI-3 seed test assumes MI-3's ranges are the newest. It fails when imported in the same pytest process as the
   campaign ranges, so the suites were run as separate processes. The MI-3 test was not edited.
4. **Evaluation time:** 695 s charged against a predicted 901 s; abstention-heavy episodes end early.

### 1.10 Closing verdict (strictly from the measurements)

1. **What R and L did NEXUS invent?** A small library of arithmetic and aggregation idioms extracted by anti-unification
   from verified F1, F3 and A2 solutions: the sum of squares, element-wise squaring, scaled sums, a·x + b·c patterns and
   grouped counts / sums. It also built input re-encodings (R) such as squared-element lists and per-key count tables. These
   items are genuine programs constructed from primitives. They are small, few (8–13 per lineage), and nearly all from one
   world.
2. **What transferred?**
   * To **withheld families**: the sum-of-squares macro family let Full and Fixed (which carry it) solve F4 compositions,
     F.F4.L4 uniquely, in 2 of 3 repetitions. That is real but narrow reuse, inside the same world.
   * To **Worlds C and E: nothing measurable.** Full − Init is −2.1 pp, Full − Placebo is −1.0 pp, and the C / E solves
     (C2 double rotation, E1 latent switch) are equally available to Init.
   * There is mild **negative transfer:** learned cost skew cost Full r0 / r1 two tasks each that Init solves.
3. **Did NEXUS learn a better policy π\* for search and experiments?** Not convincingly. π* alone is the most consistently
   non-negative component (+2 to +5 pp in 2 of 3 repetitions), which corresponds to 1–3 tasks. Some learned relaxations
   (margin 0, fit_alpha 1.0) bought speed at the price of the only silent errors.
4. **Did M\* produce better subsequent learners than M0?** The question is untestable here. No meta-edit was ever adopted,
   so M* = M0, and against M_rand the panel solves are identical. The meta-comparison protocol could not credit edits that
   do not change the current round's proposals, and that is where it failed.
5. **What still fails, and where is the frontier?**
   * The 0.6 s enumerator reaches cost 9–10, enough for atomic F and A mechanisms and a few two-step compositions.
   * World B (stateful scans with guards), World D (iteration / graph search and plans) and everything at L4 are beyond it
     for every arm.
   * Admission was usually **uninformative**: no admission task was solved under either state, so additive items entered
     on MDL support alone and π changes were refused.
   * The library therefore reflects whatever the cheapest-to-solve source family produced. It is far from mechanisms that
     would carry structure into spatial or causal worlds.

**Recommended next experiment (one):** make admission and meta-evaluation informative before scaling anything else.
* Give admission a dense graded signal: hypotheses' log-likelihood or partial-output agreement on admission tasks, not
  binary solves.
* Evaluate an M-edit over a multi-round window, with paired RNG, instead of a single round.
* Rerun Stages 2–4 at the same budget, with B and D partial credit as the target.

Until the learning signal reaches beyond F and A, cross-world transfer cannot be tested meaningfully.

## 2. Errata (2026-10-29, after `86953d3`; the negative transfer conclusion is unchanged)

Each correction below was checked against the saved artifacts.

1. **Level-4 solves.** The statement "no level-4 task was ever solved" is false for the evaluation. `F.F4.L4.36012` was solved
   by Full and Fixed in repetitions 0 and 2 (4 arm-runs; `artifacts/agi_eval/main_c*.jsonl`). §1.2's "L4 never" refers to
   source learning only, where it is correct.
2. **Admission solves.** "No admission task was solved under either state" is too strong. The three Full lineages recorded
   a baseline admission solve in **15 of 52** proposal rounds (`artifacts/agi_src/Full_r*.json`, `rounds[].base_solved`).
   Admission was uninformative in the remaining 37 rounds and for most proposals.
3. **B / D denominator.** "B and D: 0 of 64 tasks for every arm" used the wrong denominator. The main evaluation contains
   **12 distinct B / D tasks per arm**, all unsolved: **240 unsuccessful arm–task evaluations** across the 20 evaluated
   arm-runs.
