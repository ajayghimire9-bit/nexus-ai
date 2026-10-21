# NEXUS Seed Disjoint Compositional Meta-Learning Results (`seed_disjoint_meta_v1`)

## 1. Executive Summary & Permitted Scientific Conclusion

- **Experiment ID**: `seed-disjoint-meta-1` (`seed_disjoint_meta_v1`)
- **Branch**: `codex/seed-disjoint-meta-learning-replication`
- **Starting `main` Commit**: `492de6f48f5b07f7a666af45f0abfe5942c2f5a8`
- **Pre-Execution Protocol/Implementation Commit**: `540a30596814ec1687db13e7e38cdc0ab43aa701`
- **Protocol**: [NEXUS_SEED_DISJOINT_META_PROTOCOL.md](NEXUS_SEED_DISJOINT_META_PROTOCOL.md) (SHA-256: `498e8412a5dda340362600d1810fac1f21992a66ffc60f8bcfe75f9991070e05`)
- **Configuration**: [seed_disjoint_meta.json](../configs/seed_disjoint_meta.json) (SHA-256: `6ab93c0157e41671b4602840aaf4751719e6cc2b95ed9da74b23d09ce44eef20`)
- **Raw Artifact**: [seed_disjoint_meta.json](../artifacts/seed_disjoint_meta.json) (SHA-256: `13159690aacd36d393f9aa699ed5bddfce044530f802e773b00fb9024ca065fa`)
- **Independent Audit**: [seed_disjoint_meta_audit.json](../artifacts/seed_disjoint_meta_audit.json) (`valid: true`)
- **Advancement Screen**: `failed` (`all_gates_passed: false`; Gate 1 passed, Gates 2–7 failed)
- **Live Promotion**: `No live promotion`

### Permitted Scientific Conclusion

> **The registered bounded learning-to-learn screen failed. The architecture and benchmark remain useful engineering infrastructure, but useful learning-to-learn was not established.**

---

## 2. Audit of the Prior `seed_master_architecture_v1` Benchmark

Before running `seed_disjoint_meta_v1`, we audited [meta_learning.py](../src/nexus/seed/master/meta_learning.py), [memory.py](../src/nexus/seed/master/memory.py), [skill_programs.py](../src/nexus/seed/skill_programs.py), and [NEXUS_SEED_MASTER_ARCHITECTURE.md](NEXUS_SEED_MASTER_ARCHITECTURE.md):

1. **Exact Canonical Motif Overlap**: Source and target curricula in [meta_learning.py](../src/nexus/seed/master/meta_learning.py) reused the exact same 3 canonical operator motifs (`sort -> unique`, `reverse -> increment`, `even -> sort`).
2. **Held-Out Inputs vs. Held-Out Program Mechanisms**: The prior benchmark varied integer lists between source and target tasks while keeping the underlying target program mechanisms identical to source programs.
3. **Retention Conflated with Target Correctness**: `retention_scores` recorded held-out execution accuracy on the newly solved target tasks rather than re-testing old source tasks before and after meta-learning.
4. **Constructed Transfer Metric**: `transfer_scores` was computed as `min(1.0, round(meta_score + 0.02, 6))` rather than independently measured on a separate target domain.
5. **Hand-Authored Multi-Reasoner Integration Suite**: The 6-domain suite in [meta_learning.py](../src/nexus/seed/master/meta_learning.py) is a bounded multi-reasoner integration suite using hand-authored domain solvers (`planning`, `causal`, `logic`, `program_synthesis`, `arithmetic`, `symbolic_state`), not evidence of acquired general intelligence.

The historical numbers (`9.5 -> 1.75` candidate evaluations, `81.58%` reduction) are preserved intact in [meta_learning.py](../src/nexus/seed/master/meta_learning.py) and relabeled across code, docs, and UI as the **bounded exact-motif program-prior reuse demo** (**engineering demonstration of within-family search-prior reuse**).

---

## 3. Combinatorial Grammar & Disjointness Proof (Gate 1 — PASSED)

Both the `list` domain ($\mathcal{O} = (\text{reverse}, \text{sort}, \text{unique}, \text{increment}, \text{even})$) and the cross-domain `action_token_sequence` domain ($\mathcal{O}_{\text{act}} = (\text{reverse\_actions}, \text{order\_actions}, \text{dedup\_actions}, \text{advance\_mag}, \text{filter\_even\_mag})$) were enumerated exhaustively for lengths $L \in \{1, 2, 3\}$ over 781 deterministic probe inputs ($X_{\text{probe}} = \bigcup_{\ell=0}^{4}\{-2,-1,0,1,2\}^\ell$):

