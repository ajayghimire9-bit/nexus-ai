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
