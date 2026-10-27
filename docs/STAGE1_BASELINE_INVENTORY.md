# Stage 1 Baseline Inventory (NOT LOCKED)

**Starting revision:** `46c3e53` on `codex/nexus-broader-programme`. Branch `codex/nexus-data-engineering` was created
from it.

**Paused work.** Before branching, the paused Wave 41 work was preserved in commit `84091eb` on
`codex/nexus-broader-programme`. It contains dev-only code and artifacts. No Wave 41 confirmation seed was claimed, no
sealed Split.Text file was opened, and its draft freeze is not a freeze. That work is **not** part of this branch.

**Untouched:** `main`; `final_sealed`; Checkers v1–v5 and their pins.

## A. Implemented and verified at `46c3e53` (reusable)

| Component | Module(s) | Verified by | Notes |
| --- | --- | --- | --- |
| Completeness-fixed search (state dominance) | `w40_search.py` (`min_depth_seen[values]`: a state is re-expanded when a strictly shorter route arrives) | `tests/test_search_order_invariance.py` **175/175** (84 problems × orderings vs brute force; byte-identical v5 certificates; detects the old defect in 54 problem × ordering pairs) | Wave 39 modules kept unchanged for reproducibility |
| Checker kernels v1–v5, read-only (RULE 2) | `checker_kernel*.py` | `test_checker_kernel*.py` (4 + 14 + 13 + 5 + 6 tests); pins v1 `5082402f…`, v2 `6ba0a268…`, v3 `3c68230e…`, v4 `c07e21ec…`, **v5 `2cd3a4ca…` (commit `622a29a`)** | v5 output contract: SCOPE_UNIQUE / AMBIGUOUS / ABSTAIN + per-extra-input answer counts + UNDER_SPECIFIED_WARNING |
| Witness short-circuit, O(T) learned cost rows | `w40_eval.py`, `w40_learn.py` | `tests/test_w40_components.py` 5/5 | Witness shortcut sound (0 unsound in Wave 40 C3) |
| Learned priors and memory ledgers | `w40_learn.py` (Repr, Fixed+Repr), `w39_online.py` / `w40_online.py` (Hierarchical Stream Memory, payoff gate) | Wave 40 C1 / C2 confirmations | Measured benefit is internal and small (see the Wave 40 matrix) |
| **N1-merge-exact** change detection | `w39_world.py` (`N1Lite`) | Wave 39 C3: cheap adaptation PROVED (2.8× fixed-model compute, return 1.003× N1, 5/5 seeds) | It detects **regime changes in the world testbed**, not data drift. Its reuse for pipeline drift alarms is a Stage 5 *proposal* |
| Meters | `wave31_evaluator.instructions` (OS retired instructions via `proc_pid_rusage`), wall clock, `getrusage` CPU and RSS | Every Wave 31–40 ledger row | A measured process cannot alter the counter |
| Sandboxed runners | `wave31_evaluator.Child` (`sandbox-exec`: no writes under the repo, no vault reads, no network) | Waves 31–40 | Isolation for honest code; per the reuse map, **not a hostile-code security sandbox** |
| Seed hygiene, ledger, vault firewall | `seed_registry.py`, hash-chained `ledger_append`, `sealed_vault_loader.py`, `standing_gates.install_vault_audit_hook` | `tests/conftest.py` hook in every pytest session | One-use ranges are recorded in `runs/experimental/seed_registry_spent.jsonl` |

## B. Added in Stages 1–3 on this branch (NOT LOCKED)

