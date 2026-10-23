# NEXUS Seed — Adversarial Audit of `seed-learned-investigation-policy-v1`

## 1. Verdict on `v1` (`8033e06`)

Following post-run audit of `seed-learned-investigation-policy-v1` (`artifacts/seed_learned_investigation_policy_v1/seed_learned_investigation_policy_v1.json`, preserved untouched), **the `v1` claim of "bounded learning-to-learn established" is withdrawn**. While `v1` demonstrated a functioning bounded active-identification prototype and three separately resettable knowledge stores, five concrete methodological confounds prevent `v1` from establishing superior learning-to-learn or cross-domain skill transfer:

| Confound in `v1` | What `v1` Actually Did | Impact on `v1` Claim |
| :--- | :--- | :--- |
| **1. Asymmetric shortlist & questioning rules** | `learned_investigation_policy` used `shortlist_limit = 4` and `allow_questions = True`, whereas `strong_fixed_infogain` scanned `len(ranked) = 18` and `original_untrained_policy` / `strategy_reset_ablation` used `shortlist_limit = 8` with `allow_questions = False`. | Under equalized rules (`shortlist_limit = 4`, `allow_questions = True`), fixed and unlearned active baselines solved `24/24` in `342`–`343` reported executions vs `350` for the learned policy because natural-language requests contained explicit operator keywords matched by the unlearned `LocalNeuralProposer`. |
| **2. Reuse seeded from assessment tasks** | `build_training_and_excluded_tasks()` set `skill_seed_tasks = excluded_tasks[:8]` and `_populate_seed_skills()` registered their target programs directly. | The 8 capsule hits in `v1` Experiment 3 measured exact lookup of seeded assessment answers rather than transfer of capsules acquired through learning on disjoint source tasks. |
| **3. Repository probe / assessment overlap** | Repository tasks (`ex17..ex24`) set `assess_inps = list(LearnedInvestigationPolicy.REPO_PROBE_INPUTS)`. | Active questions during learning queried inputs from the same `REPO_PROBE_INPUTS` tuple used for final assessment. |
| **4. Unmetered candidate function calls** | `construct_disagreement_probe()` executed every surviving candidate on up to 6 probe inputs without incrementing `n_executions`, and `filter_consistent_candidates()` counted 1 execution per candidate across multiple support examples. | Actual candidate function calls (`fn(inp)`) for `learned_investigation_policy_curriculum` were `844` rather than the reported `350`. |
| **5. Non-reconstructing cost verifier** | `scripts/verify_seed_learned_investigation_policy.py` replayed final accuracy and checked arithmetic on saved `n_questions` and `n_executions`, but did not reconstruct call counts from an execution log or recompute summary tables from episodes. | Forged zero-execution/zero-question episodes with matching `objective_J_phi` arithmetic were not rejected. |

---

## 2. Corrective Actions Implemented in `v2` (`seed-learned-investigation-policy-v2`)

1. **Preserved `v1` Artifacts & Updated `v1` Report**: `artifacts/seed_learned_investigation_policy_v1/` is preserved intact; `docs/NEXUS_SEED_LEARNED_INVESTIGATION_POLICY_V1_RESULTS.md` and `docs/NEXUS_CANONICAL_CURRENT_STATE.md` explicitly mark `v1` as **FAILED / CONFOUNDED** on the learning-to-learn claim.
2. **100% Equalized Controller Rules**: In `v2`, every active policy (`untrained_default_active`, `simple_frequency_active`, `fixed_infogain_active`, `learned_ranker_only_active`, `learned_policy_random_curr_active`, `learned_policy_curriculum_active`, and `strategy_reset_active`) uses the **exact same** `shortlist_limit = 4`, `allow_questions = True`, `max_questions_per_task = 2`, and `probe_min_disagreement_ratio = 0.15`. Only the learned parameters $\phi = (\phi_{\text{rank}}, \phi_{\text{probe}})$ vary. Passive (`allow_questions = False`) configurations are evaluated in a separate $2 \times 2$ factorial table.
3. **Strict Separation of Source Acquisition, Probe Pool, and Held-Out Assessment**:
   - Source skills are acquired by actually running `investigate(..., consolidate_on_solve=True)` on 8 disjoint 2-step source tasks (`src01..src08`), and transferred as compiled prefix macros (`cap_2step + op3`) onto unseen 3-step assessment tasks.
   - Support inputs, probe-pool inputs, and held-out assessment inputs are strictly pairwise disjoint across all sequence and repository tasks (`set(support) & set(probes) == ∅`, `set(probes) & set(assessment) == ∅`, `set(support) & set(assessment) == ∅`).
4. **Full Call-Level Metering & Reconstructing Verifier**:
   - Every single `fn(inp)` call across support checks, probe construction, probe filtering, and capsule verification is wrapped in `MeteredCandidateCallable` and recorded in `candidate_call_log`.
   - `scripts/verify_seed_learned_investigation_policy_v2.py` replays every call in `candidate_call_log`, every oracle query in `oracle_question_log`, re-executes the deterministic controller to verify call counts cannot be forged or omitted, and recomputes all summary tables from scratch.
5. **Real Local GGUF Model + Bounded Worker Repository Repair Integration**:
   - Connects live local GGUF inference (`PersistentLocalRuntime`), `PythonASTMutationSynthesizer`, and isolated subprocess execution (`agent_loop_worker.py`) on multi-file Python repositories with disjoint support, probe, and held-out test suites.
