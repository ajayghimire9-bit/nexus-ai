# NEXUS Seed Source-Only Input-Output Signature Audit Results (`seed_signature_audit_v1`)

## 1. Summary

- **Protocol**: [NEXUS_SEED_SIGNATURE_AUDIT_PROTOCOL.md](NEXUS_SEED_SIGNATURE_AUDIT_PROTOCOL.md)
- **Implementation**: [signature_audit.py](../src/nexus/seed/signature_audit.py), [run_seed_signature_audit.py](../scripts/run_seed_signature_audit.py)
- **Artifact**: [seed_signature_audit.json](../artifacts/seed_signature_audit.json)
- **Source Data**: `17` source programs and `128` saved source tasks from [seed_disjoint_meta.json](../artifacts/seed_disjoint_meta.json) (SHA-256: `13159690aacd36d393f9aa699ed5bddfce044530f802e773b00fb9024ca065fa`)
- **Target Outcomes Accessed**: **`false`**
- **Audit Status**: **`PASSED`** (`audit_passed: true`)

---

## 2. Six-Category Input-Output Clue Separation Across the 17 Source Programs

All `17 / 17` source programs produced **unique** 17-dimensional input-output calibration signatures:

| Clue Category | Feature Count | Active Source Programs (`/17`) | Mean Pairwise $L_1$ Contribution |
|---|---:|---:|---:|
| **1. Output length change** (`len_preserved`, `len_decreased`, `mean_len_ratio`) | `3` | `17` | `1.264400` |
| **2. Sorting or reversal** (`sorted_asc`, `sorted_desc`, `direct_reversal`) | `3` | `12` | `1.126838` |
| **3. Duplicates removed & unique order** (`dup_removed`, `first_app`, `rev_first_app`, `last_app_rev`) | `4` | `13` | `1.625000` |
| **4. Even/odd filtering** (`all_even_output`, `all_odd_output`, `pre_shift_odd_origin`) | `3` | `4` | `0.382353` |
| **5. Constant value shift** (`positive_shift`, `negative_shift`, `zero_shift`) | `3` | `17` | `0.686275` |
| **6. Order & cardinality preservation** (`order_and_cardinality_preserved`) | `1` | `1` | `0.117647` |

---

## 3. Leave-One-Source-Program-Out (LOSO) Evaluation on 128 Source Tasks ($B \in \{1, 2, 4\}$)

For each of the 128 source tasks, the true program was excluded when fitting the structural prior (`structural_meta_prior_loso`), and candidate ranking was evaluated across budgets $B \in \{1, 2, 4\}$ over the 17 source programs:

| Method | Mean Candidate Evaluations ($B \in \{1,2,4\}$) | Held-Out Accuracy ($B \in \{1,2,4\}$) | Reduction vs `flat_catalogue` | Reduction vs `structural_meta_prior_loso` |
|---|---:|---:|---:|---:|
| **`deterministic_signature` ($S(p \mid D_B)$)** | **`1.06770833`** | **`0.92513021`** | **`+87.54%`** | **`+91.00%`** |
| `flat_catalogue` | `8.56770833` | `0.92594401` | `0.00%` | — |
| `shortest_program` | `8.66666667` | `0.92513021` | `-1.15%` | — |
| `structural_meta_prior_loso` | `11.86197917` | `0.89192708` | `-38.45%` | `0.00%` |

### Locked Hyperparameters for Sealed Replication
- $\alpha = 0.05$ (structural prior weight)
- $\beta = 0.05$ (program length complexity penalty weight)
- $\lambda = 1.0$ (ridge regularization)
