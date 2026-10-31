# NEXUS Phase 13 — program-aware investigation, trained Delta-State selector, counterfactual regret, SQL localize-and-lift (NOT LOCKED)

Status: **protocol and handoff; revision answering the second review round.**

Results may be copied only from these sources:
- `artifacts/agi13_eval/results.json`, `rows.jsonl`, `baselines.jsonl` and `ablations.jsonl`;
- the coordinator's `test_execution` and `experiment_execution` records.

Section 10.1 reproduces the **previous** live execution evidence. That evidence was produced by code *before* the fixes in
section 0.2, so it is **not** a result of the current revision.

Current-revision numbers must be taken from the coordinator's new `experiment_execution`. If that record is missing, or its
returncode is not 0, the current revision has **no result**.

## 0. Scope and files

| File | Role |
|---|---|
| `src/nexus/de_phase13/__init__.py` | Package marker. Defines `PHASE = 13` and `WORK_CAPS` (full_checks 5000, rel_evals 4000, micro_evals 400000, constructed_asts 400000). |
| `src/nexus/de_phase13/proposals13.py` | Program-aware input proposals built from candidate ASTs; Shadow-Edge Version Space; scoring with completeness metadata (`ScoredList`). |
| `src/nexus/de_phase13/selector13.py` | Trainable task-conditioned Delta-State selector, counterfactual regret audit, shortcut-tag prior and Delta-State search guide. |
| `src/nexus/de_phase13/pipeline_lifter13.py` | SQL subset front end with qualified-identity resolution, fail-closed parse fidelity, localisation, Sub-AST Localize-and-Lift, compile back to SQL, native SQLite gate. |
| `src/nexus/de_phase13/runner13.py` | Bounded experiment runner: Fixed / Random / Untrained / Trained; regret ablation; single-shot baseline; streams rep0 / rep1; `--grant-seconds`. |
| `tests/test_de_phase13.py` | Unit tests (section 9). |
| `docs/NEXUS_PHASE13_PROTOCOL_AND_HANDOFF.md` | This file. |

Phase 1–12 artifacts, checkers and synthesizers are **not modified**. Phase 13 imports two modules read-only:
`nexus.de_phase11.core11` (semantics) and `nexus.de_phase12.synth12` (strict budget and synthesizer).

### 0.1 Changes answering the first review round (already in place)

| Review finding | Change |
|---|---|
| SQL parser dropped column qualifiers | `_Parser.resolve` checks every column reference against its FROM scope. Ambiguous, unresolvable, renamed or duplicated references are rejected (`SqlParseError` / `SqlUnsupported`). ON keys must compare one column of each side. |
| Unfaithful parses could be lifted | `sql_fidelity` executes each stage's original SQL on SQLite against core11 on the parsed AST, and is **fail-closed**. `repair_pipeline` stops on `unfaithful_parse` (provable disagreement / core error) or `fidelity_unverified` (native error, load error, budget-refused comparison). |
| Incomplete scoring could count as resolution | `score_proposals` returns a `ScoredList` (`.complete`, `.reason`, `.requested`, `.dropped`). An incomplete final scoring abstains with reason `incomplete_scoring`. |
| Unbounded source supervision | `runner13.SourceMeter` with pre-registered `SOURCE_CAPS`, charged before execution (section 4.2). |
| `self_evolution_delta` did not isolate regret | Matched ablation arm `trained_no_regret` (section 3). |

### 0.2 Changes answering the second review round (this revision)

| Review finding (codex MEDIUM, gemini MEDIUM) | Change |
|---|---|
| Pipeline submission safety depended on the arm's query menu: the static-menu Fixed / Random arms could accept alternatives that program-aware probes separate. | `_attempt` now runs its final resolution test on **one common menu for every arm**: `pipeline_lifter13.resolution_menu(vs)` = `program_aware_proposals` ∪ `generic_proposals`. This is identical to `runner13.investigate`'s submission check. The injected `menu` is used **only to choose queries**. Results record `query_menu` (`injected` / `program_aware`) and `resolution_menu = "program_aware+static"`. |
| The native gate omitted answered investigation queries. | The native gate now executes the compiled SQL on every observation the core11 repair was verified on (`_native_obs`): every fit batch, the held-out batch **and every answered query**. Each is one metered full check, and one disagreement rejects the member. Results record `native_checked` and `native_query_checks`; rejected members record `failed_on_query`. |
| The protocol misdescribed the pipeline controls and listed only P1–P3. | Section 3 now describes the static query menus of the pipeline Fixed / Random arms. Section 5 lists P1–P5 with `edit_reachable` and repair-method attribution. Section 13 no longer requests work that is already done. |

