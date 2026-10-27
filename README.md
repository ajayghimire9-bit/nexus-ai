# NEXUS — Verifiable Program Synthesis, Meta-Learning & Autonomous Data Engineering

NEXUS is a verifiable program synthesis, cross-domain meta-learning, and autonomous data engineering system built around a strict architectural boundary: **untrusted search and learning components may propose candidate programs, but only an independently implemented, cryptographically hash-pinned verification kernel (`checker_kernel_v1`–`v5`) can certify them.**

---

## 1. Core Design Principles

1. **Pinned Verification Boundary (`src/nexus/checker_kernel*.py`):**
   Every checker kernel (`v1` through `v5`) is a zero-internal-import specification verifier whose exact file bytes are SHA-256 pinned (at commit `622a29a`) and verified before every test and benchmark run. Solver and learning modules share zero code with the checker kernel.
2. **Search-Order & Input-Permutation Invariance (`src/nexus/w40_search.py`, `src/nexus/w40_learn.py`):**
   Candidate enumeration, sketch deduplication, and LODO representation learning use canonical lexicographic tie-breaking (`(cost, str(expr))`). Permuting input-output examples or dictionary iteration order produces the exact same certified program and evaluation count (`175/175` invariance tests).
3. **Strict Data Quarantine (`dev` / `val` / `confirm` / `BURNED` / `final_sealed`):**
   Development (`dev`), validation (`val`), and confirmation (`confirm`) splits are strictly separated. Any external benchmark task inspected during grammar or operator design is permanently logged as `BURNED` (`BillingCode.000002`, `EmergencyCall.000004`, `FilePath.000001`, `UserAgent.000007`) and excluded from confirmation claims. The sealed blind vault (`final_sealed`) is isolated outside the working tree via `$NEXUS_SEALED_VAULT_DIR`.
4. **Hardware-Grounded Dual-Budget Accounting (`B_exec = 500`, `B_total = 700.0`):**
   Every synthesis and online learning episode enforces both a candidate execution ceiling (`B_exec = 500`) and a total work ceiling (`B_total = 700.0` execution-equivalents), charging `C_ROW = 0.052` per static cost-row evaluation and `C_FIT = 2.0` per online prior refit, alongside macOS kernel retired CPU instruction counts (`rusage_info_v4.ri_instructions`) inside a 5-detector subprocess sandbox.
5. **Canonical 4-State Outcome Contract (`src/nexus/outcome_contract.py`):**
   Every task execution resolves to one of four mutually exclusive, cryptographically receipted states: `CERTIFIED`, `REPAIRED`, `ABSTAINED`, or `REJECTED`.

---

## 2. Current Verified Scorecard (Baseline `46c3e53` / Wave 40 + Stage 1)

| Subsystem / Benchmark | Metric | Verified Result (`46c3e53`) | Verification Artifact / Test |
| :--- | :--- | :--- | :--- |
| **Pinned Checker Kernels (`v1`–`v5`)** | SHA-256 Integrity & False Accepts | **`5/5` hashes intact, `0` false accepts** (`42/42` differential & mutation tests) | `tests/test_checker_kernel*.py` |
| **Search & Learning Order Invariance** | Identical Output & Eval Count across `5` Example Permutations | **`100%` (`175/175` tests; `16/16` LODO cells; `24/24` PROSE tasks)** | `tests/test_search_order_invariance.py` (`artifacts/w40_invariance.json`) |
| **8-Domain LODO Synthesis (`80` confirm tasks)** | Certified Solve Rate & Mean Evaluations (`Learned` vs `Uniform`) | **`80.0%` (`64/80`) solved; `22.71` vs `58.59` evals (`-61.2%` work, `p = 0.0078`, `8/8` domains win)** | `scripts/w40_lodo.py` (`artifacts/w40_lodo.json`) |
| **External Benchmark Transfer (`PROSE`)** | Unburned Confirmation Solve Rate (`24` unburned tasks; `4` `BURNED`) | **`79.2%` (`19/24` unburned; `0` false accepts)** (`23/28 = 82.1%` all-task reference) | `scripts/w40_prose.py` (`artifacts/w40_prose.json`) |
| **Budgeted Online Stream Learning (`16` streams)** | Total Execution-Equivalent Cost (`exec + 0.052*rows + 2.0*fits`) | **`118.21` (`Buffered K=4`) vs `138.62` (`NoLearn`) (`-14.7%`, `16/16` streams win)** | `scripts/w40_online.py` (`artifacts/w40_online.json`) |
| **Non-Stationary World (`N1-merge-exact`)** | Change-Point Recall, False Alarms / 1000, Delay, Full-2000 Accuracy | **Recall `1.000`, FAR `0.0/1000` (`<= 0.10`), Delay `11.1` steps, Acc `0.9467` (`96.2%` of oracle)** | `src/nexus/w39_world.py` (`artifacts/w39_world.json`) |
| **Stage 1 Unified Regression Gate** | Core Wave 40 (`222`) + Stage 1 Outcome Contract (`6`) | **`228/228` passing (`100%`), `0` failures** | `scripts/de_stage1_regression.py` (`artifacts/de_stage1_regression.json`) |

