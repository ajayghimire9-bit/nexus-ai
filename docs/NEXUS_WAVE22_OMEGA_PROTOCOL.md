# NEXUS Wave 22 (`NEXUS-OMEGA`) — Pre-Assessment Code Freeze Protocol

## 1. Branch & Starting Point
- **Branch**: `cursor/seed-wave22-nexus-omega-wake-sleep-sinkhorn-world-engine`
- **Base Commit**: `301c7a2`
- **Part 1 Forensic Disclosure**: Recorded in `docs/NEXUS_WAVE21_REAL_AUDIT_RESULTS.md` and `docs/NEXUS_CANONICAL_CURRENT_STATE.md` (disclosing the Wave 21 `30c7427 -> e2f627c` amend and the `27/30 -> 30/30` fixture adjustment on `w21f_dlg_06_ambiguous_dialogue`).

## 2. Non-Negotiable Scientific & Git Protocol Rules
1. **Zero History Rewriting**: `git commit --amend`, `git rebase`, and `git reset` are strictly banned on `cursor/seed-wave22-nexus-omega-wake-sleep-sinkhorn-world-engine`. The standalone verifier (`scripts/verify_wave22_nexus_omega.py`) inspects `git reflog -n 50` and asserts `zero_amend_on_branch == True`.
2. **Strict Physical Two-Commit Separation**:
   - **Commit 1 (Pre-Assessment Code Freeze)**: Commits the Wave 22 `NEXUS-OMEGA` engine, benchmark runner, standalone verifier, unit tests, and protocol documentation while `src/nexus/seed/mechanism_wave22_fresh_assessment.py` does **not** exist in the working tree or git index.
   - **Commit 2 (Post-Freeze Single-Shot Assessment)**: Authors `src/nexus/seed/mechanism_wave22_fresh_assessment.py` (`w22f_*`), validates every fixture's mathematical well-posedness via `validate_wave22_suite_well_posedness` prior to execution, runs `scripts/run_wave22_nexus_omega_benchmark.py` and `scripts/verify_wave22_nexus_omega.py --freeze-commit <commit_1_sha>` once, and commits the artifacts and results with **zero diff** on all Phase-1 files.

## 3. Pre-Freeze Phase-1 File SHA-256 Hashes
| File | SHA-256 |
|---|---|
| `src/nexus/seed/wave22_nexus_omega_engine.py` | `ad215f47d6c2b4e940e9a44c20dad56a50e081b34609a910955691c9d3f25e31` |
| `scripts/run_wave22_nexus_omega_benchmark.py` | `a298541d25f895e0e3f5790389a998e70d10ac3312739d44bd2993e27e9d2da4` |
| `scripts/verify_wave22_nexus_omega.py` | `10477335bcdc40bfd2d6338edc5c6c50e766c0c1956b926d31f1c16685fd0359` |
| `tests/test_seed_wave22_nexus_omega.py` | `c25b5c6e3f4fb762d314be1f04c9eb7ce12e0c27f6e93a5a014b080874521533` |

## 4. Quantitative Evaluation Grid (`369` Total Cells Across `3` Seeds)
- **Track 1 (`SinkhornHomomorphismEngine` on M4 `mps`)**: `3 seeds x 4 methods x 6 tasks = 72 cells` ($K_A = 6, K_B = 9$ with 3 distractors, $M_A = 2, M_B = 3$ with 1 distractor guard).
- **Track 2 (`WakeSleepCodeEvolver` on M4 `mps`)**: `3 seeds x 6 methods x 12 tasks = 216 cells` + `3 seeds x 3 repos = 9 multi-file repository repair cells`.
- **Track 3 (`OmegaEpistemicWorldAgent` + `CompositionalNLWorldCompiler` + Real `Qwen2.5-0.5B-Instruct` on Metal)**: `3 seeds x 2 methods x 12 turns = 72 cells`.