**Not yet added:** dedicated regression tests for these two invariants (section 9). Their effect on results is unmeasured until the
new coordinator run.

## 1. Question

The Phase 12 verdict was mixed, and NEXUS was less safe than Fixed B_q = 2. The diagnosed cause was **candidate-set completeness**:
- 11 of 18 wrong NEXUS submissions had a single candidate (usually the passthrough or COUNT(*) shape);
- the frozen rule then spent no query.

Phase 13 asks:

> With program-aware proposals built from candidate ASTs, shadow alternatives that keep the version space open (no passthrough or
> COUNT(*) lock), and a query rule that challenges even a lone candidate: does a selector trained on source experience beat Fixed,
> Random and Untrained controls? The comparison uses identical query budgets and strict inner-loop work caps, on fresh tasks and on
> out-of-sandbox SQL pipelines.

## 2. Mechanisms (engineering machinery)

### 2.1 Program-aware proposals (`proposals13`)

`program_facts` reads these facts from every live member's expanded AST:
- read columns;
- `isnull` checks;
- column/constant comparisons (bounds);
- joins (kind, keys, base relations per side);
- complete group-key tuples;
- rank partitions and orders;
- passthrough columns;
- whether COUNT(*) is used.

`program_aware_proposals` edits a visible batch exactly where the programs are sensitive:

| Kind | Construction |
|---|---|
| `boundary` | The comparison constant, ±1 (INT), ±0.5 (NUM), or a fresh non-matching string, in the first row. |
| `null` | A NULL in every touched column, in place and as an appended copy row. |
| `unmatched` | An appended row on each join side with a fresh key, and one with a NULL key. |
| `dupkey` | Multi-row duplicate keys: join keys; complete group-key tuples (altered measures and exact copy); partition keys. |
| `tie` | An ordering tie: a copy keeping both partition and order columns. |

Other rules:
- Proposals are deduplicated against the base batches and against each other, round-robin across bases, and capped at
  `PROP_CAP = 64`.
- `generic_proposals` is the AST-blind static menu: duplicate the first row; NULL / zero in the first row's columns.

### 2.2 Shadow-Edge Version Space (`proposals13.VersionSpace`)

Each synthesized candidate contributes single-edit **shadow** neighbours along these edges:
- passthrough ↔ `coalesce(col, k)`;
- `COUNT(*)` ↔ `COUNT(col)`, where col ranges over every column of the fold's base, group keys included;
- join-kind swaps;
- strict ↔ loose comparisons;
- rank direction flips.

Rules:
- **Admission:** a member is `alive` only after one metered full check shows it reproduces every observation.
- **Falsification:** only an executed observation can falsify a member.
- **No permanent lock:** a passthrough or COUNT(*) fit never suppresses its alternatives.
- **Unchecked members:** a member the budget refused to check is `unchecked`, and is never treated as consistent.
- **Shadow cap:** `SHADOW_CAP = 48`.

### 2.3 Scoring, features, completeness

`score_proposals` executes every live member on every proposal. Each execution is one metered `probe_evals` unit, with
`PROBE_CAP = 4000` per call. It records the output partition and the `FEATURE_NAMES` vector:
- proposal kind;
- partition statistics;
- Delta-State deltas (rows / NULLs / cells changed, normalised);
- task flags read from the live ASTs;
- kind × task-flag crosses.

Proposals not evaluated before a cap are **dropped, never guessed**. `ScoredList.complete = False` records the reason. Incomplete
final scoring is treated as unresolved and leads to abstention.

### 2.4 Selector, regret, guide (`selector13`)