| Component | Module | Purpose |
| --- | --- | --- |
| Outcome contract | `src/nexus/outcome_contract.py` | One closed outcome vocabulary over v5's verdict, so that VALID_UNIQUE, ABSTAIN_ERROR, UNDER_SPECIFIED_WARNING, ASK_CLARIFICATION and ABSTAIN_UNSUPPORTED are never conflated. v5 itself stays unmodified. **Correction:** at `46c3e53`, `ABSTAIN_ERROR` and `ASK_CLARIFICATION` did not exist, and v5 counts an ERROR answer on a future input as one unique answer (Wave 40 UserAgent.000007). The new layer separates these cases (test below) |
| Logistics environment | `src/nexus/de_env.py` | Truth world plus messy encodings (Stage 2) |
| Protected evaluator and stakeholder oracle | `src/nexus/de_evaluator.py` | Independent reference, fault diagnosis, four-state protocol (Stage 2) |
| Shared pipeline generator | `src/nexus/de_template.py` | 14 decisions; standalone stdlib pipelines |
| NEXUS invariants | `src/nexus/de_checks.py` | Metamorphic, operational and conformance checks; ambiguity coverage |
| Engineering agents | `src/nexus/de_agent.py` | Metered tools; Conventional vs NEXUS (Stage 3) |

## C. Proposed (Stages 4–10): not built, not measured

These are design proposals only; no claim is made about them:
* streaming offsets and exactly-once sinks;
* schema registry and backfills;
* incident operations and N1-based drift alarms;
* cross-project memory;
* new domains and engines;
* open-ended code generation;
* self-evolution.

See `docs/NEXUS_10_STAGE_ROADMAP.md`.

## D. Historical claims affected by the pre-Wave-40 state-dominance defect

The defect lived in the Wave 38/39 search (`w38_search` / `w39_search`). It was repaired in Wave 40 (`w40_search`), and the
repair is in `46c3e53`.

| Historical claim | Status (unchanged from the Wave 40 Step 1 audit) |
| --- | --- |
| W38 E3 "Fixed DSL cheaper but loses 10 solves (149/160)" | **RETRACTED (artifact):** all 10 losses were traced to the defect. The cost comparison is also void (truncated search was charged) |
| W39 C2 "Fixed-v5 344 vs 346" | **RETRACTED (artifact)** |
| W39 C4 "Hierarchical Stream Memory −3 solves, NEGATIVE" | **RETRACTED (artifact);** re-tested in Wave 40 C2 (lost solves eliminated) |
| W39 C2 Placebo-v5 solve losses | not an artifact claim (no loss at full budget) |
| W38 E1 "Fixed DSL cheaper at equal solves", W38 E6 regime memory, W39 C1 PROSE rows | **QUALIFIED (provisional):** Fresh / uniform numbers stand (identical search under a uniform prior, tested); costs of non-uniform arms may shift |
| Claims depending on v4 `None` handling | not affected (332 exact differentials, 0 verdicts changed) |

## E. Stage 1 regression and distinguishability verification

Command: `scripts/de_stage1_regression.py`. Results are in `artifacts/de_stage1_regression.json` (per-file sha256, JUnit
counts).

| Suite | Tests | Result |
| --- | --- | --- |
| Search-order invariance (state-dominance repair) | 175 | 175 pass |
| Wave 40 components | 5 | 5 pass |
| Checker kernel v1 / v2 / v3 / v4 / v5 | 4 / 14 / 13 / 5 / 6 | all pass |
| Stage 1 outcome contract (`tests/test_stage1_regression.py`) | 6 | 6 pass |
| **Total** | **228** | **228 pass (100%)** |

**Distinguishability cases, each built from Checker v5's real verdict:**
* SCOPE_UNIQUE gives VALID_UNIQUE.
* An ERROR answer on a future input gives ABSTAIN_ERROR (raw v5 says `answers: 1`).
* A query whose candidate errors gives ABSTAIN_ERROR (v5 `candidate_fails`).
* Two or more in-scope answers give UNDER_SPECIFIED_WARNING, or ASK_CLARIFICATION when a stakeholder channel exists.
* AMBIGUOUS gives the same as two or more answers.
* An unsupported operation gives ABSTAIN_UNSUPPORTED.

Only VALID_UNIQUE (for inputs) and COMPLETED_VERIFIED (for projects) may be presented as checked results.

**Matched-arm condition:** the invariance suite shows that every search ordering reaches the identical solution set with
identical certificates. In Stage 3, both arms use the identical generator, proposer permutation, tools and caps
(`tests/test_de_stage3.py::test_arms_share_generator_proposer_and_caps`).