---

## 3. Repository Structure

```text
nexus-ai/
├── README.md                          # Project overview, verified scorecard & quickstart
├── AGENTS.md                          # Scientific integrity firewall, pinned hashes & BURNED registry
├── pyproject.toml                     # Python package & pytest configuration
├── src/
│   └── nexus/
│       ├── checker_kernel.py          # Pinned Checker Kernel v1 (+ .sha256)
│       ├── checker_kernel_v2.py       # Pinned Checker Kernel v2 (+ .sha256)
│       ├── checker_kernel_v3.py       # Pinned Checker Kernel v3 (+ .sha256)
│       ├── checker_kernel_v4.py       # Pinned Checker Kernel v4 (+ .sha256)
│       ├── checker_kernel_v5.py       # Pinned Checker Kernel v5 (+ .sha256, frozen at 622a29a)
│       ├── outcome_contract.py        # Canonical 4-state contract (CERTIFIED/REPAIRED/ABSTAINED/REJECTED)
│       ├── w40_search.py              # Order-invariant synthesis engine with dual-budget early stop
│       ├── w40_learn.py               # Canonical LODO representation & macro learner
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
│   ├── de_budget.py                   # Dual-budget calibration & verification utility
│   ├── w40_invariance.py              # Reproduces artifacts/w40_invariance.json
│   ├── w40_lodo.py                    # Reproduces artifacts/w40_lodo.json
│   ├── w40_online.py                  # Reproduces artifacts/w40_online.json
│   ├── w40_prose.py                   # Reproduces artifacts/w40_prose.json
│   └── archive/                       # Archived historical one-off wave drivers (Waves 27–39)
├── docs/
│   ├── INDEX.md                       # Complete documentation index
│   ├── ARCHITECTURE.md                # System block diagram, module map & data quarantine spec
│   ├── ROADMAP_10_STAGES.md           # 10-Stage Autonomous Data Engineering Roadmap & 7-Measure Scorecard
│   ├── NEXUS_WAVE40_INVARIANCE_AND_CEILINGS.md
│   ├── NEXUS_WAVE39_EXTERNAL_TRANSFER.md
│   ├── NEXUS_CHECKER_V2_SPEC.md .. NEXUS_CHECKER_V5_SPEC.md
│   └── history/                       # Archived historical wave reports (Waves 26–37)
└── artifacts/
    ├── w40_invariance.json            # Verified Wave 40 invariance results
    ├── w40_lodo.json                  # Verified Wave 40 8-domain LODO results
    ├── w40_online.json                # Verified Wave 40 budgeted online results
    ├── w40_prose.json                 # Verified Wave 40 external PROSE transfer results
    └── de_stage1_regression.json      # Verified Stage 1 regression & contract receipt
```

---

## 4. Quickstart & Reproducibility

### 4.1 Run the Core Wave 40 + Stage 1 Test Suite (`228` Tests)
```bash
PYTHONPATH=src .venv/bin/pytest \
  tests/test_checker_kernel.py \
  tests/test_checker_kernel_v2.py \
  tests/test_checker_kernel_v3.py \
  tests/test_checker_kernel_v4.py \
  tests/test_checker_kernel_v5.py \
  tests/test_search_order_invariance.py \
  tests/test_w40_components.py \
  tests/test_stage1_regression.py -q
```

### 4.2 Run the Unified Stage 1 Regression Gate (Tests + Pinned SHA-256 Check + Scorecard Verification)
```bash
PYTHONPATH=src .venv/bin/python scripts/de_stage1_regression.py
```

### 4.3 Reproduce Wave 40 Benchmark Artifacts
```bash
PYTHONPATH=src .venv/bin/python scripts/w40_invariance.py
PYTHONPATH=src .venv/bin/python scripts/w40_lodo.py
PYTHONPATH=src .venv/bin/python scripts/w40_prose.py
PYTHONPATH=src .venv/bin/python scripts/w40_online.py
```

---

## 5. Documentation & Next Horizon

- **System Architecture & Module Map:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **10-Stage Autonomous Data Engineering Roadmap & 7-Measure Scorecard:** [`docs/ROADMAP_10_STAGES.md`](docs/ROADMAP_10_STAGES.md)
- **Full Documentation Index:** [`docs/INDEX.md`](docs/INDEX.md)
- **Agent Operational & Anti-Cheat Rules:** [`AGENTS.md`](AGENTS.md)
