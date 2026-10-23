# NEXUS Seed — Equalized, Call-Metered Learned Investigation Policy Protocol v2 (`seed-learned-investigation-policy-v2`)

## 1. Motivation & Repairs Over `v1`

Following the post-run audit of `seed-learned-investigation-policy-v1` ([`NEXUS_SEED_LEARNED_INVESTIGATION_POLICY_V1_AUDIT.md`](NEXUS_SEED_LEARNED_INVESTIGATION_POLICY_V1_AUDIT.md)), which withdrew the `v1` learning-to-learn conclusion while preserving `artifacts/seed_learned_investigation_policy_v1/`, this `v2` protocol enforces five structural repairs:

1. **100% Equalized Controller Bounds Across All Active Policies (`EqualizedControllerConfig`)**:
   - Every active policy (`untrained_default_active`, `simple_frequency_active`, `fixed_infogain_active`, `learned_ranker_only_active`, `learned_policy_random_curr_active`, `learned_policy_curriculum_active`, and `strategy_reset_active`) runs with the **exact same**:
     - `shortlist_limit = 3`
     - `allow_questions = True`
     - `max_questions_per_task = 2`
     - `probe_min_disagreement_ratio = 0.15`
   - Resetting the learned strategy (`strategy_reset_active`) resets **only** the learned weights $\phi = (\phi_{\text{rank}}, \phi_{\text{probe}}) \to \phi_0$ while **keeping `allow_questions = True` and `shortlist_limit = 3`**.
   - Passive controls (`allow_questions = False`) are reported in a separate $2 \times 2$ factorial table (`untrained_passive_no_questions` vs `learned_ranker_passive_no_questions`) so the effects of active questioning and weight learning are never confounded.

2. **Full Call-Level Metering (`EpisodeCallLedger`)**:
   - Every single candidate function invocation `fn(inp)`—across support checks (`support_check`), probe construction (`probe_construction`), and capsule verification—increments `n_candidate_calls` by `1` and appends a verifiable record `(call_index, candidate_id, phase, input, output, status)` to `candidate_call_log`.
   - Every oracle query appends `(question_index, task_id, probe_input, oracle_answer)` to `oracle_question_log`.

3. **Strict Separation of Source Acquisition, Probe Pool, and Held-Out Assessment**:
   - **Pairwise Disjoint Input Sets**: For all 64 tasks (`32` training pool + `8` source acquisition + `24` excluded assessment), `support_examples`, `probe_pool_inputs`, and `assessment_inputs` are verified to have zero intersection (`verify_disjoint_task_inputs`).
   - **Autonomous Source Skill Acquisition (`src01..src08`) $\to$ Compositional Prefix Transfer (`ex01..ex16`)**:
     - No assessment answers are ever seeded into `CapsuleSkillStore`.
     - Instead, NEXUS must first solve 8 disjoint **2-step** source tasks (`src01..src08`) via `investigate_v2(..., consolidate_on_solve=True)` to acquire 2-step prefix capsules (`cap(op1 -> op2)`).
     - On the 24 unseen assessment tasks (16 **3-step** sequence compositions `op1 -> op2 -> op3` + 8 real multi-file Python repository repairs `repo17..repo24`), `CapsuleExecutor` uses acquired 2-step capsules as compositional prefix macros (`cap(op1 -> op2) + op3`) without any overlap between 2-step source targets and 3-step assessment targets.

4. **Reconstructing, Tamper-Rejecting Verifier (`scripts/verify_seed_learned_investigation_policy_v2.py`)**:
   - Re-executes the deterministic controller on every episode from scratch and checks that `n_candidate_calls == len(candidate_call_log) == replayed_calls` and `n_questions == len(oracle_question_log) == replayed_questions`.
   - Recomputes all summary tables (`equalized_active_comparison`, `passive_factorial_controls`, `compositional_transfer_experiment`) directly from the raw episode records.
   - Runs three tamper self-tests:
     1. Zeroing `n_candidate_calls` and `n_questions` with updated `objective_J_phi` arithmetic (the exact attack that passed `v1`—must fail in `v2`).
     2. Altering a summary table metric without changing episode records (must fail).
     3. Forging an episode's `solved` status (must fail).

5. **Real System Integration (Live Local GGUF Runtime + Bounded Subprocess Repository Verification)**:
   - Evaluates all 8 multi-file Python repository repair tasks (`repo17..repo24`) inside the isolated bounded worker (`src/nexus/seed/agent_loop_worker.py`) and runs a live local GGUF proposal probe (`PersistentLocalRuntime` with `qwen2.5-0.5b-instruct-q4_k_m.gguf`) comparing direct one-shot local LLM proposals against NEXUS's active investigation loop.