- **Selector.** Linear `w · features`, argmax, ties broken by menu order. Uniform weights are the **Untrained** control.
- **Counterfactual utilities (source training only).** Utility = the fraction of evaluated members a proposal would falsify given the
  reference answer on its input, plus `LEADER_BONUS = 0.5` if it would falsify the leader.
- **Regret audit.** `regret = max utility − chosen utility`. When regret > 0: `w += regret_lr · regret · (f_best − f_chosen)`.
  Every update is logged.
- **Listwise policy gradient.** `w += lr · Σ (q_i − p_i) f_i` with `q = softmax(utilities / 0.25)`, L2 decay and clipping at
  ±`W_CLIP = 8`.
- **Shortcut demotion.** When a would-be leader is falsified on hidden source batches:
  - its shortcut tags are demoted;
  - tags carried only by correct surviving alternatives are promoted;
  - a confirmed leader gets a small promotion.

  The prior is clipped at ±3 and **only orders** `VersionSpace.leader`. It never removes, skips or locks a member.
- **DeltaStateGuide.** A production-cost table (1..`synth12.MAX_COST`) learned from verified (+) and falsified (−) programs.
  `rel` / `col` / `const` are pinned at 1, and empty experience gives uniform costs.
- **Isolation.** `freeze()` makes every learning entry point raise `FrozenSelectorError`. `fingerprint()` is a sha256 of the
  learned state.

### 2.5 Out-of-sandbox pipelines (`pipeline_lifter13`)

**SQL subset.** Anything outside it raises `SqlUnsupported`; it is never approximated.
- `SELECT` items / `*`; `FROM` a table or an aliased subquery;
- `[INNER|LEFT|RIGHT|FULL] JOIN … ON` equi-keys;
- `WHERE`;
- `GROUP BY` with `COUNT(*)` / `COUNT(e)` / `SUM` / `MIN` / `MAX`;
- `COALESCE` / `IFNULL`; `CASE WHEN … ELSE … END`; `CAST`; `JSON_EXTRACT`;
- arithmetic, comparisons, `IS [NOT] NULL`, `AND` / `OR` / `NOT`;
- `UNION ALL`;
- scripts of `CREATE [TEMP] TABLE|VIEW name AS …;`.

**Explicitly rejected:** `DISTINCT`, `ORDER BY`, `LIMIT`, `HAVING`, `OVER`, `WITH`, comma / cross joins, `IN` / `BETWEEN` / `LIKE`,
scalar subqueries, untyped NULL, `NVL`.

**Qualified identity.** Over a join, a column name present in more than one joined relation is **rejected**, because core11 joins
do not keep qualified identity. This is a declared coverage limit.

**Parse fidelity.** Fail-closed (section 0.1). One metered full check is charged per comparison.

**Localize.**
- Each stage runs on its **observed** upstream outputs (preserved ground truth), so each observed stage is `verified` or `broken`.
- The suspect span is the broken stage's unobserved ancestors.
- A localisation cut short by the budget is `complete=False`, never a pass.

**Lift.** Attempts run in order: `stage` → `span` (span inlined) → `widen` (all available upstream relations offered, at most 6).
- Working relational sub-ASTs are preserved as pre-materialised inputs (`nx_keepK`, at most 2).
- Candidates are generated in this order:
  1. generic single structural edits (the shadow edges; no repair templates);
  2. then the synth12 atomic synthesizer, on a fork of 70 % of the remaining budget.
- Synthesized programs are compiled back by inlining the preserved sub-ASTs.
- Every repaired stage records its **method** (`edit` / `synth`), the accepted origin and edge, and provenance.

**Investigate.**
- A version space with budgeted oracle queries, chosen from the arm's **query menu** with the arm's choice rule.
- Synthesis resumes once, with the answered queries as observations, if every member is falsified.

**Epistemic safety (`require_unique`, default on).** The final resolution test always uses the **common menu**
(`resolution_menu`, program-aware ∪ static), whatever the arm's query menu. The lift abstains when either of these holds:
- admissible members disagree on a scored proposal (`unresolved_alternatives`);
- the final scoring was incomplete (`incomplete_scoring`).

It also abstains on budget exhaustion. With at least 3 observed batches, a held-out observed batch must be reproduced before
acceptance. Agreement on bounded probes is recorded as `agreement_unproven`, never as proof.

