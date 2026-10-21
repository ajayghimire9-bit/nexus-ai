# NEXUS Seed Real Cross-Lab Shared-Memory Transfer Results (`seed_cross_lab_transfer_v1`)

## 1. Overview & Experimental Design (Step 5)

This study ([cross_lab_transfer.py](../src/nexus/seed/cross_lab_transfer.py), artifact [seed_cross_lab_transfer.json](../artifacts/seed_cross_lab_transfer.json)) tests whether teaching an executable transformation once in **Language Lab** and persisting it in the shared `Session` / `E1 Journal` memory enables zero-re-enumeration transfer across:
1. **Language Lab** (`lab="language"`): Acquire and verify an executable `list` program $p^\star$ from 4 teaching examples and 2 verification checks (`mode="enumerate"`).
2. **Coding Lab** (`lab="coding"`): Invoke the transformation under different wording/naming (`name + "code"`) from a 2-example transfer hint and execute it on 2 unseen coding inputs.
3. **Reasoning Lab** (`lab="reasoning"`): Apply the executable skill to a relational invariant reasoning query (determining whether two distinct sequences collapse to the same canonical invariant and extracting the leading invariant element).
4. **World Lab** (`lab="world"`): Apply the executable skill to raw sensor readings to compute a target grid coordinate `(gx, gy)` inside a $5 \times 5$ `GridWorld` with hazards and execute the shortest collision-free trajectory (`up`, `down`, `left`, `right`) to reach the goal cell.

### Three Compared Regimes Across 8 Multi-Lab Episodes (`c1..c8`)
- **`shared_memory_transfer`**: All four labs share one `Session` and `SeedBrain`; Coding Lab uses `mode="reuse_first"` to bind against verified shared skills before falling back to search, and Reasoning/World Labs invoke the verified shared skill directly.
- **`scratch_learning`**: Each downstream lab runs in an independent `Session` without shared skill memory and must re-acquire the program from scratch (`mode="enumerate"`) before solving its lab task.
- **`isolated_labs`**: Downstream labs cannot access Language Lab memory and do not re-run full grammar enumeration (`0` candidate evaluations in downstream labs, falling back to identity/default behavior).

---

## 2. Quantitative Results Across All 8 Multi-Lab Episodes

| Regime | Mean Downstream Candidate Evaluations / Episode | Total Downstream Candidate Evaluations (8 Episodes) | Downstream Accuracy (`Coding` + `Reasoning` + `World`) | World Lab Goal Completion Rate |
| :--- | :---: | :---: | :---: | :---: |
| **`shared_memory_transfer`** | **`1.0000`** | **`8`** | **`1.0000` (`24 / 24`)** | **`1.0000` (`8 / 8`)** |
| `scratch_learning` | `66.0000` | `528` | `1.0000` (`24 / 24`) | `1.0000` (`8 / 8`) |
| `isolated_labs` | `66.0000` (unsearched fallback penalty) | `528` | `0.0000` (`0 / 24`) | `0.0000` (`0 / 8`) |

- **Downstream Search Reduction (`shared_memory_transfer` vs. `scratch_learning`)**: **`98.4848%`** (`1.0` vs. `66.0` downstream candidate evaluations per episode; `8` vs. `528` total evaluations).
- **Downstream Accuracy Gain (`shared_memory_transfer` vs. `isolated_labs`)**: **`+100.0%`** (`1.0000` vs. `0.0000` across Coding, Reasoning, and World Lab goal completion).

---

## 3. Per-Episode Breakdown

| Episode | Taught Skill | Canonical Program `ops` | Language Acquisition Evals | `shared_memory_transfer` Downstream Evals / Acc / World Goal | `scratch_learning` Downstream Evals / Acc / World Goal | `isolated_labs` Downstream Acc / World Goal |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: |
| `1` | `c1` | `["even", "sort"]` | `15` | `1` / `1.00` / `True` | `45` / `1.00` / `True` | `0.00` / `False` |
| `2` | `c2` | `["reverse", "increment"]` | `31` | `1` / `1.00` / `True` | `93` / `1.00` / `True` | `0.00` / `False` |
| `3` | `c3` | `["sort", "unique"]` | `44` | `1` / `1.00` / `True` | `132` / `1.00` / `True` | `0.00` / `False` |
| `4` | `c4` | `["even", "increment"]` | `13` | `1` / `1.00` / `True` | `39` / `1.00` / `True` | `0.00` / `False` |
| `5` | `c5` | `["unique", "reverse"]` | `49` | `1` / `1.00` / `True` | `147` / `1.00` / `True` | `0.00` / `False` |
| `6` | `c6` | `["increment", "sort"]` | `20` | `1` / `1.00` / `True` | `60` / `1.00` / `True` | `0.00` / `False` |
| `7` | `c7` | `["even", "unique"]` | `2` | `1` / `1.00` / `True` | `6` / `1.00` / `True` | `0.00` / `False` |
| `8` | `c8` | `["even", "reverse"]` | `2` | `1` / `1.00` / `True` | `6` / `1.00` / `True` | `0.00` / `False` |

---

## 4. Scientific Interpretation & Scope Boundary

- **What this establishes**: A single executable program representation acquired and verified in `Language Lab` transfers with `1` candidate check via `mode="reuse_first"` into `Coding Lab`, solves relational equivalence queries in `Reasoning Lab`, and drives goal-directed navigation in `World Lab` (`98.48%` fewer downstream candidate evaluations than `scratch_learning` and `100%` goal completion vs `0%` for `isolated_labs`).
- **What remains unestablished**: Cross-lab transfer here relies on the shared typed `list` / `grid` execution substrate (`src/nexus/seed/foundation/programs.py`). Open-ended cross-modal invention of new primitives without a shared typed IR remains future work.