| Quantity | `list` Domain | `action_token_sequence` Domain | Status |
|---|---:|---:|---|
| Raw operator sequences ($5^1 + 5^2 + 5^3$) | `155` | `155` | Verified |
| Non-empty canonical signatures | `68` | `68` | Verified |
| Semantically unique programs over 781 probes | `41` | `41` | Verified |
| Source pool $\|\mathcal{C}_{\text{source}}\|$ (no pair in $P_{\text{holdout}}$) | `17` | `17` | Verified |
| Target pool $\|\mathcal{C}_{\text{target}}\|$ ($\ge 1$ pair in $P_{\text{holdout}}$) | `24` | `24` | Verified |
| Canonical overlap $\|\operatorname{ Canon }(\mathcal{C}_{\text{source}}) \cap \operatorname{ Canon }(\mathcal{C}_{\text{target}})\|$ | `0` | `0` | Verified (`canonical_disjoint: true`) |
| Semantic overlap $\|\operatorname{ Sem }(\mathcal{C}_{\text{source}}) \cap \operatorname{ Sem }(\mathcal{C}_{\text{target}})\|$ | `0` | `0` | Verified (`semantic_disjoint: true`) |
| Catalogue proof SHA-256 | `eb49d7f6...c20b0` | `bdaee35f...739d1` | Independently reproduced |

Held-out adjacent pairs $P_{\text{holdout}}$:
- `("even", "increment")`, `("even", "sort")`, `("increment", "even")`, `("increment", "increment")`, `("reverse", "unique")`.

---

## 4. In-Domain Disjoint Target Results ($F=8$ Families, 24 Unique Target Tasks)

Primary evaluation averages across the 8 non-repeating task families and primary teaching budgets $B \in \{1, 2, 4\}$ (with secondary check at $B = 8$):

| Method | Primary Evaluations (Construction-Inclusive) | Search-Only Evaluations | Primary Held-Out Accuracy ($B \in \{1,2,4\}$) | Budget $B=8$ Held-Out Accuracy | Mean Examples for Semantic ID |
|---|---:|---:|---:|---:|---:|
| **`structural_meta_prior` (Candidate)** | **`18.55555556`** | `18.38888889` | **`0.91145833`** | `1.00000000` | **`1.62500000`** |
| `flat_catalogue` | `15.58333333` | `15.58333333` | `0.92187500` | `1.00000000` | `1.50000000` |
| `random_ordering` (64-perm exact mean) | `18.74500868` | `18.74500868` | `0.91834852` | `1.00000000` | `1.59309896` |
| `shortest_program` | `22.40277778` | `22.40277778` | `0.91927083` | `1.00000000` | `1.54166667` |
| `operator_frequency` | `24.52777778` | `24.41666667` | `0.91319444` | `1.00000000` | `1.58333333` |
| `bayesian_model_based` | `25.26388889` | `25.15277778` | `0.91927083` | `1.00000000` | `1.54166667` |
| `exact_macro_cache` | `26.90277778` | `26.79166667` | `0.91319444` | `1.00000000` | `1.58333333` |

### Paired Family Differences ($d_f = \text{baseline}_f - \text{candidate}_f$, $F=8$, $t_{0.975,7} = 2.364624251$)

Positive evaluation differences mean `structural_meta_prior` required fewer candidate evaluations than the baseline:

| Baseline Compared | Mean Eval Difference ($\bar{d}$) | SD ($s_d$) | 95% Two-Sided Confidence Interval | Relative Search Improvement | Beats Baseline Under Gate 3? |
|---|---:|---:|---|---:|---|
| `exact_macro_cache` | `+8.34722222` | `6.27245525` | `[+3.10331840, +13.59112604]` | `+31.03%` | Yes (`CI low > 0`, `>= 10%`) |
| `bayesian_model_based` | `+6.70833333` | `5.04387714` | `[+2.49154651, +10.92512015]` | `+26.55%` | Yes (`CI low > 0`, `>= 10%`) |
| `operator_frequency` | `+5.97222222` | `4.89240494` | `[+1.88206933, +10.06237510]` | `+24.35%` | Yes (`CI low > 0`, `>= 10%`) |
| `shortest_program` | `+3.84722222` | `7.47091657` | `[-2.39862033, +10.09306477]` | `+17.17%` | No (`CI includes 0`) |
| `random_ordering` | `+0.18945312` | `4.58547633` | `[-3.64410103, +4.02300727]` | `+1.01%` | No (`< 10%`, `CI includes 0`) |
| `flat_catalogue` | `-2.97222223` | `9.22513819` | `[-10.68463075, +4.74018630]` | `-19.07%` | No (Candidate worse by `2.97` evals) |