**Native gate (a requirement).** By default `native=True` and `require_native=native`. A member is accepted only if both hold:
- it compiles to SQL;
- the compiled SQL, executed on SQLite, reproduces the expected output of **every fit batch, the held-out batch and every answered
  query**.

`repair_pipeline` reports `repaired` only when core11 end-to-end checks and `native_pipeline_check` agree on every observed stage.
Otherwise it reports `native_disagree` or `partial`.

In the runner, a pipeline repair counts as `verified` only if both hold on the **hidden** batches:
- core11 reproduces every reference stage;
- the natively executed compiled SQL agrees on every stage.

**Metering.** One strict `Budget` and one query allowance per pipeline row, shared by fidelity, localisation, lifts, end-to-end and
native checks. Each lift runs in a fork capped at 85 % of the remaining wall, and its counters are merged back.

**Not implemented:** DuckDB, Polars and PySpark front ends and back ends. Only core11 and SQLite exist.

## 3. Controls (Charter rule 3)

All arms share these settings exactly:
- version space, shadows and shadow cap;
- B_q;
- resume rule (`MAX_RESUME = 2` in the ambiguous suite; one resume per lift attempt in pipelines);
- abstention rule, including the common resolution menu;
- one strict synth12 `Budget` per row.

| Arm | Query menu (both suites) | Choice rule | Leader order | Collection / lift costs |
|---|---|---|---|---|
| `fixed` | `generic_proposals` (AST-blind static) | first in menu order | default | uniform |
| `random` | `generic_proposals` | seeded draw, seed = sha256(stream, task, B_q) | default | uniform |
| `untrained` | `program_aware_proposals` | argmax, uniform weights | default | uniform |
| `trained` | `program_aware_proposals` | frozen source-trained `Selector` | frozen tag prior | frozen guide table (own collection per task × stream) |
| `trained_no_regret` (ablation, ambiguous suite only, not in verdict) | `program_aware_proposals` | frozen selector trained with listwise steps only | its own (empty) tag prior | the **same** frozen guide and collection as `trained` |
| `single_shot` (diagnostic baseline) | none | first candidate of the shared collection | — | uniform |

In the pipeline suite, the Fixed / Random static menu is injected through `lift_stage(menu=_static_menu)`.

**Query rule.** Up to B_q reference queries per row, spent even when only one synthesized candidate remains, provided a proposal
splits the live members.

**Submission rule (both suites, every arm).** The arm submits the leader **unless** one of these holds, in which case it
**ABSTAINS**:
- (a) live members disagree on a scored proposal from the **common** program-aware ∪ static menu;
- (b) that final scoring was incomplete;
- (c) the row budget is out or exhausted, including when only one member is live.

Pipelines additionally require held-out reproduction and the native gate (section 2.5).

**No LLM baseline** exists in this phase.

## 4. Work caps and metering

### 4.1 Row budgets (0 overruns required)

**Per-row limits.** One `synth12.Budget` per row:
- full checks ≤ `fc_cap` (default 5000; the runner rejects > 5000);
- rel_evals ≤ 4000;
- micro_evals ≤ 400000;
- constructed_asts ≤ 400000.

`CappedCounter` raises at the exact increment that would pass a cap.

**What is charged to the row:**
- **Collection.** Runs in a fork limited to 70 % of the remaining headroom of every counter and of the wall, and is charged **in
  full** to every arm's row.
- **Investigation.** Every consistency, falsification, held-out and native check, and every probe evaluation, is charged to the same
  budget.
- **Not charged:** hidden-batch grading is evaluation, not learner work.

**Overruns.** Recorded as `over_cap` per row, including `queries` when more than B_q were spent. `checks.over_cap_rows` covers
control, pipeline, baseline and ablation rows, and must be 0. The runner exits 1 otherwise.

### 4.2 Privileged source supervision (`SOURCE_CAPS`, separate from row budgets)

| Unit | Per episode | Per stream |
|---|---|---|
| `ref_answers` (reference answer per scored proposal, for counterfactual utilities) | 512 | 6000 |
| `grade_execs` (hidden source batch executions, for leader / alternative grading) | 48 | 1200 |

