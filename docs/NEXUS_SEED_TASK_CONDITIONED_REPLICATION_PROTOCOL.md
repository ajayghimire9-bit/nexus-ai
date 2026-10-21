# NEXUS Seed Task-Conditioned Program Ranking & Sealed Compositional Replication Protocol (`seed_task_conditioned_replication_v1`)

## 1. Scientific Questions & Hypotheses

Following the negative result of the task-independent structural prior in [NEXUS_SEED_DISJOINT_META_RESULTS.md](NEXUS_SEED_DISJOINT_META_RESULTS.md) and the positive source-only clue separation in [NEXUS_SEED_SIGNATURE_AUDIT_RESULTS.md](NEXUS_SEED_SIGNATURE_AUDIT_RESULTS.md), this preregistered study tests whether conditioning candidate program ranking on the current task's observed teaching examples $D_B = \{(x_i, y_i)\}_{i=1}^B$:
$$S(p \mid D_B) = -d\big(\operatorname{signature}(D_B), \operatorname{signature}(p)\big) + \alpha S_{\text{structural}}(p) - \beta \operatorname{complexity}(p)$$
accelerates program search on a **fresh, unexposed sealed compositional grammar and target split**, without reducing held-out accuracy or old-task retention, while also transferring across domains under a supplied operator-role mapping and transferring across the four Shared Labs (`Language`, `Coding`, `Reasoning`, `World`).

- **Primary Hypothesis ($H_1$)**: Deterministic task-conditioned signature ranking (`deterministic_signature`, locked $\alpha = 0.05, \beta = 0.05$) reduces candidate evaluations by $\ge 10\%$ against all simple ordering baselines (`flat_catalogue`, `shortest_program`, `operator_frequency`, `exact_macro_cache`, `random_ordering`) and against task-independent `structural_meta_prior`, with 95% paired family confidence intervals strictly above zero, while preserving held-out execution accuracy, old-source retention ($\ge 0.98$), and total amortized compute ($\le 1.25\times$ strongest baseline).
- **Deterministic vs. Learned Inference Comparison ($H_2$)**: Compare `deterministic_signature`, `bayesian_version_space`, and source-trained `learned_linear_ranker` before introducing any neural ranker. Add a neural model only if the deterministic methods fail to represent the input-output relationship.
- **Secondary Cross-Domain Hypothesis ($H_3$)**: Under an explicitly supplied 6-operator role mapping (`"structural transfer under a supplied mapping"`), task-conditioned structural transfer (`transferred_signature_prior`) reduces search evaluations in `action_token_sequence` by $\ge 10\%$ versus `scratch_flat`, `exact_macro_cache`, and `structural_meta_prior` with 95% CI $> 0$.
- **Cross-Lab Shared-Memory Transfer Hypothesis ($H_4$)**: Teaching an executable transformation once in `Language Lab` and reusing the shared `Session`/`E1 Journal` representation across `Coding Lab`, `Reasoning Lab`, and `World Lab` reduces downstream candidate evaluations and improves downstream accuracy relative to `scratch_learning` and `isolated_labs`.

---

## 2. Fresh Sealed Compositional Grammar & Three-Way Disjoint Partition

### 2.1 Primary `list` Grammar ($\mathcal{O}_{\text{rep}}$, 6 Primitives, Length $L \in \{1, 2, 3\}$)
- Primitives: $\mathcal{O}_{\text{rep}} = (\text{reverse}, \text{sort}, \text{unique}, \text{increment}, \text{decrement}, \text{even})$.
  - `decrement(x) = [v - 1 for v in x]` (rejecting elements $\le -64$).
- Canonicalization over $L \in \{1, 2, 3\}$:
  - Involution & inverse cancellation: `reverse -> reverse` $\to \varepsilon$, `increment -> decrement` $\to \varepsilon$, `decrement -> increment` $\to \varepsilon$.
  - Idempotence: `sort -> sort` $\to$ `sort`, `unique -> unique` $\to$ `unique`, `even -> even` $\to$ `even`.
  - Exact commutation pairs (ordered by source operator name): `{increment, reverse}`, `{increment, sort}`, `{increment, unique}`, `{decrement, reverse}`, `{decrement, sort}`, `{decrement, unique}`, `{sort, unique}`, `{unique, even}`.
- Exhaustive probe domain $X_{\text{probe}} = \bigcup_{\ell=0}^4 \{-2,-1,0,1,2\}^\ell$ (`781` inputs):
  - Raw sequences: $6^1 + 6^2 + 6^3 = 258$.
  - Non-empty canonical signatures: `100`.
  - Semantically unique non-empty programs: `65`.

### 2.2 Three-Way Partition (Zero Overlap with Source AND Zero Overlap with Previously Exposed Targets)
1. **Source Pool $\mathcal{C}_{\text{source, rep}}$ (`18` programs)**:
   - The 17 source programs from `seed_disjoint_meta_v1` plus length-1 `["decrement"]`.
   - All 6 primitives appear in every family's 18 solved source tasks.
2. **Quarantined Historical Pool $\mathcal{C}_{\text{quarantine}}$ (`23` programs)**:
   - All previously exposed non-`decrement` target compositions from `seed_disjoint_meta_v1`.
   - Retained in the 65-program search catalogue so every method searches the full 65-program space, but **strictly quarantined from being sampled as target tasks**.
