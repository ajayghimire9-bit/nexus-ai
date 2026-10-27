# NEXUS Wave 40: search-order invariance and the external certification ceiling (NOT LOCKED)

* **Branch and range:** `codex/nexus-broader-programme`, from `199a7bf`. `main`, `final_sealed` and Checkers v1–v5 are untouched
  (v5 pin `2cd3a4ca…` from `622a29a` is verified by every evaluator call; v4 pin `c07e21ec…`).
* **Grant:** 12,924 s carried from Wave 39 (tally: `scripts/w40_budget.py`).
* **Steps:** executed in the requested order. Every confirmation ran once, after the freeze commit.

## Step 1: lost solves traced, Checker v4 `None` audit, provisional historical claims

### 1a. Where the solution path disappeared (`scripts/w40_trace.py` → `artifacts/w40_step1_trace.json`)

**Method.** The lost tasks were replayed with an instrumented copy of the *unchanged* shared search. The copy is asserted to
return exactly what the real search returns.
* **Stream cases:** the Wave 39 C4 streams were replayed in-process up to the lost task, so the trace uses the exact
  HierLearner prior. The replayed solve sequence matches the artifact in all 3 streams.
* **Trace target:** the solution path is Fresh's (uniform) solution chain.

**What happened in every case.** The same value state was first reached by a cheaper route one level *deeper*. That route
started with `fill`, an encoder that is a no-op on these record lists. Fixed and learned priors make encoders cheap as a
first step. The dedup marked the state seen, and the true route arrived later at a shallower depth, still able to finish. It
was discarded by the rule "observational dedup: value state already in `seen` (raw value equality, at any depth)".

| Case | Task (mechanism) | Prior | Fresh solution | Discarded prefix (depth, score, steps left) | Route that had marked the state (depth, score, steps left) |
| --- | --- | --- | --- | --- | --- |
| W39 C4 stream 7842 #26 | tables `dept_counts` | Hierarchical (s = 1) | `countby dept` → `map count` | `countby dept` (1, 9.80, 1) | `fill count:=0` → `countby dept` (2, 8.75, 0) |
| W39 C4 stream 7843 #26 | tables `present_names` | Hierarchical | `filter x≠null` → `map name` → `join ,` | `filter x≠null` (1, 9.59, 2) | `fill x:=0` → `filter x>0` (2, 8.56, 1) |
| W39 C4 stream 7845 #25 | tables `dept_counts` | Hierarchical | `countby dept` → `map count` | `countby dept` (1, 9.58, 1) | `fill count:=0` → `countby dept` (2, 8.65, 0) |
| W39 C2 7831 tables #6 | `present_names` | Fixed-v5 | `filter x≠null` → `map name` → `join ,` | `filter x≠null` (1, 2.0, 2) | `fill x:=0` → `filter x>0` (2, 1.5, 1) |
| W39 C2 7832 tables #6 | `present_names` | Fixed-v5 | same | same (1, 2.0, 2) | same (2, 1.5, 1) |
| W38 E3 7801 tables #6 | `present_names` | Fixed (W38) | same | `filter`→`map name` (2, 3.0, 1) | `fill count:=0`→`filter`→`map name` (3, 2.5, 0) |
| W38 E3 7801 tables #7 | `present_names` | Fixed (W38) | same | same (2, 3.0, 1) | same (3, 2.5, 0) |
| W38 E3 7803 tables #6 | `present_names` | Fixed (W38) | `map name` → `uniq` → `join ,` | `map name` (1, 2.0, 2) | `fill count:=0` → `map name` (2, 1.5, 1) |