Rules:
- Units are charged **before** they run.
- A refusal skips the learning step (`skipped_learning_steps`) or the grading (`grading = "refused"`, `alternatives_ungraded`).
- Any overrun makes the runner exit 1.

**Wall clock.** Caps (`collect_wall`, `investigate_wall`, `lift_wall`) are safety caps, so exact counts are machine-dependent. The
environment is recorded.

## 5. Task families, pipeline cases, seeds, isolation

| Family | Source? | Reference shape | Shortcut it exposes |
|---|---|---|---|
| `null_default` | yes | `map(t, y = coalesce(x, 0))` | passthrough |
| `count_col` | yes | `fold(e, g, count(v))` | COUNT(*) |
| `dup_sum` | yes | `fold(p, k, sum(amt))` (visible duplicates add 0) | passthrough / max / min |
| `left_lookup` | **no** (held out) | left join orders → custs | inner join |
| `rank_latest` | **no** (held out) | `rank(u, uid, ts desc) = 1` | direction flip / other measures |

**Batches.** Visible batches use `vis` mode. Hidden batches (3 per task) use `edge` mode. Reference ASTs and hidden batches are
runner-private.

**Pipeline cases.** 3 observed and 2 hidden batches each, all in `edge` mode. The oracle is `pipeline_oracle`, counted against B_q.
`edit_reachable` is the engineer's **design claim**. The measured method of every repair is recorded regardless
(`repair_methods`, `verified_method` ∈ {`edit`, `synth`, `mixed`}).

| Case | Broken | Reference | `edit_reachable` |
|---|---|---|---|
| `P1_left_lookup` | `enriched` uses inner `JOIN` (stage `clean` preserved) | `LEFT JOIN` | yes |
| `P2_count_col` | `COUNT(*)` | `COUNT(v)` | yes |
| `P3_null_default` | `out` uses `x AS y` (stage `kept` preserved) | `COALESCE(x, 0) AS y` | yes |
| `P4_lookup_default` | inner `JOIN` | `LEFT JOIN` + `COALESCE(tier, 'none')` | **no** (two edits) |
| `P5_sum_measure` | `COUNT(*) AS total` | `SUM(amt) AS total` | **no** (different measure) |

P4 and P5 are summarised separately as `pipelines_beyond_single_edit`, with their own verdict. Join column sets do not overlap, so
the qualified-identity rules accept them.

**Seed namespaces.** These are disjoint by construction and re-checked before the run; `run_experiment` refuses any overlap.
- source: `1310000 + 10000·stream + 100·family + i`;
- evaluation: `132000 + 100·family + i`;
- pipelines: `133000 + 100·spec + i`;
- indices lie in 0..99.

**Streams.** `rep0` and `rep1` train independent selectors, no-regret selectors and guides on disjoint source seeds. Evaluation tasks
are identical across streams.

**Isolation.**
- The selectors are copied frozen, and the guide is frozen.
- sha256 fingerprints are recorded before evaluation and re-checked after.
- `isolation.ok` requires no seed overlap, every object frozen and every fingerprint unchanged. The runner exits 1 otherwise.

## 6. Pre-registered verdict

**Primary setting:** ambiguous suite, B_q = max(budgets) (default 2).

**Verdict rule:**
- **positive:** Trained − X ≥ +2 verified for every X ∈ {fixed, random, untrained} in every stream, **and** Trained's wrong count
  ≤ every comparator's;
- **negative:** Trained − X ≤ −2 for some X in every stream;
- **mixed:** otherwise.

The same rule is applied separately to `pipelines` and to `pipelines_beyond_single_edit`.

**Also reported:** B_q = 1; Untrained − Fixed; per-family results; the regret ablation; single-shot.

**Missing rows** are listed and never imputed. Default size is 10 ambiguous tasks per stream, so a ±2 contrast is a coarse signal,
not a powered result.

### 6.1 Progression metrics (charter section 10; per stream, primary B_q; `None` when undefined)

