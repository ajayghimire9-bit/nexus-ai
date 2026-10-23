# NEXUS Seed — Four-Bottleneck Architecture & Live-Model Benchmark Protocol (`seed-bottleneck-breaker-1`)

## 1. Objective & Scope

This pre-registered source-development protocol (`seed-bottleneck-breaker-1`) isolates and evaluates the four architectural and capacity bottlenecks separating NEXUS from open-ended conversation, multi-file coding, unseen task reasoning, and process-level learning-to-learn:

1. **Bottleneck 1 — Proposer Interface Architecture (`max_tokens=128` Starved vs `max_tokens=512` Symbol-Targeted AST)**:
   - Tests whether starving the local proposer (`max_tokens=128`, raw file-replace validation) versus a symbol-targeted AST interface (`max_tokens=512`, `insert_function`, `replace_function`, multi-definition splitting, function indentation/return-deduplication repair, cross-file symbol routing, and line/call-return trace diagnostics) improves structural edit validity and public/private task pass rates on the exact same frozen `Qwen2.5-0.5B-Instruct-Q4_K_M` weights.
2. **Bottleneck 2 — Pretrained Code Capacity (`0.5B-Instruct` vs `1.5B-Coder-Instruct`) & Document-Grounded Conversation**:
   - Compares `Qwen2.5-0.5B-Instruct-Q4_K_M` (`512` tokens, symbol-targeted) against `Qwen2.5-Coder-1.5B-Instruct-Q4_K_M` (`512` tokens, symbol-targeted, and `512` tokens + closed-loop AST fallback) across 4 fresh coding tasks (`py_bb_kebab_pair`, `py_bb_duty_then_rebate`, `py_bb_quota_inclusive`, `py_bb_doc_retry_backoff`), and evaluates document-grounded workspace conversation (`KnowledgeAndDocRetriever`, help paraphrases, typo-tolerant workspace state queries, underspecified `"fix it"` clarification, and interrupt/cancel handling).
3. **Bottleneck 3 — Unseen Tasks via Test-Time Compute (`Interpret -> Plan -> Execute -> Inspect -> Revise`)**:
   - Evaluates multi-round execution trace inspection (`sys.setprofile` call-and-return locals, source line, and return value) on 3 fresh unseen tasks (`py_bb_ttc_tiered_shipping`, `py_bb_ttc_doc_sla_penalty`, `py_bb_ttc_null_rebate_ledger`).
4. **Bottleneck 4 — Process-Level "Learning to Learn" (`CodingDiagnosticMetaPolicy` $\phi_{\text{diag}}$ with `reset_skills()`)**:
   - Trains a 36-parameter diagnostic meta-policy $\phi_{\text{diag}}$ on 6 disjoint source coding tasks (`py_bb_src_*`) mapping 6-dimensional public failure trace signatures $\psi(T, \text{trace}_0)$ to 6 repair operator families.
   - Evaluates on 6 unseen assessment repositories (`py_bb_eval_*`) across 5 falsifiable conditions:
     - `fixed_default_order`
     - `learned_diag_policy_capsules_cleared` (`reset_skills()`: `RepairSchemaStore` and `OrdinaryExactCache` completely cleared, retaining only $\phi_{\text{diag}}$)
     - `learned_diag_policy_plus_repair_memory`
     - `diag_policy_reset_control` (`reset_strategy()`: $\phi_{\text{diag}} \to 0$)
     - `diag_policy_shuffled_control` (`shuffle_weights()`: deterministic derangement of $\phi_{\text{diag}}$)

## 2. Falsifiable Gates & Disjointness Constraints

- **Zero Task Overlap**: Every task ID in `coding_tasks`, `unseen_reasoning_tasks`, `meta_learning.source_tasks`, and `meta_learning.assessment_tasks` is disjoint from `closed_coding_ids_excluded`, and `source_tasks` $\cap$ `assessment_tasks` $= \emptyset$.
- **Process-Level Learning-to-Learn Criterion**: `process_level_learning_to_learn_established` is `True` iff `learned_diag_policy_capsules_cleared` solves at least as many unseen assessment tasks on private tests as `fixed_default_order` while using strictly fewer metered worker evaluations (`worker_evaluations < fixed_default_order`), with `capsules_cleared == True`, `reused_memory_count == 0`, and `cache_hits == 0`, and this advantage disappears under both `diag_policy_reset_control` and `diag_policy_shuffled_control`.
- **Independent Verification**: `scripts/verify_seed_bottleneck_breaker.py` independently verifies the `EventMeter` SHA-256 hash chain, reconstructs every `meta_learning` episode's worker evaluation count from raw `EventMeter` events, recomputes all summary metrics, and verifies all historical artifact fingerprints.
