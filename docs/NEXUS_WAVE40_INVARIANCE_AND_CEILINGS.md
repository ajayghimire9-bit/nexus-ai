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