### Scientific Diagnosis of Why Source-Trained Priors Underperformed `flat_catalogue` on Disjoint Target Compositions

1. **Structural Support Shift Between $\mathcal{C}_{\text{source}}$ and $\mathcal{C}_{\text{target}}$**:
   - All 5 length-1 programs belong to $\mathcal{C}_{\text{source}}$, and all 24 target programs in $\mathcal{C}_{\text{target}}$ have length 2 or 3 and contain at least one held-out adjacent operator pair $P_{\text{holdout}}$.
   - Baselines fitted to source empirical frequencies (`exact_macro_cache`: `26.90`, `bayesian_model_based`: `25.26`, `operator_frequency`: `24.53`) and `shortest_program` (`22.40`) rank all 17 source programs (or all length-1 and source-bigram programs) ahead of target programs, systematically delaying target discovery.
   - `structural_meta_prior` (`18.56`) partially mitigates this via role-category and shape features—significantly beating `exact_macro_cache`, `bayesian_model_based`, and `operator_frequency`—but still assigns positive ridge weights to source-observed adjacent role transitions and shorter lengths, leaving it close to `random_ordering` (`18.75`) and behind `flat_catalogue` (`15.58`), whose alphabetical canonical signature order happens to place `even`- and `increment`-prefixed target compositions near the start of the catalogue.

---

## 5. Old-Task Retention Results (Gate 5 — FAILED)

Old-source retention was evaluated on 32 frozen source tasks (4 per family) before source meta-training (`flat_catalogue` scratch ordering) and after source meta-training ($B \in \{1, 2, 4\}$):

| Method | Pre-Meta Accuracy | Post-Meta Accuracy | Accuracy Retention ($\Delta$) | Worst Family Accuracy $\Delta$ | Pre-Meta Search Cost | Post-Meta Search Cost | Search Retention ($\Delta$ Fraction) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`structural_meta_prior`** | `0.85481771` | **`0.88151042`** | **`+0.02669271`** | **`-0.07812500`** | `28.07291667` | **`21.12500000`** | **`-24.75%`** |
| `exact_macro_cache` | `0.85481771` | `0.98567708` | `+0.13085938` | `0.00000000` | `28.07291667` | `6.56250000` | `-76.62%` |
| `operator_frequency` | `0.85481771` | `0.98046875` | `+0.12565104` | `-0.00520833` | `28.07291667` | `9.47916667` | `-66.23%` |
| `bayesian_model_based` | `0.85481771` | `0.98046875` | `+0.12565104` | `0.00000000` | `28.07291667` | `9.84375000` | `-64.94%` |
| `shortest_program` | `0.85481771` | `0.98046875` | `+0.12565104` | `0.00000000` | `28.07291667` | `12.40625000` | `-55.81%` |
| `random_ordering` | `0.85481771` | `0.90788778` | `+0.05307007` | `-0.01586914` | `28.07291667` | `18.68457031` | `-33.44%` |
| `flat_catalogue` | `0.85481771` | `0.85481771` | `0.00000000` | `0.00000000` | `28.07291667` | `28.07291667` | `0.00%` |

While `structural_meta_prior` improved mean old-source accuracy (`+0.02669271`) and reduced mean old-source search cost by `24.75%`, it did not meet Gate 5 (`accuracy_after = 0.88151042 < 0.98` and `worst_family_accuracy_delta = -0.07812500 < -0.01`).

---

## 6. Structural Transfer Under a Supplied Mapping (`action_token_sequence`, Gate 6 — FAILED)

All cross-domain results are explicitly labeled **structural transfer under a supplied mapping** (`SUPPLIED_ROLE_MAPPING`):

| Cross-Domain Method | Primary Evaluations ($B \in \{1,2,4\}$) | Primary Held-Out Accuracy | Paired Eval Difference vs `transferred_structural_prior` | 95% Confidence Interval |
|---|---:|---:|---:|---|
| **`transferred_structural_prior`** | **`17.65277778`** | **`0.94270833`** | — | — |
| `scratch_flat` | `16.72222222` | `0.94531250` | `-0.93055556` | `[-6.91536145, +5.05425033]` |
| `random_ordering` | `17.09201389` | `0.95010037` | `-0.56076389` | `[-4.11287252, +2.99134474]` |
| `shortest_program` | `19.51388889` | `0.94184028` | `+1.86111111` | `[-3.62087605, +7.34309826]` |
| `exact_macro_cache` | `19.62500000` | `0.94184028` | `+1.97222222` | `[-3.50976494, +7.45420937]` |
| `target_operator_frequency` | `22.33333333` | `0.93576389` | `+4.68055555` | `[-0.36373609, +9.72484720]` |
| `bayesian_model_based` | `23.29166667` | `0.94184028` | `+5.63888888` | `[+1.57959296, +9.69818481]` |

