# Wave-8 hierarchical gated evolution results

Branch `cursor/seed-wave8-hierarchical-gated-evolution` from `907db66`.
Protocol `561a563`. This results commit is separate.
Artifact hash
`ec06a9508d6138b78d6ef2a06ca374925b71b33967c29594c7fff5530722a8c2`.
Verifier `valid: true` on 216 cells. Historical grids, including
`907db66`, were not rescored. Track B coding/LLM closed. 0 model
calls. Frozen 1.5B debit **0**. Wall **0.066 s**, classified as
symbolic standing-grant CPU (not the frozen 1.5B ledger). Grammar
prior was not retrained. Pilot, not confirmation. Not general
learning-to-learn. Not AGI.

```
total = public_env + public_validation + channel_invariance
      + binding + role_probe + schema_distill + gate_evals
      + retrieval + synthesis + micro_codegen + operator_compile
```

Private interactions are excluded from total work and were never
read before lock.

## Mapping / private correctness

NEXUS and the three evolving methods scored **36/36** mapping and
**36/36** private. Scratch and static analogy abstain on both L2
tasks (**30/36**); they have no hierarchical compile path. False
analogy locks **0**. False unique claims **0**. Ambiguous **3/3**.
OOG abstain **3/3**. Domain A retain **3/3**. MDL demoted the
one-off `first_eq_last` helper and the spent `rotate_bang_tf`
operator; `palindrome_pred` stayed warm for L2.

| Method | G1 | G2 | G3 L1 | G3 L2 | Amb | OOG | Retain | Suite |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| factored_interface_scratch | 6/6 | 6/6 | 9/9 | 0/6 | 3/3 | 3/3 | 3/3 | 30/36 |
| factored_relational_analogy_static_bank | 6/6 | 6/6 | 9/9 | 0/6 | 3/3 | 3/3 | 3/3 | 30/36 |
| wave7_ungated_flat_evolving | 6/6 | 6/6 | 9/9 | 6/6 | 3/3 | 3/3 | 3/3 | 36/36 |
| ablation_hierarchical_ungated | 6/6 | 6/6 | 9/9 | 6/6 | 3/3 | 3/3 | 3/3 | 36/36 |
| ablation_gated_flat_L1_only | 6/6 | 6/6 | 9/9 | 6/6 | 3/3 | 3/3 | 3/3 | 36/36 |
| nexus_hierarchical_gated_evolving | 6/6 | 6/6 | 9/9 | 6/6 | 3/3 | 3/3 | 3/3 | 36/36 |

## Total work

| Method | Suite | G1 | G1+G2 | G3 | G3 L2 | Amb | OOG | Retain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| factored_interface_scratch | 13893 | 201 | 1650 | 9186 | 2310 | 96 | 2295 | 666 |
| factored_relational_analogy_static_bank | 14403 | 558 | 1080 | 10086 | 2670 | 96 | 2475 | 666 |
| wave7_ungated_flat_evolving | 20979 | 558 | 1080 | 13710 | 7863 | 96 | 5427 | 666 |
| ablation_hierarchical_ungated | 9210 | 546 | 1062 | 3474 | 213 | 96 | 3912 | 666 |
| ablation_gated_flat_L1_only | 8865 | 201 | 756 | 6069 | 4092 | 96 | 1278 | 666 |
| nexus_hierarchical_gated_evolving | **4989** | **201** | **756** | **2202** | **225** | 96 | **1269** | 666 |

`micro_codegen + synthesis`:

| Method | Suite code | G3 code | G3 L2 code | OOG code |
| --- | ---: | ---: | ---: | ---: |
| factored_interface_scratch | 12909 | 8781 | 2148 | 2214 |
| factored_relational_analogy_static_bank | 11703 | 8841 | 2172 | 2226 |
| wave7_ungated_flat_evolving | 18111 | 12345 | 7305 | 5130 |
| ablation_hierarchical_ungated | 6882 | 2649 | 15 | 3615 |
| ablation_gated_flat_L1_only | 7092 | 5223 | 3879 | 1185 |
| nexus_hierarchical_gated_evolving | **3228** | **1359** | **15** | **1185** |

Per-seed suite (identical on seeds 0–2):

| Seed | Scratch | Static | Wave-7 ungated | Hier. ungated | Flat gated L1 | NEXUS |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0–2 | 4631 | 4801 | 6993 | 3070 | 2955 | **1663** |

Per-seed G1 / G1+G2 / G3 / OOG:

| Seed | NEXUS G1 | Wave-7 G1 | Scratch G1 | NEXUS G12 | Scratch G12 | NEXUS G3 / code | Flat L1 G3 / code | NEXUS OOG | Wave-7 OOG | Hier. ungated OOG | Scratch OOG |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0–2 | **67** | 186 | 67 | **252** | 550 | **734 / 453** | 2023 / 1741 | **423** | 1809 | 1304 | 765 |

## Gates

| Gate | Result |
| --- | --- |
| 1 Private isolation, 0 false analogy locks, 100% amb/OOG/retain, NEXUS 36/36 | **pass** |
| 2 Lazy G1: NEXUS 201 < wave7-ungated 558 and = scratch 201; G1+G2 756 < scratch 1650 | **pass** |
| 3 Activation gate: OOG 1269 < wave7-ungated 5427 and hierarchical-ungated 3912, and below scratch 2295 | **pass** |
| 4 Hierarchy: G3 2202 / 1359 and suite 4989 / 3228 strictly below flat-gated L1, wave7-ungated, static, and scratch on every seed | **pass** |

Lazy depth-1 search matches scratch on easy first-fit (G1 201 vs
Wave-7's eager 558) and still pays role-probe only after a confirm
conflict, so G1+G2 stays below scratch (756 vs 1650). The
alphabet-closed activation gate keeps compiled `L1`/`L2` operators
out of OOG Caesar expansions (1269 vs ungated 5427 / 3912). Staging
`op_L2` as an AST over compiled `palindrome_pred` plus two rotate
transforms cuts L2 from flat `DEEP_L0` search (flat-gated 4092,
wave7-ungated 7863) to 225. This is an authored hierarchical catalog
with a hand-specified I/O gate, not open-ended operator discovery or
general learning-to-learn. `907db66` was not rerun.

## What remains

1. The L2 catalog is two authored rotate transforms, not an unguided
   search over nested micro-programs.
2. The activation gate tests one necessary invariant
   (`alphabet_closed`). A learned or multi-predicate gate is untested.
3. Do not treat `L0→L1→L2` on this token-queue suite as a general
   operator factory or learning-to-learn result.