| Metric | Definition |
|---|---|
| `learning_to_learn_gain` | Relative reduction of (full_checks + probe_evals) per verified task, trained vs untrained. The query reduction is reported alongside. |
| `transfer_efficiency` | Trained − untrained verified on held-out families. |
| `self_evolution_delta` | (verified − wrong) / rows: trained minus `trained_no_regret`, which isolates regret. The combined trained-vs-untrained value is reported separately. |
| `unseen_domain_reuse_rate` | Share of trained verified held-out rows whose leader uses admitted library functions. Structurally 0: none are admitted. |
| `enterprise_reliability_advantage` | (verified − wrong) / rows: trained minus single-shot. Pipeline trained vs best control is reported alongside. |

## 7. Attribution (Charter rule 4)

**Learned by NEXUS during source training** (`learned_by_nexus[stream]`):
- selector weights;
- shortcut-tag prior and `demoted_shortcuts`;
- no-regret selector weights;
- guide counts and cost table;
- ledger counts;
- source-episode outcomes and supervision use.

No library functions are admitted.

**Engineering machinery** (never NEXUS learning):
- all of `proposals13`, `selector13`, `pipeline_lifter13` and `runner13`, including:
  - proposal kinds and the shadow edge set;
  - update rules;
  - the SQL parser and compiler;
  - generators and reference programs;
  - the `edit_reachable` declarations;
- `synth12` / `core11`.

Human, Claude, Codex and Gemini edits are external engineering.

The shadow edge set is a generic structural edit menu, not a per-task template, but it encodes engineer prior knowledge about which
shortcuts matter. Pipeline repairs by `edit` come from that menu. Only `synth` repairs come from the atomic synthesizer.

## 8. How to run (2400 s owner grant)

```bash
python3 -m unittest -v tests/test_de_phase13.py
python3 -m nexus.de_phase13.runner13 --quick --grant-seconds 120 --out artifacts/agi13_smoke
python3 src/nexus/de_phase13/runner13.py --grant-seconds 2400 --execute   # coordinator invocation; writes artifacts/agi13_eval
```

**Optional flags:**
- `--no-regret-ablation`
- `--no-pipelines`
- `--eval-instances` / `--source-instances` / `--pipeline-instances`
- `--budgets`
- `--fc-cap`

**Exit codes:**
- **0:** ok.
- **1:** an over-cap row, an isolation failure, or a source-supervision overrun.
- **2:** no completed rows.

**Time shares:** source ≤ 30 % of the grant; the ambiguous suite until 80 %; pipelines until the 95 % safety deadline.

## 9. Unit tests (`tests/test_de_phase13.py`, standard-library `unittest`)

| Area | What the tests check |
|---|---|
| Relations / facts | `make_rel` round trip; program facts; shortcut tags. |
| No lock: passthrough | A lone passthrough keeps its coalesce shadow. A program-aware NULL-in-x proposal splits them, the reference answer falsifies the passthrough, and the shadow survives and grades correct. |
| No lock: COUNT(*) | A lone COUNT(*) keeps its COUNT(col) shadow, and a proposal splits them. |
| Join kinds | An inner join keeps its left shadow, and an `unmatched` proposal splits them. |
| Metering | With `fc_cap = 1` there is no overrun, and `unchecked` members are never alive. |
| Menus / choice | Static menu ids and deduplication; fixed / random / weighted choice. |
| Regret | Counterfactual utilities; regret demotion; listwise step; clipping. |
| Shortcut prior | Demotion orders without removing members; the prior is bounded. |
| Isolation | Frozen selector and guide raise; fingerprints are stable. |
| SQL / pipelines | Subset parse and rejections; script split; LEFT JOIN parse; SQLite agreement on coalesce; localisation preserves the working stage; the lift repairs COUNT(*) → COUNT(v); no queries are used without an oracle. |
| Runner | Seed disjointness; verdict logic; over-cap detection; a tiny end-to-end run with 0 over-cap and 0 error rows, isolation intact and artifacts written. |

**Declared gaps (no dedicated regression test yet; reviewers should request them):**
1. Common resolution menu: live alternatives that agree on static probes but differ on an AST-derived boundary / unmatched-key
   probe must make **every** pipeline arm (including the `menu=_static_menu` arms) abstain once the query allowance is spent.
2. Native query gate: a member whose compiled SQL agrees on the fit batches but disagrees on an answered query input must be rejected
   (`failed_on_query = True`).
