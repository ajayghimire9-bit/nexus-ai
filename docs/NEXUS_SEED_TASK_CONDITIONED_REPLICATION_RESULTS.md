# NEXUS Seed Task-Conditioned Program Ranking & Sealed Compositional Replication Results (`seed_task_conditioned_replication_v1`)

## 1. Executive Verdict

- **Verdict**: **`PASS_TASK_CONDITIONED_PROGRAM_RANKING_REPLICATION` (`overall_pass = true`, `7 / 7` preregistered gates passed)**
- **Cross-Domain Transfer Under Supplied Mapping**: **`CrossDomainTransferEstablished = true`** (`97.92%` search reduction vs `scratch_flat`, 95% paired Student-$t$ CI `[+43.3523, +50.7310]`)
- **Cross-Lab Shared-Memory Transfer**: **`CrossLabTransferEstablished = true`** (`98.48%` downstream evaluation reduction vs `scratch_learning`, `+100.0%` downstream accuracy gain vs `isolated_labs`)
- **Pre-Run Registration Commit**: `cc57cddff4491a93b76a842e43a85229216f0bce`
- **Raw Artifact**: [seed_task_conditioned_replication.json](../artifacts/seed_task_conditioned_replication.json) (`SHA-256: 2e6b264ba0184c245bbed92cb582d97e38ec983890392248b4098268157c8666`)
- **Independent Audit Receipt**: [seed_task_conditioned_replication_audit.json](../artifacts/seed_task_conditioned_replication_audit.json) (`valid = true`)
- **Locked Configuration**: [seed_task_conditioned_replication.json](../configs/seed_task_conditioned_replication.json) (`SHA-256: a23951c439529b9ba8d76e9f000a454f9b26f6eb89ae6be802dc871dc105e3ff`)
- **Locked Protocol**: [NEXUS_SEED_TASK_CONDITIONED_REPLICATION_PROTOCOL.md](NEXUS_SEED_TASK_CONDITIONED_REPLICATION_PROTOCOL.md) (`SHA-256: d8b4632728d663897c21fd8eb1ce36fca0edc8ccd7121af7aec1c66531fe9b4f`)
- **Live Agent Promotion**: **None (`live_promotion = false`)**. This establishes **bounded task-conditioned program ranking and shared-memory cross-lab transfer within the registered 6-operator finite grammar**, not unrestricted open-ended general intelligence.

---

## 2. Three-Way Disjoint Compositional Space (`Gate 1: PASS`)

To prevent any tuning on previously exposed targets from [seed_disjoint_meta.json](../artifacts/seed_disjoint_meta.json), the grammar was expanded to 6 primitives (`reverse`, `sort`, `unique`, `increment`, `decrement`, `even` in `list`; `reverse_actions`, `order_actions`, `dedup_actions`, `advance_mag`, `retreat_mag`, `filter_even_mag` in `action_token_sequence`) over lengths $L \in \{1, 2, 3\}$ and partitioned into three mutually disjoint sets:

| Catalogue Metric / Invariant | `list` Domain | `action_token_sequence` Domain | Status |
| :--- | :---: | :---: | :---: |
| Raw sequences ($6^1 + 6^2 + 6^3$) | `258` | `258` | Verified |
| Non-empty canonical signatures | `100` | `100` | Verified |
| Semantically unique programs (`781` probes) | `65` | `65` | Verified |
| Source Pool (`partition = "source"`) | `18` | `18` | All 6 primitives covered |
| Quarantined Historical Pool (`partition = "quarantine"`) | `23` | `23` | Excluded from target sampling |
| Fresh Sealed Target Pool (`partition = "target"`) | `24` | `24` | 100% novel `decrement` compositions |
| Canonical signature overlap (`source` $\cap$ `target`, `quarantine` $\cap$ `target`, `source` $\cap$ `quarantine`) | `0 / 0 / 0` | `0 / 0 / 0` | **PASS** |
| Semantic hash overlap (`source` $\cap$ `target`, `quarantine` $\cap$ `target`, `source` $\cap$ `quarantine`) | `0 / 0 / 0` | `0 / 0 / 0` | **PASS** |
| Unique 17-D calibration I/O signatures | `65 / 65` | `65 / 65` | **PASS** |

---

## 3. Primary In-Domain Target Results Across All 9 Methods (`Gates 2, 3, 4: PASS`)

Across 8 independent task families (`1749000001..1749000008`) and 24 non-repeating fresh sealed target compositions evaluated at primary teaching budgets $B \in \{1, 2, 4\}$ (plus secondary budget $B = 8$):

