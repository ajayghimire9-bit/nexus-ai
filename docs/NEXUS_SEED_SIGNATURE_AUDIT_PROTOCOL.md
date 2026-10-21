# NEXUS Seed Source-Only Input-Output Signature Audit Protocol (`seed_signature_audit_v1`)

## 1. Scientific Objective & Zero-Target-Leakage Rule

Following the negative result of the task-independent structural prior in [NEXUS_SEED_DISJOINT_META_RESULTS.md](NEXUS_SEED_DISJOINT_META_RESULTS.md), this source-only audit tests whether observed teaching input-output pairs $D_B = \{(x_i, y_i)\}_{i=1}^B$ expose discriminative deterministic clues across six categories without accessing any target program or target outcome:

1. **Output length change**: `len_preserved_rate`, `len_decreased_rate`, `mean_len_ratio`
2. **Sorting or reversal**: `sorted_asc_rate`, `sorted_desc_rate`, `direct_reversal_rate`
3. **Duplicates removed**: `duplicates_removed_rate`, `first_appearance_order_rate`, `reversed_first_appearance_rate`, `last_appearance_reversed_rate`
4. **Even/odd filtering**: `all_even_output_rate`, `all_odd_output_rate`, `pre_shift_odd_origin_rate`
5. **Constant value shift**: `positive_shift_norm`, `negative_shift_norm`, `zero_shift_indicator`
6. **Preservation of order and cardinality**: `order_and_cardinality_preserved_rate`

### Strict Leakage Rule
- Reads **only** `list_catalogue["source_ids"]` (17 source programs) and `families[0..7]["source_tasks"]` (128 source tasks) from [seed_disjoint_meta.json](../artifacts/seed_disjoint_meta.json).
- `target_tasks`, `target_ids`, and `cross_domain_tasks` are stripped before evaluation (`target_outcomes_accessed: false`).

## 2. Task-Conditioned Ranking Formula & Locked Hyperparameters

For any candidate program $p$ and observed teaching examples $D_B = \{(x_i, y_i)\}_{i=1}^B$:
$$S(p \mid D_B) = -d(\operatorname{signature}(D_B), \operatorname{signature}(p)) + \alpha S_{\text{structural}}(p) - \beta \operatorname{complexity}(p)$$
where:
- $d(\operatorname{signature}(D_B), \operatorname{signature}(p)) = \|\operatorname{signature}(D_B) - \operatorname{signature}(p)\|_1$ over the 17 bounded signature features in $[0, 1]^{17}$,
- $\operatorname{signature}(p)$ is precomputed once per catalogue program on 8 fixed public calibration inputs,
- $\operatorname{complexity}(p) = \operatorname{len}(p) / 3.0$,
- Locked hyperparameters: $\alpha = 0.05$, $\beta = 0.05$, ridge $\lambda = 1.0$.

## 3. Advancement Criteria for Proceeding to Sealed Replication

1. All 17 source programs have distinct 17-feature calibration signatures (`17 / 17` unique).
2. Leave-one-source-program-out (LOSO) evaluation on the 128 source tasks ($B \in \{1, 2, 4\}$) achieves $\le 2.0$ mean candidate evaluations and $\ge 75\%$ reduction versus both `flat_catalogue` and `structural_meta_prior_loso`.
