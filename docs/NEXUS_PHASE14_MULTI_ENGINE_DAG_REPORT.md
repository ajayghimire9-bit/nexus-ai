# NEXUS Phase 14 — out-of-sandbox multi-engine full-DAG repair (Capabilities 3, 7) (NOT LOCKED)

Status: **protocol and report; revision answering the round-5 audit (codex HIGH, gemini HIGH + MEDIUM; both changes_required).**

**Allowed sources for results:**
- `artifacts/agi14_eval/results.json` and `rows.jsonl`;
- the coordinator's `test_execution` and `experiment_execution` records.

**Evidence available when this document was written:**
- The **previous** revision's `test_execution`: returncode 0, 86 tests, 3 skipped. Quoted in section 10.1.
- The **previous** revision's `experiment_execution`: returncode 1, `failures = ["capability_acceptance"]`. Quoted in section 10.1.
- No `test_execution` or `experiment_execution` for **this** revision.

This revision therefore has **no measured result of its own**. Statements about the current code are design descriptions unless they are
quoted from a coordinator record.

**Bottom line (previous revision, measured):**
- Phase 14 is **not accepted**.
- The SQLite-only DAG repair machinery works on these synthetic specs: up to 14 / 14 verified and 0 wrong per arm at B_q = 2.
- The charter's mandatory capabilities were **not demonstrated**:
  - no non-SQLite engine executed;
  - no DataFrame engine executed;
  - no positive learning-to-learn, transfer, reuse or self-evolution gain.

## 0. Scope and files

