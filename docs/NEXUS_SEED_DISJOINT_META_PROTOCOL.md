# NEXUS Seed — Preregistered Disjoint Compositional Meta-Learning Protocol (`seed_disjoint_meta_v1`)

## 1. Audit of Previous Engineering Demo (`src/nexus/seed/master/meta_learning.py`)

Before registering this experiment, we audited `src/nexus/seed/master/meta_learning.py`, `src/nexus/seed/master/memory.py`, `src/nexus/seed/skill_programs.py`, and `tests/test_seed_master_architecture.py`. The existing master-architecture benchmark (`9.5 -> 1.75` candidate evaluations, `81.58%` reduction) is preserved as historical engineering evidence (`bounded exact-motif program-prior reuse demo` / `engineering demonstration of within-family search-prior reuse`), with five documented limitations:

1. **Exact canonical motif reuse between source and target**:
   - Source and target both use `sort -> unique`, `reverse -> increment`, and `even -> sort`.
2. **Held-out inputs are not held-out program mechanisms**:
   - Changing input lists while keeping identical target programs tests execution on new inputs, not synthesis of unseen program compositions.
3. **"Retention" previously stored target held-out correctness rather than old-task retention**:
   - `retention_scores` recorded whether the target held-out check passed rather than re-evaluating frozen source tasks before and after meta-learning.
4. **"Transfer" was synthetically constructed**:
   - `transfer_score = meta_score + 0.02` rather than independently measured on a separate domain.
5. **The six-domain suite is an integration suite**:
   - It executes hand-authored solver fixtures across six reasoners (`bounded multi-reasoner integration suite`), not evidence of acquired general intelligence.

---

## 2. Locked Scientific Question and Hypotheses

- **Primary Hypothesis ($H_1$)**:
  A structural meta-prior fitted only on source programs reduces the search required to identify canonically and semantically disjoint target programs, including unseen operator compositions, without reducing held-out execution accuracy or old-task retention, and while beating strong simple ordering baselines.
- **Secondary Hypothesis ($H_2$)**:
  A source-learned abstract structural prior transfers to a separately implemented sequence domain (`action_token_sequence`) under an explicitly supplied typed operator-role mapping better than a scratch prior. This secondary result is strictly termed **structural transfer under a supplied mapping**, not unrestricted cross-domain transfer.
- **Null Hypothesis ($H_0$)**:
  Any apparent gain is explained by exact motif caching, program length, primitive frequency, deterministic catalogue order, random ordering, or a Bayesian/model-based prior.

---

## 3. Experimental Program Grammar, Canonicalization, and Semantic Probe Domain

- **Live Limit Unchanged**: The live `src/nexus/seed/skill_programs.py` length limit (`1..2`) is not modified.
- **Experiment-Local Bounded Grammar**:
  - Primitives: $O = (\text{reverse}, \text{sort}, \text{unique}, \text{increment}, \text{even})$.
  - Allowed raw sequence lengths: $1 \le |p| \le 3$ ($5 + 25 + 125 = 155$ raw sequences).
  - Execution reuses vetted primitive step semantics (`skill_programs.step`). No `eval`, arbitrary Python, dynamic imports, loops, or file I/O are permitted.
- **Fixed-Point Structural Canonicalization $C(p)$**:
  Repeatedly apply proven identities until a fixed point:
  1. Involution cancellation: `reverse ∘ reverse = []` (identity).
  2. Idempotent collapse: `sort ∘ sort = sort`, `unique ∘ unique = unique`, `even ∘ even = even`.
  3. Proven adjacent commutation rules (lexicographic swap when $a > b$):
     - `{"increment", "reverse"}`
     - `{"increment", "sort"}`
     - `{"increment", "unique"}`
     - `{"sort", "unique"}`
     - `{"unique", "even"}`
     Every commutation rule is exhaustively verified over all 781 inputs in $X_{\text{probe}}$ before catalogue construction.
- **Canonical Signature**:
  $$\sigma(p) = \text{canonical JSON serialization of } C(p)$$
