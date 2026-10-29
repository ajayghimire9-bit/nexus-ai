# NEXUS multi-world campaign Phase 2: incomplete experience, full-trajectory improvers, untouched mechanisms

Status: **NOT LOCKED**. The protocol below is committed before any Phase 2 source-learning or target outcome; results
are added in a separate commit.

## 0. Pre-registration

### 0.1 State, errata, budget

* **Start:** `86953d3` on `claude/s456-work`, which is pushed as `codex/nexus-data-engineering`; `github` and `origin` are
  equal. No campaign process was running (the only `agi`-matching process was a system daemon).
* **Errata to `86953d3`:** committed first as `b07e86b` (campaign report §2 and the register), each verified against the
  artifacts:
  * F.F4.L4.36012 was solved by Full and Fixed in r0 and r2;
  * Full lineages had a baseline admission solve in 15 of 52 rounds;
  * B / D is 12 distinct tasks per arm, all unsolved (240 arm–task evaluations).
* **Budget:** at most **3,200 charged s** of the carried 7,216 s (≥ 4,016 s stay untouched), with no new grant
  (`scripts/agi2_budget.py`, `artifacts/agi2_allocation.json`). The unit is ledger `wall_s`; child CPU is recorded
  separately.

  | stage | ceiling (s) |
  |---|---|
  | s1 | 550 → 450 |
  | src | 1,350 → 1,450 |
  | meta | 450 |
  | eval | 650 |
  | rep | 200 |

* **Transfer, recorded before any outcome:** 100 s from s1 to src. Stage 1 used 422 s. The required No-Incomplete-Experience
  ablation needs a 4th cohort, so there are 12 lineages at 120 s each instead of 9 at 150 s.
* **Protection snapshot:** `artifacts/agi2_protected_hashes_before.json` shows zero violations over 1,237 frozen files:
  MI-1 / MI-2 / X7 / MI-3 **and all Phase 1 campaign code and artifacts**. All Phase 2 code lives in new modules
  (`src/nexus/campaign2/`, `scripts/agi2_*`); `src/nexus/campaign/` is unchanged.

### 0.2 Upgrade 1: expressivity & reachability audit (`scripts/agi2_audit.py` → `artifacts/agi2_audit.json`)

A hand-written reference program (an audit fixture, never shown to a learner) was built and checked against the
independent Python reference on 3 development instances of each of the 24 Phase 1 families. Every train, hidden and
exhaustive input was compared.

* **Expressible:** every instance of every family **except C1's connected-component variants**. Those need a 2-D
  flood-fill: no visited-set construction over grids exists, and none was added, because C is a held-out world.
* **Bound block found and repaired:** the fixed lambda-body cap (`lam_max = 6`) **excluded** the scan / filter / iterate
  bodies of every B2, B3, B4, D1, D2 and D3 reference, whose body costs are 9–24.
  * Phase 2 builds lambda pools **lazily, lagging the top-level cost by 2**. A body of cost k can only occur in a program of
    cost ≥ k + 2, so there is no hard cap and no wasted pools.
  * `lam_max` is now a soft, learnable π parameter (6 … 99).
  * π0 keeps 6, because on development data the cap allocated 0.6 s better (4 vs 2 of 32 source-world tasks,
    `artifacts/agi2_dev/scratch_tuning.json`).
* **Reachable with a focused prior** (the enumerator restricted to the reference's primitives, which is what a perfect π
  or L would give), within 5 s: A1, A2, A4, B1, C2, C3, C4, D1, D2, E1, E3, E4, F1, F3 and F4.
* **Not reached in 5 s, even focused:** A3 join (cost 17), B2 hysteresis (19), B3 cooldown (24), B4 registers (41),
  D3 fuel (29; its thresholds above 5 need constant arithmetic), D4 plans (40), E2 (26) and F2 (22).
* **Reachable with the full grammar in 0.6 s:** cost levels **9–10** only. Of the references only A2, A4, F1, F3 and F4 fall
  inside that.
* **Conclusion fixed before Stage 2:** apart from C1 components and the lambda cap now removed, the blocker in B and D is
  not the language. It is search budget under the π0 prior: references cost 11–41 against a reachable 9–10. Only a
  learned prior, macros or representations can close that gap.

### 0.3 Upgrades 2–4 (`src/nexus/campaign2/agent_loop.py`)

* **Locked acceptance barrier:** `ACCEPT` = margin 1, 4 confirmation queries on the most novel probes, chance-fit bound
  0.1. It is a system constant outside π and M (tested), and the same for every arm.
* **Graded credit:** per labelled example, 1 for an exact output; otherwise the agreeing fraction of leading positions
  (time steps / rows); 0 for a wrong scalar.
* **Tier 1 — provisional experience archive P:**
  * Source: every unsolved episode's best ≤ 3 partially correct, *input-reading* executable candidates with score ≥ 0.3.
  * Evidence kept: the exactly matched labels, the score and the first counterexample.
  * Bounds: `M.archive` max_P 40, 8 per I/O signature.
  * It is never used by the solver and never treated as ground truth.
  * Proposals (anti-unification / representations) draw on solved solutions *and* P.
* **Tier 2 — validated R, L:**
  * A proposal supported by any P entry is **provisional**. It is admitted only on positive evidence on separate admission
    tasks: more exact solves, or graded admission credit up by ≥ `eps` (0.05), with no new silent error and no slowdown.
  * The neutral (no-evidence) rule applies only to solved-only proposals.
  * Global π changes need positive evidence.
