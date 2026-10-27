# NEXUS Documentation Index

This index organizes all active architecture specifications, checker kernel contracts, current baseline reports, and historical wave records across `docs/` and `docs/history/`.

---

## 1. Active Core Architecture & Roadmap (Start Here)

| Document | Purpose |
| :--- | :--- |
| [README.md](../README.md) | Root project guide, verified Wave 40 scorecard (`46c3e53`), repository structure, and quickstart commands. |
| [AGENTS.md](../AGENTS.md) | Standing operational rules, scientific integrity firewall, pinned Checker Kernel SHA-256 digests (`v1`–`v5`), and `BURNED` external task registry. |
| [docs/ARCHITECTURE.md](ARCHITECTURE.md) | System block diagram, subsystem deep dive (`w40_search.py`, `checker_kernel_v5.py`, `outcome_contract.py`, `w40_learn.py`, `w39_world.py`), directory map, and data quarantine rules. |
| [docs/ROADMAP_10_STAGES.md](ROADMAP_10_STAGES.md) | The 10-Stage Autonomous Data Engineering & AGI Roadmap and the 7-Measure Unified Scorecard. |

---

## 2. Active Wave 38–40 Baseline Reports

| Document | Scope & Verified Results |
| :--- | :--- |
| [docs/NEXUS_WAVE40_INVARIANCE_AND_CEILINGS.md](NEXUS_WAVE40_INVARIANCE_AND_CEILINGS.md) | **Current Baseline (`46c3e53`):** 100% search-order & learning-order invariance (`175/175` tests), `64/80` (`80.0%`) LODO solve rate with `-61.2%` work reduction (`p = 0.0078`), `19/24` (`79.2%`) unburned external PROSE transfer, and `-14.7%` dual-budget online stream cost (`118.21` vs `138.62`, `16/16` streams). |
| [docs/NEXUS_WAVE39_EXTERNAL_TRANSFER.md](NEXUS_WAVE39_EXTERNAL_TRANSFER.md) | External benchmark transfer (`PROSE` Microsoft Program Synthesis Benchmark), strict `BURNED` quarantine of 4 inspected dev tasks, and `N1-merge-exact` non-stationary world change-point detector (`1.000` recall, `0.0/1000` FAR, `0.9467` full-2000 accuracy). |

---

## 3. Pinned Checker Kernel Specifications (`v2`–`v5`)

Each checker kernel specification defines the exact invariants enforced by the corresponding SHA-256 hash-pinned verifier in `src/nexus/`:

| Specification | Pinned Implementation | SHA-256 Digest (`622a29a`) |
| :--- | :--- | :--- |
| *(Checker v1 Baseline)* | `src/nexus/checker_kernel.py` | `5082402ff2ba7c4de9bc6ca998f0556d88f9ef1fb7c95b2a3f0d15bf79b3121e` |
| [docs/NEXUS_CHECKER_V2_SPEC.md](NEXUS_CHECKER_V2_SPEC.md) | `src/nexus/checker_kernel_v2.py` | `6ba0a268ddc5c4f0912f985c214a21e8d92a0af7e1b6b348d5ae1a38cc48379b` |
| [docs/NEXUS_CHECKER_V3_SPEC.md](NEXUS_CHECKER_V3_SPEC.md) | `src/nexus/checker_kernel_v3.py` | `3c68230e09cd6cdbdf0c33f1f70caf68ae82c2686bb640e2515801d4d121e20f` |
| [docs/NEXUS_CHECKER_V4_SPEC.md](NEXUS_CHECKER_V4_SPEC.md) | `src/nexus/checker_kernel_v4.py` | `c07e21ec104633865f8d6d03d8d30f240962537922c67f4c6f90ea5ed74f5c13` |
| [docs/NEXUS_CHECKER_V5_SPEC.md](NEXUS_CHECKER_V5_SPEC.md) | `src/nexus/checker_kernel_v5.py` | `2cd3a4caf33070558a2d7394497dd1d548583be5b04e1d7a18eac661790244d4` |

---

## 4. Historical Wave Reports (`docs/history/` & Test-Pinned Protocols)

### 4.1 Archived Wave Reports (`docs/history/`)
Superseded intermediate wave reports moved to `docs/history/` to keep `docs/` focused on the active architecture:
- [docs/history/NEXUS_WAVE37_INTERACTION.md](history/NEXUS_WAVE37_INTERACTION.md) — Wave 37 interaction experiments.
- [docs/history/NEXUS_WAVE32_HYPERAGENT_ARCHIVE.md](history/NEXUS_WAVE32_HYPERAGENT_ARCHIVE.md) — Wave 32 5-detector anti-cheat suite & archive.
- [docs/history/NEXUS_WAVE31_MIDDLE_IR.md](history/NEXUS_WAVE31_MIDDLE_IR.md) — Wave 31 middle IR & subprocess instruction metering.
- [docs/history/NEXUS_WAVE30_KERNEL_AND_ALIEN_DR.md](history/NEXUS_WAVE30_KERNEL_AND_ALIEN_DR.md) — Wave 30 pinned checker kernel v1 & domain randomization.
- [docs/history/NEXUS_WAVE26_VS_WAVE27_SCORECARD.md](history/NEXUS_WAVE26_VS_WAVE27_SCORECARD.md), [NEXUS_WAVE26_PHASE2.md](history/NEXUS_WAVE26_PHASE2.md), [NEXUS_WAVE26_PHASE3.md](history/NEXUS_WAVE26_PHASE3.md) — Wave 26–27 intermediate phase notes.

### 4.2 Test-Pinned Historical Documents in `docs/`
Several historical protocol and milestone documents (`NEXUS_WAVE25_*` through `NEXUS_WAVE34_*`, `MASTER_CONTEXT.md`, `NEXUS_CANONICAL_CURRENT_STATE.md`, and earlier `NEXUS_*_PROTOCOL.md` files) have their exact file paths or SHA-256 digests asserted by legacy regression tests in `tests/`. They remain at their original paths in `docs/` so every historical test continues to pass without modification.
