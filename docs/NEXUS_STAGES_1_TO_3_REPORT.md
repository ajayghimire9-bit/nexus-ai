# NEXUS Data Engineering, Stages 1–3: Technical Report (NOT LOCKED)

* **Branch:** `codex/nexus-data-engineering`, from `46c3e53`.
* **Untouched:** `main`, `final_sealed`, Checkers v1–v5 (`622a29a`).
* **Roadmap and scorecard:** `docs/NEXUS_10_STAGE_ROADMAP.md`.
* **Inventory:** `docs/STAGE1_BASELINE_INVENTORY.md`.

## Corrections to the directive's premises

1. **Budget.** The directive restates the Wave 41 authorisation word for word: "remaining ~3,590 s grant + 14,400 s". An
   increase is never inferred (AGENTS.md), so this is the **same 17,990 s grant, carried**. The paused Wave 41 dev work used
   1,959 s of it (`scripts/de_budget.py`).
2. **The outcome vocabulary did not exist yet.** At `46c3e53` there was no `ABSTAIN_ERROR` and no `ASK_CLARIFICATION`.
   Checker v5 also counts an ERROR answer on a future input as one unique answer. Stage 1 adds a contract layer above the
   read-only v5 and tests that the outcomes stay distinct.
3. **N1-merge-exact is not a data change detector.** It is regime-change detection for world-model adaptation. Its reuse for
   pipeline drift is a Stage 5 proposal.
4. **Nothing LLM-based is involved.** The "model / proposer" is a symbolic code generator with 14 decisions, the same for
   both arms. It is not an LLM. **Model calls = 0** in every scorecard.
5. **Wave 41 is paused, not finished.** It was preserved before branching (`84091eb`, dev-only; no confirmation seed claimed,
   no sealed file opened). It has an open dev issue: the growth arm solved 96 vs Flat's 99 on the dev stream.

## Stage 1: trustworthy starting point

The inventory, the verified vs proposed components, and the retracted or qualified Wave 38–39 claims are in
`docs/STAGE1_BASELINE_INVENTORY.md`.

**Regression (`scripts/de_stage1_regression.py` → `artifacts/de_stage1_regression.json`):**

| Suite | Tests | Pass |
| --- | --- | --- |
| Search-order invariance (state-dominance repair, `new_depth < min_depth_seen` re-expansion) | 175 | 175 |
| Wave 40 components (witness soundness, O(T) rows) | 5 | 5 |
| Checker kernels v1 / v2 / v3 / v4 / v5 (pins + differential tests) | 4 / 14 / 13 / 5 / 6 | all |
| Stage 1 outcome contract: valid vs ABSTAIN_ERROR vs UNDER_SPECIFIED / ASK_CLARIFICATION vs unsupported, from real v5 verdicts | 6 | 6 |
| **Total** | **228** | **228 (100%)** |

**Stage 1 pass condition: met.**
* Every comparison arm reaches the identical solution space with identical certificates (175/175).
* Both Stage 3 arms share generator, proposer, tools and caps (tested).
* 100% of the regression tests pass.

## Stage 2: logistics environment and independent evaluator

**Environment (`src/nexus/de_env.py`).** Each project has a clean **truth world** encoded into messy sources:

| Source | Contents |
| --- | --- |
| Operational sqlite snapshot (per batch) | Customers, warehouses, shipments, inventory adjustments. PK / FK declarations, soft deletes (flag or timestamp encoding) and hard deletes. Replaces the previous snapshot. |
| Debezium-style CDC envelopes | Orders, `op c/u/d/r`, `event_ts` in mixed UTC offsets, `ingest_ts`, `seq`. Two partitions, redeliveries, late and retroactive corrections, out-of-order arrival. |
| Append-only telemetry | Duplicate deliveries; late events beyond the lateness window. |
| CSV weight manifests | Malformed rows (unparseable, unknown unit, missing key), orphans, mixed `kg` / `g` / `lb` (plus `oz` in the held-out pool), unit as a suffix or a column. Schema drift from batch 2 (renamed weight column, switched unit encoding); re-delivered files. |

* **Currencies:** USD / EUR / GBP; JPY / CHF are held out.
* **Outputs (lakehouse `state/lake.db`):**
  * bronze and silver tables;
  * gold tables: net fulfilled revenue, on-time SLA, carrier volume, status buckets, inventory reconciliation;
  * `late_events`;
  * a quarantine table with reason codes.