| Method | Primary Held-Out Accuracy ($B \in \{1,2,4\}$) | Primary Mean Evaluations ($B \in \{1,2,4\}$) | Mean Min Examples for $\ge 95\%$ Acc | Paired Difference vs `deterministic_signature` (Mean $\Delta$ Evals) | 95% Two-Sided Student-$t$ CI ($df=7$) | Relative Search Reduction by `deterministic_signature` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`deterministic_signature` (Primary Candidate)** | **`1.0000`** | **`1.0000`** | **`1.000`** | — | — | — |
| `bayesian_version_space` (Step 3 Comparator) | `1.0000` | `1.3333` | `1.000` | `+0.3333` | `[+0.0753, +0.5913]` | `25.00%` |
| `learned_linear_ranker` (20-D Source Ridge Ranker) | `1.0000` | `5.6250` | `1.000` | `+4.6250` | `[+1.9544, +7.2956]` | `82.22%` |
| `flat_catalogue` | `1.0000` | `12.7083` | `1.000` | `+11.7083` | `[+8.0858, +15.3309]` | **`92.13%`** |
| `shortest_program` | `1.0000` | `28.2500` | `1.000` | `+27.2500` | `[+22.8495, +31.6505]` | **`96.46%`** |
| `exact_macro_cache` | `1.0000` | `30.5000` | `1.000` | `+29.5000` | `[+25.9971, +33.0029]` | **`96.72%`** |
| `random_ordering` (64 perms/family) | `1.0000` | `33.0130` | `1.000` | `+32.0130` | `[+30.9743, +33.0517]` | **`96.97%`** |
| `structural_meta_prior` (Task-Independent Source Prior) | `1.0000` | `42.3333` | `1.000` | `+41.3333` | `[+32.7933, +49.8734]` | **`97.64%`** |
| `operator_frequency` | `1.0000` | `50.2500` | `1.000` | `+49.2500` | `[+42.7422, +55.7578]` | **`98.01%`** |

### Why Task-Conditioned Ranking Succeeded Where Task-Independent Prior Ranking Failed
1. In `seed_disjoint_meta_v1`, `structural_meta_prior` scored programs solely by source structural frequency $S_{\text{structural}}(p)$ without inspecting the current task's examples $D_B$. Because novel target compositions occupy the bottom of a static source prior, static ranking required `23.50` evaluations (and `42.33` evaluations in the 65-program space).
2. By conditioning ranking on the 17-dimensional input-output behavioral signature of the observed teaching examples:
   $$S(p \mid D_B) = -\|\operatorname{signature}(D_B) - \operatorname{signature}(p)\|_1 + \alpha S_{\text{structural}}(p) - \beta \operatorname{complexity}(p)$$
   `deterministic_signature` identifies the exact novel composition on the **first candidate evaluation (`1.0000` mean evaluations)** across all 24 unseen `decrement` compositions and all 8 families (`8 / 8` families strictly improved against every baseline).
3. **Step 3 Finding (Deterministic vs. Bayesian vs. Learned Linear Ranker)**:
   - `deterministic_signature` (`1.0000` evaluations) outperforms `bayesian_version_space` (`1.3333` evaluations, because Bayesian role-bigram priors penalize held-out role transitions when $\tau = 0.25$) and `learned_linear_ranker` (`5.6250` evaluations, because ridge regression reweights coordinates by source variance rather than uniform $\ell_1$ behavioral matching).
   - Consequently, **no neural ranker is required or justified** for this compositional program space.

---

## 4. Old-Task Retention (`Gate 5: PASS`)

Across the 32 frozen source retention tasks (4 per family) evaluated before and after target-task adaptation:
- **Pre-adaptation held-out accuracy**: `1.0000`
- **Post-adaptation held-out accuracy**: `1.0000` ($\Delta = 0.0000 \ge -0.01$)
- **Pre-adaptation mean evaluations**: `1.0000`
- **Post-adaptation mean evaluations**: `1.0000` ($0.00\%$ search regression $\le 10\%$)

---

## 5. Cross-Domain Transfer Under a Supplied Operator-Role Mapping (`Gate 6: PASS`)

On the 24 fresh sealed target compositions in the separately implemented `action_token_sequence` domain under the explicitly supplied 6-operator role mapping (`"structural transfer under a supplied mapping"`):

| Cross-Domain Method | Primary Held-Out Accuracy ($B \in \{1,2,4\}$) | Primary Mean Evaluations ($B \in \{1,2,4\}$) | Paired Reduction by `transferred_signature_prior` |
| :--- | :---: | :---: | :---: |
| **`transferred_signature_prior`** | **`1.0000`** | **`1.0000`** | — |
| `random_ordering` | `1.0000` | `32.3405` | `96.91%` |
| `exact_macro_cache` | `1.0000` | `37.2917` | `97.32%` |
| `transferred_structural_prior` | `1.0000` | `42.3333` | `97.64%` |
| `shortest_program` | `1.0000` | `46.5417` | `97.85%` |
| `scratch_flat` | `1.0000` | `48.0417` | **`97.92%` (`CI95: [+43.3523, +50.7310]`)** |
| `target_operator_frequency` | `1.0000` | `50.2500` | `98.01%` |

---

## 6. Compute Accounting & Session Ledger (`Gate 7: PASS`)

- **Target primary candidate evaluations (`deterministic_signature`)**: `72.0` total across 72 task-budget pairs (`1.0000` per evaluation) vs `915.0` for the strongest non-signature baseline (`flat_catalogue`) — a **`12.71x` (`92.13%`) reduction in target search evaluations**.
- **Source acquisition evaluations**: `7,264` across 144 source tasks (`8` families $\times 18$ source tasks). Note that `deterministic_signature` with $\alpha = 0$ achieves the exact same `1.0000` target evaluation count with **zero source acquisition overhead** because the 17-D calibration signature is computed directly from the 4 canonical calibration inputs (`260` program executions per catalogue).
- **Host Resource Accounting**:
  - `authored_steps`: `2,624` (`100%` within cap `2,624`)
  - `outer_updates`: `16` (`100%` within cap `16`)
  - `imagined_transitions`: `0`
  - `wall_s`: `6.7096 s`, `cpu_s`: `4.4423 s`, `execution_debit_s`: `8 s`
  - `session_used_s`: `2038.6321034559958 + 8 = 2046.6321034559958 s` / `3600 s` (`1553.3678965440042 s` remaining).
