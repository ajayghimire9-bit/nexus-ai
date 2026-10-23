# NEXUS Seed — Equalized, Call-Metered Learned Investigation Policy Results v2 (`seed-learned-investigation-policy-v2`)

## 1. Executive Summary & Audit Corrections Over `v1`

Executed from clean pre-registered revision `c35252a` on `codex/seed-symbiotic-workbench-v1` ([Protocol](NEXUS_SEED_LEARNED_INVESTIGATION_POLICY_V2_PROTOCOL.md), [`v1` Audit](NEXUS_SEED_LEARNED_INVESTIGATION_POLICY_V1_AUDIT.md), [Config](../configs/seed_learned_investigation_policy_v2.json)), this study preserves `artifacts/seed_learned_investigation_policy_v1/` untouched while withdrawing the confounded `v1` learning-to-learn claim and implementing all five structural repairs:

1. **100% Equalized Controller Bounds Across All Active Policies (`EqualizedControllerConfig`)**:
   - Every active policy (`untrained_default_active`, `simple_frequency_active`, `fixed_infogain_active`, `learned_ranker_only_active`, `learned_policy_random_curr_active`, `learned_policy_curriculum_active`, and `strategy_reset_active`) runs under the **exact same**:
     - `shortlist_limit = 3`
     - `allow_questions = True`
     - `max_questions_per_task = 2`
     - `probe_min_disagreement_ratio = 0.15`
   - Resetting the learned strategy (`strategy_reset_active`) resets **only** the learned weights $\phi = (\phi_{\text{rank}}, \phi_{\text{probe}}) \to \phi_0$ while **keeping `allow_questions = True` and `shortlist_limit = 3`**.
   - Passive controls (`allow_questions = False`) are evaluated separately in Section 4 (`untrained_passive_no_questions` vs `learned_ranker_passive_no_questions`).

2. **Full Call-Level Metering (`EpisodeCallLedger`)**:
   - Every single candidate function call `fn(inp)`—across initial support filtering (`support_check_calls`) and active probe construction (`probe_construction_calls`)—is metered in `n_candidate_calls` (`n_candidate_calls = support_check_calls + probe_construction_calls`) and recorded in `candidate_call_log`.
   - Objective weights: $\lambda_q = 0.08$, $\lambda_e = 0.01$ (per individual `fn(inp)` call), $\lambda_t = 0.10$.

3. **Strict Disjointness of Source Acquisition, Support, Probe Pool, and Held-Out Assessment**:
   - Across all 64 tasks (`32` training pool + `8` 2-step source acquisition + `24` 3-step/repo assessment), `support_examples`, `probe_pool_inputs`, and `assessment_inputs` are verified to be **100% pairwise disjoint** (`all_pairwise_disjoint = true`).
   - Source skills are acquired by actually solving 8 disjoint **2-step** source tasks (`src01..src08`) via `investigate_v2(..., consolidate_on_solve=True)` and transferred as **2-step compositional prefix macros (`cap(op1 -> op2) + op3`)** onto unseen **3-step** assessment tasks (`ex01..ex16`). Zero tasks or target programs overlap between `source_tasks` and `excluded_tasks`.

4. **Reconstructing, Tamper-Rejecting Verifier (`scripts/verify_seed_learned_investigation_policy_v2.py`)**:
   - Re-executes every logged call and oracle answer, re-simulates the deterministic controller to verify call counts and question counts cannot be omitted or zeroed out, recomputes all summary tables from raw episode records, and passes all 3 adversarial tamper self-tests (`v1_zero_cost_exploit_rejected = true`, `summary_table_tamper_rejected = true`, `outcome_flip_tamper_rejected = true`).

5. **Real System Integration (Live Local GGUF Runtime + Bounded Subprocess Repository Verification)**:
   - All 8 multi-file Python repository repair tasks (`repo17..repo24`) are verified inside the isolated bounded worker (`src/nexus/seed/agent_loop_worker.py`), and a live local GGUF inference probe (`qwen2.5-0.5b-instruct-q4_k_m.gguf` via `PersistentLocalRuntime`) is recorded with full token/timing telemetry.

---

## 2. Outer Training Cost Accounting (`CurriculumGenerator` vs `random_sampling`)

| Outer Training Mode | Budget Tasks | Generator Calls | Total Outer Candidate Calls | Outer Oracle Questions | Outer Wall (s) | Outer Objective Debit |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `curriculum` (`CurriculumGenerator`) | 8 | 288 | 912 | 8 | 0.001815 | 9.760181 |
| `random_sampling` | 8 | 0 | 536 | 2 | 0.000505 | 5.520050 |