* **Business rules** are predeclared in `docs/spec.json`: identifiers and synonyms, unit and FX tables, CDC last-writer-wins by
  UTC event time, deletion semantics, the lateness window, retention, freshness and idempotency.
* **Clarification traps:**
  * cancelled-after-shipped orders are not covered by the carrier-volume rule;
  * an undocumented status code has no bucket.

  The only correct action for either is `ask_clarification`; the simulated stakeholder answers per project.
* **Three batches:** the engineer receives batches 1–2. **Batch 3 is held out** for the evaluator. Every fault class occurs
  in the visible batches and again in batch 3.
* **Splits:**
  * dev (pool 0);
  * val (pools 0 + 1);
  * test (pools 1 + 2), where pool 2 holds the held-out physical names, carriers, lateness, codes, units, currencies and the
    text deletion flag.

**Evaluator (`src/nexus/de_evaluator.py`).**
* It imports nothing from NEXUS (tested). It recomputes every expected table from the truth world and never parses the
  landing files or reads pipeline code.
* Each pipeline runs sandboxed through b1 → b2 → **b3 (held out)** → b3 rerun, then from the b2 state: b3 with a crash
  injected by an audit hook (exit 137 after half the landing files) and a restart.
* **Diagnoses are exact:** a counterfactual reference with **one** rule violated must reproduce the observed table.
* Structural reasons are read from the states: rerun changed state, duplicate keys, schema, crash recovery, unasked
  ambiguity.
* The stakeholder oracle answers only genuine questions and logs every call.

**Pass-condition test (`scripts/de_stage2_proof.py` → `artifacts/de_stage2_proof.json`).** The 6 dev projects use the final
generator. Every broken pipeline exits 0 and writes non-empty tables.

| Broken pipeline (one decision wrong) | Expected reason | Caught | Exact reason | Exit 0 + non-empty |
| --- | --- | --- | --- | --- |
| 0 correct pipeline (asks; false-alarm control) | n/a | 0/6 (no false alarm) | n/a | 6/6 |
| 1 fan-out join double counting | FANOUT_DOUBLE_COUNT | 6/6 | 6/6 | 6/6 |
| 2 dropping late corrections (high-water-mark filter) | DROPPED_LATE_CHANGES | 6/6 | 6/6 | 6/6 |
| 3 updates applied out of event-time order | ARRIVAL_ORDER_APPLY | 6/6 | 6/6 | 6/6 |
| 4 ignoring soft deletes | IGNORED_SOFT_DELETES | 6/6 | 6/6 | 6/6 |
| 5 unit mismatch | UNIT_MISMATCH | 6/6 | 6/6 | 6/6 |
| 6 non-idempotent duplicate append on rerun | NON_IDEMPOTENT_RERUN (+ duplicate keys, crash recovery failed) | 6/6 | 6/6 | 6/6 |
| 7 malformed rows coerced to 0 | MALFORMED_ZERO_FILLED | 6/6 | 6/6 | 6/6 |
| 8 guessing an ambiguous business rule | GUESSED_AMBIGUOUS_RULE + UNASKED_AMBIGUITY | 6/6 | 6/6 | 6/6 |
| S1 timestamps compared as text | TEXT_TIMESTAMP_ORDER | 6/6 | 6/6 | 6/6 |
| S2 no currency conversion | NO_CURRENCY_CONVERSION | 6/6 | 6/6 | 6/6 |
| S3 malformed rows silently dropped | MALFORMED_DROPPED | 6/6 | 6/6 | 6/6 |
| S4 lateness window ignored | LATENESS_WINDOW_IGNORED | 6/6 | 6/6 | 6/6 |
| S5 dimension snapshot appended | NON_IDEMPOTENT_RERUN | 6/6 | 6/6 | 6/6 |
| S6 lucky guess (right answer, never asked) | UNASKED_AMBIGUITY | 6/6 | 6/6 | 6/6 |

**Stage 2 pass condition: met.** All 8 required pipelines are caught with exact reasons on 6/6 projects, with 0 false alarms.

**Caveats:**
* The broken pipelines and the correct pipeline come from the same generator that the agents use. The evaluator's
  independence lies in its reference, which is built from the truth world.
* The same author wrote the evaluator, the generator and the agents. Independence is therefore by construction and import
  isolation, not by different authors.