- **Fixed Semantic Probe Domain $X_{\text{probe}}$**:
  All integer lists of length $0 \dots 4$ over alphabet $\{-2, -1, 0, 1, 2\}$ in deterministic order (by length $0 \dots 4$, then lexicographic tuple order):
  $$|X_{\text{probe}}| = 1 + 5 + 25 + 125 + 625 = 781 \text{ inputs.}$$
- **Semantic Behavior Hash**:
  $$h(p) = \operatorname{SHA256}\left(\text{canonical JSON serialization of } [(x, \operatorname{run}(p, x)) \text{ for } x \in X_{\text{probe}}]\right)$$
- **Catalogue Deduplication**:
  - Exclude any sequence reducing to the empty identity `[]`.
  - Deduplicate the 68 non-empty canonical programs by $h(p)$, retaining the shortest canonical program (`len(C(p)["ops"])`) and breaking ties by lexicographic order of `tuple(C(p)["ops"])`.
  - **Exact Combinatorial Catalogue Size**:
    - `155` raw programs $\to$ `68` non-empty canonical signatures $\to$ **`41` semantically unique non-empty programs** (`5` of length 1, `13` of length 2, `23` of length 3).

---

## 4. Global Source/Target Partition and Combinatorial Bound

Across the 41 semantically unique canonical programs, there are 13 distinct ordered adjacent operator pairs $(o_i, o_{i+1})$.

- **Reserved Target Adjacent Pairs (`HOLDOUT_PAIRS`)**:
  1. `("even", "increment")`
  2. `("even", "sort")`
  3. `("increment", "even")`
  4. `("increment", "increment")`
  5. `("reverse", "unique")`
- **Global Partition**:
  - **Global Source Pool ($\mathcal{C}_{\text{source}}$, `17` programs)**: All programs in the 41-program catalogue containing zero adjacent pairs from `HOLDOUT_PAIRS` (`5` of length 1, `8` of length 2, `4` of length 3). Every primitive in $O$ appears in $\mathcal{C}_{\text{source}}$.
  - **Global Target Pool ($\mathcal{C}_{\text{target}}$, `24` programs)**: All programs in the 41-program catalogue containing at least one adjacent pair from `HOLDOUT_PAIRS` (`5` of length 2, `19` of length 3).
- **Exact Combinatorial Bound for 8 Non-Repeating Families**:
  - Because $|\mathcal{C}| = 41$ and $|\mathcal{C}_{\text{source}}| = 17$, there are exactly $|\mathcal{C}_{\text{target}}| = 24$ semantically unique target programs.
  - Under Condition 8 (target programs must not repeat across the $n = 8$ family repetitions), the exact maximum number of non-repeating target programs per family is $24 / 8 = 3$.
  - Therefore, each of the $n = 8$ families is registered with:
    - `16` solved source tasks (sampled deterministically from $\mathcal{C}_{\text{source}}$ with all 5 primitives guaranteed present in every family);
    - `3` in-domain disjoint target tasks ($8 \times 3 = 24$, exhausting $\mathcal{C}_{\text{target}}$ with zero repeats across families);
    - `4` old-source retention tasks (4 distinct source programs from $\mathcal{C}_{\text{source}}$ per family);
    - `3` structural cross-domain target tasks ($8 \times 3 = 24$ distinct target compositions in the secondary sequence domain).
  - The implementation fails closed if `len(families) * target_tasks_per_family > 24` or if any canonical signature or semantic hash overlaps between source and target.

---

## 5. Preregistered Seeds

All seeds are fresh and have never appeared in prior `configs/*.json`:

- `families` ($n = 8$): `1748000001 .. 1748000008`
- `assignment_seed`: `1748000900`
- `tasks.train` ($128$ source tasks): `1748100000 .. 1748100127`
- `tasks.target` ($24$ in-domain target tasks): `1748200000 .. 1748200023`
- `tasks.retention` ($32$ old-source retention tasks): `1748300000 .. 1748300031`
- `tasks.cross_domain` ($24$ secondary-domain target tasks): `1748400000 .. 1748400023`
- `random_permutation_seeds` ($8 \times 64 = 512$ seeds): `1748500000 .. 1748500511`