* **Draft attribution:**
  * A solution containing a subtree inserted from the task's draft (object identity) is `draft_subtree`; otherwise it is
    `pure_synthesis`. Items inherit their supports' origins: pure / draft / mixed.
  * **Odd-seed World F tasks are pure input-output synthesis**: the learner's view has no draft, in every split.
* **Full-rollout meta-evaluation (Full cohort):**
  * After every `meta_period` (2) proposal rounds, a bounded edit M′ is proposed.
  * The current M and M′ each control their own complete 24 s mini-learning rollout: their own curriculum, admission rule,
    pruning, archive and schedule (≥ 1 proposal round each). Both start from a clone of (R, L, P, π, buffer, curriculum
    history).
  * The rollouts share environment randomness (identical task-seed stream, admission seeds and RNG keys), but their actions
    are free. Curriculum divergence is logged.
  * Both post-rollout learners are scored on the same 3 held-out rollout-evaluation tasks (agi2/rollout seeds), by solves
    then graded credit. M′ is adopted iff strictly better.
  * The lineage continues from the winning post-rollout learner.

### 0.4 Upgrade 5: untouched mechanism families (`src/nexus/campaign2/worlds2.py`)

* **New families, defined once in this commit:**
  * C5: colour-histogram statistics;
  * C6: ray extension;
  * E5: gated mediation X → M → Y;
  * E6: two-parent confounded mixing.
* They appear **only** in the one-use `eval_untouched` panel. No learner, search or descriptor inspection touched them;
  only a generator self-check ran (16 of 16 deterministic, the reference passes, constants fail).

### 0.5 Seeds, panels, isolation (`src/nexus/campaign2/seeds.py`, `artifacts/agi2_protocol_check.json`)

* **Seeds:** fresh ranges at 36600–44099, above every registered range and spent seed. The 4 one-use panels are claimed
  under an **fcntl lock** (fixing the Phase 1 race).

  | panel | tasks |
  |---|---|
  | withheld | 16 (A4, B4, D1, F4 × L1–L4) |
  | ce_fresh | 16 (C1–C4, E1–E4 × 2 levels) |
  | untouched | 16 (C5, C6, E5, E6 × L1–L4) |
  | improver panel | 12 |

* **Isolation:** 1,032 sampled source, admission, rollout and source-meta tasks contain no withheld, C / E or untouched
  mechanism.
* **Dedup:** one withheld target, F.F4.L2.43614, was a behavioural copy of a possible source task (a composition that
  collapses to an F3 fold). Under the protocol rule it was replaced by the reserve seed 43664 before any outcome; after
  that, 0 copies. 3 familiar-family improver-panel collisions are disclosed.
* **Plan:** development timing (overhead ≤ 0.025 s) and the rule, largest N in {48, 32, 24} that fits 630 s, give
  **N = 32**: 8 withheld + 8 ce_fresh (one per family) + all 16 untouched. The predicted cost is 588 s.

### 0.6 Cohorts, Stage 3, arms

* **Stage 2:** 4 cohorts × 3 repetitions × 120 s.

  | cohort | definition |
  |---|---|
  | Full | M evolves by full-rollout checks; own curriculum |
  | Fixed-M0 | M frozen at M0 |
  | SolvedOnly | Fixed-M0 with P **disabled** |
  | Random-Proposal | the matched random improver; same archive capacity, admission and budget |

  * The three controls replay Full's **complete learned-task sequence**: its main loop plus the winning rollouts' tasks.
  * The cleanest causal test of P is Fixed-M0 against SolvedOnly. Full against SolvedOnly (Arm 1 vs Arm 2) additionally
    contains Full's M evolution, if any.
* **Stage 3:** 3 repetitions × {M*, M0, M_rand} × 45 s. Each clone starts from the frozen Full_r (R, L, P, π) and runs a
  complete trajectory controlled entirely by its improver: its own curriculum, admission, pruning and archive. The source-meta
  and admission seed streams are paired. The clones are then scored on the 12-task improver panel.
* **Stage 4 arms (all under the same locked acceptance barrier):**

  | arm | definition |
  |---|---|
  | Full | the frozen Full endpoint |
  | SolvedOnly | the No-Incomplete-Experience endpoint |
  | RL | R*, L* with π0 and empty P |
  | Pol | π* with empty R, L and P |
  | Init | the initial learner |
  | Placebo | matched random R / L |
  | Rand / Fixed | the control endpoints |
  | Scratch | the strong scratch configuration, tuned on source-world development data |

  * Scratch tuning (pi0 + lazy lambdas, pi0 + lambda cap 6, uniform costs, primitive cost 3) **selected pi0 with the cap
    6, which is exactly Init's configuration**. Scratch's rows are therefore Init's rows: run once and reported under both
    names.

### 0.7 Analysis (frozen)

* **Panels reported separately**, each with family-clustered rates, per-repetition differences and 95 % cluster bootstraps:
  * (a) withheld source families;
  * (b) fresh-seed C1–C4 / E1–E4 (new-instance generalisation);
  * (c) untouched C5, C6, E5, E6 (unseen-mechanism transfer).

  Each panel compares Full against Init, Placebo and Scratch, and against SolvedOnly.
* **Also reported:**
  * B / D solves out of the B / D evaluation tasks;
  * the number of validated R* / L* items with provisional (P) support, and the solve delta Full − SolvedOnly and
    Fixed − SolvedOnly per panel;
  * items by origin: pure / draft / mixed;
  * meta-edits adopted, M* against M0, curriculum divergence, and the panel scores of M*, M0 and M_rand;
  * silent errors per arm.
