# Wave18 — M4-GPU Neuro-Symbolic Canonical Evolution Results

## Executive Summary

Wave 18 (**Capabilities 6 & 7**: Self-Evolving Subtree Invention Beating `whole-macro` on Cost + Apple Silicon M4 GPU `mps` Neuro-Symbolic Proposer & Dynamic Neural Layer Growth) passed all pre-registered scientific, correctness, replay, and efficiency gates on the first and only single-shot unseen assessment (`w18f_*`):

- **Commit 1 (Pre-Assessment Code Freeze)**: `89c2e6bc3265d0e9822ff2dd17e7254f665eaf07`
- **Zero Post-Freeze Phase-1 Diff**: `git diff 89c2e6bc3265d0e9822ff2dd17e7254f665eaf07 -- src/nexus/seed/wave18_m4_gpu_neuro_symbolic_learner.py scripts/run_wave18_m4_neuro_symbolic_assessment.py scripts/verify_wave18_m4_neuro_symbolic.py tests/test_seed_wave18_m4_neuro_symbolic.py` is **100% empty**.
- **Standalone Verifier (`scripts/verify_wave18_m4_neuro_symbolic.py`)**: `"valid": true`, `"errors": []`, `"replayed_rows": 324`.
- **Unseen Assessment (`w18f_*`, 324 cells = 3 seeds × 6 methods × 18 tasks)**:
  - `nexus_m4_neuro_symbolic_full` achieves **`54/54` (`100%`) private accuracy**, `0` false unique locks, `0` cached coverage mask errors, `0` OOG piecewise evaluations, `3/3` ambiguous intent declarations, and `9` cold archive reactivations.
  - **`total_work = 554,575`** vs `nexus_whole_macro_only`'s `3,459,996` (**`-83.971802%` reduction**, **6.24x less work**).
  - **`total_primitive_op_steps = 1,633,854`** vs `nexus_whole_macro_only`'s `8,461,249` (**`-80.690156%` reduction**, **5.18x fewer primitive steps**).

---

## Fresh Assessment Results Table (`w18f_*`, 324 Cells)

| Method | Mapping Correct (`/54`) | Private Correct (`/54`) | False Unique | Ambiguous (`/3`) | Cold Archive Reactivated | `total_work` | `total_primitive_op_steps` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `standalone_m4_neural_baseline` | 48 | 24 | 30 | 0 | 0 | 114,973 | 292,971 |
| `equal_typed_scratch` | 48 | 48 | 0 | 3 | 0 | 4,122,816 | 9,903,841 |
| `ordinary_persistent_memoization` | 48 | 48 | 0 | 3 | 0 | 4,125,255 | 9,916,153 |
| `nexus_whole_macro_only` | 54 | 54 | 0 | 3 | 9 | 3,459,996 | 8,461,249 |
| `nexus_typed_without_pruning` | 39 | 39 | 0 | 3 | 0 | 846,711 | 2,960,934 |
| **`nexus_m4_neuro_symbolic_full`** | **54** | **54** | **0** | **3** | **9** | **554,575** | **1,633,854** |

---

## Hardware, Telemetry & Resource Ledger

- **Hardware**: Apple Silicon M4 (`torch.backends.mps.is_available() == True`, `PYTORCH_ENABLE_MPS_FALLBACK=0`).
- **Supervised Fresh Assessment Process Receipt (`artifacts/seed_wave18_fresh_process.json`)**:
  - `returncode`: `0`, `reason`: `null`
  - `charged_wall_s`: `119.678716s` (cap `180.626861s`)
  - `cpu_user_s`: `119.566799s`, `cpu_system_s`: `4.224503s`
  - `peak_sampled_rss_mb`: `518.109375 MiB` (cap `1024 MiB`, MPS allocator cap `256 MiB`)
  - `track_b_calls`: `0`, `track_b_debit_s`: `0`, `simulator_steps`: `0`
- **Artifact Hashes**:
  - `artifacts/seed_wave18_m4_neuro_symbolic.json`: `1fc7a0de16b1d0a7bcb904052c67a77fab5712bf299c16e32bc451591d73f0f6`
  - `artifacts/seed_wave18_registered_fixtures.json`: `a11b96369152780c7daf9f3033f38b34ecc6aed2e09470127462812c15b6e468`
  - `src/nexus/seed/mechanism_wave18_fresh_assessment.py`: `1c0df9a422bdca8479893e31bd4e6c9596566f9833bc9d62297ab9cb9d6d018f`