---

## 6. Task Data, Budgets, and Leakage Rules

- For every source, target, retention, and cross-domain task, generate:
  - `8` teaching inputs;
  - `16` held-out execution assessment inputs;
  - `2` separate counterexample/disambiguating inputs.
- **Disjoint Input Hashes**: Teaching inputs, target held-out assessment inputs, and source-retention inputs are strictly disjoint by normalized input hash (`digest(x)`) across the family.
- **Teaching Budgets**: $B = \{1, 2, 4, 8\}$, with primary budgets $\{1, 2, 4\}$ and secondary budget $8$.
- **Identical Teaching Exposure**: Every method receives the exact same teaching inputs, answers, and ordering at each budget $b \in B$.
- **Strict Leakage Prohibition**: Held-out assessment labels and target identities never enter feature construction, normalization, ridge fitting, candidate ranking, or stopping.

---

## 7. Candidate Meta-Learner (`structural_meta_prior`)

- **Public Categories**:
  - `perm` (permutation/order): `reverse`, `sort`
  - `card` (cardinality-changing): `unique`, `even`
  - `point` (pointwise): `increment`
- **Public Structural Feature Vector $\phi(p) \in \mathbb{R}^{20}$**:
  1. `intercept` (1)
  2. One-hot length: `is_len_1`, `is_len_2`, `is_len_3` (3)
  3. Normalized category counts: `perm_frac`, `card_frac`, `point_frac` (3)
  4. Structural counts: `repeated_primitives`, `idempotent_primitives`, `reversible_primitives`, `cardinality_changing_primitives`, `pointwise_primitives`, `permutation_order_primitives` (6)
  5. Abstract category-transition counts over $\{\text{perm}, \text{card}, \text{point}\}^2$ (9)
  6. `has_unseen_category_transition` (1): `1.0` if any adjacent category transition in $p$ had zero occurrences in the family's solved source episodes $S_f$, else `0.0`.
  *(Total: $1 + 3 + 3 + 6 + 9 + 1 = 23$ public structural features; zero operator hashes, zero exact macro identities, zero target labels.)*
- **Source-Only Ridge Fit ($\lambda = 1.0$)**:
  - Fitted exclusively on the 17 canonical source programs $p \in \mathcal{C}_{\text{source}}$ using source-episode structural statistics from $S_f$:
    $$y_p = \frac{\text{count}_{S_f}(p)}{|S_f|} + 0.5 \cdot \mathbb{I}[|p| \ge 2] \cdot \left(\frac{1}{|p|-1} \sum_{i=1}^{|p|-1} \hat{P}_{S_f}(\operatorname{cat}(o_i) \to \operatorname{cat}(o_{i+1}))\right)$$
  - Feature root-mean-square scaling `scale` and ridge weights $w^* = \arg\min_w \sum_{p \in \mathcal{C}_{\text{source}}} (y_p - w^\top \tilde{\phi}(p))^2 + \lambda \|w\|^2$ with $\lambda = 1.0$ are fitted on $\mathcal{C}_{\text{source}}$ only and frozen before target teaching or assessment.
  - Candidate ranking: $\operatorname{score}(p) = {w^*}^\top (\phi(p) / \text{scale})$, with canonical lexicographic order for ties.

---

## 8. Strong Baselines

All methods rank the identical 41-program catalogue:

1. `flat_catalogue`: Deterministic canonical signature lexicographic order with no source learning.
2. `shortest_program`: Rank by `(len(p["ops"]), canonical_signature(p))`.
3. `operator_frequency`: Laplace-smoothed primitive frequencies $P(o) = (\text{count}_{S_f}(o) + 1) / (\sum_{o'} \text{count}_{S_f}(o') + 5)$, scored by $\sum_{o \in p} \log P(o)$ with canonical tie-break.
4. `exact_macro_cache`: Rank exact canonical source programs seen in $S_f$ first by source frequency, then fall back to `shortest_program`.
5. `random_ordering`: Exact expectation across 64 preregistered deterministic random catalogue permutations per family (`random_permutation_seeds`).
6. `bayesian_model_based`: Dirichlet-smoothed source grammar prior over program length $P_{\text{source}}(L)$, primitive categories $P_{\text{source}}(\operatorname{cat}(o))$, and category transitions $P_{\text{source}}(c_2 \mid c_1)$, updated by teaching consistency $P(p \mid e_{1:b}) \propto P_{\text{source}}(p) \prod_{i=1}^b \mathbb{I}[\operatorname{run}(p, x_i) = y_i]$.

---

## 9. Real Retention and Structural Cross-Domain Transfer

- **Real Retention (Section 9)**:
  - Evaluate the 4 frozen old-source retention tasks per family before source meta-training (scratch `flat_catalogue` prior) and after source meta-training.
  - $R_{\text{acc}} = \text{accuracy\_after} - \text{accuracy\_before}$, $R_{\text{search}} = (\text{search\_cost\_after} - \text{search\_cost\_before}) / \max(1, \text{search\_cost\_before})$.
- **Structural Cross-Domain Transfer Under a Supplied Mapping (Section 10)**:
  - Secondary domain: `action_token_sequence` over typed token dicts `{"token": "D"|"L"|"R"|"U", "mag": int}` with separate concrete operations `reverse_actions`, `order_actions`, `dedup_actions`, `advance_mag`, `filter_even_mag`.
  - Only the abstract category structural scorer $w^*$ and `scale` over $\phi(p)$ are transferred under the explicitly supplied operator-role mapping.

---

## 10. Locked Advancement Gates and Resource Caps

- **Statistical Unit**: One generated family repetition ($n = 8$, $df = 7$, $t_{0.975, 7} = 2.364624251$).
- **Resource Caps**: `max_wall_s = 120`, `max_cpu_s = 120`, `memory_mb = 2048`, `0` neural training steps, `8` deterministic source ridge fits (`1` per family).
- **Advancement Gates (All 7 Required)**:
  - **Gate 1 (Integrity)**: Complete grid, finite values, $\Sigma_{\text{source}} \cap \Sigma_{\text{target}} = \emptyset$, $H_{\text{source}} \cap H_{\text{target}} = \emptyset$, zero target leakage, valid hashes.
  - **Gate 2 (Held-Out Quality)**: Across budgets $\{1, 2, 4\}$, $A_{\text{candidate}} \ge \max_b A_b - 0.01$, losses in $\le 2/8$ families, worst family drop $\ge -0.05$.
  - **Gate 3 (Search Efficiency)**: Against every simple baseline and the strongest model-based baseline, construction-inclusive candidate evaluations $E_{\text{candidate}} \le 0.90 \cdot E_{\text{baseline}}$ and paired 95% CI lower bound $> 0$.
  - **Gate 4 (Example Efficiency)**: Mean examples for semantic identification $Q_{\text{candidate}} \le 0.90 \cdot Q_{\text{flat}}$ and $Q_{\text{candidate}} \le 1.05 \cdot \min_b Q_b$.
  - **Gate 5 (Retention)**: Post-learning source accuracy $\ge 0.98$, $R_{\text{acc}} \ge -0.01$, $R_{\text{search}} \le 0.10$, no family accuracy loss $> 0.05$.
  - **Gate 6 (Structural Cross-Domain Transfer)**: Under the supplied mapping, held-out accuracy within $0.01$ of strongest baseline, construction-inclusive search $\ge 10\%$ lower than `scratch_flat` with paired 95% CI lower bound $> 0$, and beats `exact_macro_cache`.
  - **Gate 7 (Computation)**: Source fitting + target search fully charged; total amortized work $\le 1.25 \times$ strongest baseline; report break-even target task count.
