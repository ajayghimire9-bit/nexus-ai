# NEXUS Data Platform

> **"Give NEXUS your data sources, business requirements, infrastructure access, and budget. It designs, builds, operates, repairs, and improves your data platform—and learns reusable engineering procedures from its experience."**

NEXUS is an autonomous data engineering and operations system engineered to take end-to-end ownership of production data lifecycles—spanning ingestion, change data capture (CDC), streaming pipelines, messy structured and unstructured data, lakehouses, data warehouses, cloud infrastructure, and incident recovery—while becoming measurably cheaper and more reliable through verified experience.

Unlike conventional coding assistants that stop after generating a script that exits with code `0`, NEXUS separates **editable engineering and learning policies** from an **independent verification, invariant-checking, and cost-accounting boundary**. It treats silent data corruption, duplicate side-effects, and unverified assumptions as first-class failures.

---

## Table of Contents

1. [What NEXUS Takes Responsibility For](#1-what-nexus-takes-responsibility-for)
2. [Current Maturity & Honest Assessment](#2-current-maturity--honest-assessment)
3. [Flagship Scenario: End-to-End Logistics Platform](#3-flagship-scenario-end-to-end-logistics-platform)
4. [System Architecture](#4-system-architecture)
5. [How Learning & AGI Capabilities Work Inside the Product](#5-how-learning--agi-capabilities-work-inside-the-product)
6. [How NEXUS Stays Inexpensive](#6-how-nexus-stays-inexpensive)
7. [The 10-Stage Engineering & Verification Roadmap](#7-the-10-stage-engineering--verification-roadmap)
8. [Unified 7-Measure Scorecard](#8-unified-7-measure-scorecard)
9. [Verified Foundation (Baseline `46c3e53`)](#9-verified-foundation-baseline-46c3e53)
10. [Repository Structure & Quickstart](#10-repository-structure--quickstart)

---

## 1. What NEXUS Takes Responsibility For

NEXUS is designed around full lifecycle ownership—including what happens in production after initial deployment. "Handling all kinds of data" means an extensible system with explicit support envelopes and active uncertainty handling, never silently guessing the meaning of an unfamiliar file or ambiguous business rule.

| Area | What the Platform Must Do | Difficult Cases It Must Handle |
| :--- | :--- | :--- |
| **Discovery & requirements** | Inspect existing systems, identify dependencies, clarify business definitions, propose an implementation | Undocumented databases, conflicting requirements, unclear ownership, inconsistent definitions |
| **Data ingestion** | Connect databases, APIs, files, applications, and event streams | Pagination, rate limits, interrupted transfers, incremental snapshots, authentication changes |
| **Database change capture (CDC)** | Keep downstream systems synchronized with inserts, updates, and deletes | Snapshot-to-stream transitions, replayed changes, transaction ordering, missing history |
| **Streaming pipelines** | Build and operate continuously running transformations | Late and out-of-order events, duplicates, stateful joins, traffic spikes, backpressure |
| **Messy structured data** | Normalize, validate, reconcile, and transform records | Broken dates, mixed units, inconsistent identifiers, nested structures, missing fields |
| **Documents & other media** | Extract usable data from documents, scans, logs, audio, and images using appropriate models | Uncertain extraction, changing layouts, contradictory documents, preserving source evidence |
| **Data lakes & lakehouses** | Organize raw and curated datasets, tables, catalogs, and retention | Schema changes, concurrent writes, small-file buildup, partition changes, historical corrections |
| **Warehouses & data modeling** | Create business entities, relationships, historical models, and analytical datasets | Customer identity resolution, slowly changing dimensions, join multiplication, inconsistent metrics |
| **Cloud infrastructure** | Generate and operate infrastructure configurations, compute, storage, networking, and permissions | Capacity changes, quota limits, infrastructure drift, service failures, migrations |
| **Pipeline delivery** | Write SQL/Python and configuration, test, deploy, schedule, and document | Dependency conflicts, incompatible upgrades, partial deployments, rollback |
| **Operations & recovery** | Detect incidents, diagnose causes, repair, replay, and reconcile results | Corrupted state, delayed sources, failed checkpoints, partially completed backfills |
| **Performance & cost** | Optimize queries, storage, processing frequency, and resource allocation | Skewed keys, expensive joins, runaway retries, growing state, network transfer costs |
| **Governance & collaboration** | Track lineage, permissions, business decisions, and change history | Sensitive data, conflicting stakeholder requests, deletion requirements, downstream impact |

---

## 2. Current Maturity & Honest Assessment

Scientific honesty is a core requirement of this repository. Every claim is separated into what is already proved in code, what is technically achievable with established engineering, and what remains an open research milestone:

| Goal | Assessment & Current Status |
| :--- | :--- |
| **Generate, test, and repair complex SQL/Python pipelines** | **Technically achievable** with a capable model, execution tools, and independent testing (Active in Stages 1–3). |
| **Build streaming pipelines, lakes, warehouses, and cloud infrastructure** | **Technically achievable**, operating established engines (PostgreSQL, Debezium, Apache Flink, Apache Iceberg) through NEXUS (Stages 4–5). |
| **Operate those systems and recover from failures** | **Achievable within demonstrated operating conditions**, with strict state-reconciliation and reliability engineering (Stage 5). |
| **Reuse experience to reduce future work** | **Plausible; bounded evidence proved** (`0.796x Fresh` and `0.878x Placebo` across `5/5` seeds on internal synthesis folds; `-61.2%` LODO work reduction at Wave 40; tested on full data pipelines in Stage 6). |
| **Transfer reliably to unfamiliar companies and workloads** | **Still unproved at production project scale** (`19/24 = 79.2%` proved on unburned external PROSE string/record synthesis; tested across withheld data-engineering domains in Stage 7). |
| **Autonomously invent better learning procedures repeatedly and economically** | **Open research problem**; requires multi-lineage improvements that repay discovery cost on untouched projects (Stages 8–9). |
| **Replace an entire team across arbitrary environments at low cost** | **Not yet demonstrated**; evaluated strictly on sustained external workloads with explicit scope and authority boundaries (Stage 10). |

---

## 3. Flagship Scenario: End-to-End Logistics Platform

Consider the target workflow NEXUS is built and tested against:

> *"Combine live vehicle events, warehouse databases, customer orders, supplier spreadsheets, and delivery documents. Give us current inventory and delivery status, preserve historical corrections, and stay within our cloud budget."*

### Build Phase
1. **Discover** sources and determine how `orders`, `vehicles`, `shipments`, and `warehouses` relate.
2. **Clarify** ambiguous definitions with stakeholders (e.g., when a shipment officially counts as delivered or how cancelled-after-shipped orders affect carrier metrics) instead of guessing silently.
3. **Configure & build** database change capture (CDC), streaming ingestion, and messy file/document extraction.
4. **Construct** a lakehouse with raw evidence (`Bronze`), cleaned/deduplicated records (`Silver`), and reconciled business datasets (`Gold`).
5. **Implement** streaming joins, historical retroactive updates, and downstream analytical interfaces.
6. **Verify** correctness, failure recovery, access controls, and expected operating cost against an independent oracle.
7. **Deploy** within granted authority and monitor the running system.

### Operations Phase (When Production Gets Messy)
Writing a pipeline that runs once is only the beginning. NEXUS must detect, distinguish, and recover from live production incidents without corrupting downstream state:
- A vehicle reconnects and uploads **yesterday's telemetry events** out of order.
- A supplier **renames or reorders columns** in a manifest spreadsheet.
- A transactional database emits a **retroactive price correction and a hard deletion**.
- One warehouse's event traffic **spikes 10×**.
- A processing worker **crashes halfway through an incremental update**.

NEXUS must verify **end-to-end exactly-once semantics** across replayable sources and transactional or idempotent sinks (e.g., verifying Apache Flink source offsets and sink idempotency rather than merely toggling a checkpoint flag).

---

## 4. System Architecture

NEXUS uses a shared controller coordinating specialized engineering modules over persistent project state, bounded by an independent validation and cost-accounting kernel:

```mermaid
flowchart TD
    Goals["Business goals, policies, and budget"] --> Controller["NEXUS Controller"]
    Controller <--> State["Project state and learned procedures<br/>(Schemas, lineage, SLAs, checkpoints, skill contracts)"]
    Controller --> Specialists["Specialists: Ingestion, Streaming, Lakehouse, Cloud"]
    Specialists --> Validation["Independent Validation & Release Checks<br/>(Checkers v1–v5, Invariant Verifier, Fault Evaluator)"]
    Validation --> Engines["Customer Data Engines & Infrastructure<br/>(PostgreSQL, Debezium, Flink, Iceberg, Cloud)"]
    Engines --> Evidence["Operational Evidence & Incidents<br/>(Metrics, reconciliation diffs, failure traces)"]
    Evidence --> Controller
    Evidence --> Learning["Isolated Learning & Self-Evolution<br/>(Versioned procedure updates, shadow vault checks)"]
    Learning -. "Validated updates only" .-> State
    Learning -. "Validated updates only" .-> Controller
```

### Core Architectural Boundaries

1. **Pinned Verification Kernel (`src/nexus/checker_kernel.py` .. `checker_kernel_v5.py`):**
   Five versioned, zero-internal-import specification checkers whose exact file bytes are SHA-256 pinned at commit `622a29a`. No solver, template, or learning policy may modify them or share code with them.
2. **Closed Outcome Contract (`src/nexus/outcome_contract.py`):**
   Every per-input and project-level decision maps to an explicit, non-overlapping outcome (`VALID_UNIQUE`, `ABSTAIN_ERROR`, `ASK_CLARIFICATION`, `UNDER_SPECIFIED_WARNING`, `ABSTAIN_UNSUPPORTED`, plus project-level `COMPLETED_VERIFIED`, `COMPLETED_UNVERIFIED`, `HARD_FAIL`) so runtime errors or ambiguous requirements are never conflated with valid answers.
3. **Independent Data-Engineering Evaluator (`src/nexus/de_evaluator.py`, `src/nexus/de_env.py`):**
   Executes candidate pipelines in an isolated subprocess across a four-step operational protocol—`b1` (initial landing batch), `b2` (second batch with retention), `b2_rerun` (idempotency check), and `b2_crash` (hard `os._exit(137)` mid-batch crash followed by recovery)—and compares `Bronze`, `Silver`, and `Gold` tables against a clean truth world that the agent can never access.
4. **Non-Stationary Drift & Change Detection (`src/nexus/w39_world.py`):**
   Uses the `N1-merge-exact` binomial sufficient-statistic change detector (`1.000` recall, `0.0/1000` false-alarm rate) to trigger surgical re-synthesis or schema adaptation only when true distribution/schema shifts occur.

---

## 5. How Learning & AGI Capabilities Work Inside the Product

NEXUS does not treat "learning" as dumping raw transcripts into a prompt window. Every learned artifact—whether a representation prior, a reusable transformation macro, a verification check, or a repair policy—must earn its keep under strict statistical and budget gates:

| Capability Layer | Mechanism in Code | Acceptance Gate |
| :--- | :--- | :--- |
| **Order-Invariant Synthesis (`w40_search.py`)** | Canonical lexicographic candidate enumeration (`(cost, str(expr))`) with sketch deduplication and dual-budget early stopping (`B_exec = 500`, `B_total = 700.0`). | `100%` permutation invariance across `5` example/seed reorderings (`175/175` property tests). |
| **Cross-Domain Representation Priors (`w40_learn.py`)** | Leave-One-Domain-Out (LODO) operator cost tables and reusable macros learned from certified solutions on training domains. | Paired sign-flip permutation test (`p < 0.05`) on held-out domains before replacing uniform priors. |
| **Budgeted Online Adaptation (`w40_online.py`)** | Buffered stream learner (`K = 4`, hysteresis `tau = 0.10`) that updates priors online while charging every static row score (`C_ROW = 0.052`) and refit (`C_FIT = 2.0`). | Must reduce **total execution-equivalents** (including learning overhead) vs. `NoLearn` (`118.21` vs `138.62`, `-14.7%`). |
| **Counterexample-Guided Fault Localization (`w38_repair.py`, `de_template.py`)** | Isolates stage-level invariant failures (e.g., fan-out joins, arrival-order CDC apply, silent row drops, non-idempotent reruns) and synthesizes targeted repairs. | Zero regressions on previously passing batches (`b1`, `b2`, `b2_rerun`, `b2_crash`) and verified truth match. |
| **Active Clarification vs. Guessing (`outcome_contract.py`)** | Detects when multiple in-scope transformations or business rules satisfy the visible examples (`ASK_CLARIFICATION` / `UNDER_SPECIFIED_WARNING`). | Queries the stakeholder channel when available or abstains cleanly (`0` silent guesses on ambiguous specs). |

---

## 6. How NEXUS Stays Inexpensive

Autonomous engineering systems fail in practice if verification or meta-learning consumes unbounded compute. NEXUS enforces hardware-grounded cost discipline at every layer:

1. **Dual-Budget Accounting (`B_exec = 500`, `B_total = 700.0`):**
   Static scoring and prior refitting are not free. Every cost-table lookup (`C_ROW = 0.052` execution-equivalents, calibrated against CPU instruction ratios in `scripts/w40_calibrate.py`) and every online refit (`C_FIT = 2.0` execution-equivalents) is charged directly against the per-task budget.
2. **OS Kernel Retired-Instruction Metering (`src/nexus/wave31_evaluator.py`):**
   Subprocess workers report actual hardware retired CPU instructions via macOS `rusage_info_v4` (`ri_instructions`), preventing wall-clock noise from masking algorithmic bloat.
3. **Buffered Refits with Hysteresis (`K = 4`, `tau = 0.10`):**
   Instead of refitting after every task, `w40_online.py` batches solved episodes and only promotes a refitted prior if validation gain exceeds the hysteresis margin `tau = 0.10`.
4. **Surgical Stage Repair Over Full Rebuilds:**
   Because pipelines commit `Bronze`, `Silver`, and `Gold` stages with explicit contracts and lineage (`src/nexus/de_template.py`), faults localized to a downstream aggregation or currency conversion repair only the affected stage rather than re-ingesting raw sources.

---

## 7. The 10-Stage Engineering & Verification Roadmap

NEXUS progresses from its verified Wave 40 symbolic/transfer baseline (`46c3e53`) through a 10-stage engineering programme (detailed in [`docs/ROADMAP_10_STAGES.md`](docs/ROADMAP_10_STAGES.md)):

| Stage | Milestone | Core Verification Gate |
| :---: | :--- | :--- |
| **Stage 1** | **Baseline Freeze & Closed Outcome Contract** (`src/nexus/outcome_contract.py`, `scripts/de_stage1_regression.py`) | `228/228` tests passing (`222` Wave 40 + `6` Stage 1), 5 pinned checker SHA-256 digests intact, `0` false accepts. |
| **Stage 2** | **Logistics Data-Engineering Environment & Protected Evaluator** (`src/nexus/de_env.py`, `src/nexus/de_evaluator.py`) | Independent truth-vs-landing generator (`b1`, `b2`, `b2_rerun`, `b2_crash`) with `100%` soundness/completeness on clean vs. single-fault pipelines. |
| **Stage 3** | **Invariant-Guided Pipeline Synthesis & Repair vs. Naive Baseline** | Head-to-head comparison under matched budgets showing invariant-guided synthesis/repair eliminates silent corruption where naive exit-code-0 agents fail. |
| **Stage 4** | **Live Engines: CDC, Streaming & Lakehouse (`PostgreSQL`, `Debezium`, `Flink`, `Iceberg`)** | End-to-end exactly-once delivery across snapshot-to-stream transitions, out-of-order events, and schema evolution. |
| **Stage 5** | **Production Operations, Crash Recovery & Cost Control** | Automated incident diagnosis, idempotent backfill/replay after worker kill (`SIGKILL`), and cloud/query budget enforcement. |
| **Stage 6** | **Cross-Project Experience Reuse & Procedural Memory** | Verified reduction in total engineering cost (`B_total`) on new projects after charging all retrieval and validation overhead. |
| **Stage 7** | **Zero-Shot Transfer to Unfamiliar Enterprise Domains** | High certified completion rate (`0` silent corruptions) on held-out industry schemas and undocumented legacy sources (`Pool 2` holdouts). |
| **Stage 8** | **Autonomous Check & Operator Discovery** | Self-discovered validation checks and transformation operators that pass shadow-vault soundness gates without human authoring. |
| **Stage 9** | **Multi-Lineage Meta-Learning That Repays Discovery Cost** | End-to-end amortization: cumulative compute spent discovering better engineering procedures is repaid across unseen project streams. |
| **Stage 10** | **Sustained Autonomous Operations on Sealed External Workloads** | Single-shot confirmation on the sealed blind vault (`$NEXUS_SEALED_VAULT_DIR`) across all 7 scorecard measures. |

---

## 8. Unified 7-Measure Scorecard

Every stage is judged against all **7 measures simultaneously**—never by trading away soundness for completion or hiding learning overhead:

| # | Measure | Operational Definition | Non-Negotiable Requirement |
| :---: | :--- | :--- | :--- |
| **1** | **Correctness** | Rate of silent data corruption or false `CERTIFIED` / `COMPLETED_VERIFIED` claims on held-out truth checks. | **`0` false accepts** across all pinned checkers (`v1`–`v5`) and protected evaluators. |
| **2** | **Completion** | Fraction of tasks/projects reaching `VALID_UNIQUE` / `COMPLETED_VERIFIED` within budget (`B_exec`, `B_total`). | Monotonic or non-regressing improvement on held-out confirmation splits. |
| **3** | **Reliability** | Invariance to input/example permutation (`5` seeds), hash-seed determinism (`5` `PYTHONHASHSEED` values), idempotency (`b2_rerun`), and crash recovery (`b2_crash`). | **`100%` order invariance**; exact state convergence after crash and replay. |
| **4** | **Cost** | Total execution-equivalents (`exec_evals + 0.052*rows + 2.0*fits`), wall-clock time, and OS retired CPU instructions (`ri_instructions`). | Strictly within pre-allocated per-task and session ledger caps (`AGENTS.md`). |
| **5** | **Human Dependence** | Number of stakeholder clarifications requested (`ASK_CLARIFICATION`) and manual interventions required. | Ask **only** on genuinely under-determined rules; `0` unnecessary prompts on specified rules. |
| **6** | **Learning Benefit** | Net work/cost reduction (`Learned` vs `Uniform` / `NoLearn`) including all training, scoring, and refit costs. | Statistically significant (`p < 0.05` permutation gate) net savings on held-out tasks. |
| **7** | **Generalization** | Performance on held-out domains (`8`-domain LODO), unburned external benchmarks (`PROSE`), and unseen schema/fault pools (`Pool 2`). | Verified transfer without inspecting or tuning on confirmation/test pools (`BURNED` firewall). |

---

## 9. Verified Foundation (Baseline `46c3e53`)

All claims below are backed by committed artifacts in `artifacts/` and reproducible via the test and benchmark runners in `tests/` and `scripts/`:

| Subsystem / Benchmark | Metric | Verified Result | Artifact / Test Suite |
| :--- | :--- | :--- | :--- |
| **Pinned Checker Kernels (`v1`–`v5`)** | SHA-256 Digest Match & Differential Oracle Soundness | **`5/5` hashes intact (`622a29a`), `0` false accepts (`42/42` tests)** | [`tests/test_checker_kernel*.py`](tests/test_checker_kernel_v5.py) |
| **Search & Learning Order Invariance** | Identical Program & Eval Count across `5` Example Permutations | **`100%` (`175/175` tests; `16/16` LODO cells; `24/24` PROSE tasks)** | [`tests/test_search_order_invariance.py`](tests/test_search_order_invariance.py) ([`artifacts/w40_invariance.json`](artifacts/w40_invariance.json)) |
| **8-Domain LODO Synthesis (`80` confirm tasks)** | Certified Solve Rate & Mean Evals (`Learned` vs `Uniform`) | **`80.0%` (`64/80`) solved; `22.71` vs `58.59` evals (`-61.2%` work, `p = 0.0078`, `8/8` domains win)** | [`scripts/w40_lodo.py`](scripts/w40_lodo.py) ([`artifacts/w40_lodo.json`](artifacts/w40_lodo.json)) |
| **External Benchmark Transfer (`PROSE`)** | Unburned Confirmation Solve Rate (`24` unburned; `4` `BURNED`) | **`79.2%` (`19/24` unburned; `0` false accepts)** (`23/28 = 82.1%` all-task ref) | [`scripts/w40_prose.py`](scripts/w40_prose.py) ([`artifacts/w40_prose.json`](artifacts/w40_prose.json)) |
| **Budgeted Online Stream Learning (`16` streams)** | Total Execution-Equivalent Cost (`exec + 0.052*rows + 2.0*fits`) | **`118.21` (`Buffered K=4`) vs `138.62` (`NoLearn`) (`-14.7%`, `16/16` streams win)** | [`scripts/w40_online.py`](scripts/w40_online.py) ([`artifacts/w40_online.json`](artifacts/w40_online.json)) |
| **Non-Stationary World (`N1-merge-exact`)** | Change-Point Recall, False Alarms / 1000, Delay, Full-2000 Acc | **Recall `1.000`, FAR `0.0/1000` (`<= 0.10`), Delay `11.1` steps, Acc `0.9467` (`96.2%` of oracle)** | [`src/nexus/w39_world.py`](src/nexus/w39_world.py) ([`artifacts/w39_world.json`](artifacts/w39_world.json)) |
| **Stage 1 Unified Regression Gate** | Wave 40 Core (`222` tests) + Stage 1 Outcome Contract (`6` tests) | **`228/228` passing (`100%`), `0` failures** | [`scripts/de_stage1_regression.py`](scripts/de_stage1_regression.py) ([`artifacts/de_stage1_regression.json`](artifacts/de_stage1_regression.json)) |

---

## 10. Repository Structure & Quickstart

### 10.1 Directory Layout

```text
nexus-ai/
├── README.md                          # NEXUS Data Platform overview, architecture, roadmap & scorecard
├── AGENTS.md                          # Scientific integrity firewall, pinned SHA-256 hashes & BURNED registry
├── pyproject.toml                     # Package configuration & pytest settings
├── src/
│   └── nexus/
│       ├── checker_kernel.py          # Pinned Checker Kernel v1 (+ .sha256)
│       ├── checker_kernel_v2.py       # Pinned Checker Kernel v2 (+ .sha256)
│       ├── checker_kernel_v3.py       # Pinned Checker Kernel v3 (+ .sha256)
│       ├── checker_kernel_v4.py       # Pinned Checker Kernel v4 (+ .sha256)
│       ├── checker_kernel_v5.py       # Pinned Checker Kernel v5 (+ .sha256, frozen at 622a29a)
│       ├── outcome_contract.py        # Stage 1 closed outcome contract (VALID_UNIQUE / ASK_CLARIFICATION / ...)
│       ├── de_env.py                  # Stage 2 logistics data-engineering environment (truth vs messy landing)
│       ├── de_evaluator.py            # Stage 2 protected operational evaluator (b1, b2, b2_rerun, b2_crash)
│       ├── de_template.py             # Stage 2/3 bronze-silver-gold pipeline generator & decision space
│       ├── w40_search.py              # Order-invariant synthesis engine (B_exec=500, B_total=700)
│       ├── w40_learn.py               # Order-invariant LODO representation & macro learner
│       ├── w40_online.py              # Dual-budget buffered online stream learner (K=4, tau=0.10)
│       ├── w40_eval.py                # Wave 40 subprocess evaluation harness
│       ├── w39_lang.py                # Extended string/record transformation IR & AST primitives
│       ├── w39_prose.py               # External Microsoft PROSE benchmark loader & BURNED quarantine
│       ├── w39_world.py               # N1-merge-exact non-stationary change-point detector
│       ├── w38_domains.py             # 8-domain synthetic task & metamorphic invariant generators
│       ├── w38_repair.py              # Stage-level fault localization & 1-edit program repair
│       ├── wave31_evaluator.py        # Isolated subprocess sandbox & macOS ri_instructions meter
│       └── wave32_detectors.py        # 5 anti-cheat detectors (D1-D5)
├── tests/
│   ├── test_checker_kernel*.py        # 42 tests verifying pinned SHA-256 digests & differential oracles
│   ├── test_search_order_invariance.py# 175 permutation invariance tests (search, LODO, PROSE)
│   ├── test_w40_components.py         # 5 Wave 40 component & dual-budget accounting tests
│   └── test_stage1_regression.py      # 6 Stage 1 outcome contract & regression gate tests
├── scripts/
│   ├── de_stage1_regression.py        # Unified 228-test + SHA-256 + scorecard regression runner
│   ├── de_budget.py                   # Session budget ledger & cost-accounting utility
│   ├── w40_invariance.py              # Reproduces artifacts/w40_invariance.json
│   ├── w40_lodo.py                    # Reproduces artifacts/w40_lodo.json
│   ├── w40_online.py                  # Reproduces artifacts/w40_online.json
│   ├── w40_prose.py                   # Reproduces artifacts/w40_prose.json
│   └── archive/                       # 43 archived historical wave drivers (Waves 27–39)
├── docs/
│   ├── INDEX.md                       # Complete documentation index
│   ├── ARCHITECTURE.md                # System block diagram, module map & data quarantine spec
│   ├── ROADMAP_10_STAGES.md           # 10-Stage Autonomous Data Engineering Roadmap & 7-Measure Scorecard
│   ├── NEXUS_WAVE40_INVARIANCE_AND_CEILINGS.md
│   ├── NEXUS_WAVE39_EXTERNAL_TRANSFER.md
│   ├── NEXUS_CHECKER_V2_SPEC.md .. NEXUS_CHECKER_V5_SPEC.md
│   └── history/                       # Archived intermediate wave reports (Waves 26–37)
└── artifacts/
    ├── w40_invariance.json
    ├── w40_lodo.json
    ├── w40_online.json
    ├── w40_prose.json
    └── de_stage1_regression.json
```

### 10.2 Quickstart Commands

```bash
# 1. Run the unified Stage 1 + Wave 40 regression gate (228 tests + pinned SHA-256 verification)
PYTHONPATH=src .venv/bin/python scripts/de_stage1_regression.py

# 2. Run pytest directly across the core verification and invariance suites
PYTHONPATH=src .venv/bin/pytest \
  tests/test_checker_kernel.py \
  tests/test_checker_kernel_v2.py \
  tests/test_checker_kernel_v3.py \
  tests/test_checker_kernel_v4.py \
  tests/test_checker_kernel_v5.py \
  tests/test_search_order_invariance.py \
  tests/test_w40_components.py \
  tests/test_stage1_regression.py -q

# 3. Reproduce Wave 40 benchmark artifacts
PYTHONPATH=src .venv/bin/python scripts/w40_invariance.py
PYTHONPATH=src .venv/bin/python scripts/w40_lodo.py
PYTHONPATH=src .venv/bin/python scripts/w40_prose.py
PYTHONPATH=src .venv/bin/python scripts/w40_online.py
```

### 10.3 Further Reading
- **Architecture & Module Map:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **10-Stage Roadmap & 7-Measure Scorecard:** [`docs/ROADMAP_10_STAGES.md`](docs/ROADMAP_10_STAGES.md)
- **Complete Documentation Index:** [`docs/INDEX.md`](docs/INDEX.md)
- **Operational Safeguards & Pinned Hashes:** [`AGENTS.md`](AGENTS.md)