The Wave 38 sample covers 3 of the 10 Fixed losses. All 10 are the same two tasks (tables #6 and #7, each seed 7801–7805)
with the same `no_candidate` signature, below 2M executions.

### 1b. Checker v4 `None` handling (`scripts/w40_v4_none_audit.py` → `artifacts/w40_v4_none_audit.json`)

**The defect.** v4 uses `None` both as its error sentinel and as a legitimate JSON null.

**A sound filter.** From the v4 source, a legitimate top-level null can arise only in three ways:
* field access (`get`, or `f` inside a lambda) on a null field;
* `best` returning a null element;
* a bare `["c", null]` constant.

Wave 38/39 scopes contain null constants only inside `eq`/`ne`, whose results are booleans; the script asserts this for
every task. So a task without nulls in its public data or query cannot be affected.

**Exact check.** Every null-bearing task gets an exact differential: `v4._share` versus an in-memory shadow copy of v4 with a
distinct sentinel object (the kernel file is not modified), plus v4's own candidate pre-checks.

| Suite (regenerated from committed seeds) | Tasks | With null data | Exact differentials | Verdict changed |
| --- | --- | --- | --- | --- |
| W38 internal folds (dev 841–842, confirm 7801–7805; sources + targets) | 1,288 | 251 | 251 | **0** |
| W38 meta-learning confirmation streams | 45 | 30 | 30 | **0** |
| W38 continual confirmation streams | 200 | 40 | 40 | **0** |
| W38 evolution confirmation streams | 90 | 0 | 0 | 0 |
| W38 Stage 4 six-phase program stream | 20 | 2 | 2 | **0** |
| W38 Stage 4 / W39 Fresh-v4 on PROSE-dev | 34 | 0 | 0 | 0 |
| W39 Fresh-v4 on PROSE-confirm (129) | 129 | from Step 6 runner | n/a | see Step 6 |

**Result:** no Wave 38 or Wave 39 certificate, solve or label changed because of v4's `None` conflation. The first audit run
hit its 850 s cap right after the last Wave 38 suite. Its ledger row reads `COMPLETE` because the status was hard-coded at
the time; the ledger is append-only. It was resumed for PROSE-dev.

### 1c. Provisional-claim audit (Wave 38 and Wave 39)

| Historical claim | Status after Wave 40 Step 1 |
| --- | --- |
| W38 E3: "Fixed DSL cheaper but loses 10 solves (149/160)" | **ARTIFACT (search dominance defect).** All 10 losses are the traced `fill`-route pattern; the repaired search recovers them (tests). The cost comparison in that row is also provisional, because Fixed was charged a truncated search on those tasks. Superseded by the C1 rerun below. |
| W39 C2: "Fixed-v5 344 vs 346" | **ARTIFACT (search defect).** Both losses traced. |
| W39 C2: Placebo-v5 solve losses | Placebo lost no solve at full budget in W39 C2 (346 = Fresh); only its 0.25× point (344) is cap-dependent. No artifact claim. |
| W39 C4: "Hierarchical Stream Memory −3 solves, NEGATIVE" | **ARTIFACT (search defect).** All 3 traced. Re-tested in C2 below. |
| W38 E1 "Fixed DSL cheaper at equal solves", W38 E6 regime memory, W39 C1 PROSE rows | **PROVISIONAL.** They ran on the defective search, but uniform (Fresh) behaviour is provably unchanged (same candidate, same executions: test `test_new_search_matches_old_under_uniform_prior`). Every Fresh number stands; the costs of non-uniform arms may shift. |
| Any claim depending on v4 `None` handling | **NOT AFFECTED** (1b). |

## Step 2: the state-dominance repair (`src/nexus/w40_search.py`)

**The rule.** A popped state is pruned only if an already-*expanded* route to the same state dominates it in every resource
that constrains future extensions. In this language those resources are exactly:
* the value vector on the public inputs plus the query;
* the remaining depth, which also determines whether the final-step type rule applies.

**What is not in the tuple, and why.** The tool set is identical at every node, there are no bound variables, and the budget
counts executions, not prior cost. Cost and the last tool affect only the order of exploration.

**Implementation.** The search keeps `min_depth_seen[values]` and re-expands when a strictly shorter route arrives. The same
walk provides `reachable_fitting` (run to completion) and `disagreeing_witness` (Step 5). The Wave 39 modules stay unchanged,
so Wave 39 remains reproducible.

## Step 3: search-order invariance (`tests/test_search_order_invariance.py`), 175/175 pass

**Problems: 84.** All 35 internal mechanisms across the 4 domains, each with 3 public pairs and with 1 public pair (the
1-pair version is under-determined, which exercises AMBIGUOUS and multi-answer sets), plus 7 PROSE-dev tasks × 2. Each
problem uses an exhaustively enumerable sub-scope of the declared v5 scope: the teacher's tools, every `fill` tool, and a
seeded sample (depth 3 with about 25–32 tools, or depth 2 with about 100).

**Orderings: 14.** Fresh, Fixed-v5, Repr-v5, Placebo-v5, Fixed+Repr-v5, an adversarial "no-op first" ordering, and 8 random
cost matrices.

**Properties:**
1. **Same solution sets.** Run to completion, every ordering recovers exactly the brute-force set of fitting value vectors
   (all chains, no dedup, no pruning).
2. **Same certificates.** The first candidate of every ordering gets a byte-identical Checker v5 verdict (label, k, answers,
   per-input answer counts, warnings, witnesses, work counters).
3. **The suite detects the defect.** The Wave 39 search fails to find a reachable solution in 54 problem × ordering pairs.
4. **The traced losses are recovered** at full scope, in each wave's own language, scope and Fixed prior.
5. **Uniform behaviour is unchanged.**

`tests/test_w40_components.py` (5/5) adds:
* the O(T) learned and hierarchical cost rows equal Wave 39's exactly;
* Fixed+Repr with no programs orders tools exactly as Fixed-v5;
* payoff-gate behaviour;
* witness short-circuit soundness against Checker v5.

All checker-kernel tests (v1–v5) still pass.

## Development results (dev seeds and PROSE-dev only; they inform the freeze, not the claims)

* **Internal tables fold, dev seed 861** (the fold where Fixed lost in Waves 38 and 39): every arm solves 18/18 with 0 wrong.

  | Arm | Work G |
  | --- | --- |
  | Fresh-v5 | 1,114.9 |
  | Placebo-v5 | 1,047.9 |
  | Fixed-v5 | 915.9 |
  | Repr-v5 | 881.7 |
  | Fixed+Repr-v5 | **874.3** (0.955× Fixed-v5) |
  | Repr-core-v5 | 882.3 |

* **6-phase stream, dev seed 862:** all four learners solve the same 52/53 tasks (Fresh also misses task 11, a genuinely
  ambiguous `max_indeg_node`). Hierarchical Stream Memory is 1,114.8 G, against Ungated Online 1,115.0 G, Hard-Gated
  1,288.6 G and Fresh 1,318.6 G.
* **PROSE-dev (35 evaluable):**
  * Search is 7.8–8.6% of search + certification work.
  * An *unbounded* witness search made total work worse (Fresh 937.7 G with the short-circuit vs 903.8 G without). On
    scope-unique tasks it sweeps the whole scope, duplicating the kernel. This motivated the frozen 48,000-execution budget.
  * The exact O(T) cost rows alone bring ungated Online-hier to 1.004× Fresh (907.0 G vs 903.8 G), against 1.20× in Wave 39.
  * The payoff gate never switched off on dev (906.4 G).
## Step 4 freeze: Wave 40 confirmation protocol (committed before any Wave 40 confirmation seed or PROSE-confirm-2 file is opened)

**Frozen components:**
* Code: Checker v5 (pin `2cd3a4ca…`, commit `622a29a`, untouched); `w40_search` (state-dominance repair); `w40_learn`
  (Fixed+Repr-v5 and exact O(T) learned rows); `w40_online` (payoff gate, C_ROW 0.052 and C_FIT 0.47); `w40_eval`; children
  `scripts/w40_child.py` and `scripts/w40_online_child.py`.
* Drivers: `scripts/w40_lodo.py`, `w40_stream.py`, `w40_prose.py` and `w40_analyze.py`, at the freeze commit. The Wave 39
  modules are imported unchanged.
* Budgets: internal and PROSE use 4M executions per search, with curves read at 0.25×, 0.5×, 1× and 2× of 2M. The stream uses
  2M, as in Wave 39.
* Learners: `BASELINE_80F9CC2`; Hierarchical Stream Memory at s = 1 (frozen in Wave 39).
* Witness short-circuit budget: 48,000 executions for every arm. On PROSE-dev it was the only grid value with a positive net
  saving for every arm (+15 to +17 G of about 905 G). The grid is noisy (35 tasks), and the choice is disclosed.
* PROSE priors are the Wave 39 frozen internal-source priors.

| Confirmation | Data (one use) | Primary comparison and verdict rule |
| --- | --- | --- |
| **C1** Internal folds | `wave40/confirm_lodo` 7851–7855: 4 folds × (2 source + 2 target instances per mechanism) | **(a) Completeness: PASS** if every arm's full-budget solve set equals Fresh-v5's, with 0 wrong; FAIL otherwise. **(b) Repr-v5:** the Wave 39 C2 rule. **PROVED** if total work (fitting charged) is below Fresh-v5's and Placebo-v5's, pooled and in ≥ 4/5 seeds, with solves ≥ every control and 0 wrong. **PARTIAL** if it beats one. **NEGATIVE** otherwise. **(c) Fixed+Repr-v5 vs Fixed-v5:** **PROVED** if total work (fitting charged) is below Fixed-v5's, pooled and in ≥ 4/5 seeds, with solves ≥ Fixed-v5's and 0 wrong. **PARTIAL** if lower pooled but in < 4/5 seeds. **NEGATIVE** otherwise. A ratio above 0.98 is reported as *negligible* whatever the verdict. Intersection ratios, curves and source accounting are reported. |
| **C2** 6-phase stream | `wave40/confirm_stream` 7856–7860 | **(a) Completeness: PASS** if every learner solves exactly the tasks Fresh-v5 solves, in every seed. **(b) Hierarchical Stream Memory: PROVED** if total work (learning charged) is below Fresh-v5's, Ungated Online's and Hard-Gated's, pooled and in ≥ 4/5 seeds, with solves ≥ each in every seed and 0 wrong. **PARTIAL** if it beats some. **NEGATIVE** otherwise. |
| **C3** External PROSE-confirm-2 | 185 never-used PROSE tasks (sealed by hash before the freeze); claim `wave40/confirm_prose` 7861 | **(a) Decomposition (descriptive):** search vs certification work per arm; search work at 500 / 2k / 8k / 36k executions; the Amdahl ceiling (total work divided by certification work on the same tasks). **(b) Witness short-circuit: SOUND** only if no task with a disagreeing witness gets a kernel label other than AMBIGUOUS (otherwise FAIL, and no saving is claimed). The saving is (no-SC − SC) / no-SC per arm, with every SCOPE_UNIQUE verdict unchanged by construction. **(c) Learned experience (external):** the Wave 39 C1(b) rule for Repr-v5 vs Fresh-v5, Placebo-v5 and Fixed-v5, on no-SC work. Fixed+Repr-v5 vs Fixed-v5 uses rule C1(c) on tasks, pooled only. **(d) Payoff-gated online:** the penalty is **ELIMINATED** if Online-hier-payoff-v5's total work (learning charged) is ≤ 1.01 × Fresh-v5's no-SC work, with HOV ≥ Fresh-v5's. **REDUCED** if it is below ungated Online-hier-v5's but above that bound. **NOT REDUCED** otherwise. |

* **Source accounting** (C1): mandatory work counts only the marginal fitting instructions. Extra curriculum counts source
  solving plus fitting, with a break-even target-task count per prior. The core set is Repr-core-v5.
* **Missing-data rule:** runs resume from per-fold or per-arm checkpoints at the 890 s call cap. Nothing is dropped, and every
  interruption is logged.
* **Step 6 order:** the owner-requested audit of the 4 consumed PROSE-confirm tasks runs only after C3. Those tasks are then
  marked BURNED.

**Post-freeze fixes (disclosed).**
* `w40_lodo.py` crashed on launch with `SeedHygieneError`, before any seed was claimed or any task was run: a text
  substitution had left the claim key as `("wave39", "confirm_lodo5")`.
* The same bug in `w40_stream.py` was found before that driver was ever launched.
* Each fix corrects only the key (`526c2ea` and the next commit).

## Step 4: fresh confirmations at equal coverage (one-use seeds, after freeze `19885f8`)

### C1. Internal folds (4 held-out folds × 5 fresh seeds, 7851–7855; 350 targets)

| Arm | Solved | Wrong | Work G (fit charged) | Solved at 0.25× / 0.5× / 1× / 2× | Work G at caps |
| --- | --- | --- | --- | --- | --- |
| Fresh-v5 | 349/350 | 0 | 10,804.2 | 329 / 349 / 349 / 349 | 8,396 / 10,804 / 10,804 / 10,804 |
| Placebo-v5 | 349/350 | 0 | 9,801.9 | 346 / 349 / 349 / 349 | 9,491 / 9,802 / … |
| Fixed-v5 | 349/350 | 0 | 8,354.2 | 349 at every cap | 8,354 |
| Repr-v5 | 349/350 | 0 | 8,602.1 | 349 at every cap | 8,602 |
| **Fixed+Repr-v5** | 349/350 | 0 | **8,278.9** | 349 at every cap | 8,279 |
| Repr-core-v5 | 349/350 | 0 | 8,605.2 | 349 at every cap | 8,605 |

* **(a) Completeness: PASS.** All six arms have identical solve sets in every fold and seed (0 mismatches). The one unsolved
  target is the same for every arm. The Fixed losses of Waves 38–39 are gone.
* **(b) Repr-v5: PROVED** against the frozen controls.
  * vs Fresh-v5: 0.796× (intersection 0.795×), 5/5 seeds.
  * vs Placebo-v5: 0.878× (0.877×), 5/5 seeds.
  * **But Repr-v5 is 1.030× Fixed-v5 (0/5 seeds).** Once Fixed is complete, the hand-designed prior beats the learned one.
    The Wave 39 statement that Repr was "1.036× Fixed on the intersection" is confirmed; the earlier solve-count gap that
    made Repr look better than Fixed was the search defect.
* **(c) Fixed+Repr-v5 vs Fixed-v5: PROVED by the frozen rule** (0.991×, 5/5 seeds, equal solves, 0 wrong), but **negligible**
  (ratio > 0.98).

**Source accounting** (per prior):

| Prior | Mandatory work (fitting) | Extra curriculum | Saving per target task | Break-even |
| --- | --- | --- | --- | --- |
| Repr-v5 vs Fresh-v5 | 0.087 G | 708 G | 6.29 G | 112 target tasks |
| Repr-core-v5 vs Fresh-v5 | 0.046 G | 349 G | 6.28 G | 56 target tasks |
| Fixed+Repr-v5 vs Fixed-v5 | 0.086 G | 708 G | 0.22 G | about 3,300 target tasks |

### C2. Six-phase stream (5 fresh seeds, 7856–7860; 265 tasks)

| Learner | Solved | Wrong | Total work G (learning incl.) | vs Hierarchical Stream Memory |
| --- | --- | --- | --- | --- |
| Fresh-v5 | 264/265 | 0 | 6,255.7 | hier 0.837×, 5/5 seeds |
| Ungated Online (no-gate) | 264/265 | 0 | 5,233.9 | hier 1.000× (−0.2 G), 4/5 seeds |
| Hard-Gated (regime memory) | 264/265 | 0 | 6,089.3 | hier 0.859×, 5/5 seeds |
| **Hierarchical Stream Memory** (s = 1) | 264/265 | 0 | **5,233.7** | — |

* **(a) Completeness: PASS.** Every learner solves exactly Fresh's tasks in every seed. The one miss is 7860 #0, a probe error
  shared by every learner.
* **The 3 lost solves are eliminated.**
* **(b) Hierarchical Stream Memory: PROVED by the frozen rule.** It is cheapest pooled, in ≥ 4/5 seeds against every
  control, with equal solves. Against Ungated Online the margin is 0.2 G of 5,234 G (0.004%), a tie in practice. Its real
  advantage is over Fresh (−16%) and over the hard-gated per-regime memory (−14%). The regime residual itself adds
  essentially nothing beyond one global online prior.

## Step 5: the external certification ceiling, decomposed (PROSE-confirm-2, 185 never-used tasks, 175 evaluable)

**Correcting the premise first.** "Certification is about 95% of work" was true only on Wave 39's *solved intersection*.
Over all Wave 39 PROSE-confirm tasks, search was 18% of work, and on PROSE-confirm-2 it is 26%.

**Where search work goes:** 108 of 175 tasks have no in-scope candidate. That search is an exhaustive sweep that every
ordering must complete to report failure, so it is **order-invariant**: no prior can shrink it.

| Fresh-v5, by task class | Tasks | Search G | Certification G | Share of total | Ceiling if search → 0 |
| --- | --- | --- | --- | --- | --- |
| SCOPE_UNIQUE (full scope must be swept) | 42 | 34 | 1,035 | 43.7% | **1.033×** |
| AMBIGUOUS | 25 | 11 | 776 | 32.2% | 1.015× (before short-circuit) |
| No candidate (expressiveness gap) | 108 | 591 | 0 | 24.1% | 1.00× for ordering (order-invariant sweep) |

**Amdahl statement.** On tasks with a candidate, search is 2–3% of work. A perfect search ordering saves at most 3.3% on
unique tasks and 1.5% on ambiguous ones. The only large external lever is certification of ambiguous tasks, below.

### 5.1 Search work alone (candidates found, search G) at execution caps

| Arm | 500 | 2k | 8k | 36k | Search G (all) | HOV | Certified-but-held-out-fail |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Fresh-v5 | 34 / 8.4 | 45 / 24.3 | 53 / 69.8 | 62 / 255.0 | 635.1 | 36 | 6 |
| Placebo-v5 | 36 / 11.8 | 49 / 26.5 | 54 / 76.4 | 64 / 271.4 | 660.7 | 36 | 6 |
| Fixed-v5 | 28 / 8.6 | 46 / 25.5 | 59 / 72.9 | 66 / 251.2 | 631.0 | 34 | 8 |
| Repr-v5 | 38 / 9.0 | 49 / 22.0 | 56 / 66.1 | 64 / 246.9 | 622.8 | 36 | 6 |
| Fixed+Repr-v5 | 39 / 13.0 | 51 / 27.9 | 57 / 77.7 | 65 / 272.8 | 665.9 | 36 | 6 |

Learned and hand priors find candidates sooner at small caps; Repr-v5 has the least search work. On the 34 tasks every arm
verifies, search G is: Repr 18.0, Fixed 18.2, Fresh 21.1, Fixed+Repr 21.4, Placebo 24.2.

### 5.2 Sound witness short-circuiting in certification

After a candidate is found, the solver continues in its own prior order, for up to 48,000 executions, looking for a fitting
in-scope chain with a different query answer. If it finds one, the kernel sweep is skipped. That is sound: two in-scope
fitting programs that disagree on the query force AMBIGUOUS. Every SCOPE_UNIQUE verdict is untouched.

| Arm | Ambiguous short-circuited | Unsound | Total work, no short-circuit (G) | With short-circuit (G) | Saving |
| --- | --- | --- | --- | --- | --- |
| Fresh-v5 | 18 / 25 | 0 | 2,447.3 | 2,044.3 | 16.5% |
| Placebo-v5 | 16 / 25 | 0 | 2,473.6 | 2,146.6 | 13.2% |
| Fixed-v5 | 22 / 25 | 0 | 2,443.0 | **1,904.7** | **22.0%** |
| Repr-v5 | 20 / 25 | 0 | 2,434.6 | 1,920.5 | 21.1% |
| Fixed+Repr-v5 | 21 / 25 | 0 | 2,479.2 | 1,965.0 | 20.7% |

**Verdict: SOUND**, with a real saving. Prior order matters here: Fixed and Repr find disagreeing witnesses earlier than
Fresh, and Placebo is worst. With the short-circuit, Fixed-v5 is 0.932× and Repr-v5 0.939× Fresh's total. This is the first
external setting where search *order* moves total work by more than about 1%. The upper bound remains unique tasks, which
must be swept in full (43.7% of work).

### 5.3 Payoff-gated online learning

| Arm | HOV | Total work G (learning incl.) | vs Fresh-v5 (no short-circuit) |
| --- | --- | --- | --- |
| Online-hier-v5 (ungated; exact O(T) rows) | 36 | 2,461.0 | 1.006× |
| **Online-hier-payoff-v5** | 36 | **2,445.1** | **0.999×** |

* **Verdict: penalty ELIMINATED** (≤ 1.01× with equal HOV). The gate switched the prior off at task 74, when measured savings
  had not covered prior-evaluation cost.
* **Honest attribution:** most of the Wave 39 penalty (1.20×) was removed by the exact O(T) cost rows, which bring even the
  ungated learner to 1.006×. The gate removes the rest.

### 5.4 Learned experience on external tasks (rule C3(c))

* **Repr-v5:** HOV 36, equal to Fresh and Placebo and above Fixed's 34. Total no-short-circuit work is 2,434.6 G against
  2,447.3 (Fresh), 2,473.6 (Placebo) and 2,443.0 (Fixed), and it is lowest on the intersection (874.5 G against 877.4,
  880.6 and 874.7). **PROVED by the rule, negligible (0.995× Fresh).**
* **Fixed+Repr-v5 vs Fixed-v5:** 2,479.2 G vs 2,443.0 G. **NEGATIVE.** It has more HOV (36 vs 34), but the rule is about work.
* **Silent failures** (wrong held-out answers on inputs labelled unique): 11 of 420 inputs for every arm, against 19–25 under
  the v4 contract.

## Step 6: the 4 certified PROSE programs that failed held-out (Wave 39 PROSE-confirm, consumed)

**Status of these tasks.** The owner requested this audit. The committed audit runner (`scripts/w40_heldout_audit.py`)
loaded the tasks only after C3, with the harness token and SHA-256 checks. The 4 tasks are now **BURNED**
(`artifacts/external/prose_confirm/BURNED.json`) and can never again serve as sealed data. PROSE is public benchmark data,
but this is still a deliberate, disclosed exception to RULE 1's "the tuner never sees sealed tasks". The re-run reproduces
Wave 39's certificate and held-out score exactly in all 4 cases.

| Task | (a) Public examples (3) | (b) Certified v5 program | (c) First held-out failure | (d) Why it was not distinguished |
| --- | --- | --- | --- | --- |
| BillingCode.000002 | `[CPT-00350`→`[CPT-00350]`; `[CPT-00340`→`[CPT-00340]`; `[CPT-11536`→`[CPT-11536]` | `fn(x ++ "]")` | `[CPT-115]` → expected `[CPT-115]`, got `[CPT-115]]` (3/8 held-out pass) | **Missing format invariant / insufficient examples.** Every public input lacked the closing bracket; the true rule normalises to exactly one. An in-scope alternative exists (digits re-wrapped in `[CPT-…]`). UNDER_SPECIFIED_WARNING fired, and this input was labelled *not* unique (6 answers), so the failure was flagged, not silent. |
| EmergencyCall.000004 | three Lower Merion call records dated 2015-12-11 → `12 Nov 2015 4AM` / `1AM` / `7AM` | `bef ':'` → last char → `"12 Nov 2015 " ++ x ++ "AM"` | the query itself (2015-12-10 20:53) → expected `12 Oct 2015 8PM`, got `12 Nov 2015 0AM` (0/5) | **True mechanism outside v5** (date arithmetic and 12-hour clock). The three public examples share one date and all fall in the AM, so a constant prefix fits. No in-scope program fits the failing pair. A **silent** wrong answer on an input labelled unique. |
| FilePath.000001 | `/libero/quas/enim5.png`→`enim5`; `/libero/enim5.png`→`enim5`; `/libero/quas/enim2.png`→`enim2` | `toks w` → `at -2` | `/` → expected `root`, got ERROR (13/14) | **Boundary special case** (`/` maps to the literal `root`, never shown publicly). Outside scope; the program abstains (ERROR); the warning fired. |
| UserAgent.000007 | three UA strings where the platform is the text between `(` and `;` | `aft ' '` → `bef ';'` → `sl 1:` | `Firefox/6.4 (Macintosh 3.7) …` → expected `Macintosh 3.7`, got ERROR (38/47) | **Spurious boundary match.** Every public example has a `;` inside the parentheses; the true rule is "up to `;` *or* `)`". No depth-3 v5 program fits. The input was labelled unique with an ERROR answer: an abstention, but reported as unique. |

**What a product-level correctness claim would need.** On small-example tasks, scope-relative uniqueness cannot certify
correctness. Two of these four failures are outside any scope the checker can see, and one is a special case that no
example shows. At minimum, a product-level claim needs all of the following:
1. **Active distinguishing queries** answered by the user or an oracle. The solver proposes inputs on which in-scope
   candidates disagree (as the internal-domain probes already do); this would have resolved BillingCode.
2. **Coverage-based input contracts.** Abstain on any future input whose *shape* falls outside the public inputs' shape
   envelope (a missing delimiter, a different date or AM/PM class, a degenerate path). This would have flagged UserAgent,
   FilePath and EmergencyCall instead of answering.
3. **Treat an ERROR answer as abstention, never as UNIQUE** (UserAgent). This is a contract fix for a future checker
   version; v5 stays pinned.
4. **Calibration of residual risk:** an estimate of the out-of-scope failure rate on held-out families, reported with
   every certificate. Even with items 1–3, a certificate remains a statement relative to the declared scope and the
   evidence seen.

## Capability Proof Matrix (updated)

| Capability | Verdict | Evidence (Wave 40) |
| --- | --- | --- |
| Search completeness under any prior (state dominance) | **PROVED** (exhaustive tests + confirmation) | 175/175 invariance tests (84 problems × 14 orderings = brute force; identical v5 certificates); C1 and C2 identical solve sets for every arm and learner |
| Internal cross-domain transfer, learned vs uninformed (Repr-v5) | **PROVED** | 0.796× Fresh, 0.878× Placebo, 5/5 seeds, equal solves, 0 wrong; break-even 112 tasks (core set 56) |
| Learned vs hand-designed prior (internal) | **NEGATIVE for learned alone; negligible for combined** | Repr 1.030× Fixed (0/5); Fixed+Repr 0.991× Fixed (5/5, rule met, below the 0.98 practical bar; break-even about 3,300 tasks) |
| Hierarchical Stream Memory | **PROVED by rule; practically equal to ungated online** | Lost solves eliminated; 0.837× Fresh and 0.859× Hard-Gated (5/5); 1.000× Ungated (4/5, −0.004%) |
| Wave 38/39 Fixed and Hierarchical losses | **RETRACTED as artifacts** | Every traced loss = dedup defect; Checker v4 `None` handling affected 0 verdicts (332 exact differentials) |
| External search-order speedup | **CEILING ≤ 3.3%** | Search is 2–3% of work on candidate tasks; the 24% no-candidate sweep is order-invariant |
| Sound witness short-circuit in certification | **PROVED (sound, 13–22% saving)** | 0 unsound; learned and hand order help (Fixed 22.0%, Repr 21.1% vs Fresh 16.5%) |
| Online learning on external tasks | **Penalty ELIMINATED** | Payoff-gated 0.999× Fresh, equal HOV; mostly from the exact O(T) rows (ungated 1.006×) |
| Learned experience on external tasks | **PROVED by rule, negligible** | Repr 0.995× Fresh, HOV equal; Fixed+Repr vs Fixed NEGATIVE |
| Product-level correctness on small-example tasks | **NOT ESTABLISHED** | Certified-but-held-out-fail 6 of 42 (Fresh, PROSE-confirm-2); 11 silent failures in 420 inputs; Step 6: 3 of 4 audited failures are outside the v5 scope |
| Cheap adaptation (N1-merge-exact), Wave 39 | unchanged (PROVED) | not re-run |
| Meta-learning, evolution, neural ranker, planning (Wave 38) | unchanged (NEGATIVE); repairs inconclusive | not re-run |

## Resources

* **Grant:** 9,334 s of the 12,924 s carried grant used (`scripts/w40_budget.py`); 3,590 s remain.
* **Ledger caveats:** the first v4-audit row reads `COMPLETE` although it hit its cap. The ~3 s PROSE-confirm null check was
  written as 0 s. The ledger is append-only, so both are disclosed here instead.
* **Tests:** 222 pass (checker kernels v1–v5, the invariance suite, Wave 40 components).
* **CPU only;** no paid service. The 185 PROSE-confirm-2 files came by curl from the public GitHub benchmark.

## Next experiment (one)

**Shape-envelope abstention + active distinguishing queries on external tasks.** Freeze a contract that abstains on future
inputs outside the public inputs' character-class and delimiter envelope, and lets the solver ask up to k distinguishing
queries to a simulated user, answered from held-out pairs only through the evaluator. Evaluate once on a new external
split, with silent failures and certified-but-held-out-fail as primaries. Step 6 shows this is where correctness is lost,
and Step 5 shows ordering cannot buy more speed.
