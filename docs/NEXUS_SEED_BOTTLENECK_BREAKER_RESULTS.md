# NEXUS Seed — Four-Bottleneck Architecture & Live-Model Benchmark Results (`seed-bottleneck-breaker-1`)

## 1. Executive Summary

- **Pre-Registered Protocol Commit**: `a686b711be421657899c56b61a2c75eec0149051` on `codex/seed-bottleneck-breaker-v1` (based on `33b9fdef26fd5212ef790bc110f5dc196a35216f`).
- **Independent Verifier**: `scripts/verify_seed_bottleneck_breaker.py` $\to$ `valid: true` (`279` metered `EventMeter` execution events across `16` coding ablation cells, `3` unseen test-time compute cells, `6` grounded conversation turns, `6` meta-training episodes, and `30` meta-assessment episodes).
- **Live GGUF Models Executed (`40` live completions, `25,061` input tokens, `2,484` generated tokens, `206.181003 s` model wall)**:
  - `Qwen2.5-0.5B-Instruct-Q4_K_M` (`74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`)
  - `Qwen2.5-Coder-1.5B-Instruct-Q4_K_M` (`cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`)
- **Ledger**: Carried `2433.667484455996 s` + run wall `235.197426 s` = **`2668.864910455996 s` used / `931.135089544004 s` remaining**.

---

## 2. Results by Bottleneck

### Bottleneck 1 & 2 — Proposer Interface Architecture vs Pretrained Code Capacity

| Condition | Model | Max Tokens | Interface Mode | Valid Edit Rate | Public Pass | Private Pass |
| :--- | :--- | :---: | :--- | :---: | :---: | :---: |
| `qwen_0_5b_starved_128` | `Qwen2.5-0.5B-Instruct` | `128` | Raw file-replace (`starved_128`) | `3 / 7` (`42.9%`) | `1 / 4` | `1 / 4` (`25.0%`) |
| `qwen_0_5b_symbol_512` | `Qwen2.5-0.5B-Instruct` | `512` | Symbol-targeted AST (`symbol_512`) | **`11 / 11` (`100.0%`)** | `1 / 4` | `1 / 4` (`25.0%`) |
| `qwen_1_5b_coder_symbol_512` | `Qwen2.5-Coder-1.5B-Instruct` | `512` | Symbol-targeted AST (`symbol_512`) | `7 / 9` (`77.8%`) | **`3 / 4`** | **`2 / 4` (`50.0%`)** |
| `qwen_1_5b_coder_closed_loop_ast` | `Qwen2.5-Coder-1.5B-Instruct` | `512` | Symbol-targeted AST + Closed-Loop AST | `7 / 9` (`77.8%`) | **`4 / 4`** | **`3 / 4` (`75.0%`)** |

- **Separating Interface from Capacity**:
  1. Upgrading the proposer interface from `starved_128` to `symbol_512` (`insert_function`, `replace_function`, multi-definition splitting, function indentation/return-deduplication repair, cross-file symbol routing, and trace hints) on the **same `0.5B` model** raised structural edit validity from **`42.9%` (`3/7`) to `100.0%` (`11/11`)**.
  2. Upgrading pretrained code priors from `0.5B-Instruct` to `1.5B-Coder-Instruct` under the same `symbol_512` interface doubled private pass rate (`25.0%` $\to$ `50.0%`, `3/4` public pass), and combining `1.5B-Coder` with closed-loop AST verification reached **`4/4` public pass and `3/4` (`75.0%`) private pass**.

### Bottleneck 2b — Grounded Workspace Conversation (`6 / 6` Rubrics Met)

- Across 6 live conversation turns (`conv_help_capabilities`, `conv_typo_workspace_state`, `conv_grounded_doc_rpc`, `conv_grounded_doc_arch`, `conv_ambiguous_fix_it`, `conv_topic_shift_after_clarify`), NEXUS met **`6 / 6` rubrics** and attached grounded local documentation (`KnowledgeAndDocRetriever`) on **`3` turns**, answering `"wich coding workspace is selected right now?"` accurately, asking for clarification on `"fix it"`, and clearing pending clarification on `"Never mind, cancel that."`.

### Bottleneck 3 — Unseen Tasks via Test-Time Compute (`3 / 3` Public & Private Solved)

- On 3 unseen tasks (`py_bb_ttc_tiered_shipping`, `py_bb_ttc_doc_sla_penalty`, `py_bb_ttc_null_rebate_ledger`), the `Interpret -> Plan -> Execute -> Inspect -> Revise` loop recorded `8` initial call/return trace events and solved **`3 / 3` (`100%`)** on both public and held-out private test suites (including `local_model_per_file` live 1.5B-Coder repair on `py_bb_ttc_null_rebate_ledger`).

### Bottleneck 4 — Process-Level "Learning to Learn" (`CodingDiagnosticMetaPolicy` $\phi_{\text{diag}}$)

Trained on `6` disjoint source coding tasks (`py_bb_src_*`) and evaluated on `6` unseen assessment repositories (`py_bb_eval_*`) under identical candidate pools and budgets:

| Condition | Capsules Cleared (`reset_skills()`) | Public Solved | Private Solved | Metered Worker Evaluations | Memory Reuses | Cache Hits |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `fixed_default_order` | `True` | `6 / 6` | `6 / 6` | `41` | `0` | `0` |
| **`learned_diag_policy_capsules_cleared`** | **`True`** | **`6 / 6`** | **`6 / 6`** | **`14` (`-65.9%`)** | **`0`** | **`0`** |
| `learned_diag_policy_plus_repair_memory` | `False` | `6 / 6` | `6 / 6` | `14` | `2` | `0` |
| `diag_policy_reset_control` ($\phi_{\text{diag}} \to 0$) | `True` | `6 / 6` | `6 / 6` | `41` | `0` | `0` |
| `diag_policy_shuffled_control` | `True` | `6 / 6` | `6 / 6` | `22` | `0` | `0` |

- With **all cached code patches and repair schemas cleared (`capsules_cleared: true, reused_memory_count: 0, cache_hits: 0`)**, retaining only the learned diagnostic meta-policy $\phi_{\text{diag}}$ reduced metered worker evaluations on unseen repositories from **`41` to `14` (`65.9%` fewer worker executions)** while solving **`6 / 6`** on held-out private tests.
- Resetting $\phi_{\text{diag}} \to 0$ (`diag_policy_reset_control`) reverted worker evaluations back to **`41`** (`disappears_when_reset: true`), and permuting $\phi_{\text{diag}}$ (`diag_policy_shuffled_control`) degraded worker evaluations to **`22`** (`disappears_when_shuffled: true`).
