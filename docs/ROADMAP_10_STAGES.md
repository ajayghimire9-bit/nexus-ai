# NEXUS 10-Stage Autonomous Data Engineering & AGI Roadmap

Starting from the verified Wave 40 baseline (`46c3e53`), NEXUS advances through a structured **10-Stage Roadmap** transforming the core synthesis and verification kernel into a fully autonomous, budget-disciplined, self-improving data engineering and program synthesis system.

---

## 1. The 7-Measure Unified Scorecard

Every stage is evaluated against a single **7-Measure Unified Scorecard**—never by cherry-picking isolated metrics:

| # | Measure | Operational Definition | Baseline (`46c3e53` / Wave 40) | Target Direction |
| :---: | :--- | :--- | :--- | :--- |
| **1** | **Correctness** | False-accept rate across all pinned checker kernels (`v1`–`v5`), held-out confirmation inputs, and adversarial mutation probes. | **`0` false accepts** (`42/42` kernel tests, `0` detector bypasses) | Hard invariant (`== 0` always) |
| **2** | **Completion** | Certified solve rate on held-out confirmation suites (`LODO`, `PROSE` unburned external, and multi-stage pipelines) within budget (`B_exec <= 500`, `B_total <= 700`). | **LODO:** `80.0%` (`64/80`)<br>**External PROSE (unburned):** `79.2%` (`19/24`) | Increase without relaxing `B_exec` or `B_total` |
| **3** | **Reliability** | Search-order invariance under input/example permutation (`5` seeds), hash-seed determinism (`5` `PYTHONHASHSEED` values), and non-stationary false-alarm ceiling. | **Invariance:** `100%` (`175/175` tests, `16/16` LODO cells, `24/24` PROSE)<br>**World FAR:** `0.0 / 1000` (`<= 0.10` ceiling) | Hard invariant (`100%` invariance, `FAR <= 0.10/1000`) |
| **4** | **Cost** | Dual-budget accounting combining execution evaluations (`exec_evals`), static cost-row scoring (`0.052` exec-eq/row), prior refits (`2.0` exec-eq/fit), and OS retired CPU instructions (`ri_instructions`). | **LODO mean evals:** `22.71` (learned) vs `58.59` (uniform)<br>**Online total cost:** `118.21` vs `138.62` (`-14.7%`) | Lower total execution-equivalents & retired instructions |
| **5** | **Human Dependence** | Number of human interventions, hand-coded domain hints, or manual grammar patches required per new task family. | **Zero manual hints at inference**; grammar extensions still human-authored across waves | Autonomous failure clustering & verified operator discovery |
| **6** | **Learning Benefit** | Statistically gated (`p < 0.05` sign-flip permutation test) work reduction or solve-rate gain of learned priors/macros over uniform search under identical total budgets. | **LODO work reduction:** `-61.2%` (`p = 0.0078`)<br>**Online budgeted reduction:** `-14.7%` (`16/16` streams) | Positive net savings after charging all learning & refit overhead |
| **7** | **Generalization** | Zero-shot and few-shot transfer to held-out domains (8-domain LODO) and external benchmarks (`PROSE` Microsoft Program Synthesis Benchmark) with strict `BURNED` quarantine. | **LODO:** `8/8` held-out domains beat uniform<br>**External PROSE:** `19/24` (`79.2%`) unburned | Expand across multi-column tables, messy CSV/JSON logs, and relational pipelines |

---

## 2. The 10 Stages

### Stage 1: Canonical Outcome Contract & Unified Regression Gate (`Active`)
- **Objective:** Lock in the Wave 40 baseline (`46c3e53`) behind an executable regression gate (`scripts/de_stage1_regression.py`) and formalize the mutually exclusive 4-state task outcome contract (`CERTIFIED`, `REPAIRED`, `ABSTAINED`, `REJECTED`) in `src/nexus/outcome_contract.py`.
- **Gate:** `228/228` tests passing (`222` Wave 40 + `6` Stage 1 contract tests), all 5 Checker Kernel SHA-256 hashes verified, and `artifacts/de_stage1_regression.json` emitted.