3. Rejection of the ambiguous `SELECT a.id, b.id FROM a JOIN b …` reference.
4. `sql_fidelity` disagreement → `unfaithful_parse`, and native error → `fidelity_unverified`.
5. A probe-cap regression: an agreeing prefix followed by a distinguishing proposal beyond the cap → `incomplete_scoring`.
6. `SourceMeter` refusal, and the presence of `trained_no_regret` rows.

## 10. Results

### 10.1 Previous execution (pre-fix code for section 0.2; superseded; reproduced from the coordinator record)

This run used pipeline code in which the final resolution test followed the arm's query menu, and in which the native gate did
**not** cover answered queries. Its pipeline numbers are therefore **not** valid for the current rules.

**Tests.** `python3.13 -m unittest -v tests/test_de_phase13.py`: returncode 0, **18 tests OK** (3.06 s).

**Experiment.** `runner13.py --grant-seconds 2400.0 --execute`: returncode 0, coordinator wall 33.3 s (runner total 33.21 s, source
3.27 s).

**Source training:**

| Stream | Episodes | `demoted_shortcuts` | Supervision used | Refused |
|---|---|---|---|---|
| rep0 | 9 | [] | ref_answers 272, grade_execs 69 | none |
| rep1 | 9 | [] | ref_answers 329, grade_execs 78 | none |

**Verdict:** `ambiguous` **mixed**, `pipelines` **mixed**, `pipelines_beyond_single_edit` **mixed** (primary B_q = 2).

**Ambiguous suite, verified / wrong / abstained of 10 rows** (from the captured stdout tail):

| Arm | rep0 B_q=1 | rep1 B_q=1 | rep0 B_q=2 | rep1 B_q=2 |
|---|---|---|---|---|
| fixed | not in captured tail | 0 / 0 / 10 | 0 / 0 / 10 | 0 / 0 / 10 |
| random | 0 / 0 / – (submitted 0; rest of entry not captured) | 0 / 0 / 10 | 2 / 0 / 8 | 0 / 0 / 10 |
| untrained | 3 / 0 / 7 | 3 / 0 / 7 | 6 / 0 / 4 | 6 / 0 / 4 |
| trained | 2 / 0 / 8 | 2 / 0 / 8 | 6 / 0 / 4 | 6 / 0 / 4 |
| trained_no_regret (ablation) | 2 / 0 / 8 | 2 / 0 / 8 | 6 / 0 / 4 | 6 / 0 / 4 |
| single_shot (B_q = 0) | 2 / 8 / 0 | 2 / 8 / 0 | — | — |

- **B_q = 2 contrasts (rep0, rep1):**
  - Trained − Fixed: +6, +6;
  - Trained − Random: +4, +6;
  - Trained − Untrained: **0, 0**;
  - Trained − no-regret: **0, 0**.
- **B_q = 1:** Trained − Untrained = **−1** in both streams.
- **Query quality** (splitting / issued, B_q = 2, both streams): trained 18 / 20; untrained 17 / 20; fixed 5 / 20; random 8 / 20.
- **Work:** max full checks per row 3,593 (≤ 5,000); 0 over-cap rows in every summary shown.

**Pipeline suite (pre-fix resolution and native rules), verified of 10 rows per stream / B_q / arm:**
- Every arm verified **8**, with 0 wrong, in both streams at both B_q. The one exception is trained rep0 B_q = 2, with **9**.
- In every arm, 6 of the verified repairs were by `edit`, and the remaining 2 (3 for trained rep0 B_q = 2) were by `synth`.
- **Beyond a single edit** (P4 + P5, 4 rows each): every arm verified 2, all by `synth`. The exception is trained rep0 B_q = 2, with
  3.
- Max full checks per row was 3,526.
- Pipeline Trained − X at B_q = 2 was +1 / 0, so the verdict is mixed.

**Not in the captured tail:** the progression metric values, `learned_by_nexus` details, the full `checks` block and the rep0 B_q = 1
Fixed entry. Take them from `artifacts/agi13_eval/results.json` of that run, if it was retained; they are not reproduced here.

