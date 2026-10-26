# Wave 30 (increment 1, not locked) — read-only Checker Kernel + A0 / A1 / A1b diagnostics on dev and admission_val

Branch `codex/wave30-kernel-and-alien-dr` (from Wave 29 `c78d476`).

## Built

**Checker Kernel** (`src/nexus/checker_kernel.py`).
* Standard library only; read-only under AGENTS.md RULE 2; sha256 pinned; about 300 lines.
* It has its own interpreter for the mechanism language: F / S / Sort / comp, plus the A1 DSL.
* It re-verifies every pruning lemma against its own postcondition table, then exhaustively enumerates the
  declared finite scope: all sizes ≤ d, which is stricter than a minimal-size certificate.
* Labels: `exhaustive_UNIQUE`, `proposal_relative_UNIQUE`, `AMBIGUOUS(k)`, `ABSTAIN`.
* Tests:
  * the kernel and prover interpreters agree on every mechanism;
  * tampered answers, unknown ops and mis-cited lemmas are rejected;
  * lemmas never change the label, only the number of chains checked.
* Checking finite-scope uniqueness costs about as much as the enumeration. What the kernel provides is a small,
  independent trusted base, not cheaper checking.

**Evidence Object** (`wave30_arms.prove`). Contents:
* candidate chain specs;
* the declared scope, as tool specs plus depth;
* pruning lemmas (tool, postcondition, violating public output);
* the trace;
* public pairs, including the charged probe pairs.

**Prover.** An exact unpruned Searcher to k_min, plus the k_min + 1 shell, with up to 3 rich verification probes
while ambiguous. It uses a harness-local 6M budget and records worlds with 3 fields.

**Arms.**
* **A0:** base plus the 10-schema comp menu.
* **A1:** A0 plus a fixed richer DSL: projection, arithmetic maps, accumulators (prefix sum, running max,
  difference), objects (run heads, group counts), and bounded loops (repeat 2–3 × diff).
* **A1b:** A1 tools behind a no-pretraining wake-sleep prior over operator families.
  * The prior starts at Dirichlet(1) and is updated only from NEXUS's own kernel-certified candidates in the
    same stream.
  * It proposes families covering 80% of the mass. If nothing fits there, it escalates to the full scope, and
    both searches are charged.

**Splits (registry).**
* `wave30/dev`: 751–755.
* `wave30/admission_val`: 7001–7005, reusable for admission decisions only, never for final claims.
* `final_sealed` (alien worlds): not yet generated.

## Initial diagnostics

Each split has 5 seeds × 16 tasks, half A0-expressible teachers and half A1-only (by construction).

| Split | Arm | Solved | False certificates | Labels | Work | A0-family solved | A1-family solved |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev | A0 | 43/80 | 0 | 43 exhaustive_UNIQUE, 1 AMBIGUOUS, 36 ABSTAIN (no fit) | 19.4M | 40/40 | 3/40 |
| dev | A1 | 78/80 | 0 | 78 exhaustive_UNIQUE, 2 AMBIGUOUS | 25.4M | 40/40 | 38/40 |
| dev | A1b | 79/80 | 0 | 62 proposal_relative, 17 exhaustive, 1 AMBIGUOUS | 23.4M (−8% vs A1) | 40/40 | 39/40 |
| admission_val | A0 | 38/80 | 0 | 38 exhaustive, 4 AMBIGUOUS, 38 ABSTAIN | 24.4M | 37/40 | 1/40 |
| admission_val | A1 | 74/80 | 0 | 74 exhaustive, 6 AMBIGUOUS | 32.7M | 36/40 | 38/40 |
| admission_val | A1b | 73/80 | 0 | 56 proposal_relative, 17 exhaustive, 7 AMBIGUOUS | 32.1M (−2%) | 37/40 | 36/40 |

**Wall time.** dev 178 s; admission_val 220 s.

**Prover vs kernel.**
* The prover was UNIQUE but the kernel was not on 1 dev and 1 admission_val task (A1, A1b).
* The kernel's exhaustive all-sizes scope found a disagreeing program. The prover's k_min + 1 shell is weaker
  than the kernel's full-scope semantics.

## Reading and caveats

* **No false certificates under any arm.** The kernel never issued a wrong UNIQUE, and A0 abstains instead of
  guessing on out-of-grammar tasks.
* **A1's coverage advantage is built into the task distribution.** Half the teachers are A1-only by
  construction. It shows that the richer DSL is usable at about 1.3× the cost of A0. It does not show that A1
  helps on a natural distribution.
* **A1b's learned proposal saves little** (−8% / −2%).
  * Records-world A0-family tasks dominate the cost.
  * Escalation to the full scope happens 17–19 times per split and is charged twice.
  * Proposal-relative labels are weaker claims than exhaustive ones.
* **Not yet built:**
  * A2 / A3, which need a coder model (paid services are excluded, and no local coder is configured);
  * A4;
  * the bit-gap meter;
  * lineage ablation;
  * admission net of costs;
  * the alien `final_sealed` worlds;
  * the `possibly_contaminated` ARC report.

**Budget used:** about 400 s for diagnostics. About 6,100 s remain.