## Stage 3: protocol and freeze (committed before any val or test project is generated)

**Arms.**
* Both arms use the **same** generator (`de_template`), tools, proposer and caps: at most 40 proposals and 300 CPU s per
  project.
* The proposer order is a seeded random permutation of each decision's options, keyed by (project, decision), and is
  identical for both arms.
* An exception is attributed to the decision whose stage raised it.
* No history crosses projects.

| Arm | Behaviour |
| --- | --- |
| `Conventional_Agent_No_NEXUS_Checks` | Stops at the first configuration that runs without an exception; never asks. |
| `NEXUS_Engineer_No_History` | Runs the ambiguity coverage check and asks `ask_clarification` for every rule gap the data hits. Then generates, runs and verifies with 13 invariants (`de_checks`). Each failing invariant changes the decision it implicates. It submits only if all invariants hold; otherwise it abstains or hard-fails, and never submits silently. |
| `Conventional_BestCaseProposer_Sensitivity` | *Descriptive only.* The conventional stop rule with a proposer whose first option is always the correct-shape one. It bounds what verification adds beyond code quality. |

**The 13 invariants:**
* schema and primary keys;
* idempotent rerun;
* duplicate-delivery invariance;
* crash-restart equivalence;
* seq-relabel invariance;
* UTC-offset invariance;
* incremental = full refresh;
* currency-representation invariance;
* unit-representation invariance;
* quarantine conservation;
* deletion contract;
* shipment-split invariance (fan-out);
* late-event-removal invariance.

They use only the docs and the visible batches. `tests/test_de_stage3.py` shows on dev projects that **every** single wrong
option of every decision fails a check that implicates it, with no false alarm.

**Development history (dev only).**
* The first NEXUS dev run certified a pipeline that ignored the lateness window: my bounded lateness check was too loose. On
  the evaluator it was a silent error.
* The fix replaced the loose bounds with two metamorphic checks: late-event removal and shipment split.
* The generator was also changed so that every fault class appears in the visible batches.
* After the fix, NEXUS was correct on 6/6 dev projects, Conventional on 0/6 and BestCase on 0/6 (`artifacts/de_stage3_dev.json`).

**Admission gate on val.**
* **Data:** `de1/val`, seeds 7901–7904; one use; generated by the runner, with no inspection beforehand.
* **Rule:** NEXUS must reach 0 silent data errors, 0 unresolved ambiguity, ≥ 3/4 independently checked correct, 0 human
  repairs, and every submitted bundle idempotent and crash-recovered.
* **If it fails:** val is reclassified as dev, the failure is fixed and disclosed, and `de1/val_b` (7913–7916) is used once.

**Final test.**
* **Data:** `de1/test`, seeds 7905–7912, eight projects. They are sealed by `scripts/de_seal_test.py` as opaque blobs, and the
  manifest is committed before the run.
* **Run:** `scripts/de_stage3.py --split test` runs once, with `NEXUS_SEALED_HARNESS_TOKEN` set.

**Verdict rules (predeclared):**
* **Correctness: NEXUS better** if NEXUS's independently checked correct count is higher than Conventional's, with 0 NEXUS
  silent data errors. A one-sided sign test across the paired projects is reported (n = 8, descriptive).
* **Milestone (Stages 1–3) PASS** iff all of the following hold:
  * Stage 1 is 100%;
  * Stage 2 is 8/8 with 0 false alarms;
  * on the test split, NEXUS is ≥ 7/8 independently checked correct, with 0 silent data errors, 0 unresolved ambiguity,
    0 human engineering repairs and 0 operational interventions;
  * every submitted NEXUS bundle is idempotent and crash-recovered;
  * every cost is recorded.
* Completion, reliability, cost, human dependence and generalization (held-out batch 3, held-out pool features) are reported
  in full for every arm.
* Learning benefit is n/a: this is the 0-history baseline.

**Missing-data rule.**
* A harness crash on a project records HARD_FAIL for the affected arm.
* The test is never re-run; runs resume per project only after a harness interruption, and that is disclosed.

**Isolation (honest limits).**
* The agent workspace holds docs/ and batches 1–2 only.
* Truth is held in the runner process and a temporary directory. The separation is enforced by the tool API and import
  isolation, not by an OS boundary.
* Pipelines run under the macOS sandbox: no network, no writes into the repository, no vault reads.