| File | Role |
|---|---|
| `src/nexus/de_phase14/__init__.py` | Package marker. `PHASE = 14`, `WORK_CAPS`, `ENGINES`, `DAG_LAYERS = (stg_, int_, fct_)`, `ARMS`. Optional engines are detected with `importlib.util.find_spec` and imported only when used. |
| `src/nexus/de_phase14/multi_engine14.py` | Dialect-aware core11 AST → SQL compiler (SQLite / DuckDB / Spark SQL). Empirical core11 NULL-order and rank tie-rule probes. SQL → AST reverse parser. Polars / PySpark DataFrame source → AST front ends. Polars eager and Spark SQL backends. Fail-closed conformance verifier and semantic suite. Live `engine_ready` probe. |
| `src/nexus/de_phase14/dag_repair14.py` | Native-source lifting (`lift_sources`) and fail-closed `source_fidelity` / `native_fidelity`. Layered DAG view, multi-node fault localiser, node-only lift, `compile_dag`, whole-DAG per-engine check (`engine_dag_check`), downstream invariants with **required engines** (`DEFAULT_REQUIRED = (sqlite,)` plus the caller's), and `repair_dag`. |
| `src/nexus/de_phase14/runner14.py` | Seven DAG specs with engineer-authored SQL and DataFrame source text. Native fronts. Reference-fidelity gate. Learned executable operators. One shared row budget: fidelity gate first, then the operator stage, then `repair_dag`, with **both repair paths gated by whole-DAG required-engine verification** (`solve`). Source training per stream. Frozen evaluation of Fixed / Random / Untrained / Trained, the ablations `trained_no_ops` and `trained_no_regret`, and a `single_shot` diagnostic. Whole-DAG native grading. Blocking `capability_acceptance`. |
| `tests/test_de_phase14.py` | Standard-library `unittest` tests (section 9). |
| `docs/NEXUS_PHASE14_MULTI_ENGINE_DAG_REPORT.md` | This file. |

Phase 1–13 code, artifacts and checkers are **not modified**. Phase 14 imports these read-only:
- `nexus.de_phase11.core11`;
- `nexus.de_phase12.synth12`;
- `nexus.de_phase13.proposals13`, `selector13` and `pipeline_lifter13`.

### 0.1 Earlier rounds (already in place)

- **Executable operators.** `OperatorLibrary` / `operator_stage` (section 2.6), the held-out `D7_revenue_sum` spec and the `trained_no_ops`
  ablation.
- **Rank form.** Every constructed rank uses the five-element `rank_ast`.
- **Error reporting.** Error rows and episodes carry a traceback tail. Stdout ends with an `ERRORS {...}` line.
- **Shared budget.** One strict row budget and one query allowance cover every step of `solve`.
- **Regret ablation.** `trained_no_regret` isolates regret for `self_evolution_delta`.
- **Blocking acceptance.** `capability_acceptance` is enforced by default. `--advisory-acceptance` is for smoke / unit runs only.
- **Authored native fronts.** The defaults are `--fronts sql:sqlite,df:polars`. The compiler round trip is only the diagnostic front
  `compiled_sql:<dialect>`.
- **Shared fidelity gate.** The fail-closed native-source fidelity check runs before **either** repair path.
- **Reference fidelity.** An authored DataFrame reference that cannot be established faithful is never graded.

### 0.2 Round 4: rank tie semantics (DEMONSTRATED in the latest test record)

**Problem.** The compiler emitted `RANK()`, which keeps every tied row, while core11 keeps fewer rows.
- `rank_latest_ties`: SQLite returned 5 rows, core11 returned 3.
- `rank_earliest_null_order`: also disagreed.

**Fix.**
- `core11_rank_semantics()` probes core11's tie rule empirically and keeps the unique consistent candidate of `RANK_MODES`.
- The compiler, the Polars backend, the reverse parser and the DataFrame front all follow the probed rule.
- Every rank is refused when the probe is uncalibrated or ambiguous.

**What did not change.** No test was skipped or weakened. Both tie cases stay in the suite, and core11 is untouched.

**Evidence.** The latest `test_execution` (section 10.1) reports all of these passing:
- `test_rank_ties_conform_on_sqlite`;
- `test_rank_earliest_null_order_conforms`;
- `test_rank_tie_round_trip_agrees`;
- `test_tie_rule_probe_calibrated_unique`;
- `test_suite_structure_and_no_core_errors`;
- `test_live_suite_passes_semantic_check`.

The experiment record contains no `semantic_suite` failure.

### 0.3 Round 4: missing experiment execution (RESOLVED as evidence, NEGATIVE as outcome)

The coordinator did run the experiment for the previous revision. It returned **1**, with `checks.failures = ["capability_acceptance"]`
(section 10.1). The run exists, but acceptance failed.

### 0.4 Response to the round-5 audit (this revision)

**1. Required whole-DAG native verification was deferred to unmetered grading (gemini MEDIUM). STATUS: fixed in code, UNMEASURED.**

**What the reviewer found.** `solve` passed `engines=cfg['invariant_engines']` but never `cfg['required_engines']`. As a result, the
accepting `verify_downstream` call ran `engine_dag_check` on no engine. Required whole-DAG execution happened only in `grade()`, outside
learner metering.

**Changes:**
- `solve` computes `req = _required(cfg)` and passes it to **both** repair paths:
  - `operator_stage(..., require_engines=req)`;
  - `D.repair_dag(..., require_engines=req)`.
- `dag_repair14.verify_downstream` takes `require_engines`. Its effective set is `DEFAULT_REQUIRED = (sqlite,)` plus the caller's set, and
  is never empty.
  - It runs `engine_dag_check` on every required engine **on the caller's row budget**, one metered full check per compared stage.
  - Each stage reads that engine's own upstream outputs.
  - A required engine that is `unavailable`, `disagree`s, errors or goes `unchecked` (budget refusal) fails `required_engine_dag`.
  - The repair is then **not submitted**: `repair_dag` reports `partial`, and `operator_stage` declines with
    `invariants_failed:...required_engine_dag`.
- Both paths record `required_engines` and `required_engine_dag`. `run_row` copies them into every row.
- `checks.required_engines_gate_repairs = true` is recorded.
- Grading still repeats the whole-DAG check on the hidden batches. That repetition is evaluation, not a substitute for the gate.

**New tests (`TestRequiredEnginesGateRepairs`):**
- a successful repair records `{sqlite: agree}`;
- an unavailable required engine blocks the `repair_dag` path **and** the operator path;
- a mocked required-engine disagreement blocks both paths;
- `engine_dag_check` on a refusing budget returns `unchecked`;
- the operator path records the required-engine agreement.

`TestRowsNeverError` additionally asserts that every submitted row has `agree` on every required engine.

These tests were **not** part of the 86 tests in the latest record. They are unmeasured until the next coordinator run.

**Expected effect.** In an environment where `auto` resolves to `(sqlite,)`, the whole-DAG SQLite check now adds metered full checks to
every accepting row. The previous maximum was 3,589 full checks per row, against `fc_cap = 5000`. Any change in verified counts relative
to section 10.1 is a consequence of this gate, **not** learning.

**2. Capability acceptance failed (codex HIGH, gemini HIGH). STATUS: OPEN — honest negative; not weakened.**

The latest experiment failed acceptance on these items (exact strings in section 10.1).

Environment:
- `multi_engine:no_non_sqlite_required_engine_available`: DuckDB and Polars are not installed.
- `front:df:polars:engine_unavailable:polars`.
- `front:df:polars:no_verified_repair`.

Learning progression:
- `learning_to_learn_gain` is negative in both streams (rep0 −0.0253, rep1 −0.1042). The trained arm spends more `full_checks +
  probe_evals` per verified task than untrained.
- `transfer_efficiency = 0` in both streams. Trained and untrained verify the same held-out rows.
- `unseen_domain_reuse_rate = 0.0` in both streams. The trained arm executed learned operators on 4 verified rows per budget, but none
  of them is a verified held-out row.
- `self_evolution_delta` is 0.0 (rep0) and −0.0714 (rep1, i.e. −1 / 14). In rep1 the regret-trained selector produced one wrong
  submission at B_q = 1 and at B_q = 2. The listwise-only `trained_no_regret` selector did not.
- `enterprise_reliability_advantage = 0.0` in rep1. The rep0 value is not in the captured tail and is presumably positive, because it
  is not listed as failing.

**What this revision does NOT do:**
- it does not relax `capability_acceptance`;
- it does not change the progression definitions;
- it does not waive the DataFrame front;
- it does not simulate an engine.

**Expected outcome of the next run in the same environment:** exit 1 with `capability_acceptance` failing **by design**. Multi-engine
execution and learning gains remain **not demonstrated** there.

**What would be needed to pass** (section 13):
- install DuckDB and Polars in the coordinator environment;
- diagnose the rep1 trained wrong row (rows.jsonl: `arm=trained`, `stream=rep1`, `wrong=true`);
- explain why operators fire only on source specs;
- make the learned guide / selector reduce work rather than increase it.

The last item is an open research problem, not a bookkeeping fix.

## 1. Question

**Question 1: DAG repair.** Can the machinery localise and repair the faulty node(s) of a layered `stg_ -> int_ -> fct_` DAG lifted from
engineer-authored SQL and DataFrame source? The conditions are:
- every `stg_` node is 50+ columns wide;
- the faulty node may be unobserved;
- there may be two faulty nodes;
- the repair may be unreachable by a single edit;
- only faulty nodes may change, and downstream invariants must hold, **including whole-DAG native execution on every required engine
  before submission**.

All arms are matched under identical query budgets and one strict row budget, with 0 overruns.

**Question 2: transfer.** Do executable operators learned from source repairs transfer to held-out DAGs and beat matched controls,
`trained_no_ops` and `trained_no_regret`?

**Question 3: semantics across engines.** Does a compiled repair mean the same on every available engine?
- NULL 3-valued logic;
- window ranking, including ties and NULL ordering;
- group folds;
- anti-join upserts.

## 2. Mechanisms (engineering machinery, not NEXUS learning)

### 2.1 Multi-engine compiler (`multi_engine14`)

| Concern | SQLite | DuckDB | Spark SQL |
|---|---|---|---|
| Identifier quoting | double quotes | double quotes | backticks |
| Types (INT / NUM / STR / BOOL) | INTEGER / REAL / TEXT / INTEGER | BIGINT / DOUBLE / VARCHAR / BOOLEAN | BIGINT / DOUBLE / STRING / BOOLEAN |
| Typed NULL literal | `CAST(NULL AS t)` | `CAST(NULL AS t)` | `CAST(NULL AS t)` |
| Double literal | plain | `CAST(x AS DOUBLE)` | `xD` |
| Division / modulo by zero | native NULL | `NULLIF(b, 0)` | `NULLIF(b, 0)` |
| Semi / anti join | `[NOT] EXISTS` | `[NOT] EXISTS` | `LEFT SEMI` / `LEFT ANTI JOIN` |
| Ranking (mode ≠ `rank`) | `ROW_NUMBER()` + probed tie-break | `ROW_NUMBER()` + probed tie-break | `ROW_NUMBER()` + probed tie-break |
| Input-order tie-break (`row_input`) | `rowid` | `rowid` | `monotonically_increasing_id()` |

**Ranking.**
- The ORDER BY carries explicit `NULLS FIRST` / `LAST` from `core11_null_order()`.
- The tie rule comes from `core11_rank_semantics()`.
- Without a calibrated, unique rule, every rank is `EngineUnsupported`.

**Reverse parsing.** `from_sql` accepts:
- the compiler's windows, only when they equal the probed semantics;
- `[NOT] EXISTS` and `LEFT SEMI` / `ANTI` joins;
- `NULLIF(x, 0)` divisors;
- `CAST(literal)`;
- keyless aggregates and `AVG`.

`round_trip` agrees only when both ASTs produce the same bag under core11.

**DataFrame front ends.** `from_dataframe` parses Polars / PySpark method chains with Python `ast` and never executes them. Engine
semantics are written into the AST:
- Polars SUM of an all-NULL group is 0;
- Polars rank drops NULL order values;
- Polars inner / left joins drop the right keys.

**Conformance (fail-closed).** One full check is charged before each comparison. Integers compare exactly. Unavailable and unsupported
engines never count as agreeing.

### 2.2 Native sources (`lift_sources`, `source_fidelity`, `compile_dag`)

Each stage is `dict(name, sql, dialect)`, `dict(name, code, api)` or `dict(name, ast)`. It is lifted to core11 and keeps its source text,
engine and front.

`source_fidelity` runs each original source on its own engine and compares it with core11 on the lifted AST:
- `disagree` or `core_error` means **unfaithful**;
- `unavailable`, `native_error`, `unsupported` or `unchecked` means **unverified**.

The same function gates both the broken pipeline (`solve`, on the row budget) and the reference pipeline (`make_instance`, as
evaluation).

### 2.3 DAG localisation (`localize_dag`)

The steps run in order:
1. Observed-upstream localisation (Phase 13).
2. Per-column marginal diff.
3. Lineage.
4. Single-node counterfactual explanation over the broken node and its span.
5. Program-aware probes and budgeted queries over the competing explanations. A lone survivor is challenged. The final test uses the
   common `resolution_menu`.

Outcomes: `localized`, `ambiguous` (abstain), `span` (not node-isolated), `budget`, `no_fault`.

### 2.4 Node-only repair and downstream invariants

**Repair modes:**
- **Narrowed lift**, spliced back and re-verified on core11 and native SQLite.
- **Full-node lift** (`span = []`).
- **Unobserved node:** repaired by its surviving explaining edit, verified through its observed descendant.

**Invariants.** `verify_downstream.ok` requires all of the following:
- untouched nodes keep identical ASTs;
- schema contracts hold;
- no node errors;
- end-to-end match;
- native SQLite pipeline agreement;
- conformance of every changed node;
- **`engine_dag_check` agreement on every required engine** (`required_engine_dag`), metered on the caller's budget;
- no optional DAG engine disagrees, errors or goes unchecked (`engine_dag`).

### 2.5 Metering (`solve`)

One strict `synth12.Budget` and one query allowance per row, used in this order:
1. The fail-closed fidelity gate.
2. The operator stage, only when the gate passes: a fork limited to `OP_SHARE = 0.4` of the remaining headroom, merged back. It is
   accepted only after `verify_downstream` **with the required engines** and a clean re-localisation.
3. `repair_dag`, on the **same** budget and query list, **with the same required engines**.

`over_cap` is computed on the row budget's total work.

### 2.6 Learned executable operators (`OperatorLibrary`, `operator_stage`)

**Extraction.** `extract_operator` anti-unifies a (broken node, repaired node) pair into a rewrite with wildcards `?tK`, `?cK` and `?oK`.
Design example (D6): `(?o0, count_star, None) -> (?o0, sum, col(?c0))`.

**Admission.** An operator is admitted when `pos − neg >= OP_ADMIT = 1` over graded source repairs. The library is frozen and
fingerprinted after training.

**Execution.**
1. Match at every site, with each candidate charged before it is built.
2. Require a fit on every observed batch.
3. Try depth-2 composition on a different node.
4. Split the survivors with probes and queries, and challenge a lone survivor.
5. Accept only on `verify_downstream.ok` (required engines included) and a clean re-localisation.

## 3. Controls (Charter rule 3)

Every `(task, stream, B_q)` runs each arm with identical settings:
- the same native-lifted pipeline;
- the same fidelity gate;
- the same B_q, `fc_cap` and row wall;
- the same invariant and required engines;
- the same abstention rule and common resolution menu.

| Arm | Query menu | Choice rule | Leader order / costs | Operators |
|---|---|---|---|---|
| `fixed` | `generic_proposals` (static) | first splitting proposal | default / uniform | none |
| `random` | `generic_proposals` | seeded draw, seed = sha256(stream, task, B_q) | default / uniform | none |
| `untrained` | `program_aware_proposals` | argmax, uniform weights | default / uniform | none |
| `trained` | `program_aware_proposals` | frozen source-trained `Selector` | frozen tag prior / frozen guide | frozen admitted operators |
| `trained_no_ops` (ablation) | program-aware | frozen `Selector` | frozen prior / guide | none |
| `trained_no_regret` (ablation) | program-aware | frozen listwise-only `Selector` | its own prior / the **same** frozen guide | the **same** frozen operators |
| `single_shot` (diagnostic, B_q = 0) | none | — | `require_unique = False`, `holdout = False` | none |

`single_shot` is a heuristic, **not an LLM baseline**. No LLM baseline exists in this phase.

## 4. Work caps and metering

**Row caps:**
- `full_checks <= fc_cap` (default 5000; the runner rejects > 5000);
- `rel_evals <= 4000`;
- `micro_evals <= 400000`;
- `constructed_asts <= 400000`;
- queries `<= B_q`.

`checks.over_cap_rows` must be 0.

**Charged to the row** (learner work):
- the fidelity gate;
- localisation, explanation, probes and lifts;
- the accepting `verify_downstream`, including the required-engine whole-DAG check.

**Not charged:** hidden-batch grading and reference fidelity, which are evaluation.

**Privileged source supervision (`SOURCE_CAPS`)**, charged before use:

| Unit | Per episode | Per stream |
|---|---|---|
| `ref_answers` | 512 | 6000 |
| `grade_execs` | 16 | 400 |

**Time shares.** Source training uses up to 30 % of the grant. Evaluation runs until 92 %. Rows not started are listed in `missing` and
never imputed.

## 5. DAG specs, fronts, seeds, isolation

| Spec | Fault (broken → reference) | Faulty node observed? | Split | `n_edits` / `edit_reachable` | Beyond single edit |
|---|---|---|---|---|---|
| `D1_count_col` | `int_counts`: COUNT(*) → COUNT(v) | no | source | 1 / yes | no |
| `D2_left_lookup` | `int_enriched`: INNER → LEFT JOIN | no | **held out** | 1 / yes | no |
| `D3_null_default` | `stg_readings`: `y = x` → `COALESCE(x, 0)` | yes | source | 1 / yes | no |
| `D4_filter_boundary` | `int_large`: `>` → `>=` 100 | no | **held out** | 1 / yes | no |
| `D5_lookup_two_faults` | INNER → LEFT **and** `fct_tier` passthrough → `COALESCE(tier, 'none')` | yes (both) | **held out** | 2 / yes | **yes** |
| `D6_sum_measure` | `fct_totals`: `COUNT(*) AS total` → `SUM(amt)` | yes | source | 1 / **no** | **yes** |
| `D7_revenue_sum` | `fct_region`: `COUNT(*) AS revenue_total` → `SUM(revenue)` (renamed schema) | yes | **held out** | 1 / **no** | **yes** |

- **Fronts.** `sql:<sqlite|duckdb|spark>`, `df:<polars|pyspark>`, the diagnostic `compiled_sql:<dialect>`, and `ast`. Defaults:
  `--fronts sql:sqlite,df:polars` and `--train-front sql:sqlite`.
- **Batches.** 3 observed and 2 hidden per instance. The reference is reachable only through the budgeted `pipeline_oracle`.
- **Seeds.** Source: `1410000 + 10000*stream + 100*spec + i` (D1, D3 and D6 only). Evaluation: `142000 + 100*spec + i`. Any overlap is
  refused.
- **Isolation.** Each stream freezes its selector, guide, operator library and no-regret selector, and checks sha256 fingerprints
  before and after evaluation.

## 6. Grading, verdict and acceptance

**Grading:**
- **ungraded:** submitted, but the reference is not gradable. Never verified, never wrong.
- **verified:** all of the following hold:
  - submitted;
  - the reference is gradable;
  - core11 reproduces every reference stage on every hidden batch;
  - the native SQLite pipeline agrees;
  - every required engine executes the whole DAG natively and agrees.
- **wrong:** submitted, graded and not verified.
- **abstained:** not submitted. This includes rows blocked by the fidelity gate or by required-engine verification.
- **multi_engine_verified** (reported): verified, and at least one non-SQLite engine agrees.

**Verdict.** Primary B_q = max(budgets), matched tasks only:
- **positive:** Trained − X ≥ +2 for every X ∈ {fixed, random, untrained} in every stream, **and** Trained's wrong count ≤ every
  comparator's;
- **negative:** Trained − X ≤ −2 for some X in every stream;
- **mixed:** otherwise;
- **insufficient:** a stream has no matched tasks.

### 6.1 Progression metrics (per stream, primary B_q; `None` when undefined)

| Metric | Definition as implemented |
|---|---|
| `learning_to_learn_gain` | Relative reduction of (full_checks + probe_evals) per verified task, trained vs untrained. |
| `transfer_efficiency` | Trained − untrained verified on held-out specs. |
| `self_evolution_delta` | (verified − wrong) / rows, trained minus `trained_no_regret`. |
| `self_evolution_combined` | The same score, trained minus untrained. |
| `operator_delta` | The same score, trained minus `trained_no_ops`. |
| `unseen_domain_reuse_rate` | Share of trained verified held-out rows whose accepted repair **executed** a learned operator. |
| `enterprise_reliability_advantage` | The same score, trained minus `single_shot`, on matched tasks. |

### 6.2 Capability acceptance (BLOCKING by default)

`accepted` requires all of the following:
1. every progression metric is > 0 in every stream;
2. at least one non-SQLite required engine;
3. an authored `sql` front;
4. a `df` front;
5. every native front's engine is installed;
6. every native front has at least one verified row.

## 7. Attribution (Charter rule 4)

**Learned by NEXUS during source training** (`learned_by_nexus[stream]`):
- selector weights and no-regret weights;
- tag prior and `demoted_shortcuts`;
- guide table;
- operator counts and `admitted_operators`;
- the learning log, supervision use and episode outcomes.

**Engineering machinery** (never NEXUS learning):
- all of `multi_engine14`, `dag_repair14` and `runner14`, including:
  - the rank tie probes;
  - the required-engine gate;
  - the authored SQL / DataFrame text;
  - the parsers and compilers;
  - the anti-unification rule;
  - `OP_ADMIT`;
  - the specs and `edit_reachable` claims;
- plus Phase 11–13 modules.

Human, Claude, Codex and Gemini edits are external engineering.

## 8. How to run (2400 s owner grant)

```bash
python3 -m unittest -v tests/test_de_phase14.py
python3 -m nexus.de_phase14.multi_engine14                                  # conformance suite (prints rank_semantics)
python3 src/nexus/de_phase14/runner14.py --grant-seconds 120 --quick --execute --advisory-acceptance --out artifacts/agi14_smoke
python3 src/nexus/de_phase14/runner14.py --grant-seconds 2400 --execute   # coordinator invocation; acceptance enforced
```

**Exit codes:**
- **0:** ok.
- **1:** any entry in `checks.failures`: `over_cap_rows`, `isolation`, `source_supervision`, `error_rows`, `source_error_episodes`,
  `build_errors`, `required_engine_unavailable`, `semantic_suite`, `capability_acceptance`.
- **2:** no rows.

## 9. Unit tests (`tests/test_de_phase14.py`, standard-library `unittest`)

| Class | What the tests check |
|---|---|
| `TestPackage`, `TestValues` | Availability, layers, `make_rel`, `norm`, exact large integers, `bag_equal`. |
| `TestRankSemantics` | Five-element `rank_ast`; NULL-order and tie-rule probes calibrated (unique candidate); compiler follows the probed rule; uncalibrated rule refused; reverse parser rejects a tie-keeping window; **strict** tie and NULL-order conformance on SQLite; tie round trips in every dialect. Polars / DuckDB variants run only when installed. |
| `TestSqlGeneration`, `TestReverse` | Dialect quoting and literals; anti joins; `compile_all`; round trips; the four-element rank never agrees; `ORDER BY` rejected. |
| `TestDataFrameFrontEnd`, `TestDataFrameFront` | Polars / PySpark lifting of every spec; rejections; fidelity never agrees without the engine. |
| `TestConformance` | Fail-closed conformance; UPSERT; suite with tie cases kept, `failing_cases == []`, `required_ok`. |
| `TestDagView`, `TestColumns`, `TestLocalizeAndRepair` | Topology, lineage, narrow / splice, localisation, node-only repair; `verify_downstream` fails `required_engine_dag` for an unavailable required engine. |
| `TestNativeSqlFront`, `TestReferenceFidelity` | Authored-source lifting per spec; fail-closed dialect fidelity; ungradable references never graded; an unfaithful reference is a build error. |
| `TestOperators`, `TestFidelityGate`, `TestSharedBudget` | Anti-unification, admission and isolation; D6 → D7 transfer; the fidelity gate in front of both paths; no overruns. |
| `TestRequiredEnginesGateRepairs` (**new, unmeasured**) | Required-engine whole-DAG verification gates **both** repair paths on the shared row budget: agreement recorded; an unavailable or disagreeing required engine blocks both paths; a refusing budget yields `unchecked`. |
| `TestRunnerParts` | Seeds, fronts, specs, grading, meter, arm kwargs, contrasts / verdict, progression, blocking acceptance, fail-closed `semantic_check`, the strict live suite, config. |
| `TestRowsNeverError` | No error rows; fidelity-blocked rows never submitted; ungradable references never graded; every submitted row agreed on every required engine; no error episodes. |
| `TestRunnerEndToEnd` | Error rows exit 1; acceptance enforced by default; a tiny advisory run is clean and records `required_engines_gate_repairs`. |

**Declared test gaps:**
1. No test of `ambiguous` localisation, the `span` fallback, a failed splice, or incomplete scoring in `investigate_variants`.
2. No D5 / D6 repair through `repair_dag`, and no depth-2 operator composition test.
3. No exit-1 test for `required_engine_unavailable`. PySpark is not executed in the default environment.
4. No regression test locating the rep1 trained wrong row (section 10.1).

## 10. Results

### 10.1 Previous revision (quoted from the coordinator records; predates the section 0.4 item 1 change)

**Tests.**
- Command: `python3.13 -m unittest -v tests/test_de_phase14.py`.
- Result: returncode **0**, wall 2.898 s, `Ran 86 tests in 2.769s`, `OK (skipped=3)`.
- Skips: `test_polars_front_row_executes`, `test_rank_ties_conform_on_duckdb`, `test_rank_ties_conform_on_polars` (Polars and DuckDB
  not installed).
- Every rank tie / NULL-order test passed.

**Experiment.**
- Command: `python3.13 src/nexus/de_phase14/runner14.py --grant-seconds 2400.0 --execute`.
- Result: returncode **1**, coordinator wall 24.998 s; runner wall total 24.93 s, source 1.61 s.
- Exact `ERRORS` line fields:
  - `failures: ["capability_acceptance"]`;
  - `error_rows: 0`, `source_error_episodes: 0`, `build_errors: []`;
  - `capability_failed`:
    - `rep0:learning_to_learn_gain=-0.0253`
    - `rep0:transfer_efficiency=0`
    - `rep0:self_evolution_delta=0.0`
    - `rep0:unseen_domain_reuse_rate=0.0`
    - `rep1:learning_to_learn_gain=-0.1042`
    - `rep1:transfer_efficiency=0`
    - `rep1:self_evolution_delta=-0.0714`
    - `rep1:unseen_domain_reuse_rate=0.0`
    - `rep1:enterprise_reliability_advantage=0.0`
    - `multi_engine:no_non_sqlite_required_engine_available`
    - `front:df:polars:engine_unavailable:polars`
    - `front:df:polars:no_verified_repair`
- **Verdict** (primary B_q = 2): `all`, `dag`, `beyond_single_edit`, `held_out`, `front:sql:sqlite` and `front:df:polars` are all
  **mixed**.
- **Supervision:** rep0 and rep1 each used `grade_execs 18`, `ref_answers 34`.

**Summaries.** Verified / wrong / abstained of 14 rows, from the captured stdout tail:

| Arm | rep0 B1 | rep0 B2 | rep1 B1 | rep1 B2 |
|---|---|---|---|---|
| fixed | not in captured tail | 14 / 0 / 0 | 13 / 0 / 1 | 14 / 0 / 0 |
| random | not in captured tail | 14 / 0 / 0 | 13 / 0 / 1 | 14 / 0 / 0 |
| untrained | 13 / 0 / 1 | 14 / 0 / 0 | 13 / 0 / 1 | 14 / 0 / 0 |
| trained | 13 / 0 / 1 | 14 / 0 / 0 | **12 / 1 / 1** | **13 / 1 / 0** |
| trained_no_ops | 13 / 0 / 1 | 14 / 0 / 0 | **12 / 1 / 1** | **13 / 1 / 0** |
| trained_no_regret | 13 / 0 / 1 | 14 / 0 / 0 | 13 / 0 / 1 | 14 / 0 / 0 |
| single_shot (B_q = 0) | not in captured tail | — | 12 / 0 / 2 | — |

**Further facts from the same summaries:**
- `over_cap = 0` and `errors = 0` in every summary shown.
- Maximum full checks per row: 3,589. `fidelity_blocked = 0` and `reference_ungradable = 0` in every summary shown.
- `multi_engine_verified = 0` everywhere: no non-SQLite engine ran.
- Trained and `trained_no_regret` had `operator_verified = 4` per budget. Every other arm had 0.
  - `localized_correct` was 10 / 14 for both operator-carrying arms, against 14 / 14 for the others. The operator path bypasses
    `localize_dag`, so this is bookkeeping, not mislocalisation.
- Work at B_q = 2, full_checks / probe_evals summed over 14 rows:
  - trained: 15,492 / 1,779;
  - untrained: 15,352 / 1,483.
  - So the trained arm did **more** work. This is the source of the negative `learning_to_learn_gain`.

**Honest reading:**
- **Shown (SQLite only, 7 synthetic specs × 2 instances):**
  - Every arm repairs nearly every DAG at B_q = 2.
  - That includes the two-fault D5 and the synthesis-only D6 / D7, with node-isolated repairs and zero overruns.
- **Not shown:**
  - Any advantage of training. Trained ≤ untrained in every cell.
  - Transfer.
  - Held-out reuse of learned operators.
  - Regret benefit. In rep1 the regret-trained selector is worse than the listwise-only one by one wrong submission.
  - Any non-SQLite or DataFrame execution.
- **Ceiling effect.** Fixed and Random already verify 14 / 14 at B_q = 2. These specs cannot show a ±2 learned-selector gain. Harder,
  independently authored specs are required.
- **Rep1 wrong row.** It appears in `trained` and `trained_no_ops` but not in `trained_no_regret`. It therefore comes from the
  regret-trained selector's choices, not from executed operators. Which spec it is cannot be read from the captured tail; it must be read
  from `rows.jsonl`.

### 10.2 Current revision

**NOT YET AVAILABLE.** Copy these items verbatim from the coordinator records and `artifacts/agi14_eval/results.json`, reporting any
failed check first:
- **Tests:** returncode, test count, failures and skips. The new `TestRequiredEnginesGateRepairs` tests must appear and pass.
- **Experiment:** returncode, `exit_code`, `checks.failures`, and the `ERRORS` line.
- **`checks`:** `required_engines`, `required_engines_unavailable`, `required_engines_gate_repairs`, `max_full_checks` against `fc_cap`,
  `over_cap_rows`, `error_rows` and `capability_accepted`.
- **Per row:** the `required_engine_dag` distribution, and any rows blocked by `required_engine_dag`.
- **Verdicts, contrasts, ablations, summaries, `progression`, `capability_acceptance` and `learned_by_nexus`.**

**Changes against 10.1** caused by the required-engine gate (extra metered full checks, possible budget abstentions) must be attributed
to the gate, not to learning.

## 11. Known limitations and confounds (declared)

1. **Capability not demonstrated.** No non-SQLite engine and no DataFrame engine have executed in any coordinator run. Acceptance
   correctly fails.
2. **Ceiling.** Controls reach 14 / 14 at B_q = 2, so the specs cannot separate the arms.
3. **Learning regresses.** The trained arm spends more work per verified task. Regret training introduced one wrong submission in rep1.
   Operators transfer only on source-family shapes in evaluation (`unseen_domain_reuse_rate = 0`), although the D6 → D7 unit test
   shows the mechanism can transfer.
4. **Rank tie rule is probed, not proven.** Six probes select one rule from `RANK_MODES`.
5. **`row_input` portability.** `rowid` and `monotonically_increasing_id()` follow insertion order only for local base tables.
6. **Authored sources are synthetic.** They are written by the engineering team for seven small specs.
7. **Menu confound.** Fixed and Random query from the static menu. Abstention uses the common menu in every arm.
8. **Small sample.** 14 evaluation tasks per front per stream in the latest run, and 3 source specs × few instances.
9. **Machine dependence.** Wall caps make counters machine-dependent.

## 12. Reviewer checklist

- [ ] `test_execution` and `experiment_execution` are present **for this revision**, with returncode 0 and `checks.failures == []`.
  Expected to fail on `capability_acceptance` in an environment without DuckDB / Polars.
- [ ] `TestRequiredEnginesGateRepairs` passes; every submitted row has `agree` on every required engine.
- [ ] `over_cap_rows == 0`, `error_rows == 0`, `isolation_ok`, empty seed overlap, `required_engines_unavailable == []`.
- [ ] `capability_acceptance.enforced == true`; `accepted` is read directly and not relaxed.
- [ ] All arms plus both ablations are present per (task, stream, B_q); `missing` rows are listed.

## 13. Handoff: next steps

1. **Environment.** Install DuckDB and Polars, and optionally PySpark with a JVM, in the coordinator environment. Then `auto` required
   engines include a non-SQLite engine and the `df:polars` front can establish fidelity. This is an owner / infrastructure action, not a
   code change.
2. **Rep1 wrong row.** Extract it from `rows.jsonl` and identify the selector-chosen query that let a falsifiable leader through.
   Inspect `learned_by_nexus.rep1.top_weights` and `tag_prior` against the no-regret weights.
3. **Work regression.** Compare per-row work of trained vs untrained. The operator stage's 40 % fork and the guide costs are the likely
   sources. Report this; do not tune it on evaluation tasks.
4. **Specs.** Add harder, independently authored held-out specs (synthesis-only, multi-join, schema drift) that remove the 14 / 14
   ceiling, so that a learned gain can be measured at all.
5. Fill section 10.2 from coordinator records only, and close the test gaps in section 9.