---

## 3. Equalized Active Comparison (24 Excluded Unfamiliar Tasks, Capsules Cleared, Identical Controller Rules)

All 7 active configurations below run with `active_capsules == 0`, `shortlist_limit = 3`, `allow_questions = True`, and `max_questions_per_task = 2`:

| Active Policy Configuration (`shortlist=3, questions=True`) | Solved (`24`) | Seq Solved (`16`) | Repo Solved (`8`) | Support Check Calls | Probe Construction Calls | **Total Candidate Calls** | Mean Calls / Task | Total Questions ($N_q$) | Mean Objective $J(\phi)$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `untrained_default_active` ($\phi_0$) | 23 / 24 | 15 / 16 | 8 / 8 | 455 | 410 | **865** | 36.0417 | 19 | 0.465431 |
| `fixed_infogain_active` (brute-force entropy) | 23 / 24 | 15 / 16 | 8 / 8 | 455 | 410 | **865** | 36.0417 | 19 | 0.465433 |
| `simple_frequency_active` ($\phi_{\text{freq}}$) | 24 / 24 | 16 / 16 | 8 / 8 | 413 | 410 | **823** | 34.2917 | 19 | 0.406264 |
| `learned_ranker_only_active` ($\phi_{\text{rank}}$ only) | 24 / 24 | 16 / 16 | 8 / 8 | 397 | 410 | **807** | 33.6250 | 19 | 0.399600 |
| `learned_policy_random_curr_active` ($\phi_{\text{rank}}+\phi_{\text{probe}}$, random) | 24 / 24 | 16 / 16 | 8 / 8 | 447 | 70 | **517** | 21.5417 | 19 | 0.278762 |
| **`learned_policy_curriculum_active`** ($\phi_{\text{rank}}+\phi_{\text{probe}}$, curriculum) | **24 / 24** | **16 / 16** | **8 / 8** | **397** | **70** | **467** | **19.4583** | **19** | **0.257929** |
| `strategy_reset_active` ($\phi \to \phi_0$, `questions=True`) | 23 / 24 | 15 / 16 | 8 / 8 | 455 | 410 | **865** | 36.0417 | 19 | 0.465431 |

### Why Each Learned Mechanism Contributes Under Equalized Rules
1. **Learned Behavioral Ranker ($\phi_{\text{rank}}$: `455` $\to$ `397` support check calls, `23/24` $\to$ `24/24` solved)**:
   - Because `v2` ticket descriptions use realistic domain-opaque wording without operator keyword spoilers, `AlgebraicPropertySynthesizer` extracts input-output transition features $\psi(D_{\text{support}})$ and $\phi_{\text{rank}}$ prioritizes the target composition and its boundary foils ahead of distractors, cutting `support_check_calls` from `455` (`untrained_default_active` / `fixed_infogain_active`) to `397` (and outperforming `learned_policy_random_curr_active` at `447` support calls, because `CurriculumGenerator` covered all 8 behavioral families while `random_sampling` wasted budget on repetitive tasks).
2. **Learned Amortized Probe Selector ($\phi_{\text{probe}}$: `410` $\to$ `70` probe construction calls)**:
   - Without $\phi_{\text{probe}}$, `fixed_infogain_active` and `learned_ranker_only_active` must evaluate all 8 candidate probes across surviving candidates (`410` metered `probe_construction_calls`) to compute version-space entropy.
   - With $\phi_{\text{probe}}$, the learner identifies during training that probes `P6` and `P7` (negative + zero + duplicate boundary probes) partition confusable survivors on the first check, reducing `probe_construction_calls` by **82.93%** (`410` $\to$ `70`) and total metered candidate calls by **46.01%** (`865` $\to$ `467`).
3. **Equalized Strategy Reset (`strategy_reset_active`)**:
   - Resetting $\phi \to \phi_0$ while **keeping `allow_questions = True` and `shortlist_limit = 3`** reverts total candidate calls from `467` back to **`865`** (`455` support + `410` probe calls) and $J(\phi)$ from `0.257929` back to **`0.465431`**, matching `untrained_default_active` identically.

---

## 4. Separate Passive Factorial Controls (`allow_questions = False`)

| Passive Control Configuration (`shortlist=3, questions=False`) | Solved (`24`) | Seq Solved (`16`) | Repo Solved (`8`) | Total Candidate Calls | Total Questions ($N_q$) | Mean Objective $J(\phi)$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `untrained_passive_no_questions` ($\phi_0$) | 7 / 24 | 7 / 16 | 0 / 8 | 455 | 0 | 0.814589 |
| `learned_ranker_passive_no_questions` ($\phi_{\text{rank}}$) | 16 / 24 | 9 / 16 | 7 / 8 | 397 | 0 | 0.488342 |