### Stage 2: Richer Multi-Type Schema & Messy Record Ingestion
- **Objective:** Extend the input/output representation beyond single-string transformations to structured records (`dict`, typed columns, nullable fields, malformed rows) while preserving deterministic canonicalization and zero shared code with the checker kernel.
- **Gate:** Zero regressions on Stage 1 (`228/228`), deterministic schema inference on messy tabular/log fixtures, and `0` false accepts under Checker Kernel `v5`.

### Stage 3: Compositional Relational & Aggregation Primitives
- **Objective:** Add verifiable record-level filtering, key-extraction grouping, and deterministic fold/aggregation operators with bounded complexity and strict AST size accounting.
- **Gate:** Order-invariant synthesis across multi-record relational tasks within `B_exec = 500`, `B_total = 700.0`.

### Stage 4: Counterexample-Guided Fault Localization & Multi-Edit Repair
- **Objective:** Upgrade the 1-edit fault-localization repair engine (`src/nexus/w38_repair.py`) to localize stage-level failures across multi-column pipelines and synthesize bounded 2-edit repairs (`REPAIRED` state) when specs drift or edge-case formatting changes.
- **Gate:** Verified repair gain over scratch re-synthesis in total execution-equivalents (`B_total`).

### Stage 5: Active Abstention & Ambiguity Witness Generation
- **Objective:** When public examples under-determine the target transformation, actively synthesize a **distinguishing witness input** $x^*$ where two minimal surviving programs $p_1(x^*) \neq p_2(x^*)$ disagree, or cleanly return `ABSTAINED` when no program exists in the bounded grammar.
- **Gate:** `0` false accepts on under-specified tasks and exact separation between `ABSTAINED (under-determined)` vs. `ABSTAINED (out-of-grammar)`.

### Stage 6: Autonomous Macro & Sub-Program Library Compression
- **Objective:** Discover, validate, and prune reusable multi-operator macros automatically from certified solutions across domains using minimum description length (MDL) and held-out validation savings—charging macro-scoring overhead (`C_ROW`) honestly inside `B_total`.
- **Gate:** Net reduction in `B_total` on held-out confirmation domains (`p < 0.05` permutation gate) with zero human-authored macros.

### Stage 7: Non-Stationary Pipeline Drift Detection & Surgical Re-Synthesis
- **Objective:** Couple the `N1-merge-exact` change-point detector (`src/nexus/w39_world.py`) directly to multi-stage data pipelines so schema or format drift triggers surgical repair of only the broken pipeline stage rather than full re-synthesis.
- **Gate:** Maintain `FAR <= 0.10 / 1000` steps while reducing post-drift recovery cost (`B_total`) below full re-synthesis.

### Stage 8: Self-Curated Curriculum & Failure-Boundary Task Generation
- **Objective:** Generate solvable, checker-verified frontier tasks targeted at current solver failure modes (`ABSTAINED` boundary) without human task authoring, filtered for non-triviality and diversity.
- **Gate:** Statistically significant transfer improvement on held-out confirmation suites from self-curated training curricula vs. random task generation.

### Stage 9: End-to-End Autonomous Data Engineering Workbench
- **Objective:** Integrate schema ingestion, synthesis, repair, drift monitoring, and cryptographic audit receipts (`OutcomeRecord`) into a single deterministic CLI and batch runner for real-world file/stream cleansing.
- **Gate:** End-to-end execution on multi-file data engineering benchmarks with full reproducibility and zero unverified outputs.

### Stage 10: Sealed Blind Vault Final Confirmation
- **Objective:** Execute a single-shot, zero-intervention evaluation on the sealed blind vault (`$NEXUS_SEALED_VAULT_DIR`) across all 7 scorecard measures.
- **Gate:** All 7 scorecard measures pass pre-registered thresholds on the sealed blind vault with zero post-hoc adjustments.