**Honest reading of the previous run:**
- **What is shown:**
  - The program-aware menu plus shadows (Untrained vs Fixed / Random) produced the ambiguous-suite gain.
  - Abstention kept wrong submissions at 0, against single-shot's 8 / 10.
  - The atomic synthesizer verified P4 / P5 repairs that the single-edit menu could not reach.
- **What is not shown:**
  - No learned-selector gain (Trained − Untrained ≤ 0).
  - No regret-isolated gain (Trained = no-regret).
  - No shortcut demoted in the full run.
  - No transfer, no library reuse and no multi-engine transfer.
- The pipeline Trained +1 (rep0, B_q = 2) is a single row and is not a signal.
- Single-shot is a heuristic, not an LLM baseline.

### 10.2 Current revision

**NOT YET AVAILABLE in this document.** Copy the following verbatim from the new `experiment_execution` and
`artifacts/agi13_eval/results.json`:
- verdicts;
- contrasts, including `regret_ablation` and `pipelines_beyond_single_edit`;
- summaries, including `verified_by_edit` / `verified_by_synth`, `incomplete_scoring` and `budget_abstentions`;
- `checks`, including `source_supervision_over_cap`;
- progression;
- `learned_by_nexus`;
- isolation, wall and environment.

State wrong next to verified for every arm, and report any failed check first.

Pipeline Fixed / Random results may now **drop** relative to 10.1. They abstain where the common menu still separates members, and
reject repairs that disagree natively on answered queries. Any such change must be reported as a consequence of the section 0.2
fixes, not as learning.

## 11. Known limitations and confounds (declared)

1. **Menu confound.** Fixed and Random query from the static menu, while Untrained and Trained query from the program-aware menu, in
   both suites. Untrained − Fixed therefore measures menu and rule together. Abstention uses the common menu in every arm.
2. **Trained collects with its own guide costs**, so its effect combines search guide and selection. Trained − `trained_no_regret`
   isolates regret only, and only in the ambiguous suite.
3. **Finite shadow menu.** Programs more than one edit away depend on the synthesizer (P4 / P5) or on resume after total
   falsification.
4. **Engines.** Only core11 and SQLite. Shared join column names are rejected. DuckDB, Polars and PySpark are out of scope.
5. **Synthetic tasks.** Small, hand-generated families and pipelines; not real-world schemas.
6. **Privileged source supervision.** Metered, and never available at test time.
7. **Machine dependence.** Wall caps make counters machine-dependent.
8. **Bounded probes.** Agreement is not proof; `agreement_unproven` submissions must be reported.
9. **Source volume.** 9 episodes per stream did not move the shortcut prior in the previous run.

## 12. Reviewer checklist

- [ ] `test_execution` and `experiment_execution` are present, with returncode 0, **for the current revision**.
- [ ] `over_cap_rows == 0`, `error_rows == 0`, `isolation.ok`, empty seed overlaps, empty `source_supervision_over_cap`.
- [ ] No passthrough / COUNT(*) lock. The tag prior only orders.
- [ ] All four control arms are present per (task, stream, B_q) with identical B_q, caps and abstention rule. Ablation rows are
  present.
- [ ] Pipeline final resolution uses `resolution_menu` in every arm (`resolution_menu = "program_aware+static"` in results).
- [ ] The native gate covers answered queries (`native_query_checks`).
- [ ] Incomplete scoring abstains. Ambiguous qualified references are rejected. Unfaithful or unverified parses are not lifted.
- [ ] Edit vs synth repairs are reported separately. Learned state is reported apart from machinery.
- [ ] The verdict follows the pre-registered rule, and missing rows are listed.

## 13. Handoff: next steps

1. Fill section 10.2 from the current run only.
2. Add the regression tests listed in section 9, especially gaps 1 and 2 (this revision's safety invariants).
3. If Trained − Untrained and Trained − no-regret stay ≤ 0, raise `--source-instances` within the grant. Inspect `top_weights`,
   `tag_prior` and `skipped_learning_steps` before concluding anything about learning.
4. Add harder pipeline specs beyond a single edit (multi-stage joins, overlapping column names once core11 carries qualified
   identity).
5. Add DuckDB and Polars back ends behind `native_check`, reported as additional engines.