3. **Fresh Sealed Target Pool $\mathcal{C}_{\text{target, rep}}$ (`24` programs)**:
   - All 24 semantically unique length-$\ge 2$ compositions containing held-out adjacent pairs with `decrement` (`("decrement", op)` or `(op, "decrement")`).
   - Disjointness invariants:
     - $|\operatorname{Canon}(\mathcal{C}_{\text{source, rep}}) \cap \operatorname{Canon}(\mathcal{C}_{\text{target, rep}})| = 0$,
     - $|\operatorname{Sem}(\mathcal{C}_{\text{source, rep}}) \cap \operatorname{Sem}(\mathcal{C}_{\text{target, rep}})| = 0$,
     - $|\operatorname{Canon}(\mathcal{C}_{\text{target, v1}}) \cap \operatorname{Canon}(\mathcal{C}_{\text{target, rep}})| = 0$,
     - $|\operatorname{Sem}(\mathcal{C}_{\text{target, v1}}) \cap \operatorname{Sem}(\mathcal{C}_{\text{target, rep}})| = 0$.

### 2.3 Cross-Domain `action_token_sequence` Grammar (`6` Primitives)
- Primitives: $\mathcal{O}_{\text{act, rep}} = (\text{reverse\_actions}, \text{order\_actions}, \text{dedup\_actions}, \text{advance\_mag}, \text{retreat\_mag}, \text{filter\_even\_mag})$.
- Identical combinatorics (`258` raw $\to$ `100` canonical $\to$ `65` unique: `18` source, `23` quarantine, `24` target).

---

## 3. Seeds, Families, Budgets, and Methods

- **8 Families**: `1749000001..1749000008`, `assignment_seed = 1749000900`.
- **Task Seeds**:
  - Source (`144` tasks, 18 per family): `1749100000..1749100143`
  - Target (`24` tasks, 3 per family, non-repeating): `1749200000..1749200023`
  - Retention (`32` tasks, 4 per family): `1749300000..1749300031`
  - Cross-domain (`24` tasks, 3 per family, non-repeating): `1749400000..1749400023`
  - Random permutations (`512` seeds, 64 per family): `1749500000..1749500511`
- **Budgets**: Primary $B \in \{1, 2, 4\}$, secondary $B = 8$; $M = 16$ disjoint assessment examples per task.
- **9 In-Domain Methods**:
  1. `deterministic_signature` (Primary Candidate: $S(p \mid D_B) = -\|\operatorname{signature}(D_B) - \operatorname{signature}(p)\|_1 + 0.05 S_{\text{structural}}(p) - 0.05 \operatorname{len}(p)/3$)
  2. `learned_linear_ranker` (Source-only 20-feature ridge ranker over per-coordinate signature differences, $S_{\text{structural}}(p)$, and complexity, $\lambda = 1.0$)
  3. `bayesian_version_space` (Bayesian log-prior $\log P_{\text{Bayesian}}(p) - 4.0 \|\operatorname{signature}(D_B) - \operatorname{signature}(p)\|_1$)
  4. `structural_meta_prior` (Task-independent 24-feature ridge structural prior)
  5. `flat_catalogue`
  6. `shortest_program`
  7. `operator_frequency`
  8. `exact_macro_cache`
  9. `random_ordering`
- **7 Cross-Domain Methods**:
  `transferred_signature_prior`, `transferred_structural_prior`, `scratch_flat`, `shortest_program`, `target_operator_frequency`, `exact_macro_cache`, `random_ordering`.

---

## 4. Seven Advancement Gates (All Seven Required)

1. **Gate 1 (Integrity & Double Disjointness)**: `65` unique programs (`18` source, `23` quarantine, `24` target); `0` canonical/semantic overlap with source AND `0` canonical/semantic overlap with `seed_disjoint_meta_v1` exposed targets; all 6 primitives in source; every target has length $\ge 2$ and $\ge 1$ unseen pair.
2. **Gate 2 (Held-Out Target Quality)**: `deterministic_signature` primary accuracy within `-0.01` of best baseline, loses in $\le 2/8$ families, no family drop $> 0.05$, and $B=8$ accuracy $\ge 0.99$.
3. **Gate 3 (Search-Efficiency Gain)**: `deterministic_signature` reduces construction-inclusive evaluations by $\ge 10\%$ against all 5 simple baselines (`flat_catalogue`, `shortest_program`, `operator_frequency`, `exact_macro_cache`, `random_ordering`) AND against task-independent `structural_meta_prior`, with 95% two-sided paired t-intervals strictly $> 0$.
4. **Gate 4 (Example-Efficiency)**: Mean examples for exact semantic identification improves by $\ge 10\%$ vs `flat_catalogue` or is within `5%` of best baseline.
5. **Gate 5 (Old-Task Retention)**: Post-meta-learning accuracy on the 32 frozen old-source retention tasks $\ge 0.98$, accuracy retention $\ge -0.01$, and search retention regression $\le +10\%$.
6. **Gate 6 (Structural Cross-Domain Transfer Under Supplied Mapping)**: `transferred_signature_prior` reduces construction-inclusive evaluations by $\ge 10\%$ vs `scratch_flat` (with 95% CI $> 0$) and beats `exact_macro_cache` and `transferred_structural_prior`.
7. **Gate 7 (Honest Computation)**: Total amortized work (including source fitting, calibration signatures, and per-episode signature extraction) $\le 1.25\times$ strongest baseline, with finite positive break-even $K^*$.