`transferred_structural_prior` beat `exact_macro_cache` (`17.65` vs `19.625`) and `bayesian_model_based` (`17.65` vs `23.29`, 95% CI `[+1.58, +9.70]`), but did not beat `scratch_flat` (`16.72`), failing Gate 6.

---

## 7. Honest Compute & Resource Accounting (Gate 7 — FAILED)

- **Wall-Clock Time**: `31.431138 s` (cap `120 s`), conservative whole-second ledger debit `33 s`
- **CPU Time**: `20.690358 s` (cap `120 s`)
- **Peak Sampled RSS Memory**: `47.609375 MB` (cap `2048 MB`)
- **Outer Meta-Updates**: `8` (1 ridge fit per family, parameter count $d=23$)
- **Real Steps**: `2496` (`1024` source teaching + `192` target teaching + `1280` assessment examples)
- **Imagined Transitions / Network Forwards**: `0` / `0`
- **Session Ledger**: `carried_used_s = 2005.632103 s -> session_used_s = 2038.632103 s`, `session_remaining_s = 1561.367897 s`

| Method | Search Candidate Evaluations (72 Target Episodes) | Source Fit Units | Catalogue Constructions | Ridge Fits | Feature Scalars | Total Amortized Work Units |
|---|---:|---:|---:|---:|---:|---:|
| **`structural_meta_prior`** | `1324.0` | `128.0` | `8.0` | `8.0` | `10672.0` | **`1452.0`** |
| `flat_catalogue` | `1122.0` | `0.0` | `8.0` | `0.0` | `0.0` | **`1122.0`** |
| `random_ordering` | `1349.640625` | `0.0` | `0.0` | `0.0` | `0.0` | `1349.640625` |
| `shortest_program` | `1613.0` | `0.0` | `8.0` | `0.0` | `0.0` | `1613.0` |
| `operator_frequency` | `1758.0` | `128.0` | `8.0` | `0.0` | `0.0` | `1854.0` |
| `bayesian_model_based` | `1811.0` | `128.0` | `8.0` | `0.0` | `0.0` | `1907.0` |
| `exact_macro_cache` | `1929.0` | `128.0` | `8.0` | `0.0` | `0.0` | `2025.0` |

Total amortized overhead vs. strongest baseline (`flat_catalogue`) was `(1452.0 - 1122.0) / 1122.0 = +29.41%` (`> 25%` cap), failing Gate 7.

---

## 8. Summary of Advancement Gates

| Gate | Requirement | Measured Value | Verdict |
|---|---|---|---|
| **Gate 1: Integrity & Disjointness** | 0 canonical/semantic overlap, all 5 ops in source, target length $\ge 2$ with $\ge 1$ held-out pair | `17` source, `24` target, `0` overlap | **PASSED** |
| **Gate 2: Held-Out Target Quality** | Accuracy within `-0.01` of best baseline, $\le 2$ family losses, no drop $> 0.05$ | `0.91145833` vs `0.92187500` (`-0.01041667`), `3` losses, worst `-0.16666667` | **FAILED** |
| **Gate 3: Search-Efficiency Gain** | $\ge 10\%$ fewer evals than all 5 simple baselines & `bayesian_model_based` with 95% CI $> 0$ | Beats 3 source-fit baselines (`+24.35%` to `+31.03%`, CI $> 0$), loses to `flat_catalogue` (`-19.07%`) | **FAILED** |
| **Gate 4: Example-Efficiency** | $\ge 10\%$ fewer examples than `flat_catalogue` or within `5%` of best | `1.62500000` vs `1.50000000` (`-8.33%`) | **FAILED** |
| **Gate 5: Old-Task Retention** | Post-meta accuracy $\ge 0.98$, $\Delta \ge -0.01$, search regression $\le 10\%$ | Accuracy `0.88151042` (`+0.02669271`), worst family `-0.07812500`, search `-24.75%` | **FAILED** |
| **Gate 6: Structural Cross-Domain Transfer** | $\ge 10\%$ fewer evals than `scratch_flat` (`CI > 0`) and beats `exact_macro_cache` | `17.65277778` beats `exact_macro_cache` (`19.62500000`), loses to `scratch_flat` (`16.72222222`) | **FAILED** |
| **Gate 7: Honest Computation** | Total amortized work $\le 1.25\times$ strongest baseline | `1452.0` vs `1122.0` (`+29.41%`) | **FAILED** |