This $2 \times 2$ separation shows both contributions independently:
- Without questions (`allow_questions = False`), learning $\phi_{\text{rank}}$ improves solve rate from `7/24` to `16/24` and reduces support calls from `455` to `397`, but `8/24` tasks remain unsolvable without an active boundary query because confusable foils agree on initial positive support examples.
- With questions enabled (`allow_questions = True`), active querying resolves the boundary ambiguity (`23/24` for unlearned $\phi_0$, `24/24` for learned $\phi$), and learning $(\phi_{\text{rank}}, \phi_{\text{probe}})$ cuts total metered candidate calls from `865` to `467`.

---

## 5. Autonomous Source Skill Acquisition (`src01..src08`) $\to$ Compositional Prefix Transfer

1. **Phase A — Autonomous Source Skill Acquisition (`source_skill_acquisition`)**:
   - NEXUS investigated 8 disjoint **2-step** source tasks (`src01..src08`), solving **8 / 8** in `131` candidate calls (`119` support + `12` probe) and `4` oracle questions, and consolidating **8 verified 2-step capsules** (`cap(op1 -> op2)`).
2. **Phase B — Compositional Prefix Transfer onto Unseen 3-Step & Repository Assessment Tasks**:

| Compositional Transfer Configuration (`shortlist=3, questions=True`) | Solved (`24`) | 2-Step Prefix Reuses | Support Check Calls | Probe Construction Calls | **Total Candidate Calls** | Total Questions ($N_q$) | Mean Objective $J(\phi)$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `skills_only_untrained_active` (`8` 2-step capsules, $\phi_0$) | 24 / 24 | 10 | 410 | 378 | **788** | 19 | 0.391680 |
| `strategy_only_capsules_cleared_active` (`0` capsules, $\phi^*$) | 24 / 24 | 0 | 397 | 70 | **467** | 19 | 0.257927 |
| **`combined_dual_engine_compositional_prefix_active`** (`8` capsules + $\phi^*$) | **24 / 24** | **10** | **368** | **63** | **431** | **19** | **0.242928** |

---

## 6. Live Local GGUF Model Probe & Bounded Worker Verification

- **Bounded Worker Repository Verification**: All 8 multi-file Python repository repair tasks (`repo17..repo24`) passed held-out verification inside `agent_loop_worker.py` (`worker_verified = true`).
- **Live Local GGUF Model Probe (`PersistentLocalRuntime`, `.models/qwen2.5-0.5b-instruct-q4_k_m.gguf`)**:
  - Executed live inference (`inference_ran = true`, `input_tokens = 128`, `generated_tokens = 128`, `wall_s = 2.793933 s`, `71.91 tokens/s`) on `repo17_billing_adjustment`. While the local model can propose plausible code edits (`max(0, extra)` vs `abs(extra)`), the opaque ticket text alone does not specify which negative-adjustment convention holds in the target environment—confirming why active environment probing (`MechanismBActiveEnvironment`) is required to disambiguate surviving candidate patches.

---

## 7. Independent Verification, Claim Discipline & Ledger

- **Verifier (`scripts/verify_seed_learned_investigation_policy_v2.py`)**:
  - `valid = true`, `mismatches = []`
  - `v1_zero_cost_exploit_rejected = true`
  - `summary_table_tamper_rejected = true`
  - `outcome_flip_tamper_rejected = true`
- **Resource Accounting & Standing Ledger**:
  - Total wall time (including live GGUF model probe and bounded worker runs): `3.173751 s` (`4.0 s` debit against the standing Seed budget)
  - Total CPU time: `0.252281 s`
  - Peak RSS: `37.016 MB`
  - Updated standing ledger: `2210.632103455996 s` used / `1389.367896544004 s` remaining.
- **Claim Discipline**:
  - Establishes that under equalized shortlist and questioning rules with full call-level metering and disjoint input sets, learning behavioral ranking weights ($\phi_{\text{rank}}$) and amortized probe selection weights ($\phi_{\text{probe}}$) reduces candidate evaluations on held-out sequence compositions and template-structured repository repairs (`865` $\to$ `467` calls, and `431` with 2-step compositional prefix transfer).
  - Does **not** establish open-ended learning-to-learn across arbitrary unconstrained software repositories, unrestricted neural language acquisition, or AGI (`agi = false`), and does not include a live Gemini API comparison.
